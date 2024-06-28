from bpy.types import PropertyGroup
from bpy.props import StringProperty, PointerProperty, CollectionProperty, IntProperty, BoolProperty, EnumProperty


class BDK_PG_repository_package_pattern(PropertyGroup):
    pattern: StringProperty(name='Pattern')


repository_package_status_enum_items = (
    ('NEEDS_EXPORT', 'Export Pending', 'The package contents need to be exported', 'EXPORT', 0),
    ('NEEDS_BUILD', 'Build Pending', 'The package library needs to be built', 'MOD_BUILD', 1),
    ('UP_TO_DATE', 'Up To Date', 'The package is up to date', 'CHECKMARK', 2),
)

filter_repository_package_status_enum_items = (
    ('ALL', 'All', 'Show all packages', 'NONE', 3),
) + repository_package_status_enum_items


def repository_package_is_enabled_update_cb(self, context):
    from ...helpers import get_addon_preferences
    addon_prefs = get_addon_preferences(context)
    repository = None
    for r in addon_prefs.repositories:
        if r.id == self.repository_id:
            repository = r
            break
    if repository is None:
        return
    repository.runtime.disabled_package_count += 1 if not self.is_enabled else -1
    match self.status:
        case 'NEEDS_EXPORT':
            repository.runtime.need_export_package_count += 1 if self.is_enabled else -1
        case 'NEEDS_BUILD':
            repository.runtime.need_build_package_count += 1 if self.is_enabled else -1
        case 'UP_TO_DATE':
            repository.runtime.up_to_date_package_count += 1 if self.is_enabled else -1


class BDK_PG_repository_package(PropertyGroup):
    repository_id: StringProperty(name='Repository ID', options={'HIDDEN'})
    index: IntProperty()
    filename: StringProperty(name='File Name')
    path: StringProperty(name='Path')
    status: EnumProperty(name='Status', items=repository_package_status_enum_items, default='NEEDS_EXPORT')
    is_selected: BoolProperty(name='Selected', default=False)
    is_enabled: BoolProperty(name='Enabled', default=True, update=repository_package_is_enabled_update_cb)
    modified_time: IntProperty(name='Modified Time', default=0)
    exported_time: IntProperty(name='Exported Time', default=0)
    build_time: IntProperty(name='Build Time', default=0)


repository_rule_type_enum_items = (
    ('IGNORE', 'Ignore', 'Ignore the package'),
    ('INCLUDE', 'Include', 'Include the package'),
    ('SET_ASSET_DIRECTORY', 'Set Asset Directory', 'Set the asset directory for the package. Relative paths are relative to the Game Directory'),
)


class BDK_PG_repository_rule(PropertyGroup):
    type: EnumProperty(name='Action', items=repository_rule_type_enum_items, default='IGNORE')
    pattern: StringProperty(name='Pattern', default='*')
    mute: BoolProperty(name='Mute', default=False)
    asset_directory: StringProperty(name='Asset Directory', default='', description='The directory where assets are stored', subtype='DIR_PATH')


class BDK_PG_repository_runtime(PropertyGroup):
    """
    Runtime repository information, evaluated when necessary.
    """
    has_been_scanned: BoolProperty(name='Has Been Scanned', default=False, options={'SKIP_SAVE'})
    packages: CollectionProperty(type=BDK_PG_repository_package, name='Packages', options={'SKIP_SAVE'})
    packages_index: IntProperty(name='Index', default=-1, options={'SKIP_SAVE'})
    package_patterns: CollectionProperty(type=BDK_PG_repository_package_pattern, name='Package Patterns', options={'SKIP_SAVE'})
    package_patterns_index: IntProperty(name='Index', default=-1, options={'SKIP_SAVE'})

    disabled_package_count: IntProperty(name='Disabled Package Count', default=0)
    up_to_date_package_count: IntProperty(name='Up To Date Package Count', default=0)
    need_export_package_count: IntProperty(name='Need Export Package Count', default=0)
    need_build_package_count: IntProperty(name='Need Build Package Count', default=0)


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
    BDK_PG_repository_package_pattern,
    BDK_PG_repository_package,
    BDK_PG_repository_runtime,
    BDK_PG_repository_rule,
    BDK_PG_repository,
)
