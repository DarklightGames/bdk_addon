from bpy.types import PropertyGroup
from bpy.props import StringProperty, PointerProperty, CollectionProperty, IntProperty, BoolProperty, EnumProperty

from ...helpers import get_repository_by_id


class BDK_PG_repository_package_pattern(PropertyGroup):
    pattern: StringProperty(name='Pattern')


repository_package_status_enum_items = (
    ('NEEDS_EXPORT', 'Export Pending', 'The package contents need to be exported', 'EXPORT', 0),
    ('NEEDS_BUILD', 'Build Pending', 'The package library needs to be built', 'MOD_BUILD', 1),
    ('UP_TO_DATE', 'Up-To-Date', 'The package is up-to-date', 'CHECKMARK', 2),
)


class BDK_PG_repository_package(PropertyGroup):
    repository_id: StringProperty(name='Repository ID', options={'HIDDEN'})
    index: IntProperty()
    filename: StringProperty(name='File Name')
    path: StringProperty(name='Path')
    status: EnumProperty(name='Status', items=repository_package_status_enum_items, default='NEEDS_EXPORT')
    is_excluded_by_rule: BoolProperty(name='Excluded By Rule', default=False)
    modified_time: IntProperty(name='Modified Time', default=0)
    exported_time: IntProperty(name='Exported Time', default=0)
    build_time: IntProperty(name='Build Time', default=0)


repository_rule_type_enum_items = (
    ('EXCLUDE', 'Exclude', 'Ignore the package'),
    ('INCLUDE', 'Include', 'Include the package'),
    ('SET_ASSET_DIRECTORY', 'Set Asset Directory', 'Set the asset directory for the package. Relative paths are '
                                                   'relative to the repository cache directory'),
)

# TODO: one of these things is not like the other! move asset directories to its own thing.


def repository_rule_mute_update_cb(self, context):
    from .kernel import repository_runtime_packages_update_rule_exclusions, repository_metadata_write
    repository = get_repository_by_id(context, self.repository_id)
    if repository is not None:
        repository_runtime_packages_update_rule_exclusions(repository)
        repository_metadata_write(repository)


class BDK_PG_repository_rule(PropertyGroup):
    repository_id: StringProperty(name='Repository ID', options={'HIDDEN'})
    type: EnumProperty(name='Type', items=repository_rule_type_enum_items, default='EXCLUDE')
    pattern: StringProperty(name='Pattern', default='*')
    mute: BoolProperty(name='Mute', default=False, update=repository_rule_mute_update_cb)
    asset_directory: StringProperty(name='Asset Directory', default='', subtype='DIR_PATH',
                                    description='The directory where assets are stored')


class BDK_PG_repository_orphaned_asset(PropertyGroup):
    file_name: StringProperty(name='File Name', options={'HIDDEN'})


class BDK_PG_repository_runtime(PropertyGroup):
    """
    Runtime repository information, evaluated when necessary.
    """
    has_been_scanned: BoolProperty(name='Has Been Scanned', default=False)
    packages: CollectionProperty(type=BDK_PG_repository_package, name='Packages')
    packages_index: IntProperty(name='Index', default=-1)
    package_patterns: CollectionProperty(type=BDK_PG_repository_package_pattern, name='Package Patterns')
    package_patterns_index: IntProperty(name='Index', default=-1)

    excluded_package_count: IntProperty(name='Excluded Package Count', default=0)
    up_to_date_package_count: IntProperty(name='Up-To-Date Package Count', default=0)
    need_export_package_count: IntProperty(name='Need Export Package Count', default=0)
    need_build_package_count: IntProperty(name='Need Build Package Count', default=0)
    orphaned_assets: CollectionProperty(type=BDK_PG_repository_orphaned_asset, name='Orphaned Assets')
    orphaned_assets_index: IntProperty(name='Index', default=-1)


class BDK_PG_repository(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'}, description='Unique identifier')
    name: StringProperty(name='Name')
    game_directory: StringProperty(name='Game Directory', subtype='DIR_PATH',
                                   description='The game\'s root directory')
    mod: StringProperty(name='Mod', description='The name of the mod directory within the game directory (optional)')
    rules: CollectionProperty(type=BDK_PG_repository_rule, name='Rules')
    rules_index: IntProperty(name='Index', default=-1)
    cache_directory: StringProperty(name='Cache Directory', subtype='DIR_PATH',
                                    description='The directory where asset exports, manifests and libraries are stored.'
                                                '\n\n'
                                                'Relative paths are relative to the Game Directory',
                                    default='./.bdk/')
    runtime: PointerProperty(type=BDK_PG_repository_runtime, name='Runtime', options={'SKIP_SAVE'})


classes = (
    BDK_PG_repository_orphaned_asset,
    BDK_PG_repository_package_pattern,
    BDK_PG_repository_package,
    BDK_PG_repository_runtime,
    BDK_PG_repository_rule,
    BDK_PG_repository,
)
