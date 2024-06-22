import math
import copy
import os
from typing import Dict, cast, Tuple, Callable, Any, List, Optional

import bpy
from bpy.props import StringProperty
from bpy.types import ShaderNodeTexImage, NodeTree, NodeSocket, Context, Node, Operator
from bpy_extras.io_utils import ImportHelper
from pathlib import Path

from .cache import MaterialCache
from .data import UColorModifier, UCombiner, UConstantColor, UCubemap, UFinalBlend, UTexCoordSource, UTexEnvMap, \
    UTexOscillator, UTexPanner, UTexRotator, UTexScaler, UTexture, UShader, UVariableTexPanner, UVertexColor, \
    UFadeColor, UMaterialSwitch, EAlphaOperation, EColorOperation, EColorFadeType, UMaterial, ETexCoordSrc, \
    ETexEnvMapType, ETexOscillationType, ETexRotationType, ETexClampMode
from ..bdk.preferences import BdkAddonPreferences
from ..bdk.repository.properties import BDK_PG_repository
from ..data import UReference


class MaterialSocketOutputs:
    color_socket: NodeSocket = None
    alpha_socket: NodeSocket = None
    blend_method: str = 'OPAQUE'
    use_backface_culling: bool = False
    size: Tuple[int, int] = (1, 1)


class MaterialSocketInputs:
    uv_source_socket: NodeSocket = None
    uv_socket: NodeSocket = None


class MaterialBuilder:
    def __init__(self, material_caches: List[MaterialCache], node_tree: NodeTree):
        self._material_caches = material_caches
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
            UFadeColor: self._import_fade_color,
            UMaterialSwitch: self._import_material_switch,
        }

    def _load_image(self, reference: UReference):
        extensions = ['.tga', '.png']  # A little dicey 🤔
        # myLevel images are stored within the blend files.
        if reference.package_name == 'myLevel':
            for extension in extensions:
                image_path = f'{reference.object_name}{extension}'
                # The key is a tuple of the image path and the library to look in. Since we're not looking in a library,
                # the library is None.
                key = (image_path, None)
                image = bpy.data.images.get(key, None)
                if image is not None:
                    return image
            raise RuntimeError(f'Could not find image {reference.object_name} in myLevel')

        for material_cache in self._material_caches:
            image_path = material_cache.resolve_path_for_reference(reference)
            image_path = str(image_path)
            for extension in extensions:
                file_path = image_path.replace('.props.txt', extension)
                if os.path.isfile(file_path):
                    image = bpy.data.images.load(str(file_path), check_existing=True)
                    image.alpha_mode = 'CHANNEL_PACKED'
                    return image
        raise RuntimeError(f'Could not find file for reference {reference} in {len(self._material_caches)} material caches')

    def load_material(self, reference: Optional[UReference]):
        if reference is None:
            return None
        for material_cache in self._material_caches:
            material = material_cache.load_material(reference)
            if material is not None:
                return material
        return None

    def _import_color_modifier(self, color_modifier: UColorModifier,
                               socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        material = self.load_material(color_modifier.Material)
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

        material1 = self.load_material(combiner.Material1)
        material2 = self.load_material(combiner.Material2)
        mask_material = self.load_material(combiner.Mask)

        material1_outputs = self._import_material(material1, copy.copy(inputs))
        material2_outputs = self._import_material(material2, copy.copy(inputs))
        mask_outputs = self._import_material(mask_material, copy.copy(inputs))

        def create_color_combiner_mix_node(blend_type: str) -> Node:
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
            if mask_outputs and mask_outputs.color_socket:
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

    def _import_fade_color(self, fade_color: UFadeColor, _: MaterialSocketInputs) -> MaterialSocketOutputs:
        node_tree = self._node_tree

        outputs = MaterialSocketOutputs()

        color_1_rgb_node = node_tree.nodes.new('ShaderNodeRGB')
        color_1_rgb_node.outputs[0].default_value = (
            float(fade_color.Color1.R) / 255.0,
            float(fade_color.Color1.G) / 255.0,
            float(fade_color.Color1.B) / 255.0,
            1.0
        )

        color_2_rgb_node = node_tree.nodes.new('ShaderNodeRGB')
        color_2_rgb_node.outputs[0].default_value = (
            float(fade_color.Color2.R) / 255.0,
            float(fade_color.Color2.G) / 255.0,
            float(fade_color.Color2.B) / 255.0,
            1.0
        )

        mix_rgb_node = node_tree.nodes.new('ShaderNodeMix')
        mix_rgb_node.data_type = 'RGBA'

        node_tree.links.new(mix_rgb_node.inputs[6], color_1_rgb_node.outputs['Color'])
        node_tree.links.new(mix_rgb_node.inputs[7], color_2_rgb_node.outputs['Color'])

        time_value_node = node_tree.nodes.new('ShaderNodeValue')
        time_value_node.label = 'Time'
        time_value_node.outputs[0].driver_add('default_value').driver.expression = 'frame/bpy.context.scene.render.fps'

        fade_offset_value_node = node_tree.nodes.new('ShaderNodeValue')
        fade_offset_value_node.label = 'FadeOffset'
        fade_offset_value_node.outputs[0].default_value = fade_color.FadeOffset

        fade_period_value_node = node_tree.nodes.new('ShaderNodeValue')
        fade_period_value_node.label = 'FadePeriod'
        fade_period_value_node.outputs[0].default_value = fade_color.FadePeriod

        factor_socket = None

        if fade_color.ColorFadeType == EColorFadeType.FC_Linear:
            time_multiply_node = node_tree.nodes.new('ShaderNodeMath')
            time_multiply_node.operation = 'MULTIPLY'
            time_multiply_node.inputs[1].default_value = 2.0
            node_tree.links.new(time_value_node.outputs[0], time_multiply_node.inputs[0])

            frequency_divide_node = node_tree.nodes.new('ShaderNodeMath')
            frequency_divide_node.operation = 'DIVIDE'
            frequency_divide_node.label = 'Frequency'
            frequency_divide_node.inputs[0].default_value = 1.0
            node_tree.links.new(fade_period_value_node.outputs['Value'], frequency_divide_node.inputs[1])

            frequency_multiply_node = node_tree.nodes.new('ShaderNodeMath')
            frequency_multiply_node.operation = 'MULTIPLY'
            node_tree.links.new(time_multiply_node.outputs[0], frequency_multiply_node.inputs[0])
            node_tree.links.new(frequency_divide_node.outputs[0], frequency_multiply_node.inputs[1])

            phase_add_node = node_tree.nodes.new('ShaderNodeMath')
            phase_add_node.operation = 'ADD'
            node_tree.links.new(frequency_multiply_node.outputs[0], phase_add_node.inputs[0])
            node_tree.links.new(fade_offset_value_node.outputs['Value'], phase_add_node.inputs[1])

            ping_pong_node = node_tree.nodes.new('ShaderNodeMath')
            ping_pong_node.operation = 'PINGPONG'
            ping_pong_node.inputs[1].default_value = 1.0
            node_tree.links.new(phase_add_node.outputs[0], ping_pong_node.inputs[0])

            factor_socket = ping_pong_node.outputs[0]
        elif fade_color.ColorFadeType == EColorFadeType.FC_Sinusoidal:
            def get_sinusoidal_driver_expression(phase: float, period: float) -> str:
                return f'(cos({phase}+(1/{period})*2*pi*(frame/bpy.context.scene.render.fps))+1)/2'

            sinusoidal_factor_value_node = node_tree.nodes.new('ShaderNodeValue')
            sinusoidal_factor_value_node.outputs[0].driver_add('default_value').driver.expression = get_sinusoidal_driver_expression(fade_color.FadeOffset, fade_color.FadePeriod)

            # TODO: For consistency, we should not be using a driver for the whole expression.
            #  Make this a series of nodes instead. (sure would be nice to have code that could take a math expression
            #  and turn it into a node tree)

            factor_socket = sinusoidal_factor_value_node.outputs[0]

        mix_alpha_node = node_tree.nodes.new('ShaderNodeMix')
        mix_alpha_node.data_type = 'FLOAT'
        mix_alpha_node.inputs['A'].default_value = fade_color.Color1.A / 255.0
        mix_alpha_node.inputs['B'].default_value = fade_color.Color2.A / 255.0

        if factor_socket is not None:
            node_tree.links.new(factor_socket, mix_rgb_node.inputs['Factor'])
            node_tree.links.new(factor_socket, mix_alpha_node.inputs['Factor'])

        outputs.color_socket = mix_rgb_node.outputs[2]
        outputs.alpha_socket = mix_alpha_node.outputs['Result']

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
                                color_socket: NodeSocket, uv_source_socket: Optional[NodeSocket]) -> NodeSocket:
        # Create UV scaling sockets.
        scale_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        scale_node.operation = 'SCALE'
        scale_node.inputs['Scale'].default_value = detail_scale
        if uv_source_socket:
            self._node_tree.links.new(scale_node.inputs[0], uv_source_socket)
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
        material = self.load_material(final_blend.Material)
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
            opacity_material = self.load_material(shader.Opacity)
            opacity_material_outputs = self._import_material(opacity_material, copy.copy(socket_inputs))
            outputs.alpha_socket = opacity_material_outputs.alpha_socket
            outputs.blend_method = opacity_material_outputs.blend_method

        # Diffuse
        diffuse_material = self.load_material(shader.Diffuse)
        if diffuse_material is not None:
            diffuse_material_outputs = self._import_material(diffuse_material, copy.copy(socket_inputs))
            detail_material = self.load_material(shader.Detail) if shader.Detail is not None else None
            if detail_material is not None:
                self._import_detail_material(detail_material, shader.DetailScale, diffuse_material_outputs.color_socket,
                                             uv_source_socket=socket_inputs.uv_source_socket)
            outputs.color_socket = diffuse_material_outputs.color_socket
            outputs.use_backface_culling = diffuse_material_outputs.use_backface_culling

        # Specular
        specular_material = self.load_material(shader.Specular)
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
            specular_mask_material = self.load_material(shader.SpecularityMask)
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

        material = self.load_material(tex_coord_source.Material)
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
            geometry_node = self._node_tree.nodes.new('ShaderNodeNewGeometry')
            inputs.uv_socket = geometry_node.outputs['Position']
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

        material = self.load_material(tex_env_map.Material)

        return self._import_material(material, inputs)

    def _import_tex_oscillator(self, tex_oscillator: UTexOscillator,
                               socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        vector_subtract_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'
        vector_add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_add_node.operation = 'ADD'
        vector_transform_node = self._node_tree.nodes.new('ShaderNodeVectorMath')

        offset_node = self._node_tree.nodes.new('ShaderNodeCombineXYZ')

        self._node_tree.links.new(vector_subtract_node.inputs[0], socket_inputs.uv_source_socket)
        self._node_tree.links.new(vector_add_node.inputs[0], vector_transform_node.outputs[0])
        self._node_tree.links.new(vector_transform_node.inputs[0], vector_subtract_node.outputs[0])
        self._node_tree.links.new(vector_subtract_node.inputs[1], offset_node.outputs['Vector'])
        self._node_tree.links.new(vector_add_node.inputs[1], offset_node.outputs['Vector'])

        socket_inputs.uv_socket = vector_add_node.outputs['Vector']

        material = self.load_material(tex_oscillator.Material)
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
        vector_rotate_node = self._node_tree.nodes.new('ShaderNodeVectorRotate')
        vector_rotate_node.rotation_type = 'EULER_XYZ'
        vector_rotate_node.inputs['Rotation'].default_value = tex_panner.PanDirection.get_radians()

        vector_add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_add_node.operation = 'ADD'

        fcurve = vector_add_node.inputs[1].driver_add('default_value', 0)
        fcurve.driver.expression = f'(frame / bpy.context.scene.render.fps) * {tex_panner.PanRate}'

        # TODO: there are strange interactions with stacking multiple UV modifiers, handle this later
        self._node_tree.links.new(vector_add_node.inputs[0], vector_rotate_node.outputs['Vector'])

        if socket_inputs.uv_source_socket:
            self._node_tree.links.new(vector_rotate_node.inputs[0], socket_inputs.uv_source_socket)

        socket_inputs.uv_socket = vector_add_node.outputs['Vector']

        material = self.load_material(tex_panner.Material)
        material_outputs = self._import_material(material, socket_inputs)

        return material_outputs

    def _import_tex_rotator(self, tex_rotator: UTexRotator,
                            socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        vector_rotate_node = self._node_tree.nodes.new('ShaderNodeVectorRotate')
        vector_rotate_node.rotation_type = 'EULER_XYZ'

        socket_inputs.uv_socket = vector_rotate_node.outputs['Vector']

        material = self.load_material(tex_rotator.Material)
        material_outputs = self._import_material(material, socket_inputs)

        if material_outputs is None:
            return None

        u = tex_rotator.UOffset / material_outputs.size[0]
        v = tex_rotator.VOffset / material_outputs.size[1]
        vector_rotate_node.inputs['Center'].default_value = (u, v, 0.0)

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

        self._node_tree.links.new(vector_rotate_node.inputs['Vector'], socket_inputs.uv_source_socket)

        return material_outputs

    def _import_tex_scaler(self, tex_scaler: UTexScaler, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        vector_subtract_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'
        vector_add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_add_node.operation = 'ADD'
        vector_transform_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
        vector_transform_node.operation = 'MULTIPLY'
        vector_transform_node.inputs[1].default_value = (1.0 / tex_scaler.UScale, 1.0 / tex_scaler.VScale, 0.0)

        offset_node = self._node_tree.nodes.new('ShaderNodeCombineXYZ')

        if socket_inputs.uv_source_socket is not None:
            self._node_tree.links.new(vector_subtract_node.inputs[0], socket_inputs.uv_source_socket)

        self._node_tree.links.new(vector_add_node.inputs[0], vector_transform_node.outputs[0])
        self._node_tree.links.new(vector_transform_node.inputs[0], vector_subtract_node.outputs[0])
        self._node_tree.links.new(vector_subtract_node.inputs[1], offset_node.outputs['Vector'])
        self._node_tree.links.new(vector_add_node.inputs[1], offset_node.outputs['Vector'])

        socket_inputs.uv_socket = vector_add_node.outputs['Vector']

        material = self.load_material(tex_scaler.Material)
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
        elif socket_inputs.uv_source_socket is not None:
            self._node_tree.links.new(image_node.inputs['Vector'], socket_inputs.uv_source_socket)

        if texture.UClampMode == ETexClampMode.TC_Clamp:
            image_node.extension = 'EXTEND'
        elif texture.UClampMode == ETexClampMode.TC_Wrap:
            image_node.extension = 'REPEAT'

        # Detail texture
        detail_material = None if texture.Detail is None else self.load_material(texture.Detail)
        if detail_material is not None:
            outputs.color_socket = self._import_detail_material(detail_material, texture.DetailScale,
                                                                image_node.outputs['Color'],
                                                                uv_source_socket=socket_inputs.uv_source_socket)
        else:
            outputs.color_socket = image_node.outputs['Color']

        outputs.use_backface_culling = not texture.bTwoSided

        if texture.bAlphaTexture or texture.bMasked:
            outputs.alpha_socket = image_node.outputs['Alpha']

        if texture.bMasked:
            outputs.blend_method = 'CLIP'
        elif texture.bAlphaTexture:
            outputs.blend_method = 'BLEND'
        else:
            outputs.blend_method = 'OPAQUE'

        outputs.size = (texture.UClamp, texture.VClamp)

        return outputs

    def _import_material_switch(self, material_switch: UMaterialSwitch, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
        node_tree = self._node_tree
        current_value_node = node_tree.nodes.new('ShaderNodeValue')
        current_value_node.outputs['Value'].default_value = material_switch.Current  # TODO: in future this could be driven by a driver?

        # Truncate and Modulo the current value node.
        truncate_node = node_tree.nodes.new('ShaderNodeMath')
        truncate_node.operation = 'FLOOR'
        node_tree.links.new(truncate_node.inputs[0], current_value_node.outputs['Value'])

        modulo_node = node_tree.nodes.new('ShaderNodeMath')
        modulo_node.operation = 'MODULO'
        modulo_node.inputs[1].default_value = len(material_switch.Materials)
        node_tree.links.new(modulo_node.inputs[0], truncate_node.outputs['Value'])

        current_socket = modulo_node.outputs['Value']
        last_color_socket: Optional[NodeSocket] = None
        last_alpha_socket: Optional[NodeSocket] = None

        materials = []
        material_outputs = []

        for switch_index, switch_material in reversed(list(enumerate(material_switch.Materials))):
            # Add a new compare node and compare the current value to the switch index.
            compare_node = node_tree.nodes.new('ShaderNodeMath')
            compare_node.operation = 'COMPARE'
            compare_node.inputs[1].default_value = switch_index
            node_tree.links.new(compare_node.inputs[0], current_socket)

            material = self.load_material(switch_material)
            outputs = self._import_material(material, socket_inputs)

            # Add a mix color node.
            mix_rgb_node = node_tree.nodes.new('ShaderNodeMixRGB')
            mix_rgb_node.data_type = 'RGBA'
            node_tree.links.new(mix_rgb_node.inputs['Fac'], compare_node.outputs['Value'])
            node_tree.links.new(mix_rgb_node.inputs['Color2'], outputs.color_socket)
            if last_color_socket is not None:
                # Hook up the color socket of the material output to the Color1 input of the mix color node.
                node_tree.links.new(mix_rgb_node.inputs['Color1'], last_color_socket)

            # Add a mix alpha node.
            mix_alpha_node = node_tree.nodes.new('ShaderNodeMixRGB')
            mix_alpha_node.data_type = 'FLOAT'
            node_tree.links.new(mix_alpha_node.inputs[0], compare_node.outputs['Value'])
            node_tree.links.new(mix_alpha_node.inputs[3], outputs.alpha_socket)  # B
            if last_alpha_socket is not None:
                node_tree.links.new(mix_alpha_node.inputs[1], last_alpha_socket)

            last_color_socket = mix_rgb_node.outputs[0]
            last_alpha_socket = mix_alpha_node.outputs[0] # TODO: one of these is wrong...

            materials.append(material)
            material_outputs.append(outputs)

        outputs = MaterialSocketOutputs()
        outputs.color_socket = last_color_socket
        outputs.alpha_socket = last_alpha_socket
        outputs.size = material_outputs[material_switch.Current].size   # TODO: make this the max size of all materials
        outputs.use_backface_culling = material_outputs[material_switch.Current].use_backface_culling  # TODO: make this...i dunno lol
        outputs.blend_method = material_outputs[material_switch.Current].blend_method

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

        uv_socket = socket_inputs.uv_socket if socket_inputs.uv_socket else socket_inputs.uv_source_socket

        if uv_socket is not None:
            # TODO: a generic way to handle this would be better, since it's possible to chain these UV modifiers
            #  together ad infinitum.
            #  Maybe just add UV socket outputs to a list and add them together whenever they're being used?

            # Add the two UV modifiers together.
            add_node = self._node_tree.nodes.new('ShaderNodeVectorMath')
            add_node.operation = 'ADD'

            self._node_tree.links.new(add_node.inputs[0], uv_socket)
            self._node_tree.links.new(add_node.inputs[1], vector_rotate_node.outputs['Vector'])

            socket_inputs.uv_socket = add_node.outputs['Vector']

        if variable_tex_panner.Material is not None:
            material = self.load_material(variable_tex_panner.Material)
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

    def build(self, material: UMaterial, uv_source_socket: Optional[NodeSocket]) -> Optional[MaterialSocketOutputs]:
        inputs = MaterialSocketInputs()
        inputs.uv_source_socket = uv_source_socket
        return self._import_material(material, inputs=inputs)


def _add_shader_from_outputs(node_tree: NodeTree, outputs: MaterialSocketOutputs) -> Optional[NodeSocket]:
    diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    if outputs.color_socket:
        node_tree.links.new(diffuse_node.inputs['Color'], outputs.color_socket)

    if outputs.blend_method in ['CLIP', 'BLEND']:
        transparent_node = node_tree.nodes.new('ShaderNodeBsdfTransparent')
        mix_node = node_tree.nodes.new('ShaderNodeMixShader')
        if outputs.alpha_socket:
            node_tree.links.new(mix_node.inputs['Fac'], outputs.alpha_socket)
        node_tree.links.new(mix_node.inputs[1], transparent_node.outputs['BSDF'])
        node_tree.links.new(mix_node.inputs[2], diffuse_node.outputs['BSDF'])
        return mix_node.outputs['Shader']
    else:
        return diffuse_node.outputs['BSDF']


class BDK_OT_material_import(Operator, ImportHelper):
    bl_idname = 'bdk.import_material'
    bl_label = 'Import Unreal Material'
    filename_ext = '.props.txt'
    filter_glob: StringProperty(default='*.props.txt', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the PSA file',
        maxlen=1024,
        default='')
    repository_id: StringProperty(
        name='Repository ID',
        description='The ID of the repository to search for the material in',
        maxlen=1024,
        default=''
    )

    # TODO: use only a single asset library; it makes no sense to go searching in asset libraries unrelated to the
    #  current repository.

    def execute(self, context: Context):
        repositories = getattr(context.preferences.addons[BdkAddonPreferences.bl_idname].preferences, 'repositories')

        def find_repository_by_id(repository_id: str) -> Optional[BDK_PG_repository]:
            for repository in repositories:
                if repository.id == repository_id:
                    return repository
            return None

        repository = find_repository_by_id(self.repository_id)
        if repository is None:
            self.report({'ERROR_INVALID_CONTEXT'}, f'Repository with ID "{self.repository_id}" not found.')
            return {'CANCELLED'}

        material_caches = [MaterialCache(Path(repository.cache_directory) / repository.id)]

        # Get an Unreal reference from the file path.
        reference = UReference.from_path(Path(self.filepath))

        # Create the material and prepare it.
        material_data = bpy.data.materials.new(reference.object_name)
        material_data.use_nodes = True
        material_data.preview_render_type = 'FLAT'

        # Add custom property with Unreal reference.
        material_data.bdk.package_reference = str(reference)

        node_tree = material_data.node_tree
        node_tree.nodes.clear()

        # Try to load the material from the cache.
        unreal_material = None
        for material_cache in material_caches:
            unreal_material = material_cache.load_material(reference)
            if unreal_material is not None:
                break

        tex_coord_node = node_tree.nodes.new('ShaderNodeTexCoord')

        # Build the material.
        material_builder = MaterialBuilder(material_caches, node_tree)
        outputs = material_builder.build(unreal_material, uv_source_socket=tex_coord_node.outputs['UV'])

        # Make a new function to do the conversion from Color & Alpha socket to Shader.
        if outputs:
            material_data.bdk.size_x = outputs.size[0]
            material_data.bdk.size_y = outputs.size[1]
            material_data.use_backface_culling = outputs.use_backface_culling
            material_data.show_transparent_back = not outputs.use_backface_culling
            material_data.blend_method = outputs.blend_method

            # For material switch this may be a bit harder!
            shader_socket = _add_shader_from_outputs(node_tree, outputs)

            output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')
            node_tree.links.new(output_node.inputs['Surface'], shader_socket)

        return {'FINISHED'}


classes = (
    BDK_OT_material_import,
)
