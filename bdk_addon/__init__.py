from bpy.props import PointerProperty

if 'bpy' in locals():
    import importlib

    importlib.reload(constants)
    importlib.reload(property_group_helpers)
    importlib.reload(node_helpers)

    importlib.reload(actor_properties)

    importlib.reload(repository_kernel)
    importlib.reload(repository_properties)
    importlib.reload(repository_operators)
    importlib.reload(repository_ui)

    importlib.reload(package_reader)

    importlib.reload(bdk_data)
    importlib.reload(bdk_helpers)
    importlib.reload(bdk_preferences)
    importlib.reload(bdk_operators)

    importlib.reload(g16)

    importlib.reload(material_data)
    importlib.reload(material_reader)
    importlib.reload(material_importer)
    importlib.reload(material_operators)
    importlib.reload(material_ui)

    # Projector
    importlib.reload(projector_builder)
    importlib.reload(projector_properties)
    importlib.reload(projector_operators)
    importlib.reload(projector_ui)

    # Fluid Surface
    importlib.reload(fluid_surface_builder)
    importlib.reload(fluid_surface_properties)
    importlib.reload(fluid_surface_operators)
    importlib.reload(fluid_surface_ui)

    # Terrain
    importlib.reload(terrain_sample)
    importlib.reload(terrain_properties)
    importlib.reload(terrain_context)
    importlib.reload(terrain_kernel)
    importlib.reload(terrain_builder)
    importlib.reload(terrain_exporter)
    importlib.reload(terrain_operators)
    importlib.reload(terrain_ui)

    # Terrain Doodad Paint
    importlib.reload(terrain_doodad_paint_properties)
    importlib.reload(terrain_doodad_paint_operators)

    # Terrain Doodad Scatter
    importlib.reload(terrain_doodad_scatter_builder)
    importlib.reload(terrain_doodad_scatter_properties)

    # Terrain Doodad Sculpt
    importlib.reload(terrain_doodad_sculpt_builder)
    importlib.reload(terrain_doodad_sculpt_properties)
    importlib.reload(terrain_doodad_sculpt_operators)

    # Terrain Doodad
    importlib.reload(terrain_doodad_data)
    importlib.reload(terrain_doodad_builder)
    importlib.reload(terrain_doodad_properties)
    importlib.reload(terrain_doodad_operators)
    importlib.reload(terrain_doodad_ui)

    # BSP
    importlib.reload(bsp_data)
    importlib.reload(bsp_builder)
    importlib.reload(bsp_tools)
    importlib.reload(bsp_properties)
    importlib.reload(bsp_operators)
    importlib.reload(bsp_ui)

    # T3D
    importlib.reload(t3d_data)
    importlib.reload(t3d_operators)
    importlib.reload(t3d_importer)
    importlib.reload(t3d_writer)

    importlib.reload(bdk_properties)
    importlib.reload(bdk_ui)
else:
    from . import data as bdk_data
    from . import helpers as bdk_helpers

    from .actor import properties as actor_properties

    from .bdk.repository import kernel as repository_kernel
    from .bdk.repository import properties as repository_properties
    from .bdk.repository import operators as repository_operators
    from .bdk.repository import ui as repository_ui

    from .bdk import operators as bdk_operators
    from .bdk import properties as bdk_properties
    from .bdk import ui as bdk_ui
    from .bdk import preferences as bdk_preferences

     # G16
    from .io import g16

    # Package
    from .package import reader as package_reader

    # Material
    from .material import data as material_data
    from .material import reader as material_reader
    from .material import importer as material_importer
    from .material import operators as material_operators
    from .material import ui as material_ui

    # Projector
    from .projector import builder as projector_builder
    from .projector import properties as projector_properties
    from .projector import operators as projector_operators
    from .projector import ui as projector_ui

    # Fluid Surface
    from .fluid_surface import builder as fluid_surface_builder
    from .fluid_surface import properties as fluid_surface_properties
    from .fluid_surface import operators as fluid_surface_operators
    from .fluid_surface import ui as fluid_surface_ui

    # Terrain
    from .terrain import properties as terrain_properties
    from .terrain import context as terrain_context
    from .terrain import kernel as terrain_kernel
    from .terrain import builder as terrain_builder
    from .terrain import exporter as terrain_exporter
    from .terrain import operators as terrain_operators
    from .terrain import ui as terrain_ui

    # Terrain Doodad Common (these are used by paint, sculpt, scatter, doodad)
    from .terrain.doodad import data as terrain_doodad_data
    from .terrain.doodad import builder as terrain_doodad_builder

    # Terrain Doodad Paint Layers
    from .terrain.doodad.paint import properties as terrain_doodad_paint_properties
    from .terrain.doodad.paint import operators as terrain_doodad_paint_operators

    # Terrain Doodad Sculpt Layers
    from .terrain.doodad.sculpt import builder as terrain_doodad_sculpt_builder
    from .terrain.doodad.sculpt import properties as terrain_doodad_sculpt_properties
    from .terrain.doodad.sculpt import operators as terrain_doodad_sculpt_operators

    # Terrain Doodad Scatter Layers
    from .terrain.doodad.scatter import builder as terrain_doodad_scatter_builder
    from .terrain.doodad.scatter import properties as terrain_doodad_scatter_properties
    from .terrain.doodad.scatter import operators as terrain_doodad_scatter_operators
    from .terrain import terrain_sample as terrain_sample

    # Terrain Doodad
    from .terrain.doodad import properties as terrain_doodad_properties
    from .terrain.doodad import operators as terrain_doodad_operators
    from .terrain.doodad import ui as terrain_doodad_ui

    # BSP
    from .bsp import data as bsp_data
    from .bsp import builder as bsp_builder
    from .bsp import tools as bsp_tools
    from .bsp import properties as bsp_properties
    from .bsp import operators as bsp_operators
    from .bsp import ui as bsp_ui

    # T3D
    from .t3d import data as t3d_data
    from .t3d import importer as t3d_importer
    from .t3d import writer as t3d_writer
    from .t3d import operators as t3d_operators

# Ensure the preferences class is registered with the correct package name.
bdk_preferences.BdkAddonPreferences.bl_idname = __package__


import bpy

classes = actor_properties.classes + \
          material_importer.classes + \
          material_operators.classes + \
          material_ui.classes + \
          projector_properties.classes + \
          projector_operators.classes + \
          projector_ui.classes + \
          fluid_surface_properties.classes + \
          fluid_surface_operators.classes + \
          fluid_surface_ui.classes + \
          terrain_properties.classes + \
          terrain_operators.classes + \
          terrain_ui.classes + \
          terrain_doodad_paint_properties.classes + \
          terrain_doodad_paint_operators.classes + \
          terrain_doodad_sculpt_properties.classes + \
          terrain_doodad_sculpt_operators.classes + \
          terrain_doodad_scatter_properties.classes + \
          terrain_doodad_scatter_operators.classes + \
          terrain_doodad_operators.classes + \
          terrain_doodad_properties.classes + \
          terrain_doodad_ui.classes + \
          bsp_properties.classes + \
          bsp_operators.classes + \
          bsp_ui.classes + \
          repository_properties.classes + \
          repository_operators.classes + \
          repository_ui.classes + \
          bdk_preferences.classes + \
          bdk_operators.classes + \
          bdk_ui.classes + \
          t3d_operators.classes

classes += bdk_properties.classes


def material_import_menu_func(self, _context: bpy.types.Context):
    self.layout.operator(material_importer.BDK_OT_material_import.bl_idname, text='Unreal Material (.props.txt)')


def bdk_add_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.menu(bdk_ui.BDK_MT_object_add_menu.bl_idname, text='BDK')


def bdk_select_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(bdk_operators.BDK_OT_select_all_of_active_class.bl_idname, text='Select All of Active Class', icon='RESTRICT_SELECT_OFF')


def bdk_object_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.menu(bdk_ui.BDK_MT_object_menu.bl_idname, text='BDK')


def bdk_t3d_copy_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(t3d_operators.BDK_OT_t3d_copy_to_clipboard.bl_idname, icon='COPYDOWN')


def bdk_asset_browser_import_data_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(bdk_operators.BDK_OT_asset_import_data_linked.bl_idname, icon='LINKED')


def bdk_terrain_export_func(self, _context: bpy.types.Context):
    self.layout.operator(terrain_operators.BDK_OT_terrain_info_export.bl_idname)


def bdk_t3d_import_func(self, _context: bpy.types.Context):
    self.layout.operator(t3d_operators.BDK_OT_t3d_import_from_file.bl_idname)

addon_keymaps = []


def clear_preferences_runtime_data():
    preferences = bpy.context.preferences.addons[__package__].preferences

    for repository in preferences.repositories:
        repository.runtime.has_been_scanned = False


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.bdk = PointerProperty(type=bdk_properties.BDK_PG_object)
    bpy.types.Material.bdk = PointerProperty(type=bdk_properties.BDK_PG_material)
    bpy.types.NodeTree.bdk = PointerProperty(type=bdk_properties.BDK_PG_node_tree)
    bpy.types.Scene.bdk = PointerProperty(type=bdk_properties.BDK_PG_scene)

    bpy.types.TOPBAR_MT_file_import.append(material_import_menu_func)

    bpy.types.TOPBAR_MT_file_export.append(bdk_terrain_export_func)

    bpy.types.VIEW3D_MT_add.append(bdk_add_menu_func)
    bpy.types.VIEW3D_MT_object.append(bdk_object_menu_func)

    bpy.types.VIEW3D_MT_select_object.append(bdk_select_menu_func)

    bpy.types.TOPBAR_MT_file_import.append(bdk_t3d_import_func)
    bpy.types.VIEW3D_MT_object_context_menu.append(bdk_t3d_copy_func)
    bpy.types.OUTLINER_MT_collection.append(bdk_t3d_copy_func)

    # Asset browser
    bpy.types.ASSETBROWSER_MT_context_menu.append(bdk_asset_browser_import_data_func)

    # Keymaps
    addon_keymaps.clear()
    window_manager = bpy.context.window_manager
    key_configuration = window_manager.keyconfigs.addon
    if key_configuration is not None:
        keymap = key_configuration.keymaps.new(name='3D View', space_type='VIEW_3D')
        addon_keymaps.append((keymap, keymap.keymap_items.new(bsp_operators.BDK_OT_bsp_build.bl_idname, 'B', 'PRESS', ctrl=True, shift=True)))
        addon_keymaps.append((keymap, keymap.keymap_items.new(bdk_operators.BDK_OT_toggle_level_visibility.bl_idname, 'L', 'PRESS', alt=True, shift=True)))

    clear_preferences_runtime_data()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Object.bdk
    del bpy.types.Material.bdk

    bpy.types.TOPBAR_MT_file_import.remove(material_import_menu_func)

    bpy.types.TOPBAR_MT_file_export.remove(bdk_terrain_export_func)

    bpy.types.VIEW3D_MT_add.remove(bdk_add_menu_func)
    bpy.types.VIEW3D_MT_object.remove(bdk_object_menu_func)
    bpy.types.VIEW3D_MT_select_object.remove(bdk_select_menu_func)

    # T3DMap Copy (doodad/collections)
    bpy.types.TOPBAR_MT_file_import.remove(bdk_t3d_import_func)
    bpy.types.VIEW3D_MT_object_context_menu.remove(bdk_t3d_copy_func)
    bpy.types.OUTLINER_MT_collection.remove(bdk_t3d_copy_func)

    # Asset browser
    bpy.types.ASSETBROWSER_MT_context_menu.remove(bdk_asset_browser_import_data_func)

    # Keymaps
    for keymap, item in addon_keymaps:
        keymap.keymap_items.remove(item)


if __name__ == '__main__':
    register()
