import copy
import json
import os
from typing import Dict, cast, Tuple, Callable, Any

import bpy.types
from bpy.props import StringProperty
from bpy.types import ShaderNodeTexImage
from bpy_extras.io_utils import ImportHelper
from bpy_types import Operator

from .data import *
from .reader import read_material


class MaterialCache:
    def __init__(self, root_directory: str):
        self._root_directory = root_directory
        self._materials: Dict[str, UMaterial] = {}
        self._package_paths: Dict[str, str] = {}

        self._build_package_paths()

    def _build_package_paths(self):
        # Read the list of packages managed by BDK in the manifest.
        manifest = {'files': {}}
        try:
            with open(os.path.join(self._root_directory, '.bdkmanifest'), 'r') as fp:
                manifest = json.load(fp)
        except IOError as e:
            print(e)
        except UnicodeDecodeError as e:
            print(e)

        # Build list of texture packages.
        file_paths = manifest['files'].keys()

        package_paths = filter(lambda x: os.path.splitext(x)[1] in ['.utx', '.usx'], file_paths)

        # Register package name with package directory
        for package_path in package_paths:
            package_name = os.path.splitext(os.path.basename(package_path))[0]
            # Just like in UE2, the root folder takes precedence when there is a conflict.
            # TODO: technically not working here, would need to sort and put mod folders later in the list.
            if package_name not in self._package_paths:
                self._package_paths[package_name] = package_path

    def resolve_path_for_reference(self, reference: UReference) -> Optional[Path]:
        try:
            package_path = self._package_paths[reference.package_name]
            return Path(os.path.join(self._root_directory, os.path.splitext(package_path)[0], reference.type_name,
                                     f'{reference.object_name}.props.txt')).resolve()
        except RuntimeError:
            pass
        return None

    def load_material(self, reference: UReference) -> Optional[UMaterial]:
        if reference is None:
            return None
        key = str(reference)
        if key in self._materials:
            return self._materials[str(reference)]
        path = self.resolve_path_for_reference(reference)
        if path is None:
            return None
        material = read_material(str(path))
        self._materials[key] = material
        return material


class MaterialSocketOutputs:
    color_socket: bpy.types.NodeSocket = None
    alpha_socket: bpy.types.NodeSocket = None
    blend_method: str = 'OPAQUE'
    use_backface_culling: bool = False
    size: Tuple[int, int] = (1, 1)


class MaterialSocketInputs:
    uv_socket: bpy.types.NodeSocket = None


class MaterialBuilder:
    def __init__(self, material_cache: MaterialCache, node_tree: bpy.types.NodeTree):
        self._material_cache = material_cache
        self._node_tree = node_tree
        self._material_type_importers: Dict[
            type, Callable[[Any, MaterialSocketInputs], Optional[MaterialSocketOutputs]]] = {}

        self._register_material_importers()

    def _register_material_importers(self):
        self._material_type_importers = {
            UColorModifier: self._import_color_modifier,
            UCombiner: self._import_combiner,
            UConstantColor: self._import_constant_color,
            UCubemap: self._import_cubemap,
            UFinalBlend: self._import_final_blend,
            UTexCoordSource: self._import_tex_coord_source,
            UTexEnvMap: self._import_tex_env_map,
            UTexOscillator: self._import_tex_oscillator,
            UTexPanner: self._import_tex_panner,
            UTexRotator: self._import_tex_rotator,
            UTexScaler: self._import_tex_scaler,
            UTexture: self._import_texture,
            UShader: self._import_shader,
            UVariableTexPanner: self._import_variable_tex_panner,
            UVertexColor: self._import_vertex_color,
        }

    def _load_image(self, reference: UReference):
        image_path = self._material_cache.resolve_path_for_reference(reference)
        image_path = str(image_path)
        extensions = ['.tga', '.hdr']  # A little dicey :think:
        for extension in extensions:
            file_path = image_path.replace('.props.txt', extension)
            if os.path.isfile(file_path):
                return bpy.data.images.load(str(file_path), check_existing=True)
        raise RuntimeError(f'Could not find file for reference {reference}')

    def _import_color_modifier(self, color_modifier: UColorModifier,
                               socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        material = self._material_cache.load_material(color_modifier.Material)
        material_outputs = self._import_material(material, socket_inputs)

        if material_outputs and material_outputs.color_socket is not None:
            mix_node = self._node_tree.nodes.new('ShaderNodeMix')
            mix_node.data_type = 'RGBA'
            mix_node.blend_type = 'MULTIPLY'
            mix_node.inputs['Factor'].default_value = 1.0

            rgb_node = self._node_tree.nodes.new('ShaderNodeRGB')
            rgb_node.outputs[0].default_value = (
                float(color_modifier.Color.R) / 255.0,
                float(color_modifier.Color.G) / 255.0,
                float(color_modifier.Color.B) / 255.0,
                float(color_modifier.Color.A) / 255.0
            )

            self._node_tree.links.new(mix_node.inputs[6], material_outputs.color_socket)
            self._node_tree.links.new(mix_node.inputs[7], rgb_node.outputs[0])

            material_outputs.color_socket = mix_node.outputs[2]

        return material_outputs

    def _import_combiner(self, combiner: UCombiner, inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        # https://docs.unrealengine.com/udk/Two/MaterialsCombiners.html

        outputs = MaterialSocketOutputs()

        material1 = self._material_cache.load_material(combiner.Material1)
        material2 = self._material_cache.load_material(combiner.Material2)
        mask_material = self._material_cache.load_material(combiner.Mask)

        material1_outputs = self._import_material(material1, copy.copy(inputs))
        material2_outputs = self._import_material(material2, copy.copy(inputs))
        mask_outputs = self._import_material(mask_material, copy.copy(inputs))

        def create_color_combiner_mix_node(blend_type: str) -> bpy.types.Node:
            mix_node = self._node_tree.nodes.new('ShaderNodeMixRGB')
            mix_node.blend_type = blend_type
            mix_node.inputs['Fac'].default_value = 1.0

            if combiner.InvertMask:
                if material1_outputs is not None:
                    self._node_tree.links.new(mix_node.inputs['Color2'], material1_outputs.color_socket)
                if material2_outputs is not None:
                    self._node_tree.links.new(mix_node.inputs['Color1'], material2_outputs.color_socket)
            else:
                if material1_outputs is not None:
                    self._node_tree.links.new(mix_node.inputs['Color1'], material1_outputs.color_socket)
                if material2_outputs is not None:
                    self._node_tree.links.new(mix_node.inputs['Color2'], material2_outputs.color_socket)

            return mix_node

        # Color Operation
        if combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Material1:
            outputs.color_socket = material1_outputs.color_socket
        elif combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Material2:
            outputs.color_socket = material2_outputs.color_socket
        elif combiner.CombineOperation == EColorOperation.CO_Multiply:
            mix_node = create_color_combiner_mix_node('MULTIPLY')
            if combiner.Modulate2x or combiner.Modulate4x:
                modulate_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
                modulate_node.operation = 'SCALE'
                modulate_node.inputs['Scale'].default_value = 4.0 if combiner.Modulate4x else 2.0
                self._node_tree.links.new(modulate_node.inputs['Vector'], mix_node.outputs[2])
                outputs.color_socket = modulate_node.outputs['Vector']
            else:
                outputs.color_socket = mix_node.outputs[0]
        elif combiner.CombineOperation == EColorOperation.CO_Add:
            mix_node = create_color_combiner_mix_node('ADD')
            outputs.color_socket = mix_node.outputs[0]
        elif combiner.CombineOperation == EColorOperation.CO_Subtract:
            mix_node = create_color_combiner_mix_node('SUBTRACT')
            outputs.color_socket = mix_node.outputs[2]
        elif combiner.CombineOperation == EColorOperation.CO_AlphaBlend_With_Mask:
            mix_node = create_color_combiner_mix_node('MIX')
            if mask_outputs and mask_outputs.alpha_socket:
                self._node_tree.links.new(mix_node.inputs['Fac'], mask_outputs.alpha_socket)
            outputs.color_socket = mix_node.outputs[0]
        elif combiner.CombineOperation == EColorOperation.CO_Add_With_Mask_Modulation:
            mix_node = create_color_combiner_mix_node('ADD')
            outputs.color_socket = mix_node.outputs[0]
            # This doesn't use the Mask, but instead uses the alpha channel of Material 2, or if it hasn't got one,
            # modulates it on Material1.
            if material2_outputs is not None and material2_outputs.alpha_socket is not None:
                self._node_tree.links.new(mix_node.inputs['Fac'], material2_outputs.alpha_socket)
            elif material1_outputs is not None and material1_outputs.alpha_socket is not None:
                self._node_tree.links.new(mix_node.inputs['Fac'], material1_outputs.alpha_socket)
        elif combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Mask:  # dropped in UE3, apparently
            outputs.color_socket = mask_outputs.color_socket

        # Alpha Operation
        if combiner.AlphaOperation == EAlphaOperation.AO_Use_Mask:
            outputs.alpha_socket = mask_outputs.alpha_socket if mask_outputs else None
        elif combiner.AlphaOperation == EAlphaOperation.AO_Multiply:
            mix_node = self._node_tree.nodes.new('ShaderNodeMixRGB')
            mix_node.blend_type = 'MULTIPLY'
            if material1_outputs is not None and material1_outputs.alpha_socket:
                self._node_tree.links.new(mix_node.inputs[1], material1_outputs.alpha_socket)
            if material2_outputs is not None and material2_outputs.alpha_socket:
                self._node_tree.links.new(mix_node.inputs[2], material2_outputs.alpha_socket)
            outputs.alpha_socket = mix_node.outputs[0]
        elif combiner.AlphaOperation == EAlphaOperation.AO_Add:
            mix_node = self._node_tree.nodes.new('ShaderNodeMixRGB')
            mix_node.blend_type = 'ADD'
            if material1_outputs.alpha_socket:
                if material1_outputs is not None and material1_outputs.alpha_socket:
                    self._node_tree.links.new(mix_node.inputs[6], material1_outputs.alpha_socket)
                if material2_outputs is not None and material2_outputs.alpha_socket:
                    self._node_tree.links.new(mix_node.inputs[7], material2_outputs.alpha_socket)
            outputs.alpha_socket = mix_node.outputs[2]
        elif combiner.AlphaOperation == EAlphaOperation.AO_Use_Alpha_From_Material1:
            outputs.alpha_socket = material1_outputs.alpha_socket if material1_outputs else None
        elif combiner.AlphaOperation == EAlphaOperation.AO_Use_Alpha_From_Material2:
            outputs.alpha_socket = material2_outputs.alpha_socket if material2_outputs else None

        # NOTE: This is a bit of guess. Maybe investigate how this is actually determined.
        if material1_outputs is not None:
            outputs.size = material1_outputs.size
        elif material2_outputs is not None:
            outputs.size = material2_outputs.size
        elif mask_outputs is not None:
            outputs.size = mask_outputs.size

        return outputs

    def _import_constant_color(self, constant_color: UConstantColor, _: MaterialSocketInputs) -> MaterialSocketOutputs:
        outputs = MaterialSocketOutputs()

        rgb_node = self._node_tree.nodes.new('ShaderNodeRGB')
        rgb_node.outputs[0].default_value = (
            float(constant_color.Color.R) / 255.0,
            float(constant_color.Color.G) / 255.0,
            float(constant_color.Color.B) / 255.0,
            float(constant_color.Color.A) / 255.0
        )

        outputs.color_socket = rgb_node.outputs[0]

        return outputs

    def _import_cubemap(self, cubemap: UCubemap, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        outputs = MaterialSocketOutputs()
        tex_environment_node = self._node_tree.nodes.new('ShaderNodeTexEnvironment')
        tex_environment_node.image = self._load_image(cubemap.Reference)
        if socket_inputs.uv_socket is not None:
            self._node_tree.links.new(tex_environment_node.inputs['Vector'], socket_inputs.uv_socket)
        outputs.color_socket = tex_environment_node.outputs['Color']
        return outputs

    def _import_detail_material(self, detail_material: UMaterial, detail_scale: float,
                                color_socket: bpy.types.NodeSocket) -> bpy.types.NodeSocket:
        # Create UV scaling sockets.
        tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
        scale_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        scale_node.operation = 'SCALE'
        scale_node.inputs['Scale'].default_value = detail_scale
        self._node_tree.links.new(scale_node.inputs[0], tex_coord_node.outputs['UV'])
        detail_socket_inputs = MaterialSocketInputs()
        detail_socket_inputs.uv_socket = scale_node.outputs['Vector']

        # Import the detail material.
        detail_socket_outputs = self._import_material(detail_material, detail_socket_inputs)

        # This is a decent approximation for how detail textures look in-engine.
        hsv_node = self._node_tree.nodes.new('ShaderNodeHueSaturation')
        hsv_node.inputs['Value'].default_value = 4.0
        self._node_tree.links.new(hsv_node.inputs['Color'], detail_socket_outputs.color_socket)
        mix_node = self._node_tree.nodes.new('ShaderNodeMix')
        mix_node.data_type = 'RGBA'
        mix_node.blend_type = 'MULTIPLY'
        mix_node.inputs['Factor'].default_value = 1.0

        self._node_tree.links.new(mix_node.inputs[6], color_socket)
        self._node_tree.links.new(mix_node.inputs[7], hsv_node.outputs['Color'])

        return mix_node.outputs[2]

    def _import_final_blend(self, final_blend: UFinalBlend,
                            socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        material = self._material_cache.load_material(final_blend.Material)
        material_outputs = self._import_material(material, socket_inputs)

        outputs = MaterialSocketOutputs()
        outputs.use_backface_culling = not final_blend.TwoSided

        if material_outputs:
            outputs.color_socket = material_outputs.color_socket
            outputs.alpha_socket = material_outputs.alpha_socket
            outputs.size = material_outputs.size
            outputs.blend_method = material_outputs.blend_method

        return outputs

    def _import_shader(self, shader: UShader, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        outputs = MaterialSocketOutputs()

        # Opacity
        if shader.Opacity is not None:
            opacity_material = self._material_cache.load_material(shader.Opacity)
            opacity_material_outputs = self._import_material(opacity_material, copy.copy(socket_inputs))
            outputs.alpha_socket = opacity_material_outputs.alpha_socket
            outputs.blend_method = opacity_material_outputs.blend_method

        # Diffuse
        diffuse_material = self._material_cache.load_material(shader.Diffuse)
        if diffuse_material is not None:
            diffuse_material_outputs = self._import_material(diffuse_material, copy.copy(socket_inputs))
            detail_material = self._material_cache.load_material(shader.Detail) if shader.Detail is not None else None
            if detail_material is not None:
                self._import_detail_material(detail_material, shader.DetailScale, diffuse_material_outputs.color_socket)
            outputs.color_socket = diffuse_material_outputs.color_socket
            outputs.use_backface_culling = diffuse_material_outputs.use_backface_culling

        # Specular
        specular_material = self._material_cache.load_material(shader.Specular)
        if specular_material:
            # Final Add Node
            add_node = self._node_tree.nodes.new('ShaderNodeMix')
            add_node.data_type = 'RGBA'
            add_node.blend_type = 'ADD'
            add_node.inputs['Factor'].default_value = 1.0

            # Specular Multiply
            multiply_node = self._node_tree.nodes.new('ShaderNodeMix')
            multiply_node.data_type = 'RGBA'
            multiply_node.blend_type = 'MULTIPLY'
            multiply_node.inputs['Factor'].default_value = 1.0

            specular_material_outputs = self._import_material(specular_material, copy.copy(socket_inputs))
            self._node_tree.links.new(multiply_node.inputs[6], specular_material_outputs.color_socket)

            # Specular Mask
            specular_mask_material = self._material_cache.load_material(shader.SpecularityMask)
            if specular_mask_material is not None:
                specular_mask_material_outputs = self._import_material(specular_mask_material, copy.copy(socket_inputs))
                self._node_tree.links.new(multiply_node.inputs[7], specular_mask_material_outputs.color_socket)

            self._node_tree.links.new(add_node.inputs[7], multiply_node.outputs[2])
            if outputs.color_socket is not None:
                self._node_tree.links.new(add_node.inputs[6], outputs.color_socket)

            outputs.color_socket = add_node.outputs[2]

        return outputs

    def _import_tex_coord_source(self, tex_coord_source: UTexCoordSource,
                                 socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
        if tex_coord_source.SourceChannel == 0:
            uv_map_node.uv_map = 'VTXW0000'
        elif tex_coord_source.SourceChannel > 0:
            uv_map_node.uv_map = f'EXTRAUV{tex_coord_source.SourceChannel - 1}'
        else:
            raise RuntimeError('SourceChannel cannot be < 0')

        socket_inputs.uv_socket = uv_map_node.outputs['UV']

        material = self._material_cache.load_material(tex_coord_source.Material)
        material_outputs = self._import_material(material, copy.copy(socket_inputs))

        return material_outputs

    def _import_tex_env_map(self, tex_env_map: UTexEnvMap, _: MaterialSocketInputs) -> MaterialSocketOutputs:
        inputs = MaterialSocketInputs()

        if tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream0:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'VTXW0000'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream1:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV0'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream2:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV1'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream3:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV2'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream4:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV3'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream5:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV4'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream6:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV5'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_Stream7:
            uv_map_node = self._node_tree.nodes.new('ShaderNodeUVMap')
            uv_map_node.uv_map = 'EXTRAUV6'
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_WorldCoords:
            tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
            inputs.uv_socket = tex_coord_node.outputs['Object']
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_CameraCoords:
            tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
            inputs.uv_socket = tex_coord_node.outputs['Camera']
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_WorldEnvMapCoords:
            tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
            if tex_env_map.EnvMapType == ETexEnvMapType.EM_WorldSpace:
                inputs.uv_socket = tex_coord_node.outputs['Reflection']
            elif tex_env_map.EnvMapType == ETexEnvMapType.EM_CameraSpace:
                inputs.uv_socket = tex_coord_node.outputs['Reflection']
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_CameraEnvMapCoords:
            pass
        elif tex_env_map.TexCoordSource == ETexCoordSrc.TCS_ProjectorCoords:
            pass

        material = self._material_cache.load_material(tex_env_map.Material)

        return self._import_material(material, inputs)

    def _import_tex_oscillator(self, tex_oscillator: UTexOscillator,
                               socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
        vector_subtract_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'
        vector_add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_add_node.operation = 'ADD'
        vector_transform_node = self._node_tree.nodes.new('ShaderNodeVectorMath')

        offset_node = self._node_tree.nodes.new('ShaderNodeCombineXYZ')

        self._node_tree.links.new(vector_subtract_node.inputs[0], tex_coord_node.outputs['UV'])
        self._node_tree.links.new(vector_add_node.inputs[0], vector_transform_node.outputs[0])
        self._node_tree.links.new(vector_transform_node.inputs[0], vector_subtract_node.outputs[0])
        self._node_tree.links.new(vector_subtract_node.inputs[1], offset_node.outputs['Vector'])
        self._node_tree.links.new(vector_add_node.inputs[1], offset_node.outputs['Vector'])

        socket_inputs.uv_socket = vector_add_node.outputs['Vector']

        material = self._material_cache.load_material(tex_oscillator.Material)
        material_outputs = self._import_material(material, socket_inputs)

        if material_outputs is not None:
            offset_node.inputs['X'].default_value = tex_oscillator.UOffset / material_outputs.size[0]
            offset_node.inputs['Y'].default_value = tex_oscillator.VOffset / material_outputs.size[1]

        def get_driver_expression_for_pan(rate, amplitude):
            return f'sin((frame / bpy.context.scene.render.fps) * {rate * math.pi * 2}) * {amplitude}'

        def get_driver_expression_for_stretch(rate, amplitude):
            return f'1.0 + sin((frame / bpy.context.scene.render.fps) * {rate * math.pi * 2}) * {amplitude}'

        # TODO: make this generic for the whole thing (just a socket + expression)
        def add_driver_to_vector_transform_input(expression: str, index: int):
            fcurve = vector_transform_node.inputs[1].driver_add('default_value', index)
            fcurve.driver.expression = expression

        if tex_oscillator.UOscillationType == ETexOscillationType.OT_Pan:
            vector_transform_node.operation = 'ADD'
            if tex_oscillator.UOscillationRate != 0 and tex_oscillator.UOscillationAmplitude != 0:
                add_driver_to_vector_transform_input(
                    get_driver_expression_for_pan(tex_oscillator.UOscillationRate,
                                                  tex_oscillator.UOscillationAmplitude), 0)
            if tex_oscillator.VOscillationRate != 0 and tex_oscillator.VOscillationAmplitude != 0:
                add_driver_to_vector_transform_input(
                    get_driver_expression_for_pan(tex_oscillator.VOscillationRate,
                                                  tex_oscillator.VOscillationAmplitude), 1)
        elif tex_oscillator.UOscillationType == ETexOscillationType.OT_Jitter:
            vector_transform_node.operation = 'ADD'
            # same as add, but weird
            pass
        elif tex_oscillator.UOscillationType == ETexOscillationType.OT_Stretch:
            vector_transform_node.operation = 'MULTIPLY'
            if tex_oscillator.UOscillationRate != 0 and tex_oscillator.UOscillationAmplitude != 0:
                add_driver_to_vector_transform_input(
                    get_driver_expression_for_stretch(tex_oscillator.UOscillationRate,
                                                      tex_oscillator.UOscillationAmplitude), 0)
            if tex_oscillator.VOscillationRate != 0 and tex_oscillator.VOscillationAmplitude != 0:
                add_driver_to_vector_transform_input(
                    get_driver_expression_for_stretch(tex_oscillator.VOscillationRate,
                                                      tex_oscillator.VOscillationAmplitude), 1)
        elif tex_oscillator.UOscillationType == ETexOscillationType.OT_StretchRepeat:
            vector_transform_node.operation = 'MULTIPLY'
            # same as stretch, but weird...
            pass

        return material_outputs

    def _import_tex_panner(self, tex_panner: UTexPanner, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:

        tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')

        vector_rotate_node = self._node_tree.nodes.new('ShaderNodeVectorRotate')
        vector_rotate_node.rotation_type = 'EULER_XYZ'
        vector_rotate_node.inputs['Rotation'].default_value = tex_panner.PanDirection.get_radians()

        vector_add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_add_node.operation = 'ADD'

        fcurve = vector_add_node.inputs[1].driver_add('default_value', 0)
        fcurve.driver.expression = f'(frame / bpy.context.scene.render.fps) * {tex_panner.PanRate}'

        # TODO: there are strange interactions with stacking multiple UV modifiers, handle this later
        self._node_tree.links.new(vector_add_node.inputs[0], vector_rotate_node.outputs['Vector'])
        self._node_tree.links.new(vector_rotate_node.inputs[0], tex_coord_node.outputs['UV'])

        socket_inputs.uv_socket = vector_add_node.outputs['Vector']

        material = self._material_cache.load_material(tex_panner.Material)
        material_outputs = self._import_material(material, socket_inputs)

        return material_outputs

    def _import_tex_rotator(self, tex_rotator: UTexRotator,
                            socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
        vector_rotate_node = self._node_tree.nodes.new('ShaderNodeVectorRotate')
        vector_rotate_node.rotation_type = 'EULER_XYZ'

        socket_inputs.uv_socket = vector_rotate_node.outputs['Vector']

        material = self._material_cache.load_material(tex_rotator.Material)
        material_outputs = self._import_material(material, socket_inputs)

        u = tex_rotator.UOffset / material_outputs.size[0]
        v = tex_rotator.VOffset / material_outputs.size[1]
        vector_rotate_node.inputs['Center'].default_value = (u, v, 0.0)
        vector_rotate_node.inputs['Axis'].default_value = (0.0, 0.0, -1.0)

        rotation_radians = tex_rotator.Rotation.get_radians()

        def add_driver_to_vector_rotate_rotation_input(expression: str, index: int):
            fcurve = vector_rotate_node.inputs['Rotation'].driver_add('default_value', index)
            fcurve.driver.expression = expression

        if tex_rotator.TexRotationType == ETexRotationType.TR_FixedRotation:
            vector_rotate_node.inputs['Rotation'].default_value = rotation_radians
        elif tex_rotator.TexRotationType == ETexRotationType.TR_OscillatingRotation:
            amplitude_radians = tex_rotator.OscillationAmplitude.get_radians()
            rate_radians = tex_rotator.OscillationRate.get_radians()
            for i, (amplitude, rate) in enumerate(zip(amplitude_radians, rate_radians)):
                if amplitude != 0 or rate != 0:
                    add_driver_to_vector_rotate_rotation_input(
                        f'sin(frame / bpy.context.scene.render.fps * {rate}) * {amplitude}', i)
        elif tex_rotator.TexRotationType == ETexRotationType.TR_ConstantlyRotating:
            for i, radians in enumerate(rotation_radians):
                if radians != 0:
                    add_driver_to_vector_rotate_rotation_input(f'(frame / bpy.context.scene.render.fps) * {radians}', i)

        self._node_tree.links.new(vector_rotate_node.inputs['Vector'], tex_coord_node.outputs['UV'])

        return material_outputs

    def _import_tex_scaler(self, tex_scaler: UTexScaler, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        tex_coord_node = self._node_tree.nodes.new('ShaderNodeTexCoord')
        vector_subtract_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'
        vector_add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_add_node.operation = 'ADD'
        vector_transform_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_transform_node.operation = 'MULTIPLY'
        vector_transform_node.inputs[1].default_value = (1.0 / tex_scaler.UScale, 1.0 / tex_scaler.VScale, 0.0)

        offset_node = self._node_tree.nodes.new('ShaderNodeCombineXYZ')

        self._node_tree.links.new(vector_subtract_node.inputs[0], tex_coord_node.outputs['UV'])
        self._node_tree.links.new(vector_add_node.inputs[0], vector_transform_node.outputs[0])
        self._node_tree.links.new(vector_transform_node.inputs[0], vector_subtract_node.outputs[0])
        self._node_tree.links.new(vector_subtract_node.inputs[1], offset_node.outputs['Vector'])
        self._node_tree.links.new(vector_add_node.inputs[1], offset_node.outputs['Vector'])

        socket_inputs.uv_socket = vector_add_node.outputs['Vector']

        material = self._material_cache.load_material(tex_scaler.Material)
        material_outputs = self._import_material(material, socket_inputs)

        offset_node.inputs['X'].default_value = tex_scaler.UOffset / material_outputs.size[0]
        offset_node.inputs['Y'].default_value = tex_scaler.VOffset / material_outputs.size[1]

        return material_outputs

    def _import_texture(self, texture: UTexture, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        outputs = MaterialSocketOutputs()

        if texture.Reference is None:
            return outputs

        image_node = cast(ShaderNodeTexImage, self._node_tree.nodes.new('ShaderNodeTexImage'))
        image_node.image = self._load_image(texture.Reference)

        if socket_inputs.uv_socket is not None:
            # Hook up UV socket input to image texture.
            self._node_tree.links.new(image_node.inputs['Vector'], socket_inputs.uv_socket)

        if texture.UClampMode == ETexClampMode.TC_Clamp:
            image_node.extension = 'EXTEND'
        elif texture.UClampMode == ETexClampMode.TC_Wrap:
            image_node.extension = 'REPEAT'

        # Detail texture
        detail_material = None if texture.Detail is None else self._material_cache.load_material(texture.Detail)
        if detail_material is not None:
            outputs.color_socket = self._import_detail_material(detail_material, texture.DetailScale,
                                                                image_node.outputs['Color'])
        else:
            outputs.color_socket = image_node.outputs['Color']

        outputs.use_backface_culling = not texture.bTwoSided

        if texture.bAlphaTexture or texture.bMasked:
            outputs.alpha_socket = image_node.outputs['Alpha']

        if texture.bMasked or texture.bAlphaTexture:
            outputs.blend_method = 'CLIP'  # TODO: using 'BLEND' looks like ass, maybe figure this out later.
        else:
            outputs.blend_method = 'OPAQUE'

        outputs.size = (texture.UClamp, texture.VClamp)

        return outputs

    def _import_variable_tex_panner(self, variable_tex_panner: UVariableTexPanner,
                                    socket_inputs: MaterialSocketInputs) -> Optional[MaterialSocketOutputs]:
        vector_rotate_node = self._node_tree.nodes.new('ShaderNodeVectorRotate')
        vector_rotate_node.rotation_type = 'EULER_XYZ'
        vector_rotate_node.inputs['Rotation'].default_value = variable_tex_panner.PanDirection.get_radians()

        combine_xyz_node = self._node_tree.nodes.new('ShaderNodeCombineXYZ')

        multiply_node = self._node_tree.nodes.new('ShaderNodeMath')
        multiply_node.operation = 'MULTIPLY'
        multiply_node.inputs[1].default_value = variable_tex_panner.PanRate

        value_node = self._node_tree.nodes.new('ShaderNodeValue')

        fcurve = value_node.outputs[0].driver_add('default_value')
        fcurve.driver.expression = 'frame / bpy.context.scene.render.fps'

        self._node_tree.links.new(multiply_node.inputs[0], value_node.outputs['Value'])
        self._node_tree.links.new(combine_xyz_node.inputs['X'], multiply_node.outputs['Value'])
        self._node_tree.links.new(vector_rotate_node.inputs['Vector'], combine_xyz_node.outputs['Vector'])

        if socket_inputs.uv_socket is not None:
            # TODO: a generic way to handle this would be better, since it's possible to chain these UV modifiers
            #  together ad infinitum.
            #  Maybe just add UV socket outputs to a list and add them together whenever they're being used?

            # Add the two UV modifiers together.
            add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
            add_node.operation = 'ADD'

            self._node_tree.links.new(add_node.inputs[0], socket_inputs.uv_socket)
            self._node_tree.links.new(add_node.inputs[1], vector_rotate_node.outputs['Vector'])

            socket_inputs.uv_socket = add_node.outputs['Vector']

        if variable_tex_panner.Material is not None:
            material = self._material_cache.load_material(variable_tex_panner.Material)
            material_outputs = self._import_material(material, copy.copy(socket_inputs))
            return material_outputs

        return None

    def _import_vertex_color(self, _: UVertexColor, __: MaterialSocketInputs) -> MaterialSocketOutputs:
        vertex_color_node = self._node_tree.nodes.new('ShaderNodeAttribute')
        vertex_color_node.attribute_type = 'GEOMETRY'
        vertex_color_node.attribute_name = 'VERTEXCOLOR'

        outputs = MaterialSocketOutputs()
        outputs.color_socket = vertex_color_node.outputs['Color']
        outputs.alpha_socket = vertex_color_node.outputs['Alpha']

        return outputs

    def _import_material(self, material: UMaterial, inputs: MaterialSocketInputs) -> Optional[MaterialSocketOutputs]:
        if material is None:
            return None
        material_import_function = self._material_type_importers.get(type(material), None)
        if material_import_function is None:
            raise NotImplementedError(f'No importer registered for type "{type(material)}"')
        return material_import_function(material, inputs)

    def build(self, material: UMaterial) -> Optional[MaterialSocketOutputs]:
        return self._import_material(material, inputs=MaterialSocketInputs())


class BDK_OT_material_import(Operator, ImportHelper):
    bl_idname = 'bdk.import_material'
    bl_label = 'Import Unreal Material'
    filename_ext = '.props.txt'
    filepath: StringProperty()
    filter_glob: StringProperty(default='*.props.txt', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the PSA file',
        maxlen=1024,
        default='')

    def execute(self, context: bpy.types.Context):
        bdk_build_path = getattr(context.preferences.addons['bdk_addon'].preferences, 'build_path')

        if bdk_build_path == '':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The BDK build path has not been set in the addon preferences.')
            return {'CANCELLED'}

        if not os.path.isdir(bdk_build_path):
            self.report({'ERROR_INVALID_CONTEXT'}, f'The BDK build path ({bdk_build_path}) is not a directory that '
                                                   f'could be found.')
            return {'CANCELLED'}

        # Get an Unreal reference from the file path.
        reference = UReference.from_path(Path(self.filepath))

        # Create the material and prepare it.
        material_data = bpy.data.materials.new(reference.object_name)
        material_data.use_nodes = True
        node_tree = material_data.node_tree
        node_tree.nodes.clear()

        # Add custom property with Unreal reference.
        material_data['bdk_reference'] = str(reference)

        material_cache = MaterialCache(bdk_build_path)
        reference = UReference.from_path(Path(self.filepath))
        unreal_material = material_cache.load_material(reference)
        outputs = MaterialBuilder(material_cache, node_tree).build(unreal_material)

        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')
        diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')

        if outputs:
            material_data['UClamp'] = outputs.size[0]
            material_data['VClamp'] = outputs.size[1]
            material_data.use_backface_culling = outputs.use_backface_culling
            material_data.show_transparent_back = not outputs.use_backface_culling
            material_data.blend_method = outputs.blend_method

            if outputs.color_socket:
                node_tree.links.new(diffuse_node.inputs['Color'], outputs.color_socket)

            if outputs.blend_method in ['CLIP', 'BLEND']:
                transparent_node = node_tree.nodes.new('ShaderNodeBsdfTransparent')
                mix_node = node_tree.nodes.new('ShaderNodeMixShader')
                if outputs.alpha_socket:
                    node_tree.links.new(mix_node.inputs['Fac'], outputs.alpha_socket)
                node_tree.links.new(mix_node.inputs[1], transparent_node.outputs['BSDF'])
                node_tree.links.new(mix_node.inputs[2], diffuse_node.outputs['BSDF'])
                node_tree.links.new(output_node.inputs['Surface'], mix_node.outputs['Shader'])
            else:
                node_tree.links.new(output_node.inputs['Surface'], diffuse_node.outputs['BSDF'])

        return {'FINISHED'}


classes = (
    BDK_OT_material_import,
)