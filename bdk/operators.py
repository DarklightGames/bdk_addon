from typing import Dict

from bpy.types import Operator, Context, NodeTree, Node
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
        # Return false if no doodad are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No doodad selected')
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


class BDK_OT_generate_node_code(Operator):
    bl_idname = 'bdk.generate_node_code'
    bl_label = 'Generate Node Code'
    bl_description = 'Generate code for the selected nodes'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # Return true if we are currently in the node editor.
        if context.area.type != 'NODE_EDITOR':
            cls.poll_message_set('Not in node editor')
            return False
        return True

    def execute(self, context: Context):
        # Get the selected nodes in the node editor.
        selected_nodes = context.selected_nodes

        lines = []

        nodes: Dict[str, Node] = dict()

        for node in selected_nodes:
            if node.label:
                variable_name = node.label.replace(' ', '_').lower()
            else:
                variable_name = node.bl_label.replace(' ', '_').lower()
            variable_name += '_node'
            nodes[variable_name] = node

        for variable_name, node in nodes.items():
            lines.append(f'{variable_name} = node_tree.nodes.new(type=\'{node.bl_idname}\')')
            # If a label is set, set it.
            if node.label:
                lines.append(f'{variable_name}.label = \'{node.label}\'')

            # For any of the node's properties that are not default, set them.
            for property_name, property_meta in node.bl_rna.properties.items():
                if property_meta.is_readonly:
                    continue
                if property_name.startswith('bl_'):
                    continue
                # Ignore PointerProperty properties.
                if property_meta.type == 'POINTER':
                    continue
                if property_name in ('name', 'label', 'location', 'width', 'height', 'name', 'color', 'select', 'show_options'):
                    continue
                if getattr(node, property_name) != property_meta.default:
                    value = getattr(node, property_name)
                    if isinstance(value, str):
                        value = f'\'{value}\''
                    lines.append(f'{variable_name}.{property_name} = {value}')

        # Get all the links between the selected nodes.
        links = set()
        for variable_name, node in nodes.items():
            for input in node.inputs:
                if input.is_linked:
                    for link in input.links:
                        if link.from_node in selected_nodes:
                            links.add(link)
            for output in node.outputs:
                if output.is_linked:
                    for link in output.links:
                        if link.to_node in selected_nodes:
                            links.add(link)

        for link in links:
            from_node = link.from_node
            to_node = link.to_node

            # Get variable names for the nodes.
            from_variable_name = None
            for variable_name, node in nodes.items():
                if node == from_node:
                    from_variable_name = variable_name
                    break
            to_variable_name = None
            for variable_name, node in nodes.items():
                if node == to_node:
                    to_variable_name = variable_name
                    break

            lines.append(f'node_tree.links.new({from_variable_name}.outputs[\'{link.from_socket.identifier}\'], {to_variable_name}.inputs[\'{link.to_socket.identifier}\'])')

        # Copy the lines to the clipboard.
        context.window_manager.clipboard = '\n'.join(lines)

        return {'FINISHED'}

classes = (
    BDK_OT_install_dependencies,
    BDK_OT_select_all_of_active_class,
    BDK_OT_fix_bsp_import_materials,
    BDK_OT_generate_node_code,
)
