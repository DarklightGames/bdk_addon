import bpy
from bpy.props import EnumProperty, BoolProperty
from bpy.types import UIList, Menu
from fnmatch import fnmatch

from .operators import BDK_OT_repository_delete, BDK_OT_repository_cache_invalidate, BDK_OT_repository_package_build, \
    BDK_OT_repository_purge_orphaned_assets
from .properties import repository_package_status_enum_items
from ...helpers import get_addon_preferences


def filter_packages(self, packages) -> list[int]:
    bitflag_filter_item = 1 << 30
    flt_flags = [bitflag_filter_item] * len(packages)

    if self.filter_name:
        # Filter name is non-empty.
        for i, package in enumerate(packages):
            if not fnmatch(package.path, f'*{self.filter_name}*'):
                flt_flags[i] &= ~bitflag_filter_item

    # Invert filter flags for all items.
    if not self.filter_up_to_date:
        for i, package in enumerate(packages):
            if package.status == 'UP_TO_DATE':
                flt_flags[i] &= ~bitflag_filter_item

    if not self.filter_excluded:
        for i, package in enumerate(packages):
            if package.is_excluded_by_rule:
                flt_flags[i] &= ~bitflag_filter_item

    return flt_flags


class BDK_UL_repository_packages(UIList):
    bl_idname = 'BDK_UL_repository_packages'

    filter_enabled: EnumProperty(
        name='Enabled',
        items=(
            ('ENABLED', 'Enabled', 'Show enabled packages'),
            ('DISABLED', 'Disabled', 'Show disabled packages'),
        ), options={'ENUM_FLAG'}, default={'ENABLED'}
    )
    filter_up_to_date: BoolProperty(name='Up to Date', default=False)
    filter_excluded: BoolProperty(name='Excluded', default=False, description='Show packages excluded by rules')
    use_filter_show: BoolProperty(default=True)

    def draw_filter(self, context, layout):
        col = layout.column()
        col.use_property_split = True
        col.prop(self, 'filter_name', text='Pattern')
        col.prop(self, 'filter_excluded', text='Show Excluded')
        col.prop(self, 'filter_up_to_date', text='Show Up-to-Date')
        row = col.row(align=True)
        row.prop(self, 'filter_enabled')

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, **kwargs):
        col = layout.column(align=True)

        row = col.row(align=True)
        row.label(text=item.path)

        col = layout.column(align=True)
        row = col.row(align=True)

        # Look up the description of the status enum item.
        col = row.column(align=True)
        col.enabled = False
        col.alignment = 'RIGHT'
        if item.is_excluded_by_rule:
            col.label(text='Excluded')
        else:
            status_enum_item = next((i for i in repository_package_status_enum_items if i[0] == item.status), None)
            if status_enum_item is not None:
                col.label(text=status_enum_item[1])

    def filter_items(self, context, data, property_):
        packages = getattr(data, property_)
        flt_flags = filter_packages(self, packages)
        flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(packages, 'path')
        return flt_flags, flt_neworder


class BDK_UL_repositories(UIList):
    bl_idname = 'BDK_UL_repositories'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, **kwargs):
        addon_prefs = get_addon_preferences(context)

        row = layout.row(align=True)
        row.prop(item, 'name', emboss=False, icon='DISK_DRIVE', text='')
        row = row.row()
        row.enabled = False
        row.alignment = 'RIGHT'
        if addon_prefs.default_repository_id == item.id:
            row.label(text='Default')
        if item.id == context.scene.bdk.repository_id:
            row.label(text='', icon='SCENE_DATA')


class BDK_MT_repository_special(Menu):
    bl_idname = 'BDK_MT_repository_special'
    bl_label = 'Repository Specials'

    def draw(self, context):
        layout = self.layout
        layout.operator(BDK_OT_repository_delete.bl_idname, icon='TRASH')
        layout.operator_menu_enum(BDK_OT_repository_cache_invalidate.bl_idname, 'mode', icon='FILE_REFRESH')
        layout.operator(BDK_OT_repository_purge_orphaned_assets.bl_idname, icon='X')
        layout.separator()
        layout.operator(BDK_OT_repository_package_build.bl_idname, text='Build Selected Package', icon='BLENDER')


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


class BDK_UL_repository_rules(UIList):
    bl_idname = 'BDK_UL_repository_rules'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, **kwargs):
        row = layout.row(align=True)
        row_left = row.row(align=True)
        row_left.enabled = False
        row_left.prop(item, 'type', text='', emboss=False)
        row_left.prop(item, 'pattern', text='', emboss=False)
        row_right = row.column(align=True)
        row_right.alignment = 'RIGHT'
        row_right.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_repository_orphaned_assets(UIList):
    bl_idname = 'BDK_UL_repository_orphaned_assets'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, **kwargs):
        layout.label(text=item.file_name)


classes = (
    BDK_UL_repositories,
    BDK_UL_repository_packages,
    BDK_MT_repository_special,
    BDK_MT_repository_add,
    BDK_MT_repository_remove,
    BDK_UL_repository_rules,
    BDK_UL_repository_orphaned_assets,
)
