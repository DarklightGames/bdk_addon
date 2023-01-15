from bpy.props import PointerProperty, StringProperty
from bpy_types import AddonPreferences

bl_info = {
    "name": "Blender Development Kit (BDK)",
    "author": "Colin Basnett",
    "version": (0, 1, 0),
    "blender": (3, 5, 0),
    "description": "Blender Development Kit (BDK), a toolset for authoring levels for Unreal 1 & 2",
    "warning": "",
    "doc_url": "https://github.com/DarklightGames/bdk-addon",
    "tracker_url": "https://github.com/DarklightGames/bdk-addon",
    "category": "Development"
}

if 'bpy' in locals():
    import importlib

    importlib.reload(material_data)
    importlib.reload(material_reader)
    importlib.reload(material_importer)

    importlib.reload(g16)
    importlib.reload(terrain_types)
    importlib.reload(terrain_builder)
    importlib.reload(terrain_operators)
    importlib.reload(terrain_exporter)

    importlib.reload(bdk_panel)

    importlib.reload(t3d_data)
    importlib.reload(t3d_operators)
else:
    from .material import data as material_data
    from .material import reader as material_reader
    from .material import importer as material_importer

    from .terrain import types as terrain_types
    from .terrain import builder as terrain_builder
    from .terrain import operators as terrain_operators
    from .terrain import exporter as terrain_exporter
    from .terrain import g16

    from .panel import panel as bdk_panel

    from .t3d import data as t3d_data
    from .t3d import operators as t3d_operators


import bpy


class BdkAddonPreferences(AddonPreferences):
    bl_idname = __name__

    build_path: StringProperty(subtype='DIR_PATH', name='Build Path')

    def draw(self, _: bpy.types.Context):
        self.layout.prop(self, 'build_path')


classes = material_importer.classes + \
          terrain_types.classes + \
          terrain_operators.classes + \
          terrain_exporter.classes + \
          bdk_panel.classes + \
          t3d_operators.classes + \
          (BdkAddonPreferences,)


def material_import_menu_func(self, _context: bpy.types.Context):
    self.layout.operator(material_importer.BDK_OT_material_import.bl_idname, text='Unreal Material (.props.txt)')


def bdk_add_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(terrain_operators.BDK_OT_TerrainInfoAdd.bl_idname, text='Terrain Info', icon='GRID')


def bdk_t3d_copy_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(t3d_operators.BDK_OP_CopyObject.bl_idname, icon='COPYDOWN')


def bdk_t3d_copy_asset_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(t3d_operators.BDK_OP_CopyAsset.bl_idname, icon='COPYDOWN')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.terrain_info = PointerProperty(type=terrain_operators.BDK_PG_TerrainInfoPropertyGroup)

    bpy.types.TOPBAR_MT_file_import.append(material_import_menu_func)

    # For now, put the add-terrain operator in the add menu
    bpy.types.VIEW3D_MT_add.append(bdk_add_menu_func)

    # T3D Copy (objects/collections)
    bpy.types.VIEW3D_MT_object_context_menu.append(bdk_t3d_copy_func)
    bpy.types.OUTLINER_MT_collection.append(bdk_t3d_copy_func)

    # T3D Copy (assets)
    bpy.types.ASSETBROWSER_MT_context_menu.append(bdk_t3d_copy_asset_func)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Object.terrain_info

    bpy.types.TOPBAR_MT_file_import.remove(material_import_menu_func)
    bpy.types.VIEW3D_MT_add.remove(bdk_add_menu_func)

    # T3D Copy (objects/collections)
    bpy.types.VIEW3D_MT_object_context_menu.remove(bdk_t3d_copy_func)
    bpy.types.OUTLINER_MT_collection.remove(bdk_t3d_copy_func)

    # T3D Copy (assets)
    bpy.types.ASSETBROWSER_MT_context_menu.remove(bdk_t3d_copy_asset_func)


if __name__ == '__main__':
    register()
