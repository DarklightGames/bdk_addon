from enum import Enum, IntFlag, IntEnum


class ParticleCoordinateSystem(IntEnum):
    Independent = 0,
    Relative = 1,
    Absolute = 2,


class DetailMode(IntEnum):
    Low = 0,
    High = 1,
    SuperHigh = 2,


class ParticleDrawStyle(IntEnum):
    Regular = 0,
    AlphaBlend = 1,
    Modulated = 2,
    Translucent = 3,
    AlphaModulate_MightNotFogCorrectly = 4,
    Darken = 5,
    Brighten = 6,

class ParticleMeshSpawning(IntEnum):
    None_ = 0,
    Linear = 1,
    Random = 2,


class ParticleRotationSource(IntEnum):
    None_ = 0,
    Actor = 1,
    Offset = 2,
    Normal = 3,

class ParticleVelocityDirection(IntEnum):
    None_ = 0,
    StartPositionAndOwner = 1,
    OwnerAndStartPosition = 2,
    AddRadial = 3,


class ParticleSkelLocationUpdate(IntEnum):
    None_ = 0,
    SpawnOffset = 1,
    Location = 2,

class ParticleCollisionSound(IntEnum):
    None_ = 0,
    LinearGlobal = 1,
    LinearLocal = 2,
    Random = 3,

class ParticleStartLocationShape(IntEnum):
    Box = 0,
    Sphere = 1,
    Polar = 2,
    All = 3,


class ParticleEffectAxis(IntEnum):
    NegativeX = 0,
    PositiveY = 1,


class SkelLocationUpdate(IntEnum):
    None_ = 0,
    SpawnOffset = 1,
    Location = 2


class ParticleFlags(IntFlag):
    Active = 1
    NoTick = 2
    InitialSpawned = 4


class ParticleSpawnFlags(IntFlag):
    NoGlobalOffset = 1
    NoOwnerLocation = 2


class ParticleDirectionUsage(IntEnum):
    None_ = 0,
    Up = 1,
    Right = 2,
    Forward= 3,
    Normal = 4,
    UpAndNormal = 5,
    RightAndNormal = 6,
    Scale = 7
