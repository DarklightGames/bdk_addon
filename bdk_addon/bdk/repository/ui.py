import bpy
from bpy.props import EnumProperty
from bpy.types import UIList, Menu
from fnmatch import fnmatch

from .properties import repository_package_status_enum_items, filter_repository_package_status_enum_items


def filter_packages(self, packages) -> list[int]:
    bitflag_filter_item = 1 << 30
    flt_flags = [bitflag_filter_item] * len(packages)

    if self.filter_name:
        # Filter name is non-empty.
        for i, package in enumerate(packages):
            if not fnmatch(package.path, f'*{self.filter_name}*'):
                flt_flags[i] &= ~bitflag_filter_item

    # Invert filter flags for all items.
    if self.filter_status != 'ALL':
        for i, sequence in enumerate(packages):
            if sequence.status != self.filter_status:
                flt_flags[i] &= ~bitflag_filter_item

    match self.filter_is_enabled:
        case 'ENABLED':
            for i, sequence in enumerate(packages):
                if not sequence.is_enabled:
                    flt_flags[i] &= ~bitflag_filter_item
        case 'DISABLED':
            for i, sequence in enumerate(packages):
                if sequence.is_enabled:
                    flt_flags[i] &= ~bitflag_filter_item
        case 'ALL':
            pass

    #
    # if not pg.sequence_filter_asset:
    #     for i, sequence in enumerate(packages):
    #         if hasattr(sequence, 'action') and sequence.action is not None and sequence.action.asset_data is not None:
    #             flt_flags[i] &= ~bitflag_filter_item

    return flt_flags


class BDK_UL_repository_packages(UIList):
    bl_idname = 'BDK_UL_repository_packages'

    filter_status: EnumProperty(
        name='Status',
        items=filter_repository_package_status_enum_items,
        default='ALL',
    )
    filter_is_enabled: EnumProperty(
        name='Enabled',
        items=(
            ('ALL', 'All', 'Show all packages'),
            ('ENABLED', 'Enabled', 'Show only enabled packages'),
            ('DISABLED', 'Disabled', 'Show only disabled packages'),
        ),
    )

    def draw_filter(self, context, layout):
        row = layout.row()
        row.prop(self, 'filter_name', text='')
        row.prop(self, 'use_filter_invert', text='', icon='ARROW_LEFTRIGHT')
        row = layout.row()
        row.prop(self, 'filter_status', text='Status')
        row.prop(self, 'filter_is_enabled', text='Enabled', icon='CHECKBOX_HLT')

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        col = layout.column(align=True)

        row = col.row(align=True)
        row.label(text=item.path)

        col = layout.column(align=True)
        row = col.row(align=True)

        # Look up the description of the status enum item.
        col = row.column(align=True)
        col.enabled = False
        col.alignment = 'RIGHT'
        if not item.is_enabled:
            col.label(text='Disabled')
        else:
            status_enum_item = next((i for i in repository_package_status_enum_items if i[0] == item.status), None)
            if status_enum_item is not None:
                col.label(text=status_enum_item[1])

        row.prop(item, 'is_enabled', text='', icon='CHECKBOX_HLT' if item.is_enabled else 'CHECKBOX_DEHLT', emboss=False)

    # def draw_filter(self, context, layout):
    #     pg = getattr(context.scene, 'psa_import')
    #     row = layout.row()
    #     sub_row = row.row(align=True)
    #     sub_row.prop(pg, 'sequence_filter_name', text='')
    #     sub_row.prop(pg, 'sequence_use_filter_invert', text='', icon='ARROW_LEFTRIGHT')
    #     sub_row.prop(pg, 'sequence_use_filter_regex', text='', icon='SORTBYEXT')
    #     sub_row.prop(pg, 'sequence_filter_is_selected', text='', icon='CHECKBOX_HLT')

    def filter_items(self, context, data, property_):
        packages = getattr(data, property_)
        flt_flags = filter_packages(self, packages)
        flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(packages, 'path')
        return flt_flags, flt_neworder


class BDK_UL_repositories(UIList):
    bl_idname = 'BDK_UL_repositories'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, 'name', emboss=False, icon='DISK_DRIVE', text='')
        row = row.row()
        row.alignment = 'RIGHT'
        if item.id == context.scene.bdk.repository_id:
            row.label(text='', icon='SCENE_DATA')


class BDK_MT_repository_special(Menu):
    bl_idname = 'BDK_MT_repository_special'
    bl_label = 'Repository Specials'

    def draw(self, context):
        layout = self.layout
        layout.operator('bdk.repository_cache_delete', icon='TRASH')
        layout.operator('bdk.repository_cache_invalidate', icon='FILE_REFRESH')
        layout.separator()
        layout.operator('bdk.repository_packages_set_enabled_by_pattern')



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
