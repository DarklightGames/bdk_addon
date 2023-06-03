from bpy.types import AddonPreferences, Context
from bpy.props import StringProperty, BoolProperty
from pkg_resources import DistributionNotFound, get_distribution
from .operators import BDK_OT_install_dependencies


class BdkAddonPreferences(AddonPreferences):
    bl_idname = 'bdk_addon'

    build_path: StringProperty(subtype='DIR_PATH', name='Build Path')
    developer_extras: BoolProperty(name='Developer Extras', default=False,
                                   description='Enable developer extras such as debug panels and operators.')

    def draw(self, _: Context):
        self.layout.prop(self, 'developer_extras')
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
    BdkAddonPreferences,
)
