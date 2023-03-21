from bpy.types import Object
from mathutils import Vector, Euler, Matrix, Quaternion
from ..units import radians_to_unreal


class T3DInterface:
    """
    Interface for Unreal Text File format (T3D).
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
        self.pitch: int = -radians_to_unreal(euler.y)
        self.roll: int = radians_to_unreal(euler.x)
        self.yaw: int = -radians_to_unreal(euler.z)

    def __str__(self) -> str:
        return f'(Pitch={self.pitch},Roll={self.roll},Yaw={self.yaw})'


# TODO: Get 'defaultproperties' from object's custom properties
class UActor(T3DInterface):
    """
    Unreal Actor

    :param object: Blender object
    :param asset_instance: Collection instance containing the object (optional)
    """

    def __init__(self, object: Object, asset_instance: Object | None = None) -> None:
        self.object: Object = object
        self.asset_instance: Object | None = asset_instance
        self.classname: str = 'Actor'
        self.matrix_world: Matrix

        if self.asset_instance:
            self.matrix_world: Matrix = self.asset_instance.matrix_world @ self.instance_offset @ object.matrix_local
        else:
            self.matrix_world = self.object.matrix_world

        # Location is corrected by 32 units as it gets offset when actor 
        # is pasted into the Unreal Editor.
        loc: Vector = self.matrix_world.to_translation() - Vector((32.0, -32.0, 32.0))
        # Y-Axis is inverted in UE.
        loc.y = -loc.y 

        self.location: UVector = UVector(loc)
        self.rotation: URotator = URotator(self.matrix_world.to_euler('XYZ')) 
        self.scale: UVector = UVector(self.matrix_world.to_scale())

    def __repr__(self) -> str:
        return self.to_text()

    @property
    def instance_offset(self) -> Matrix:
        try:
            local_offset: Vector = self.asset_instance.instance_collection.instance_offset
            return Matrix().Translation(local_offset).inverted()
        except AttributeError:
            return Matrix()
    
    def get_property_dict(self) -> dict[str, str]:
        """Returns properties of the actor as a dictionary."""
        return {
            'Location': str(self.location),
            'Rotation': str(self.rotation),
            'DrawScale3D': str(self.scale)
        }

    def to_text(self, name: str = '') -> str:
        actor_name: str = name if name else self.classname
        props: str = ''
        indent: str = '   '

        for _, (key, value) in enumerate(self.get_property_dict().items()):
            props += f'\n{indent}{key}={value}'

        return f'Begin Actor Class={self.classname} Name={actor_name}{props}\nEnd Actor'


class UStaticMeshActor(UActor):
    def __init__(self, object: Object, asset_instance: Object | None = None) -> None:
        super().__init__(object, asset_instance)
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
