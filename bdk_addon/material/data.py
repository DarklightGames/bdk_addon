from enum import Enum
from typing import get_type_hints
from ..data import UReference, UColor, URotator


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
    FallbackMaterial: UReference | None = None
    DefaultMaterial: UReference | None = None
    SurfaceType: int = 0

    def __init__(self, reference: UReference):
        self.Reference = reference

    def __repr__(self):
        lines = []
        type_hints = get_type_hints(self)
        for key, value in type_hints.items():
            lines.append(f'{key} = {getattr(self, key)}')
        return '\n'.join(lines)


class URenderedMaterial(UMaterial):
    pass


class UConstantMaterial(URenderedMaterial):
    pass


class UConstantColor(UConstantMaterial):
    Color: UColor = UColor(0, 0, 0, 255)


class EColorFadeType(Enum):
    FC_Linear = 0,
    FC_Sinusoidal = 1


class UFadeColor(UConstantMaterial):
    Color1: UColor = UColor(0, 0, 0, 0)
    Color2: UColor = UColor(0, 0, 0, 0)
    FadePeriod: float = 0.0
    FadeOffset: float = 0.0
    ColorFadeType: EColorFadeType = EColorFadeType.FC_Linear


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
    Detail: UReference | None = None
    DetailScale: float = 1.0
    bMasked: bool = False
    bAlphaTexture: bool = False
    bTwoSided: bool = False


class UCubemap(UTexture):
    Faces: list[UReference | None] = []


class UVertexColor(URenderedMaterial):
    pass


class EOutputBlending(Enum):
    OB_Normal = 0,
    OB_Masked = 1,
    OB_Modulate = 2,
    OB_Translucent = 3,
    OB_Invisible = 4,
    OB_Brighten = 5,
    OB_Darken = 6


class UShader(URenderedMaterial):
    Diffuse: UReference | None = None
    Opacity: UReference | None = None
    Specular: UReference | None = None
    SpecularityMask: UReference | None = None
    SelfIllumination: UReference | None = None
    SelfIlluminationMask: UReference | None = None
    Detail: UReference | None = None
    DetailScale: float = 8.0
    OutputBlending: EOutputBlending = EOutputBlending.OB_Normal
    TwoSided: bool = False
    Wireframe: bool = False
    ModulateStaticLighting2X: bool = False
    PerformLightingOnSpecularPass: bool = False
    ModulateSpecular2X: bool = False


class UModifier(UMaterial):
    Material: UReference | None = None


class UColorModifier(UModifier):
    Color: UColor = UColor(255, 255, 255, 255)
    RenderTwoSided: bool = False
    AlphaBlend: bool = False


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
    AlphaOperation: EAlphaOperation = EAlphaOperation.AO_Use_Mask
    Material1: UReference | None = None
    Material2: UReference | None = None
    Mask: UReference | None = None
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
    TexCoordSource: ETexCoordSrc = ETexCoordSrc.TCS_Stream0
    TexCoordCount: ETexCoordCount = ETexCoordCount.TCN_2DCoords
    TexCoordProjected: bool = False


class UTexCoordSource(UTexModifier):
    SourceChannel: int = 1


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
    VOffset: float = 0.0


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


class UVariableTexPanner(UTexModifier):
    PanDirection: URotator = URotator()
    PanRate: float = 0.0


class UMaterialSwitch(UMaterial):
    Current: int = 0
    Materials: list[UReference] = []


class EEMaterialSequenceAction(Enum):
    MSA_ShowMaterial = 0,
    MSA_FadeToMaterial = 1,


class EMaterialSequenceTriggerActon(Enum):
    MSTA_Ignore = 0,
    MSTA_Reset = 1,
    MSTA_Pause = 2,
    MSTA_Stop = 3


class FMaterialSequenceItem:
    Material: UReference | None = None
    Time: float
    Action: EEMaterialSequenceAction = EEMaterialSequenceAction.MSA_ShowMaterial


class UMaterialSequence(UMaterial):
    SequenceItems: list[FMaterialSequenceItem] = []
    TriggerAction: EMaterialSequenceTriggerActon = EMaterialSequenceTriggerActon.MSTA_Ignore
    bLoop: bool = False
    bPaused: bool = False
    CurrentTime: float = 0.0
    LastTime: float = 0.0
    TotalTime: float = 0.0


class MaterialTypeRegistry:

    _material_type_map: dict[str, type] = {
        'ColorModifier': UColorModifier,
        'Combiner': UCombiner,
        'ConstantColor': UConstantColor,
        'Cubemap': UCubemap,
        'FinalBlend': UFinalBlend,
        'Shader': UShader,
        'TexCoordSource': UTexCoordSource,
        'TexEnvMap': UTexEnvMap,
        'TexOscillator': UTexOscillator,
        'TexPanner': UTexPanner,
        'TexRotator': UTexRotator,
        'TexScaler': UTexScaler,
        'Texture': UTexture,
        'VariableTexPanner': UVariableTexPanner,
        'VertexColor': UVertexColor,
        'FadeColor': UFadeColor,
        'MaterialSwitch': UMaterialSwitch,
    }

    @classmethod
    def get_type_from_string(cls, string: str) -> type | None:
        return cls._material_type_map.get(string)
