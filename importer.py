import os
from pathlib import Path

from bpy.types import ShaderNodeTexImage
import bpy.types
import typing
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy_types import Operator, Node

from .data import UMaterial, UTexture, ETexClampMode, UReference, UCombiner, EColorOperation, EAlphaOperation
from .reader import read_material


class MaterialCache:
    def __init__(self, root_directory: str):
        self.__root_directory__ = root_directory
        self.__materials__: typing.Dict[str, UMaterial] = {}

    def resolve_path_for_reference(self, reference: UReference) -> typing.Optional[Path]:
        try:
            return Path(os.path.join(self.__root_directory__, reference.package_name, reference.type_name, f'{reference.object_name}.props.txt')).resolve()
        except RuntimeError:
            pass
        return None

    def load_material(self, reference: UReference) -> typing.Optional[UMaterial]:
        key = str(reference)
        if key in self.__materials__:
            return self.__materials__[str(reference)]
        path = self.resolve_path_for_reference(reference)
        if path is None:
            return None
        material = read_material(str(path))
        self.__materials__[key] = material
        return material


class MaterialSocketOutputs:
    color_socket: bpy.types.NodeSocket = None
    alpha_socket: bpy.types.NodeSocket = None
    has_alpha: bool = False
    use_backface_culling: bool = False


class MaterialSocketInputs:
    uv_socket: bpy.types.NodeSocket = None


# TODO: needs to accept
def import_texture(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, texture: UTexture, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    outputs = MaterialSocketOutputs()

    image_node = typing.cast(ShaderNodeTexImage, node_tree.nodes.new('ShaderNodeTexImage'))
    image_path = material_cache.resolve_path_for_reference(texture.Reference)
    image_path = str(image_path)
    image_path = image_path.replace('.props.txt', '.tga')

    image_node.image = bpy.data.images.load(str(image_path), check_existing=True)

    if socket_inputs.uv_socket is not None:
        # Hook up UV socket input to image texture.
        node_tree.links.new(image_node.inputs['Vector'], socket_inputs.uv_socket)

    match texture.UClampMode:
        case ETexClampMode.TC_Clamp:
            image_node.extension = 'EXTEND'
        case ETexClampMode.TC_Wrap:
            image_node.extension = 'REPEAT'

    # Detail texture
    detail_material = None if texture.Detail is None else material_cache.load_material(texture.Detail)
    if detail_material is not None:

        # Create UV scaling sockets.
        texcoord_node = node_tree.nodes.new('ShaderNodeTexCoord')

        scale_node = node_tree.nodes.new('ShaderNodeVectorMath')
        scale_node.operation = 'SCALE'
        scale_node.inputs['Scale'].default_value = texture.DetailScale

        node_tree.links.new(scale_node.inputs[0], texcoord_node.outputs['UV'])

        detail_socket_inputs = MaterialSocketInputs()
        detail_socket_inputs.uv_socket = scale_node.outputs['Vector']

        # Import the detail material.
        detail_socket_outputs = import_material(material_cache, node_tree, detail_material, detail_socket_inputs)

        # This is a decent approximation for how detail textures look in-engine.

        hsv_node = node_tree.nodes.new('ShaderNodeHueSaturation')
        hsv_node.inputs['Value'].default_value = 4.0

        node_tree.links.new(hsv_node.inputs['Color'], detail_socket_outputs.color_socket)

        mix_node = node_tree.nodes.new('ShaderNodeMix')
        mix_node.data_type = 'RGBA'
        mix_node.blend_type = 'MULTIPLY'
        mix_node.inputs['Factor'].default_value = 1.0

        #
        node_tree.links.new(mix_node.inputs[6], image_node.outputs['Color'])
        node_tree.links.new(mix_node.inputs[7], hsv_node.outputs['Color'])

        outputs.color_socket = mix_node.outputs[2]
    else:
        outputs.color_socket = image_node.outputs['Color']

    outputs.use_backface_culling = not texture.bTwoSided

    if texture.bAlphaTexture or texture.bMasked:
        outputs.has_alpha = True
        outputs.alpha_socket = image_node.outputs['Alpha']

    return outputs


def import_combiner(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, combiner: UCombiner, inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    # https://docs.unrealengine.com/udk/Two/MaterialsCombiners.html

    outputs = MaterialSocketOutputs()

    material1 = material_cache.load_material(combiner.Material1)
    material2 = material_cache.load_material(combiner.Material2)
    mask_material = material_cache.load_material(combiner.Mask)

    material1_outputs = import_material(material_cache, node_tree, material1, inputs)
    material2_outputs = import_material(material_cache, node_tree, material2, inputs)
    mask_outputs = import_material(material_cache, node_tree, mask_material, inputs)

    def create_color_combiner_mix_node(blend_type: str) -> bpy.types.ShaderNode:
        mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = blend_type
        mix_node.inputs['Fac'].default_value = 1.0

        # TODO:
        material1_index = 6
        material2_index = 7

        if combiner.InvertMask:
            node_tree.links.new(mix_node.inputs[material2_index], material1_outputs.color_socket)
            node_tree.links.new(mix_node.inputs[material1_index], material2_outputs.color_socket)
        else:
            node_tree.links.new(mix_node.inputs[material1_index], material1_outputs.color_socket)
            node_tree.links.new(mix_node.inputs[material2_index], material2_outputs.color_socket)
        return mix_node

    # Color Operation
    if combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Material1:
        outputs.color_socket = material1_outputs.color_socket
    elif combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Material2:
        outputs.color_socket = material2_outputs.color_socket
    elif combiner.CombineOperation == EColorOperation.CO_Multiply:
        mix_node = create_color_combiner_mix_node('MULTIPLY')
        if combiner.Modulate2x or combiner.Modulate4x:
            modulate_node = node_tree.nodes.new('ShaderNodeVectorMath')
            modulate_node.operation = 'SCALE'
            modulate_node.inputs['Scale'].default_value = 4.0 if combiner.Modulate4x else 2.0
            node_tree.links.new(modulate_node.inputs['Vector'], mix_node.outputs[2])
            outputs.color_socket = modulate_node.outputs['Vector']
        else:
            outputs.color_socket = mix_node.outputs[2]
    elif combiner.CombineOperation == EColorOperation.CO_Add:
        mix_node = create_color_combiner_mix_node('ADD')
        outputs.color_socket = mix_node.outputs[2]
    elif combiner.CombineOperation == EColorOperation.CO_Subtract:
        mix_node = create_color_combiner_mix_node('SUBTRACT')
        outputs.color_socket = mix_node.outputs[2]
    elif combiner.CombineOperation == EColorOperation.CO_AlphaBlend_With_Mask:
        mix_node = create_color_combiner_mix_node('MIX')
        node_tree.links.new(mix_node.inputs['Fac'], mask_outputs.alpha_socket)
    elif combiner.CombineOperation == EColorOperation.CO_Add_With_Mask_Modulation:
        mix_node = create_color_combiner_mix_node('ADD')
        outputs.color_socket = mix_node.outputs[2]
        # This doesn't use the Mask, but instead uses the alpha channel of Material 2, or if it hasn't got one,
        # modulates it on Material1.
        if material2_outputs.alpha_socket is not None:
            node_tree.links.new(mix_node.inputs['Fac'], material2_outputs.alpha_socket)
        else:
            node_tree.links.new(mix_node.inputs['Fac'], material1_outputs.alpha_socket)
    elif combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Mask:   # dropped in UE3, apparently
        outputs.color_socket = mask_outputs.color_socket

    # Alpha Operation
    if combiner.AlphaOperation == EAlphaOperation.AO_Use_Mask:
        outputs.alpha_socket = mask_outputs.alpha_socket
    elif combiner.AlphaOperation == EAlphaOperation.AO_Multiply:
        mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = 'MULTIPLY'
        node_tree.links.new(mix_node.inputs[6], material1_outputs.alpha_socket)
        node_tree.links.new(mix_node.inputs[7], material2_outputs.alpha_socket)
        outputs.alpha_socket = mix_node.outputs[2]
    elif combiner.AlphaOperation == EAlphaOperation.AO_Add:
        mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = 'ADD'
        node_tree.links.new(mix_node.inputs[6], material1_outputs.alpha_socket)
        node_tree.links.new(mix_node.inputs[7], material2_outputs.alpha_socket)
        outputs.alpha_socket = mix_node.outputs[2]
    elif combiner.AlphaOperation == EAlphaOperation.AO_Use_Alpha_From_Material1:
        outputs.alpha_socket = material1_outputs.alpha_socket
    elif combiner.AlphaOperation == EAlphaOperation.AO_Use_Alpha_From_Material2:
        outputs.alpha_socket = material2_outputs.alpha_socket

    return outputs


def import_material(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, umaterial: UMaterial, inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    if isinstance(umaterial, UTexture):
        print('importing TEXTURE')
        return import_texture(material_cache, node_tree, umaterial, inputs)
    if isinstance(umaterial, UCombiner):
        return import_combiner(material_cache, node_tree, umaterial, inputs)
    else:
        print(f'Unhandled material type {type(umaterial)}')


class UMATERIAL_OT_import(Operator, ImportHelper):
    bl_idname = 'import.umaterial'
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
        cache_path = 'C:\\dev\\bdk-git\\bdk-build'
        material_cache = MaterialCache(cache_path)

        reference = UReference.from_path(Path(self.filepath))

        umaterial = material_cache.load_material(reference)
        material_name = os.path.basename(self.filepath).strip('.props.txt')

        material = bpy.data.materials.new(material_name)
        material.use_nodes = True
        node_tree = material.node_tree
        node_tree.nodes.clear()

        # Add custom property with Unreal reference string.
        material['bdk_reference'] = str(reference)

        socket_inputs = MaterialSocketInputs()
        outputs = import_material(material_cache, node_tree, umaterial, socket_inputs)
        material.use_backface_culling = outputs.use_backface_culling

        if outputs.has_alpha:
            material.blend_method = 'CLIP'
        else:
            material.blend_method = 'OPAQUE'

        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')
        diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')

        node_tree.links.new(diffuse_node.inputs['Color'], outputs.color_socket)

        if outputs.has_alpha:
            transparent_node = node_tree.nodes.new('ShaderNodeBsdfTransparent')
            mix_node = node_tree.nodes.new('ShaderNodeMixShader')
            node_tree.links.new(mix_node.inputs['Fac'], outputs.alpha_socket)
            node_tree.links.new(mix_node.inputs[1], transparent_node.outputs['BSDF'])
            node_tree.links.new(mix_node.inputs[2], diffuse_node.outputs['BSDF'])
            node_tree.links.new(output_node.inputs['Surface'], mix_node.outputs['Shader'])
        else:
            node_tree.links.new(output_node.inputs['Surface'], diffuse_node.outputs['BSDF'])

        return {'FINISHED'}


classes = (
    UMATERIAL_OT_import,
)
