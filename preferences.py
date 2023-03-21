from bpy.types import AddonPreferences, Context, Operator
from bpy.props import StringProperty, BoolProperty
import subprocess
from pkg_resources import DistributionNotFound, get_distribution
import sys


class BDK_OT_InstallDependencies(Operator):
    bl_idname = 'bdk.install_dependencies'
    bl_label = 'Install Dependencies'

    uninstall: BoolProperty(name='Uninstall', default=False)

    def execute(self, context):
        # Ensure PIP is installed.
        args = [sys.executable, '-m', 'ensurepip', '--upgrade']
        completed_process = subprocess.run(args)
        if completed_process.returncode != 0:
            self.report({'ERROR'}, 'An error occurred while installing PIP.')
            return {'CANCELLED'}

        # Install our requirements using PIP. TODO: use a requirements.txt file
        if self.uninstall:
            args = [sys.executable, '-m', 'pip', 'uninstall', 't3dpy', '-y']
            completed_process = subprocess.run(args)
            if completed_process.returncode != 0:
                self.report({'ERROR'}, 'An error occurred while uninstalling t3dpy.')
                return {'CANCELLED'}

        args = [sys.executable, '-m', 'pip', 'install', 't3dpy']
        completed_process = subprocess.run(args)
        if completed_process.returncode != 0:
            self.report({'ERROR'}, 'An error occurred while installing t3dpy.')
            return {'CANCELLED'}

        return {'FINISHED'}


class BdkAddonPreferences(AddonPreferences):
    bl_idname = 'bdk_addon'

    build_path: StringProperty(subtype='DIR_PATH', name='Build Path')

    def draw(self, _: Context):
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
            box.operator(BDK_OT_InstallDependencies.bl_idname)
        else:
            box.label(text='All dependencies are installed')
            operator = box.operator(BDK_OT_InstallDependencies.bl_idname, text='Reinstall')
            operator.uninstall = True



classes = (
    BdkAddonPreferences,
    BDK_OT_InstallDependencies
)
