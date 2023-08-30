from collections import OrderedDict
from typing import OrderedDict as OrderedDictType
from typing import Dict

import mathutils
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

        selected_nodes = context.selected_nodes

        # Get the selected nodes in the node editor.
        def get_socket_index(sockets, socket):
            for i, s in enumerate(sockets):
                if s == socket:
                    return i
            return None

        lines = []

        nodes: OrderedDictType[str, Node] = OrderedDict()

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

            # Check if the node has any input sockets whose default value doesn't match the default value of the socket type.
            for socket in node.inputs:
                if socket.is_linked or socket.is_unavailable:
                    continue
                if socket.default_value:  # TODO: this is imprecise but should work for now
                    default_value = socket.default_value
                    if type(socket.default_value) == str:
                        default_value = f'\'{default_value}\''
                    # TODO: other types are too much of a pain to handle right now
                    lines.append(f'{variable_name}.inputs["{socket.name}"].default_value = {default_value}')

            lines.append('')


        # Get all the links between the selected nodes.
        links = set()
        for variable_name, node in nodes.items():
            for input in node.inputs:
                if input.is_linked:
                    for link in input.links:
                        links.add(link)
            for output in node.outputs:
                if output.is_linked:
                    for link in output.links:
                        links.add(link)

        internal_links = []
        incoming_links = []
        outgoing_links = []

        for link in links:
            from_node = link.from_node
            to_node = link.to_node

            from_variable_name = None
            from_socket_index = None
            to_variable_name = None
            to_socket_index = None

            if from_node and from_node in selected_nodes:
                # Get variable names for the nodes.
                for variable_name, node in nodes.items():
                    if node == from_node:
                        from_variable_name = variable_name
                        break
                # Get the index of the "from" socket.
                from_socket_index = get_socket_index(from_node.outputs, link.from_socket)

            if to_node and to_node in selected_nodes:
                for variable_name, node in nodes.items():
                    if node == to_node:
                        to_variable_name = variable_name
                        break
                # Get the index of the "to" socket.
                to_socket_index = get_socket_index(to_node.inputs, link.to_socket)

            if from_variable_name and from_socket_index is not None and to_variable_name and to_socket_index is not None:
                internal_links.append((link, from_variable_name, from_socket_index, to_variable_name, to_socket_index))
            elif from_variable_name and from_socket_index is not None and not to_variable_name and to_socket_index is None:
                outgoing_links.append((link, from_variable_name, from_socket_index))
            elif not from_variable_name and from_socket_index is None and to_variable_name and to_socket_index is not None:
                incoming_links.append((link, to_variable_name, to_socket_index))

        if internal_links:
            lines.append('')
            lines.append('# Internal Links')
            for (link, from_variable_name, from_socket_index, to_variable_name, to_socket_index) in internal_links:
                lines.append(f'node_tree.links.new({from_variable_name}.outputs[{from_socket_index}], {to_variable_name}.inputs[{to_socket_index}])  # {link.from_socket.name} -> {link.to_socket.name}')

        if incoming_links:
            lines.append('')
            lines.append('# Incoming Links')
            for (link, to_variable_name, to_socket_index) in incoming_links:
                lines.append(f'# {to_variable_name}.inputs[{to_socket_index}]  # {link.to_socket.name}')

        if outgoing_links:
            lines.append('')
            lines.append('# Outgoing Links')
            for (link, from_variable_name, from_socket_index) in outgoing_links:
                lines.append(f'# {from_variable_name}.outputs[{from_socket_index}]  # {link.from_socket.name}')


        # Copy the lines to the clipboard.
        context.window_manager.clipboard = '\n'.join(lines)

        return {'FINISHED'}

classes = (
    BDK_OT_install_dependencies,
    BDK_OT_select_all_of_active_class,
    BDK_OT_fix_bsp_import_materials,
    BDK_OT_generate_node_code,
)

"""
map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
map_range_node.clamp = True
map_range_node.inputs["From Max"].default_value = 1.0
map_range_node.inputs["Steps"].default_value = 4.0
map_range_node.inputs["Vector"].default_value = <bpy_float[3], NodeSocketVector.default_value>
map_range_node.inputs["From Min"].default_value = <bpy_float[3], NodeSocketVector.default_value>
map_range_node.inputs["From Max"].default_value = <bpy_float[3], NodeSocketVector.default_value>
map_range_node.inputs["To Min"].default_value = <bpy_float[3], NodeSocketVector.default_value>
map_range_node.inputs["To Max"].default_value = <bpy_float[3], NodeSocketVector.default_value>
map_range_node.inputs["Steps"].default_value = <bpy_float[3], NodeSocketVector.default_value>
terrain_normal_offset_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
terrain_normal_offset_scale_node.label = 'Terrain Normal Offset Scale'
terrain_normal_offset_scale_node.operation = 'SCALE'
terrain_normal_offset_scale_node.inputs["Vector"].default_value = <bpy_float[3], NodeSocketVector.default_value>
terrain_normal_offset_scale_node.inputs["Vector"].default_value = <bpy_float[3], NodeSocketVector.default_value>
random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
random_value_node.inputs["Min"].default_value = <bpy_float[3], NodeSocketVector.default_value>
random_value_node.inputs["Max"].default_value = <bpy_float[3], NodeSocketVector.default_value>
random_value_node.inputs["Max"].default_value = 1.0
random_value_node.inputs["Max"].default_value = 100
random_value_node.inputs["Probability"].default_value = 0.5
random_value_node.inputs["Seed"].default_value = 281
vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
vector_math_node.operation = 'NORMALIZE'
vector_math_node.inputs["Vector"].default_value = <bpy_float[3], NodeSocketVector.default_value>
vector_math_node.inputs["Vector"].default_value = <bpy_float[3], NodeSocketVector.default_value>
vector_math_node.inputs["Scale"].default_value = 1.0
terrain_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
terrain_normal_attribute_node.label = 'Terrain Normal Attribute'
terrain_normal_attribute_node.data_type = 'FLOAT_VECTOR'
terrain_normal_attribute_node.inputs["Name"].default_value = terrain_normal
mix_node = node_tree.nodes.new(type='ShaderNodeMix')
mix_node.data_type = 'VECTOR'
mix_node.clamp_factor = True
mix_node.inputs["Factor"].default_value = 1.0
mix_node.inputs["Factor"].default_value = <bpy_float[3], NodeSocketVector.default_value>
mix_node.inputs["A"].default_value = <bpy_float[3], NodeSocketVector.default_value>
mix_node.inputs["A"].default_value = <bpy_float[4], NodeSocketColor.default_value>
mix_node.inputs["B"].default_value = <bpy_float[4], NodeSocketColor.default_value>
mix_node.inputs["A"].default_value = <Euler (x=0.0000, y=0.0000, z=0.0000), order='XYZ'>
mix_node.inputs["B"].default_value = <Euler (x=0.0000, y=0.0000, z=0.0000), order='XYZ'>
align_z_node = node_tree.nodes.new(type='FunctionNodeAlignEulerToVector')
align_z_node.label = 'Align Z'
align_z_node.axis = 'Z'
align_z_node.inputs["Factor"].default_value = 1.0
align_x_node = node_tree.nodes.new(type='FunctionNodeAlignEulerToVector')
align_x_node.label = 'Align X'
align_x_node.inputs["Rotation"].default_value = <Euler (x=0.0000, y=0.0000, z=0.0000), order='XYZ'>
align_x_node.inputs["Factor"].default_value = 1.0
curve_tangent_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
curve_tangent_attribute_node.label = 'Curve Tangent Attribute'
curve_tangent_attribute_node.data_type = 'FLOAT_VECTOR'
curve_tangent_attribute_node.inputs["Name"].default_value = curve_tangent
"""
