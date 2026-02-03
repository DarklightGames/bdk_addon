from bpy.types import NodeTree, bpy_struct, ID
from ..node_helpers import ensure_compositor_node_tree, ensure_inputs_and_outputs


def _add_fog_driver(struct: bpy_struct, target_id: ID, data_path: str, index: int | None = None, path: str = 'default_value'):
    """Add a driver that reads from scene.bdk.fog properties."""
    fcurve = struct.driver_add(path)
    if fcurve is None or isinstance(fcurve, list):
        return
    driver = fcurve.driver
    if driver is None:
        return
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = target_id
    full_data_path = f"bdk.fog.{data_path}"
    if index is not None:
        full_data_path += f"[{index}]"
    var.targets[0].data_path = full_data_path


def ensure_bdk_scene_compositor_node_tree():
    items = (
        ('OUTPUT', 'NodeSocketColor', 'Image'),
    )

    def build_function(nt: NodeTree):
        from bpy import context
        
        inputs, outputs = ensure_inputs_and_outputs(nt)
        render_layers_node = nt.nodes.new('CompositorNodeRLayers')
        viewer_node = nt.nodes.new('CompositorNodeViewer')

        combine_color_node = nt.nodes.new('CompositorNodeCombineColor')

        opengl_fog_node = nt.nodes.new('CompositorNodeGroup')
        opengl_fog_node.node_tree = ensure_opengl_fog_node_tree()

        nt.links.new(render_layers_node.outputs['Image'], opengl_fog_node.inputs['Image'])
        nt.links.new(render_layers_node.outputs['Depth'], opengl_fog_node.inputs['Depth'])
        nt.links.new(combine_color_node.outputs['Image'], opengl_fog_node.inputs['Fog Color'])

        nt.links.new(opengl_fog_node.outputs['Image'], viewer_node.inputs['Image'])
        nt.links.new(opengl_fog_node.outputs['Image'], outputs['Image'])

        scene = context.scene

        if scene is None:
            return

        # Add drivers for fog properties.
        _add_fog_driver(opengl_fog_node.inputs['Fog Start'], scene, 'distance_start')
        _add_fog_driver(opengl_fog_node.inputs['Fog End'], scene, 'distance_end')
        _add_fog_driver(combine_color_node.inputs['Red'], scene, 'color', index=0)
        _add_fog_driver(combine_color_node.inputs['Green'], scene, 'color', index=1)
        _add_fog_driver(combine_color_node.inputs['Blue'], scene, 'color', index=2)

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

        mix_node = nt.nodes.new('ShaderNodeMix')
        mix_node.blend_type = 'MIX'
        mix_node.data_type = 'RGBA'
        mix_node.clamp_factor = False  # Factor is already clamped between 0 and 1 by Map Range

        nt.links.new(inputs['Depth'], map_range_node.inputs['Value'])
        nt.links.new(inputs['Fog Start'], map_range_node.inputs['From Min'])
        nt.links.new(inputs['Fog End'], map_range_node.inputs['From Max'])
        nt.links.new(inputs['Image'], mix_node.inputs['A'])
        nt.links.new(inputs['Fog Color'], mix_node.inputs['B'])
        nt.links.new(map_range_node.outputs['Result'], mix_node.inputs['Factor'])

        nt.links.new(mix_node.outputs['Result'], outputs['Image'])
    
    return ensure_compositor_node_tree('BDK OpenGL Fog', items, build_function, should_force_build=True)
