from bpy.props import PointerProperty

bl_info = {
    "name": "Blender Development Kit (BDK)",
    "author": "Colin Basnett",
    "version": (0, 1, 0),
    "blender": (3, 5, 0),
    "description": "Blender Development Kit (BDK), a toolset for authoring levels for Unreal 1 & 2",
    "warning": "",
    "doc_url": "https://github.com/DarklightGames/bdk_addon",
    "tracker_url": "https://github.com/DarklightGames/bdk_addon/issues",
    "category": "Development"
}

if 'bpy' in locals():
    import importlib

    importlib.reload(constants)
    importlib.reload(property_group_helpers)
    importlib.reload(node_helpers)

    importlib.reload(bdk_helpers)
    importlib.reload(bdk_preferences)
    importlib.reload(bdk_operators)

    importlib.reload(material_data)
    importlib.reload(material_reader)
    importlib.reload(material_importer)
    importlib.reload(material_operators)
    importlib.reload(material_ui)

    importlib.reload(projector_builder)
    importlib.reload(projector_operators)

    importlib.reload(fluid_surface_builder)
    importlib.reload(fluid_surface_operators)

    importlib.reload(terrain_layers)
    importlib.reload(terrain_deco)
    importlib.reload(terrain_g16)
    importlib.reload(terrain_ui)
    importlib.reload(terrain_properties)
    importlib.reload(terrain_builder)
    importlib.reload(terrain_operators)
    importlib.reload(terrain_exporter)

    importlib.reload(terrain_doodad_scatter_builder)
    importlib.reload(terrain_doodad_sculpt_builder)
    importlib.reload(terrain_doodad_sculpt_properties)
    importlib.reload(terrain_doodad_sculpt_operators)

    importlib.reload(terrain_doodad_data)
    importlib.reload(terrain_doodad_builder)
    importlib.reload(terrain_doodad_properties)
    importlib.reload(terrain_doodad_operators)
    importlib.reload(terrain_doodad_ui)

    if bdk_helpers.are_bdk_dependencies_installed():
        importlib.reload(t3d_data)
        importlib.reload(t3d_operators)
        importlib.reload(t3d_importer)
        importlib.reload(t3d_writer)
        importlib.reload(t3d_ui)

        importlib.reload(bsp_builder)
        importlib.reload(bsp_properties)
        importlib.reload(bsp_operators)
        importlib.reload(bsp_ui)

    importlib.reload(asset_browser_operators)
    importlib.reload(bdk_properties)
    importlib.reload(bdk_ui)
else:
    from . import constants as constants
    from . import property_group_helpers as property_group_helpers
    from . import node_helpers as node_helpers
    from . import helpers as bdk_helpers
    from .bdk import operators as bdk_operators
    from .bdk import properties as bdk_properties
    from .bdk import ui as bdk_ui
    from .bdk import preferences as bdk_preferences

    # Material
    from .material import importer as material_importer
    from .material import operators as material_operators
    from .material import data as material_data
    from .material import reader as material_reader
    from .material import ui as material_ui

    # Projector
    from .projector import builder as projector_builder
    from .projector import operators as projector_operators

    # Fluid Surface
    from .fluid_surface import builder as fluid_surface_builder
    from .fluid_surface import operators as fluid_surface_operators

    # Terrain
    from .terrain import builder as terrain_builder
    from .terrain import exporter as terrain_exporter
    from .terrain import layers as terrain_layers  # TODO: rename to paint??
    from .terrain import deco as terrain_deco
    from .terrain import g16 as terrain_g16
    from .terrain import properties as terrain_properties
    from .terrain import operators as terrain_operators
    from .terrain import ui as terrain_ui

    # Terrain Doodad Sculpt Layers
    from .terrain.doodad.sculpt import builder as terrain_doodad_sculpt_builder
    from .terrain.doodad.sculpt import properties as terrain_doodad_sculpt_properties
    from .terrain.doodad.sculpt import operators as terrain_doodad_sculpt_operators

    # Terrain Doodad Scatter Layers
    from .terrain.doodad.scatter import builder as terrain_doodad_scatter_builder

    # Terrain Doodad
    from .terrain.doodad import data as terrain_doodad_data
    from .terrain.doodad import builder as terrain_doodad_builder
    from .terrain.doodad import kernel as terrain_doodad_kernel
    from .terrain.doodad import operators as terrain_doodad_operators
    from .terrain.doodad import properties as terrain_doodad_properties
    from .terrain.doodad import ui as terrain_doodad_ui

    if bdk_helpers.are_bdk_dependencies_installed():
        # T3D
        from .t3d import data as t3d_data
        from .t3d import importer as t3d_importer
        from .t3d import writer as t3d_writer
        from .t3d import ui as t3d_ui
        from .t3d import operators as t3d_operators

        # BSP
        from .bsp import builder as bsp_builder
        from .bsp import properties as bsp_properties
        from .bsp import operators as bsp_operators
        from .bsp import ui as bsp_ui

    from .asset_browser import operators as asset_browser_operators


import bpy


classes = material_importer.classes + \
          material_operators.classes + \
          material_ui.classes + \
          projector_operators.classes + \
          fluid_surface_operators.classes + \
          terrain_properties.classes + \
          terrain_operators.classes + \
          terrain_ui.classes + \
          terrain_doodad_sculpt_properties.classes + \
          terrain_doodad_sculpt_operators.classes + \
          terrain_doodad_operators.classes + \
          terrain_doodad_properties.classes + \
          terrain_doodad_ui.classes + \
          asset_browser_operators.classes + \
          bdk_preferences.classes + \
          bdk_operators.classes + \
          bdk_ui.classes

if bdk_helpers.are_bdk_dependencies_installed():
    classes += t3d_ui.classes + \
               t3d_operators.classes + \
               bsp_properties.classes + \
               bsp_operators.classes + \
               bsp_ui.classes

classes += bdk_properties.classes


def material_import_menu_func(self, _context: bpy.types.Context):
    self.layout.operator(material_importer.BDK_OT_material_import.bl_idname, text='Unreal Material (.props.txt)')


def bdk_add_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.menu(bdk_ui.BDK_MT_object_add_menu.bl_idname, text='BDK', icon='BDK_LOGO')


def bdk_select_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(bdk_operators.BDK_OT_select_all_of_active_class.bl_idname, text='Select All of Active Class', icon='RESTRICT_SELECT_OFF')


def bdk_object_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(terrain_doodad_operators.BDK_OT_convert_to_terrain_doodad.bl_idname)


def bdk_t3d_copy_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(t3d_operators.BDK_OT_t3d_copy_to_clipboard.bl_idname, icon='COPYDOWN')


def bdk_asset_browser_import_data_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(asset_browser_operators.BDK_OT_asset_import_data_linked.bl_idname, icon='LINKED')


def bdk_terrain_export_func(self, _context: bpy.types.Context):
    self.layout.operator(terrain_operators.BDK_OT_terrain_info_export.bl_idname)


def bdk_t3d_import_func(self, _context: bpy.types.Context):
    self.layout.operator(t3d_operators.BDK_OT_t3d_import_from_file.bl_idname)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.bdk = PointerProperty(type=bdk_properties.BDK_PG_object)
    bpy.types.Material.bdk = PointerProperty(type=bdk_properties.BDK_PG_material)
    bpy.types.NodeTree.bdk = PointerProperty(type=bdk_properties.BDK_PG_node_tree)

    bpy.types.TOPBAR_MT_file_import.append(material_import_menu_func)

    bpy.types.TOPBAR_MT_file_export.append(bdk_terrain_export_func)

    bpy.types.VIEW3D_MT_add.append(bdk_add_menu_func)
    bpy.types.VIEW3D_MT_object.append(bdk_object_menu_func)

    bpy.types.VIEW3D_MT_select_object.append(bdk_select_menu_func)

    if bdk_helpers.are_bdk_dependencies_installed():
        bpy.types.TOPBAR_MT_file_import.append(bdk_t3d_import_func)
        bpy.types.VIEW3D_MT_object_context_menu.append(bdk_t3d_copy_func)
        bpy.types.OUTLINER_MT_collection.append(bdk_t3d_copy_func)

    # Asset browser
    bpy.types.ASSETBROWSER_MT_context_menu.append(bdk_asset_browser_import_data_func)


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
    if bdk_helpers.are_bdk_dependencies_installed():
        bpy.types.TOPBAR_MT_file_import.remove(bdk_t3d_import_func)
        bpy.types.VIEW3D_MT_object_context_menu.remove(bdk_t3d_copy_func)
        bpy.types.OUTLINER_MT_collection.remove(bdk_t3d_copy_func)

    # Asset browser
    bpy.types.ASSETBROWSER_MT_context_menu.remove(bdk_asset_browser_import_data_func)


if __name__ == '__main__':
    register()
