from bpy.types import Context, UILayout

def draw_fog_settings(layout: UILayout, context: Context):
    scene = context.scene
    fog_props = scene.bdk.fog

    fog_header, fog_panel = layout.panel('Fog')
    fog_header.use_property_split = False
    fog_header.prop(fog_props, 'is_enabled', text='Fog')
    if fog_panel:
        fog_panel.use_property_split = True
        fog_panel.prop(fog_props, 'color', text='Color')
        fog_panel.prop(fog_props, 'distance_start', text='Distance Start')
        fog_panel.prop(fog_props, 'distance_end', text='End')