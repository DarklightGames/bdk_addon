import math
import typing
import re
from enum import Enum
from pathlib import Path
from typing import Optional, List


class UColor:
    R: int
    G: int
    B: int
    A: int

    def __init__(self, r: int, g: int, b: int, a: int):
        self.R = r
        self.G = g
        self.B = b
        self.A = a

    @staticmethod
    def from_string(string: str):
        pattern = r'{ R=(\d+), G=(\d+), B=(\d+), A=(\d+) }'
        match = re.match(pattern, string)
        return UColor(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
        )


class UReference:
    type_name: str
    package_name: str
    group_name: Optional[str]
    object_name: str

    def __init__(self, type_name: str, package_name: str, object_name: str, group_name: Optional[str] = None):
        self.type_name = type_name
        self.package_name = package_name
        self.object_name = object_name
        self.group_name = group_name

    @staticmethod
    def from_string(string: str) -> Optional['UReference']:
        if string == 'None':
            return None
        pattern = r'(\w+)\'([\w\.\d\-\_]+)\''
        match = re.match(pattern, string)
        type_name = match.group(1)
        object_name = match.group(2)
        pattern = r'([\w\d\-\_]+)'
        values = re.findall(pattern, object_name)
        package_name = values[0]
        object_name = values[-1]
        return UReference(type_name, package_name, object_name, group_name=None)

    @staticmethod
    def from_path(path: Path):
        parts = path.parts[-3:]
        package_name = parts[0]
        type_name = parts[1]
        object_name = parts[2][0:parts[2].index('.')]
        return UReference(type_name, package_name, object_name)

    def __str__(self):
        string = f"{self.type_name}'{self.package_name}'"
        if self.group_name is not None:
            string += f'.{self.group_name}'
        string += f".{self.object_name}'"
        return string


class URotator:
    Pitch: int = 0
    Yaw: int = 0
    Roll: int = 0.

    @staticmethod
    def from_string(string: str):
        self = URotator()
        match = re.match(r'\{ Yaw=(-?\d+), Pitch=(-?\d+), Roll=(-?\d+) }', string)
        self.Yaw = int(match.group(1))
        self.Pitch = int(match.group(2))
        self.Roll = int(match.group(3))
        return self

    def get_radians(self) -> (float, float, float):
        return (
                float(self.Roll) / 32768.0 * math.pi,
                float(self.Pitch) / 32768.0 * math.pi,
                float(self.Yaw) / 32768.0 * math.pi,
        )

    def __repr__(self):
        return f'{{ Yaw={self.Yaw}, Pitch={self.Pitch}, Roll={self.Roll} }}'


class EFrameBufferBlending(Enum):
    FB_Overwrite = 0,
    FB_Modulate = 1,
    FB_AlphaBlend = 2,
    FB_AlphaModulate_MightNotFogCorrectly = 3,
    FB_Translucent = 4,
    FB_Darken = 5,
    FB_Brighten = 6,
    FB_Invisible = 7


class ELODSet(Enum):
    LODSET_None = 0,
    LODSET_World = 1,
    LODSET_PlayerSkin = 2,
    LODSET_WeaponSkin = 3,
    LODSET_Terrain = 4,
    LODSET_Interface = 5,
    LODSET_RenderMap = 6,
    LODSET_Lightmap = 7


class ETexClampMode(Enum):
    TC_Wrap = 0,
    TC_Clamp = 1,


class UMaterial:
    Reference: UReference
    FallbackMaterial: Optional[UReference] = None
    DefaultMaterial: Optional[UReference] = None
    SurfaceType: int = 0

    def __init__(self, reference: UReference):
        self.Reference = reference

    def __repr__(self):
        lines = []
        type_hints = typing.get_type_hints(self)
        for key, value in type_hints.items():
            lines.append(f'{key} = {getattr(self, key)}')
        return '\n'.join(lines)


class URenderedMaterial(UMaterial):
    pass


class UConstantMaterial(URenderedMaterial):
    pass


class UConstantColor(UConstantMaterial):
    Color: UColor = UColor(0, 0, 0, 255)


class ETextureFormat(Enum):
    TEXF_P8 = 0,  # used 8-bit palette
    TEXF_RGBA7 = 1,
    TEXF_RGB16 = 2,  # 16-bit texture
    TEXF_DXT1 = 3,
    TEXF_RGB8 = 4,
    TEXF_RGBA8 = 5,  # 32-bit texture
    TEXF_NODATA = 6,
    TEXF_DXT3 = 7,
    TEXF_DXT5 = 8,
    TEXF_L8 = 9,  # 8-bit grayscale
    TEXF_G16 = 10,  # 16-bit grayscale (terrain heightmaps)
    TEXF_RRRGGGBBB = 11,  # Tribes texture formats
    TEXF_CxV8U8 = 12,
    TEXF_DXT5N = 13,  # Note: in Bioshock this value has the name 3DC, but really DXT5N is used
    TEXF_3DC = 14,  # BC5 compression


class UBitmapMaterial(URenderedMaterial):
    Format: ETextureFormat = ETextureFormat.TEXF_P8
    UClampMode: ETexClampMode = ETexClampMode.TC_Wrap
    VClampMode: ETexClampMode = ETexClampMode.TC_Wrap
    UBits: int = 0
    VBits: int = 0
    UClamp: int = 0
    VClamp: int = 0


class UTexture(UBitmapMaterial):
    Detail: Optional[UReference] = None
    DetailScale: float = 1.0
    bMasked: bool = False
    bAlphaTexture: bool = False
    bTwoSided: bool = False


class UCubemap(UTexture):
    Faces: List[Optional[UReference]] = []


class EOutputBlending(Enum):
    OB_Normal = 0,
    OB_Masked = 1,
    OB_Modulate = 2,
    OB_Translucent = 3,
    OB_Invisible = 4,
    OB_Brighten = 5,
    OB_Darken = 6


class UShader(URenderedMaterial):
    Diffuse: Optional[UReference] = None
    Opacity: Optional[UReference] = None
    Specular: Optional[UReference] = None
    SpecularityMask: Optional[UReference] = None
    SelfIllumination: Optional[UReference] = None
    SelfIlluminationMask: Optional[UReference] = None
    Detail: Optional[UReference] = None
    DetailScale: float = 8.0
    OutputBlending: EOutputBlending = EOutputBlending.OB_Normal
    TwoSided: bool = False
    Wireframe: bool = False
    ModulateStaticLighting2X: bool = False
    PerformLightingOnSpecularPass: bool = False
    ModulateSpecular2X: bool = False


class UModifier(UMaterial):
    Material: Optional[UReference] = None


class UFinalBlend(UModifier):
    FrameBufferBlending: EFrameBufferBlending = EFrameBufferBlending.FB_Overwrite
    ZWrite: bool = True
    ZTest: bool = True
    AlphaTest: bool = True
    TwoSided: bool = False
    AlphaRef: int = 0


class EColorOperation(Enum):
    CO_Use_Color_From_Material1 = 0,
    CO_Use_Color_From_Material2 = 1,
    CO_Multiply = 2,
    CO_Add = 3,
    CO_Subtract = 4,
    CO_AlphaBlend_With_Mask = 5,
    CO_Add_With_Mask_Modulation = 6,
    CO_Use_Color_From_Mask = 7


class EAlphaOperation(Enum):
    AO_Use_Mask = 0,
    AO_Multiply = 1,
    AO_Add = 2,
    AO_Use_Alpha_From_Material1 = 3,
    AO_Use_Alpha_From_Material2 = 4,


class UCombiner(UMaterial):
    CombineOperation: EColorOperation = EColorOperation.CO_Use_Color_From_Material1
    AlphaOperation: EAlphaOperation = EAlphaOperation.AO_Use_Mask,
    Material1: Optional[UReference] = None
    Material2: Optional[UReference] = None
    Mask: Optional[UReference] = None
    InvertMask: bool = False
    Modulate2x: bool = False
    Modulate4x: bool = False


class ETexCoordSrc(Enum):
    TCS_Stream0 = 0,
    TCS_Stream1 = 1,
    TCS_Stream2 = 2,
    TCS_Stream3 = 3,
    TCS_Stream4 = 4,
    TCS_Stream5 = 5,
    TCS_Stream6 = 6,
    TCS_Stream7 = 7,
    TCS_WorldCoords = 8,
    TCS_CameraCoords = 9,
    TCS_WorldEnvMapCoords = 10,
    TCS_CameraEnvMapCoords = 11,
    TCS_ProjectorCoords = 12,
    TCS_NoChange = 13,


class ETexCoordCount(Enum):
    TCN_2DCoords = 0,
    TCN_3DCoords = 1,
    TCN_4DCoords = 2


class UTexModifier(UModifier):
    TexCoordSource: ETexCoordSrc = ETexCoordSrc.TCS_Stream0,
    TexCoordCount: ETexCoordSrc = ETexCoordCount.TCN_2DCoords
    TexCoordProjected: bool = False


class ETexEnvMapType(Enum):
    EM_WorldSpace = 0,
    EM_CameraSpace = 1


class UTexEnvMap(UTexModifier):
    EnvMapType: ETexEnvMapType = ETexEnvMapType.EM_WorldSpace


class ETexOscillationType(Enum):
    OT_Pan = 0,
    OT_Stretch = 1,
    OT_StretchRepeat = 2,
    OT_Jitter = 3,


class UTexOscillator(UTexModifier):
    UOscillationRate: float = 0.0
    VOscillationRate: float = 0.0
    UOscillationPhase: float = 0.0
    VOscillationPhase: float = 0.0
    UOscillationAmplitude: float = 0.0
    VOscillationAmplitude: float = 0.0
    UOscillationType: ETexOscillationType = ETexOscillationType.OT_Pan
    VOscillationType: ETexOscillationType = ETexOscillationType.OT_Pan
    UOffset: float = 0.0
    VUOffset: float = 0.0


class UTexPanner(UTexModifier):
    PanDirection: URotator = URotator()
    PanRate: float = 0.0


class ETexRotationType(Enum):
    TR_FixedRotation = 0,
    TR_ConstantlyRotating = 1,
    TR_OscillatingRotation = 2


class UTexRotator(UTexModifier):
    TexRotationType: ETexRotationType = ETexRotationType.TR_FixedRotation
    Rotation: URotator = URotator()
    UOffset: float = 0.0
    VOffset: float = 0.0
    OscillationRate: URotator = URotator()
    OscillationAmplitude: URotator = URotator()
    OscillationPhase: URotator = URotator()


class UTexScaler(UTexModifier):
    UScale: float = 1.0
    VScale: float = 1.0
    UOffset: float = 0.0
    VOffset: float = 0.0


__material_type_map__: typing.Dict[str, type] = {
    'Combiner': UCombiner,
    'FinalBlend': UFinalBlend,
    'Shader': UShader,
    'TexOscillator': UTexOscillator,
    'TexPanner': UTexPanner,
    'TexScaler': UTexScaler,
    'TexRotator': UTexRotator,
    'Texture': UTexture,
    'ConstantColor': UConstantColor
}


def get_material_type_from_string(string: str):
    return __material_type_map__[string]
