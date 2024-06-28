from datetime import datetime
from pathlib import Path

from bpy.types import AddonPreferences
from bpy.props import CollectionProperty, IntProperty, BoolProperty

from .repository.properties import BDK_PG_repository
from .repository.ui import BDK_UL_repositories, BDK_UL_repository_packages, BDK_MT_repository_special, \
    BDK_MT_repository_add, BDK_MT_repository_remove, BDK_UL_repository_rules
from ..bdk.operators import BDK_OT_scene_repository_set
from ..bdk.repository.operators import BDK_OT_repository_set_default, BDK_OT_repository_scan, \
    BDK_OT_repository_build_asset_library, BDK_OT_repository_package_cache_invalidate, BDK_OT_repository_package_build, \
    BDK_OT_repository_rule_add, BDK_OT_repository_rule_remove

from bpy.props import StringProperty
from bpy.types import Operator, Context

from ..data import UReference
from ..helpers import get_addon_preferences
from ..material.cache import MaterialCache


class BdkAddonPreferences(AddonPreferences):
    # NOTE: bl_idname is overridden in the __init__.py file.
    # This is because it has access to the correct __package__ value.
    bl_idname = 'bdk_addon'

    repositories: CollectionProperty(type=BDK_PG_repository)
    repositories_index: IntProperty()
    default_repository_id: StringProperty(name='Default Repository ID', options={'HIDDEN'})

    developer_extras: BoolProperty(name='Developer Extras', default=False,
                                   description='Enable developer extras such as debug panels and operators')

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, 'developer_extras')

        repositories_header, repositories_panel = layout.panel('Repositories', default_closed=False)
        repositories_header.label(text='Repositories')

        if repositories_panel is not None:
            row = repositories_panel.row()
            row.column().template_list(BDK_UL_repositories.bl_idname, '', self, 'repositories', self,
                                       'repositories_index', rows=3)
            col = row.column(align=True)
            col.menu(BDK_MT_repository_add.bl_idname, icon='ADD', text='')
            col.menu(BDK_MT_repository_remove.bl_idname, icon='REMOVE', text='')
            col.separator()
            col.operator(BDK_OT_scene_repository_set.bl_idname, icon='SCENE_DATA', text='')
            col.operator(BDK_OT_repository_set_default.bl_idname, icon='RESTRICT_VIEW_OFF', text='')

            repository = self.repositories[
                self.repositories_index] if self.repositories_index >= 0 and self.repositories_index < len(
                self.repositories) else None

            if repository is not None:
                # If we have not yet scanned the repository, we need to present the user with a button to scan it.
                if not repository.runtime.has_been_scanned:
                    flow = repositories_panel.grid_flow(columns=1, row_major=True)
                    row = flow.row(align=True)
                    row.alignment = 'CENTER'
                    row.enabled = False
                    row.label(text='Packages have not been scanned.')
                    row = flow.row(align=True)
                    row.alignment = 'CENTER'
                    col = row.column()
                    col.enabled = False
                    col.label(text='Click the')
                    row.operator(BDK_OT_repository_scan.bl_idname, icon='FILE_REFRESH', text='Scan')
                    col = row.column()
                    col.enabled = False
                    col.label(text='button to scan the repository.')

                else:
                    main_row = repositories_panel.row()

                    row_left = main_row.column()
                    row_left.alignment = 'LEFT'

                    row = row_left.row()
                    row.alignment = 'LEFT'
                    if repository.runtime.disabled_package_count > 0:
                        row.label(text=f'{repository.runtime.disabled_package_count} Disabled', icon='CHECKBOX_DEHLT')
                    if repository.runtime.need_export_package_count > 0:
                        row.label(text=f'{repository.runtime.need_export_package_count} Pending Export', icon='EXPORT')
                    if repository.runtime.need_build_package_count > 0:
                        row.label(text=f'{repository.runtime.need_build_package_count} Pending Build', icon='MOD_BUILD')
                    if repository.runtime.up_to_date_package_count > 0:
                        row.label(text=f'{repository.runtime.up_to_date_package_count} Up to Date', icon='CHECKMARK')

                    main_row.column()

                    row = main_row.row()
                    row.alignment = 'RIGHT'
                    row.operator(BDK_OT_repository_scan.bl_idname, icon='FILE_REFRESH', text='Scan')
                    row.operator(BDK_OT_repository_build_asset_library.bl_idname, icon='BLENDER', text='Build Assets')

                    row = repositories_panel.row()
                    row.column().template_list(BDK_UL_repository_packages.bl_idname, '',
                                               repository.runtime, 'packages',
                                               repository.runtime, 'packages_index',
                                               rows=5)

                    col = row.column(align=True)

                    if self.developer_extras:
                        op = col.operator(BDK_OT_repository_package_cache_invalidate.bl_idname, icon='ERROR', text='')
                        op.index = repository.runtime.packages_index
                        col.separator()

                    col.menu(BDK_MT_repository_special.bl_idname, icon='DOWNARROW_HLT', text='')

                rules_header, rules_panel = repositories_panel.panel('Rules', default_closed=True)
                rules_header.label(text='Rules')

                if rules_panel is not None:
                    row = rules_panel.row()
                    row.template_list(BDK_UL_repository_rules.bl_idname, '', repository, 'rules', repository, 'rules_index', rows=3)
                    col = row.column(align=True)
                    col.operator(BDK_OT_repository_rule_add.bl_idname, icon='ADD', text='')
                    col.operator(BDK_OT_repository_rule_remove.bl_idname, icon='REMOVE', text='')

                paths_header, paths_panel = repositories_panel.panel('Paths', default_closed=True)
                paths_header.label(text='Paths')

                if paths_panel is not None:
                    col = repositories_panel.column()
                    col.enabled = False
                    col.use_property_split = True
                    col.prop(repository, 'id', emboss=False)
                    col.prop(repository, 'game_directory')
                    if repository.mod:
                        col.prop(repository, 'mod', emboss=False)
                    col.prop(repository, 'cache_directory')


class BDK_OT_debug_material_cache_lookup(Operator):
    bl_idname = 'bdk.debug_material_cache_lookup'
    bl_label = 'Test Material Cache Lookup'
    bl_description = 'Test the material cache lookup'
    bl_options = {'INTERNAL'}

    reference: StringProperty(name='Reference', default='')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        material_cache = MaterialCache(Path(repository.cache_directory) / repository.id)
        reference = UReference.from_string(self.reference)
        path = material_cache.resolve_path_for_reference(reference)

        if path is None:
            self.report({'ERROR'}, f'Failed to resolve path for reference: {self.reference}')
            return {'CANCELLED'}

        self.report({'INFO'}, f'Resolved path for reference: {self.reference} to {path}')

        return {'FINISHED'}


classes = (
    BDK_OT_debug_material_cache_lookup,
    BdkAddonPreferences,
)
