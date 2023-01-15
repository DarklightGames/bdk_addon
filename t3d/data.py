import bpy
import bmesh
from bpy.types import Object
from mathutils import Vector, Euler, Quaternion
from typing import Sequence


def rad_to_unreal(value: float) -> int:
    return int(value * 10430.378350470452724949566316381)


class T3DInterface:
    """
    Inteface for Unreal Text File format (T3D).
    https://wiki.beyondunreal.com/Legacy:T3D_File
    """

    def to_text(self, name: str = '') -> str:
        """Convert to Unreal T3D text."""
        return ''


class UVector(Vector):
    def __str__(self) -> str:
        return f'(X={self.x},Y={self.y},Z={self.z})'


class URotator:
    def __init__(self, euler: Euler):
        self.pitch: int = -rad_to_unreal(euler.y)
        self.roll: int = rad_to_unreal(euler.x)
        self.yaw: int = -rad_to_unreal(euler.z)

    def __str__(self) -> str:
        return f'(Pitch={self.pitch},Roll={self.roll},Yaw={self.yaw})'


# TODO: Get 'defaultproperties' from object's custom properties
class UActor(T3DInterface):
    def __init__(self, object: Object) -> None:
        self.object: Object = object
        self.classname: str = 'StaticMeshActor'

    def __repr__(self) -> str:
        return self.to_text()

    def location(self) -> UVector:
        """
        Returns location vector of the actor.
        Location is corrected by 32 units because it gets offset when actor is pasted into the Unreal Editor.
        Y-Axis is inverted.
        """
        v: Vector = Vector(self.object.matrix_world.decompose()[0])
        loc: Vector = v - Vector((32.0, -32.0, 32.0))
        loc.y = -loc.y

        return UVector(loc)

    def rotation(self) -> URotator:
        """Returns the actor's rotator."""
        q: Quaternion = Quaternion(self.object.matrix_world.decompose()[1])

        return URotator(q.to_euler('XYZ'))

    def scale(self) -> UVector:
        """Returns the scale vector of the actor."""
        v: Vector = Vector(self.object.matrix_world.decompose()[2])

        return UVector(v)

    def get_property_dict(self) -> dict[str, str]:
        """Returns properties of the actor as a dictionary."""

        props: dict[str, str] = {}
        props['Location'] = str(self.location())
        props['Rotation'] = str(self.rotation())
        props['DrawScale3D'] = str(self.scale())

        return props

    def to_text(self, name: str = '') -> str:
        actor_name: str = name if name else self.classname
        props: str = ''
        indent: str = '   '

        for _, (key, value) in enumerate(self.get_property_dict().items()):
            props += f'\n{indent}{key}={value}'

        return f'Begin Actor Class={self.classname} Name={actor_name}{props}\nEnd Actor'


class UStaticMeshActor(UActor):
    def __init__(self, object: Object) -> None:
        super().__init__(object)
        self.classname = 'StaticMeshActor'

    def get_property_dict(self) -> dict[str, str]:
        props: dict[str, str] = super().get_property_dict()
        props['StaticMesh'] = self.object.data.name

        return props


class UMap(T3DInterface):
    """Class containing map actors."""

    def __init__(self) -> None:
        self.actors: list[UActor] = []

    def __repr__(self) -> str:
        return self.to_text()
    
    def to_text(self) -> str:
        actors_text: str = ''

        for actor in self.actors:
            actors_text += '\n' + actor.to_text()

        return f'Begin Map{actors_text}\nBegin Surface\nEnd Surface\nEnd Map'

    def add_actor(self, actor: UActor) -> None:
        self.actors.append(actor)


