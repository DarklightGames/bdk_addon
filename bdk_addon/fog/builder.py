from bpy.types import NodeTree
from ..node_helpers import ensure_compositor_node_tree, ensure_inputs_and_outputs


def ensure_bdk_scene_compositor_node_tree():
    items = ()

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_inputs_and_outputs(nt)
        render_layers_node = nt.nodes.new('CompositorNodeRLayers')
        viewer_node = nt.nodes.new('CompositorNodeViewer')

        combine_color_node = nt.nodes.new('CompositorNodeCombineColor')

        opengl_fog_node = nt.nodes.new('CompositorNodeGroup')
        opengl_fog_node.node_tree = ensure_opengl_fog_node_tree()

    return ensure_compositor_node_tree('BDK Scene Compositor', items, build_function)


def ensure_opengl_fog_node_tree():
    items = (
        ('INPUT', 'NodeSocketFloat', 'Depth'),
        ('INPUT', 'NodeSocketColor', 'Image'),
        ('INPUT', 'NodeSocketColor', 'Fog Color'),
        ('INPUT', 'NodeSocketFloat', 'Fog Start'),
        ('INPUT', 'NodeSocketFloat', 'Fog End'),
        ('OUTPUT', 'NodeSocketColor', 'Image'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        map_range_node = nt.nodes.new('ShaderNodeMapRange')
        map_range_node.data_type = 'FLOAT'
        map_range_node.interpolation_type = 'LINEAR'
        map_range_node.inputs['To Min'].default_value = 0.0
        map_range_node.inputs['To Max'].default_value = 1.0

        mix_node = nt.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = 'MIX'

        nt.links.new(inputs['Depth'], map_range_node.inputs['Value'])
        nt.links.new(inputs['Fog Start'], map_range_node.inputs['From Min'])
        nt.links.new(inputs['Fog End'], map_range_node.inputs['From Max'])
        nt.links.new(inputs['Image'], mix_node.inputs['A'])
        nt.links.new(inputs['Fog Color'], mix_node.inputs['B'])
        nt.links.new(map_range_node.outputs['Result'], mix_node.inputs['Factor'])

        nt.links.new(mix_node.outputs['Result'], outputs['Image'])
    
    return ensure_compositor_node_tree('BDK OpenGL Fog', items, build_function)
