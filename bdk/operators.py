from bpy.types import Operator
from bpy.props import BoolProperty

import subprocess
import sys

from ..helpers import guess_package_reference_from_names, load_bdk_material


class BDK_OT_install_dependencies(Operator):
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


# TODO: figure out a better name for this operator
class BDK_OT_select_all_of_active_class(Operator):
    bl_idname = 'bdk.select_all_of_active_class'
    bl_label = 'Select All Of Active Class'
    bl_description = 'Select all static mesh actors in the scene'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Return false if no objects are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No objects selected')
            return False
        # Return false if the active object does not have a class.
        if 'Class' not in context.object:
            cls.poll_message_set('Active object does not have a class')
            return False
        return True

    def execute(self, context):
        # Get the class of the active object.
        actor_class = context.object['Class']
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.get('Class', None) == actor_class:
                obj.select_set(True)
        return {'FINISHED'}


class BDK_OT_fix_bsp_import_materials(Operator):
    bl_idname = 'bdk.fix_bsp_import_materials'
    bl_label = 'Fix BSP Import Materials'
    bl_description = 'Fix materials of BSP imported from OBJ files from the Unreal SDK'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Return true if the active object is a mesh.
        if context.object is None:
            cls.poll_message_set('No active object')
            return False
        if context.object.type != 'MESH':
            cls.poll_message_set('Active object is not a mesh')
            return False
        return True

    def execute(self, context):
        bpy_object = context.object
        # Iterate over each material slot and look for a corresponding material in the asset library or current
        # scene's assets.
        material_slot_names = [material_slot.name for material_slot in bpy_object.material_slots]
        name_references = guess_package_reference_from_names(material_slot_names)
        for material_slot in bpy_object.material_slots:
            if name_references.get(material_slot.name, None) is None:
                continue
            material_slot.material = load_bdk_material(str(name_references[material_slot.name]))
        return {'FINISHED'}


classes = (
    BDK_OT_install_dependencies,
    BDK_OT_select_all_of_active_class,
    BDK_OT_fix_bsp_import_materials,
)
