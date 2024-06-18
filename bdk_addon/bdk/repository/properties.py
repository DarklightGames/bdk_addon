from bpy.types import PropertyGroup
from bpy.props import StringProperty, PointerProperty, CollectionProperty, IntProperty, BoolProperty, EnumProperty


class BDK_PG_repository_package_pattern(PropertyGroup):
    pattern: StringProperty(name='Pattern')


repository_package_status_enum_items = (
    ('NEEDS_EXPORT', 'Needs Export', 'The package contents need to be exported', 'TIME', 0),
    ('NEEDS_BUILD', 'Needs Build', 'The package library needs to be built', 'TIME', 1),
    ('UP_TO_DATE', 'Up To Date', 'The package is up to date', 'CHECKMARK', 2),
)


class BDK_PG_repository_package(PropertyGroup):
    index: IntProperty()
    filename: StringProperty(name='File Name')
    path: StringProperty(name='Path')
    status: EnumProperty(name='Status', items=repository_package_status_enum_items, default='NEEDS_EXPORT')
    modified_time: IntProperty(name='Modified Time', default=0)
    exported_time: IntProperty(name='Exported Time', default=0)
    build_time: IntProperty(name='Build Time', default=0)


class BDK_PG_repository_runtime(PropertyGroup):
    """
    Runtime repository information, evaluated when necessary.
    """
    has_been_scanned: BoolProperty(name='Has Been Scanned', default=False, options={'SKIP_SAVE'})
    packages: CollectionProperty(type=BDK_PG_repository_package, name='Packages', options={'SKIP_SAVE'})
    packages_index: IntProperty(name='Index', default=-1, options={'SKIP_SAVE'})
    package_patterns: CollectionProperty(type=BDK_PG_repository_package_pattern, name='Package Patterns', options={'SKIP_SAVE'})
    package_patterns_index: IntProperty(name='Index', default=-1, options={'SKIP_SAVE'})

    up_to_date_package_count: IntProperty(name='Up To Date Package Count', default=0, options={'SKIP_SAVE'})
    need_export_package_count: IntProperty(name='Need Export Package Count', default=0, options={'SKIP_SAVE'})
    need_build_package_count: IntProperty(name='Need Build Package Count', default=0, options={'SKIP_SAVE'})


class BDK_PG_repository(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'}, description='Unique identifier')
    name: StringProperty(name='Name')
    game_directory: StringProperty(name='Game Directory', subtype='DIR_PATH',
                                   description='The game\'s root directory')
    mod: StringProperty(name='Mod', description='The name of the mod directory within the game directory (optional)')
    cache_directory: StringProperty(name='Cache Directory', subtype='DIR_PATH',
                                    description='The directory where asset exports, manifests and libraries are stored.'
                                                '\n\n'
                                                'Relative paths are relative to the Game Directory',
                                    default='./.bdk/')
    runtime: PointerProperty(type=BDK_PG_repository_runtime, name='Runtime', options={'SKIP_SAVE'})


classes = (
    BDK_PG_repository_package_pattern,
    BDK_PG_repository_package,
    BDK_PG_repository_runtime,
    BDK_PG_repository,
)
