from bpy.types import UIList, Menu

from .properties import repository_package_status_enum_items


class BDK_UL_repository_packages(UIList):
    bl_idname = 'BDK_UL_repository_packages'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        col = layout.column(align=True)
        col.label(text=item.path, icon='PACKAGE')

        col = layout.column(align=True)
        col.alignment = 'RIGHT'

        # Look up the description of the status enum item.
        status_enum_item = next((i for i in repository_package_status_enum_items if i[0] == item.status), None)
        if status_enum_item is not None:
            col.label(text=status_enum_item[1], icon=status_enum_item[3])


class BDK_UL_repositories(UIList):
    bl_idname = 'BDK_UL_repositories'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, 'name', emboss=False, icon='DISK_DRIVE', text='')


class BDK_MT_repository_special(Menu):
    bl_idname = 'BDK_MT_repository_special'
    bl_label = 'Repository Specials'

    def draw(self, context):
        layout = self.layout
        layout.operator('bdk.repository_cache_delete', icon='REMOVE')
        layout.operator('bdk.repository_cache_invalidate', icon='FILE_REFRESH')
        layout.separator()
        layout.operator('bdk.repository_build_dependency_graph', icon='MODIFIER')



class BDK_MT_repository_add(Menu):
    bl_idname = 'BDK_MT_repository_add'
    bl_label = 'Add Repository'

    def draw(self, context):
        layout = self.layout
        layout.operator('bdk.repository_create', icon='ADD')
        layout.operator('bdk.repository_link', icon='LINKED')


class BDK_MT_repository_remove(Menu):
    bl_idname = 'BDK_MT_repository_remove'
    bl_label = 'Remove Repository'
    def draw(self, context):
        layout = self.layout
        layout.operator('bdk.repository_unlink', icon='UNLINKED')
        layout.operator('bdk.repository_delete', icon='TRASH')




classes = (
    BDK_UL_repositories,
    BDK_UL_repository_packages,
    BDK_MT_repository_special,
    BDK_MT_repository_add,
    BDK_MT_repository_remove,
)
