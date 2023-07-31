from bpy.types import AddonPreferences, Context, PropertyGroup, UIList, Operator, Event
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty, EnumProperty
from pkg_resources import DistributionNotFound, get_distribution
from .operators import BDK_OT_install_dependencies


class BDK_UL_build_paths(UIList):
    bl_idname = 'BDK_UL_build_paths'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, 'path', text='', emboss=False)
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BdkBuildPathPropertyGroup(PropertyGroup):
    path: StringProperty(name='Path', default='', subtype='DIR_PATH')
    mute: BoolProperty(name='Mute', default=False)


class BDK_OT_build_path_add(Operator):
    bl_idname = 'bdk.build_path_add'
    bl_label = 'Add Build Path'
    bl_description = 'Add a build path to the list'

    directory: StringProperty(name='Directory')
    filename_ext: StringProperty(default='.', options={'HIDDEN'})
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})

    def invoke(self, context: Context, event: Event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        addon_prefs = context.preferences.addons['bdk_addon'].preferences
        build_path = addon_prefs.build_paths.add()
        build_path.path = self.directory
        addon_prefs.build_paths_index = len(addon_prefs.build_paths) - 1
        return {'FINISHED'}


# TODO: in future a "Game Type" property would be preferable!

class BDK_OT_build_path_remove(Operator):
    bl_idname = 'bdk.build_path_remove'
    bl_label = 'Remove Build Path'
    bl_description = 'Remove the selected build path from the list'

    def execute(self, context):
        addon_prefs = context.preferences.addons['bdk_addon'].preferences
        addon_prefs.build_paths.remove(addon_prefs.build_paths_index)
        addon_prefs.build_paths_index = min(addon_prefs.build_paths_index, len(addon_prefs.build_paths) - 1)
        return {'FINISHED'}


class BDK_OT_build_path_move(Operator):
    bl_idname = 'bdk.build_path_move'
    bl_label = 'Move Build Path'
    bl_description = 'Move the selected build path up or down in the list'

    direction: EnumProperty(name='Direction', items=(('UP', 'Up', ''), ('DOWN', 'Down', '')))

    def execute(self, context):
        preferences = context.preferences.addons['bdk_addon'].preferences

        if self.direction == 'UP':
            preferences.build_paths.move(preferences.build_paths_index, preferences.build_paths_index - 1)
            preferences.build_paths_index -= 1
        elif self.direction == 'DOWN':
            preferences.build_paths.move(preferences.build_paths_index, preferences.build_paths_index + 1)
            preferences.build_paths_index += 1

        return {'FINISHED'}


class BdkAddonPreferences(AddonPreferences):
    bl_idname = 'bdk_addon'

    build_paths: CollectionProperty(type=BdkBuildPathPropertyGroup)
    build_paths_index: IntProperty(name='Build Paths Index', default=0)
    developer_extras: BoolProperty(name='Developer Extras', default=False,
                                   description='Enable developer extras such as debug panels and operators')

    def draw(self, _: Context):
        self.layout.prop(self, 'developer_extras')

        self.layout.label(text='Build Paths')
        row = self.layout.row()
        row.column().template_list(BDK_UL_build_paths.bl_idname, '', self, 'build_paths', self, 'build_paths_index', rows=3)
        col = row.column(align=True)
        col.operator('bdk.build_path_add', icon='ADD', text='')
        col.operator('bdk.build_path_remove', icon='REMOVE', text='')
        col.separator()
        col.operator('bdk.build_path_move', icon='TRIA_UP', text='').direction = 'UP'
        col.operator('bdk.build_path_move', icon='TRIA_DOWN', text='').direction = 'DOWN'

        self.layout.prop(self, 'build_path')

        # TODO: parse the requirements.txt
        required_packages = ['t3dpy']

        # Dependencies.
        has_uninstalled_dependencies = False
        box = self.layout.box()
        box.label(text='Dependencies', icon='SCRIPTPLUGINS')
        for package in required_packages:
            try:
                dist = get_distribution(package)
                box.label(text=f'{package} ({dist.version})', icon='CHECKMARK')
            except DistributionNotFound as e:
                box.label(text=package, icon='X')
                has_uninstalled_dependencies = True

        if has_uninstalled_dependencies:
            box.operator(BDK_OT_install_dependencies.bl_idname)
        else:
            box.label(text='All dependencies are installed')
            operator = box.operator(BDK_OT_install_dependencies.bl_idname, text='Reinstall')
            operator.uninstall = True


classes = (
    BdkBuildPathPropertyGroup,
    BDK_UL_build_paths,
    BDK_OT_build_path_add,
    BDK_OT_build_path_move,
    BDK_OT_build_path_remove,
    BdkAddonPreferences,
)
