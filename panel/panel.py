import bpy
from bpy.types import Panel, Operator, Object
from dataclasses import dataclass
from mathutils import Vector, Euler


def rad_to_unreal(value: float) -> int:
    return int(value * 10430.378350470452724949566316381)


class URotator():
    def __init__(self, euler: Euler):
        self.pitch: int = -rad_to_unreal(euler.y)
        self.roll: int = rad_to_unreal(euler.x)
        self.yaw: int = -rad_to_unreal(euler.z)

    def __str__(self) -> str:
        return f'(Pitch={self.pitch},Roll={self.roll},Yaw={self.yaw})'


class UVector():
    def __init__(self, vector: Vector):
        self.x: float = vector.x - 32.0
        self.y: float = -vector.y - 32.0
        self.z: float = vector.z - 32.0
        

    def __str__(self) -> str:
        return f'(X={self.x},Y={self.y},Z={self.z})'


class StaticMeshActor:
    def __init__(self, object: Object, name: str) -> None:
        loc = Vector(object.location)
        rot = Euler(object.rotation_euler)

        self.name = name

        self.props = {}
        self.props['StaticMesh'] = object.data.name
        self.props['Location'] = str(UVector(loc))
        self.props['Rotation'] = str(URotator(rot))

    def __repr__(self) -> str:
        out = f'Begin Actor Class=StaticMeshActor Name={self.name}'
        indent = '    '

        for _, (key, value) in enumerate(self.props.items()):
            out += f'\n{indent}{key}={value}'

        out += '\nEnd Actor'

        return out


class BDK_OP_CopyObject(Operator):
    bl_idname = 'bdk_panel.copy_object'
    bl_label = 'Copy Object(s)'
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        selected = bpy.context.selected_objects

        pasta = 'Begin Map'
        for idx, object in enumerate(selected):
            pasta += '\n' + str(StaticMeshActor(object, f'StaticMeshActor{idx}'))
        pasta += '\nBegin Surface\nEnd Surface\nEnd Map'

        bpy.context.window_manager.clipboard = pasta
        print(pasta)

        return {'FINISHED'}


class BDK_PT_Panel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_label = 'BDK'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(BDK_OP_CopyObject.bl_idname, icon='COPYDOWN', text=f'Copy Object(s)')


classes = (
    BDK_PT_Panel,
    BDK_OP_CopyObject
)