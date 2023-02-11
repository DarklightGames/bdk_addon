import numpy as np
import uuid
import bpy.types
import bmesh
from typing import Tuple, cast
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, BoolProperty, StringProperty, EnumProperty
from bpy.types import Operator, Context, Mesh, Object, Collection
from bpy_extras.io_utils import ExportHelper

from .deco import TerrainDecoLayerBuilder
from .exporter import export_terrain_heightmap, export_terrain_layers

from ..helpers import auto_increment_name
from .builder import TerrainMaterialBuilder
from .types import BDK_PG_TerrainInfoPropertyGroup, BDK_PG_TerrainLayerPropertyGroup, \
    BDK_PG_TerrainDecoLayerPropertyGroup


# TODO: remove this
def build_terrain_material(active_object: Object):
    TerrainMaterialBuilder().build(active_object)


class BDK_OT_TerrainLayerRemove(Operator):
    bl_idname = 'bdk.terrain_layer_remove'
    bl_label = 'Remove Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        active_object = context.active_object
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        return terrain_info.terrain_layers_index >= 0

    def execute(self, context: Context):
        active_object = context.active_object

        if active_object is None:
            return {'CANCELLED'}

        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        if terrain_layers_index >= 0:
            # Remove color attribute.
            terrain_object = context.active_object
            mesh_data = cast(Mesh, terrain_object.data)
            color_attribute_name = terrain_layers[terrain_layers_index].color_attribute_name
            if color_attribute_name in mesh_data.color_attributes:
                color_attribute = mesh_data.color_attributes[color_attribute_name]
                mesh_data.color_attributes.remove(color_attribute)

            terrain_layers.remove(terrain_layers_index)

            terrain_info.terrain_layers_index = min(len(terrain_layers) - 1, terrain_layers_index)

            build_terrain_material(terrain_object)

        return {'FINISHED'}


class BDK_OT_TerrainLayerMove(Operator):
    bl_idname = 'bdk.terrain_layer_move'
    bl_label = 'Move Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name='Direction',
        options=set(),
        items=(
            ('UP', 'Up', 'The selected terrain layer will be moved up'),
            ('DOWN', 'Down', 'The selected terrain layer will be moved down')
        ),
    )

    def execute(self, context: Context):
        active_object = context.active_object
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        if self.direction == 'UP' and terrain_layers_index > 0:
            terrain_layers.move(terrain_layers_index, terrain_layers_index - 1)
            terrain_info.terrain_layers_index -= 1
            build_terrain_material(active_object)
        elif self.direction == 'DOWN' and terrain_layers_index < len(terrain_layers) - 1:
            terrain_layers.move(terrain_layers_index, terrain_layers_index + 1)
            terrain_info.terrain_layers_index += 1
            build_terrain_material(active_object)

        return {'FINISHED'}


def add_terrain_layer(terrain_info_object: Object, name: str,
                      fill: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object for operation')

    # Auto-increment the names if there is a conflict.
    name = auto_increment_name(name, map(lambda x: x.name, terrain_info.terrain_layers))

    mesh_data = cast(Mesh, terrain_info_object.data)

    # Create the associated color attribute.
    # TODO: in future, we will be able to paint non-color attributes, so use those once that's possible.
    color_attribute = mesh_data.color_attributes.new(uuid.uuid4().hex, type='FLOAT_COLOR', domain='POINT')
    vertex_count = len(color_attribute.data)
    color_data = np.ndarray(shape=(vertex_count, 4), dtype=float)
    color_data[:] = tuple(fill)
    color_attribute.data.foreach_set('color', color_data.flatten())

    # Add the terrain layer.
    terrain_layer: BDK_PG_TerrainLayerPropertyGroup = terrain_info.terrain_layers.add()
    terrain_layer.terrain_info_object = terrain_info_object
    terrain_layer.name = name
    terrain_layer.color_attribute_name = color_attribute.name

    # Regenerate the terrain material.
    build_terrain_material(terrain_info_object)

    # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
    for region in filter(lambda r: r.type == 'WINDOW', bpy.context.area.regions):
        region.tag_redraw()

    return terrain_layer


class BDK_OT_TerrainDecoLayerAdd(Operator):
    bl_idname = 'bdk.terrain_deco_layer_add'
    bl_label = 'Add Deco Layer'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        active_object = context.active_object
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')

        deco_layer = cast(BDK_PG_TerrainDecoLayerPropertyGroup, terrain_info.deco_layers.add())
        deco_layer.name = auto_increment_name(deco_layer.name, map(lambda x: x.name, terrain_info.deco_layers))
        deco_layer.id = uuid.uuid4().hex

        deco_layer.object = TerrainDecoLayerBuilder().build(context, active_object, deco_layer)

        collection: Collection = active_object.users_collection[0]
        collection.objects.link(deco_layer.object)
        deco_layer.object.parent = active_object

        # TODO: add the object to the scene and parent it to the active object

        return {'FINISHED'}


class BDK_OT_TerrainDecoLayerRemove(Operator):
    bl_idname = 'bdk.terrain_deco_layer_remove'
    bl_label = 'Remove Deco Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: 'Context'):
        active_object = context.active_object

        if active_object is None:
            return False

        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index

        if len(deco_layers) == 0 or deco_layers_index == -1:
            return False

        return True

    def execute(self, context: bpy.types.Context):
        terrain_info_object = context.active_object
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index

        if deco_layers_index >= 0:
            deco_layer = deco_layers[deco_layers_index]
            deco_layer_object = cast(Object, deco_layers[deco_layers_index].object)

            if deco_layer_object is not None:
                for collection in deco_layer_object.users_collection:
                    collection.objects.unlink(deco_layer_object)
                mesh_data = cast(Mesh, terrain_info_object.data)
                if mesh_data is not None:
                    attribute = mesh_data.color_attributes.get(deco_layer.id, None)
                    if attribute is not None:
                        mesh_data.attributes.remove(attribute)
                bpy.data.objects.remove(deco_layer_object)

            deco_layers.remove(deco_layers_index)
            terrain_info.deco_layers_index = min(len(terrain_info.deco_layers) - 1, deco_layers_index)

        return {'FINISHED'}


class BDK_OT_TerrainLayerAdd(Operator):
    bl_idname = 'bdk.terrain_layer_add'
    bl_label = 'Add Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name='Name')
    alpha_fill: FloatVectorProperty(name='Alpha Fill', subtype='COLOR', min=0.0, max=1.0, size=4,
                                    default=(0.0, 0.0, 0.0, 1.0))
    u_scale: FloatProperty(name='UScale', default=1.0)
    v_scale: FloatProperty(name='VScale', default=1.0)

    @classmethod
    def poll(cls, context: Context):
        active_object = context.active_object
        if not active_object:
            return False
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        if not terrain_info.is_terrain_info:
            return False
        return len(terrain_info.terrain_layers) < 32

    def execute(self, context: bpy.types.Context):
        active_object = context.active_object

        try:
            add_terrain_layer(active_object, name='TerrainLayer', fill=self.alpha_fill)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}


def quad_size_get(self):
    return self.size / (self.resolution - 1)


class BDK_OT_TerrainInfoAdd(Operator):
    bl_idname = 'bdk.create_terrain_info'
    bl_label = 'Add Terrain Info'
    bl_options = {'REGISTER', 'UNDO'}

    resolution: IntProperty(name='Resolution', default=512, min=2, max=512, description='The number of quads')
    size: FloatProperty(name='Size', default=500 * 60.352, subtype='DISTANCE',
                        description='The length and width of the terrain')
    quad_size: FloatProperty(name='Quad Size', get=quad_size_get, set=None, subtype='DISTANCE')
    location: FloatVectorProperty(name='Location', unit='LENGTH')
    lock_transforms: BoolProperty(name='Lock Transforms', default=True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return self.execute(context)

    def execute(self, context: bpy.types.Context):

        # NOTE: There is a bug in Unreal where the terrain is off-center, so we deliberately
        # have to miscalculate things in order to replicate the behavior seen in the engine.
        quad_length = float(self.size) / self.resolution
        size_half = 0.5 * self.size

        bm = bmesh.new()

        # Vertices
        for y in range(self.resolution):
            for x in range(self.resolution):
                co = (quad_length * x - size_half, quad_length * y - size_half + quad_length, 0.0)
                bm.verts.new(co)

        bm.verts.ensure_lookup_table()

        # Faces
        z = 0
        indices = [0, 1, self.resolution + 1, self.resolution]
        for y in range(self.resolution - 1):
            for x in range(self.resolution - 1):
                face = bm.faces.new(tuple([bm.verts[z + x] for x in indices]))
                face.smooth = True
                z += 1
            z += 1

        mesh_data = bpy.data.meshes.new('TerrainInfo')
        bm.to_mesh(mesh_data)
        del bm

        mesh_object = bpy.data.objects.new('TerrainInfo', mesh_data)
        mesh_object.location = self.location
        mesh_object['bdk.quad_size'] = self.quad_size

        if self.lock_transforms:
            # Lock transforms so that levelers don't accidentally move the terrain.
            mesh_object.lock_location = [True] * 3
            mesh_object.lock_scale = [True] * 3
            mesh_object.lock_rotation = [True] * 3
            mesh_object.lock_rotation_w = True
            mesh_object.lock_rotations_4d = True

        # Custom properties
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(mesh_object, 'terrain_info')
        terrain_info.is_terrain_info = True
        terrain_info.terrain_info_object = mesh_object
        terrain_info.x_size = self.resolution
        terrain_info.y_size = self.resolution
        terrain_info.terrain_scale = self.size / self.resolution

        # Add a base layer to start with.
        add_terrain_layer(mesh_object, name='Base', fill=(1.0, 1.0, 1.0, 1.0))

        # Create the "hidden" material we will use for hiding quads.
        hidden_material = bpy.data.materials.new(uuid.uuid4().hex)
        hidden_material.use_nodes = True
        hidden_material.node_tree.nodes.clear()
        hidden_material.blend_method = 'CLIP'
        node_tree = hidden_material.node_tree
        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')

        transparent_node = node_tree.nodes.new('ShaderNodeBsdfTransparent')
        node_tree.links.new(output_node.inputs['Surface'], transparent_node.outputs['BSDF'])

        mesh_data.materials.append(hidden_material)

        context.scene.collection.objects.link(mesh_object)

        return {'FINISHED'}


class BDK_OT_TerrainInfoExport(Operator, ExportHelper):
    bl_label = 'Export Terrain Info'
    bl_idname = 'bdk.export_terrain_info'

    directory: StringProperty(name='Directory')
    filename_ext: StringProperty(default='.', options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    def invoke(self, context: 'Context', event: 'Event'):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context):
        export_terrain_heightmap(context.active_object, directory=self.directory)
        export_terrain_layers(context.active_object, directory=self.directory)
        return {'FINISHED'}


classes = (
    BDK_OT_TerrainInfoAdd,
    BDK_OT_TerrainLayerAdd,
    BDK_OT_TerrainLayerRemove,
    BDK_OT_TerrainLayerMove,
    BDK_OT_TerrainDecoLayerAdd,
    BDK_OT_TerrainDecoLayerRemove,
    BDK_OT_TerrainInfoExport
)
