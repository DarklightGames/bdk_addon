bl_info = {
    "name": "Unreal Material Importer",
    "author": "Colin Basnett",
    "version": (0, 1, 0),
    "blender": (3, 4, 0),
    "location": "File > Import > Unreal Material (.props.txt)",
    "description": "Unreal Material Import (.props.txt)",
    "warning": "",
    "doc_url": "https://github.com/DarklightGames/io_import_umaterial",
    "tracker_url": "https://github.com/DarklightGames/io_import_umaterial/issues",
    "category": "Import-Export"
}

if 'bpy' in locals():
    import importlib

    importlib.reload(umaterial_data)
    importlib.reload(umaterial_reader)
    importlib.reload(umaterial_importer)
    pass
else:
    from . import data as umaterial_data
    from . import reader as umaterial_reader
    from . import importer as umaterial_importer

import bpy

classes = umaterial_importer.classes


def umaterial_import_menu_func(self, _context: bpy.types.Context):
    self.layout.operator(umaterial_importer.UMATERIAL_OT_import.bl_idname, text='Unreal Material (.props.txt)')
    pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(umaterial_import_menu_func)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(umaterial_import_menu_func)


if __name__ == '__main__':
    register()
