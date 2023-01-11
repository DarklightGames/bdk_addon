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

    importlib.reload(terrain_operators)
else:
    from .material import data as material_data
    from .material import reader as material_reader
    from .material import importer as material_importer

    from .terrain import operators as terrain_operators

import bpy


class BdkAddonPreferences(AddonPreferences):
    bl_idname = __name__

    build_path: StringProperty(subtype='DIR_PATH', name='Build Path')

    def draw(self, context: bpy.types.Context):
        self.layout.prop(self, 'build_path')


classes = material_importer.classes + terrain_operators.classes + (
    BdkAddonPreferences,
)


def material_import_menu_func(self, _context: bpy.types.Context):
    self.layout.operator(material_importer.BDK_OT_material_import.bl_idname, text='Unreal Material (.props.txt)')


def bdk_add_menu_func(self, _context: bpy.types.Context):
    self.layout.separator()
    self.layout.operator(terrain_operators.BDK_OT_TerrainInfoAdd.bl_idname, text='Terrain Info', icon='GRID')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(material_import_menu_func)

    # For now, put the add-terrain operator in the add menu
    bpy.types.VIEW3D_MT_add.append(bdk_add_menu_func)

    bpy.types.Object.terrain_info = PointerProperty(type=terrain_operators.BDK_PG_TerrainInfoPropertyGroup)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(material_import_menu_func)
    bpy.types.VIEW3D_MT_add.remove(bdk_add_menu_func)

    del bpy.types.Object.terrain_info


if __name__ == '__main__':
    register()
