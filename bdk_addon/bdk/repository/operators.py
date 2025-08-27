import bpy
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from bpy.props import StringProperty, IntProperty, EnumProperty, BoolProperty
from bpy.types import Operator, Context, Event
from bpy_extras.io_utils import ImportHelper

from .kernel import Manifest, get_repository_package_asset_path, repository_runtime_update, ensure_repository_asset_library, \
    ensure_default_repository_id, repository_asset_library_unlink, repository_remove, repository_cache_delete, \
    repository_metadata_delete, repository_package_build, get_repository_package_dependency_graph, \
    layered_topographical_sort, repository_package_export, is_game_directory_and_mod_valid, repository_metadata_write, \
    repository_metadata_read, repository_runtime_packages_update_rule_exclusions, get_repository_cache_directory, \
    get_repository_default_asset_library_directory, get_repository_package_asset_directory, \
    get_repository_package_catalog_id
from .properties import repository_rule_type_enum_items
from ...catalog import AssetCatalogFile
from ...helpers import get_addon_preferences, tag_redraw_all_windows


def poll_has_repository_selected(context):
    addon_prefs = get_addon_preferences(context)
    return (len(addon_prefs.repositories) > 0 and
            0 <= addon_prefs.repositories_index < len(addon_prefs.repositories))


def poll_has_repository_package_selected(cls, context) -> bool:
    addon_prefs = get_addon_preferences(context)
    result = (poll_has_repository_selected(context) and
            0 <= addon_prefs.repositories[addon_prefs.repositories_index].runtime.packages_index < len(
                addon_prefs.repositories[addon_prefs.repositories_index].runtime.packages))
    if not result:
        cls.poll_message_set('No package selected')
    return result


def poll_has_repository_rule_selected(context):
    addon_prefs = get_addon_preferences(context)
    return (poll_has_repository_selected(context) and
            0 <= addon_prefs.repositories[addon_prefs.repositories_index].rules_index < len(
                addon_prefs.repositories[addon_prefs.repositories_index].rules))


class BDK_OT_repository_scan(Operator):
    bl_idname = 'bdk.repository_scan'
    bl_label = 'Scan Repository'
    bl_description = 'Scan the repository and update the status of each package'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        addon_prefs = get_addon_preferences(context)
        return len(addon_prefs.repositories) > 0

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        # Update the runtime information.
        try:
            repository_metadata_read(repository)
            repository_runtime_update(repository)
        except Exception as e:
            self.report({'ERROR'}, f'Failed to scan repository: {e}')
            return {'CANCELLED'}

        return {'FINISHED'}


class BDK_OT_repository_cache_delete(Operator):
    bl_idname = 'bdk.repository_cache_delete'
    bl_label = 'Delete Cache'
    bl_description = 'Delete the repository cache. This will delete all exports, assets, and the manifest. This ' \
                     'action cannot be undone'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        # TODO: probably want a more frightening warning.
        return context.window_manager.invoke_confirm(self, event)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_addon_preferences(context)
        return len(addon_prefs.repositories) > 0

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_cache_delete(repository)
        repository_runtime_update(repository)

        return {'FINISHED'}


class BDK_OT_repository_package_build(Operator):
    bl_idname = 'bdk.repository_package_build'
    bl_label = 'Build Package'
    bl_description = 'Build the selected package'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return poll_has_repository_package_selected(cls, context)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[repository.runtime.packages_index]

        # Build the export path.
        context.window_manager.progress_begin(0, 1)

        process, _ = repository_package_build(repository, package.path)

        if process.returncode != 0:
            self.report({'ERROR'}, f'Failed to build package: {package.path}')
            return {'CANCELLED'}
        else:
            context.window_manager.progress_update(1)

        context.window_manager.progress_end()

        # Update the runtime information.
        repository_runtime_update(repository)

        return {'FINISHED'}


repository_rule_type_enum_items = (
    ('EXCLUDE', 'Exclude', 'Ignore the package'),
    ('INCLUDE', 'Include', 'Include the package'),
)

class BDK_OT_repository_rule_package_add(Operator):
    bl_idname = 'bdk.repository_package_rule_add'
    bl_label = 'Add Include'
    bl_description = ''
    bl_options = {'INTERNAL'}

    rule_type: EnumProperty(items=repository_rule_type_enum_items, name='Rule Type')

    @classmethod
    def poll(cls, context):
        return poll_has_repository_package_selected(cls, context)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[repository.runtime.packages_index]

        rule = repository.rules.add()
        rule.repository_id = repository.id
        rule.type = self.rule_type
        rule.pattern = package.path

        repository_metadata_write(repository)
        repository_runtime_packages_update_rule_exclusions(repository)

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_package_blend_open(Operator):
    bl_idname = 'bdk.repository_package_blend_open'
    bl_label = 'Open .blend File'
    bl_description = 'Open the .blend file for the selected package in another Blender instance'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return poll_has_repository_package_selected(cls, context)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[repository.runtime.packages_index]

        # Build the export path.
        context.window_manager.progress_begin(0, 1)

        asset_path = get_repository_package_asset_path(repository, package.path)

        if not asset_path.is_file():
            self.report({'ERROR'}, f'Could not open .blend file. File does not exist.')
            return {'CANCELLED'}

        import subprocess

        subprocess.Popen([bpy.app.binary_path, asset_path])

        return {'FINISHED'}


class BDK_OT_repository_package_cache_invalidate(Operator):
    bl_idname = 'bdk.repository_package_cache_invalidate'
    bl_label = 'Invalidate Package Cache'
    bl_description = 'Invalidate the cache of the selected package. This will mark the package as needing to be ' \
                     'exported and built, but will not delete any files. This action cannot be undone'
    bl_options = {'INTERNAL'}

    index: IntProperty(name='Index', default=-1)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[self.index]

        manifest = Manifest.from_repository(repository)
        manifest.invalidate_package(package.path)
        manifest.write()

        repository_runtime_update(repository)

        return {'FINISHED'}


class BDK_OT_repository_build_asset_library(Operator):
    bl_idname = 'bdk.repository_build_asset_library'
    bl_label = 'Build Asset Library'
    bl_description = 'Export and build all packages in the repository.\n\nDepending on the number of packages, ' \
                     'this may take a while'
    bl_options = {'INTERNAL'}

    max_workers_mode: EnumProperty(
        name='Max Workers',
        items=(
            ('AUTO', 'Auto', 'Automatically determine the number of workers based on the number of CPU cores'),
            ('MANUAL', 'Manual', 'Manually specify the number of workers'),
        )
    )
    max_workers: IntProperty(name='Max Workers', default=8, min=1, soft_max=8)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_addon_preferences(context)
        if len(addon_prefs.repositories) == 0:
            return False
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        count = repository.runtime.need_export_package_count + repository.runtime.need_build_package_count
        if count == 0:
            cls.poll_message_set('All packages are up to date')
            return False
        # TODO: Make sure that the PSK/PSA addon is installed and enabled (and meets version requirements)
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        flow = self.layout
        flow.use_property_split = True
        flow.prop(self, 'max_workers_mode')
        match self.max_workers_mode:
            case 'MANUAL':
                flow.prop(self, 'max_workers', text=' ')
                if self.max_workers > os.cpu_count():
                    flow.label(text='Worker count exceeds CPU core count', icon='ERROR')
            case _:
                pass

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_runtime_update(repository)

        # Find all the packages that need to be exported first.
        packages_to_export = {package for package in repository.runtime.packages if
                              package.status == 'NEEDS_EXPORT' and not package.is_excluded_by_rule}
        packages_to_build = {package for package in repository.runtime.packages if
                             package.status != 'UP_TO_DATE' and not package.is_excluded_by_rule}

        # Get the build order of the packages.
        print('Building package dependency graph')
        time = datetime.now()
        package_dependency_graph = get_repository_package_dependency_graph(repository)
        print(f'Finished building package dependency graph in {datetime.now() - time}')

        print('Determining build order')
        time = datetime.now()
        package_build_levels = layered_topographical_sort(package_dependency_graph)
        print(f'Finished determining build order in {datetime.now() - time}')

        # Map the package names to the package objects.
        package_name_to_package = {os.path.splitext(os.path.basename(package.path))[0].upper(): package for package in
                                   repository.runtime.packages}
        package_name_keys = set(package_name_to_package.keys())

        # Some packages in the build levels may not be in the runtime packages, so we need to filter them out.
        package_build_levels = [level & package_name_keys for level in package_build_levels]

        # Convert the build levels to the package objects.
        package_build_levels = [{package_name_to_package[package_name.upper()] for package_name in level} for level in
                                package_build_levels]

        # Remove the packages that do not need to be built from the build levels.
        for level in package_build_levels:
            level &= packages_to_build

        # Remove any empty levels.
        package_build_levels = [level for level in package_build_levels if level]

        # Convert package_build_levels to a list of path and filename tuples.
        package_build_levels = [[(x.path, os.path.splitext(x.filename)[0]) for x in level] for level in
                                package_build_levels]

        # Count the number of commands that will be executed.
        command_count = len(packages_to_export) + len(packages_to_build)

        if command_count == 0:
            self.report({'INFO'}, 'All packages are up to date')
            return {'CANCELLED'}

        progress = 0
        success_count = 0
        failure_count = 0

        # Ensure that the user preferences are saved before we spawn any Blender processes.
        # The repository data must be present in the preferences during the build process.
        bpy.ops.wm.save_userpref()

        context.window_manager.progress_begin(0, command_count)

        manifest = Manifest.from_repository(repository)

        # TODO: Purge Orphaned Assets should also delete the catalog.

        # Populate the asset catalog.
        # We do this ahead of time to avoid needing to use file locking to make sure that the different Blender
        # processes don't try to write to the same file at the same time.
        # TODO: extract this to a function.
        asset_directory_packages = dict()
        for package in repository.runtime.packages:
            asset_directory = get_repository_package_asset_directory(repository, package.path)
            if asset_directory not in asset_directory_packages:
                asset_directory_packages[asset_directory] = []
            asset_directory_packages[asset_directory].append(package)

        for asset_directory, packages in asset_directory_packages.items():
            catalog_file = AssetCatalogFile(asset_directory)
            for package in packages:
                catalog_path = os.path.splitext(package.path)[0]
                catalog_name = os.path.basename(catalog_path)
                catalog_id = get_repository_package_catalog_id(repository, package.path)
                catalog_file.add_catalog(catalog_name, catalog_path, catalog_id)
            catalog_file.write()

        packages_that_failed_to_export = []

        match self.max_workers_mode:
            case 'AUTO':
                max_workers = os.cpu_count() / 2
            case 'MANUAL':
                max_workers = self.max_workers

        max_workers = max(1, max_workers)

        with ThreadPoolExecutor(max_workers) as executor:
            jobs = []
            for package in packages_to_export:
                jobs.append(executor.submit(repository_package_export, repository, package))
            for future in as_completed(jobs):
                process, package = future.result()
                if process.returncode != 0:
                    failure_count += 1
                    packages_that_failed_to_export.append(package)
                else:
                    manifest.mark_package_as_exported(package.path)
                    success_count += 1
                progress += 1
                context.window_manager.progress_update(progress)

        if failure_count > 0:
            self.report({'ERROR'},
                        f'Failed to export {failure_count} packages. Aborting build step. Check logs for more '
                        f'information.')
            manifest.write()
            repository_runtime_update(repository)
            return {'CANCELLED'}

        # We must write the manifest here because the build step will read from it when linking the assets.
        manifest.write()

        success_count = 0
        failure_count = 0

        for level_index, packages in enumerate(package_build_levels):
            with ThreadPoolExecutor(max_workers=8) as executor:
                jobs = []
                for (package_path, package_filename) in packages:
                    jobs.append(executor.submit(repository_package_build, repository, package_path))
                for future in as_completed(jobs):
                    process, package_path = future.result()
                    if process.returncode != 0:
                        print('Failed to build package:', package_path)
                        failure_count += 1
                    else:
                        manifest.mark_package_as_built(package_path)
                        success_count += 1
                    progress += 1
                    context.window_manager.progress_update(progress)

            manifest.write()
            repository_runtime_update(repository)

        context.window_manager.progress_end()

        if failure_count > 0:
            self.report({'ERROR'}, f'Failed to build {failure_count} packages. Check logs for more information.')
            manifest.write()
            repository_runtime_update(repository)
            return {'CANCELLED'}

        manifest.write()
        repository_runtime_update(repository)

        self.report({'INFO'}, f'Built asset libraries for {success_count} packages.')

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_cache_invalidate(Operator):
    bl_idname = 'bdk.repository_cache_invalidate'
    bl_label = 'Invalidate Cache'
    bl_description = 'Invalidate the repository cache. This action cannot be undone'
    bl_options = {'INTERNAL'}

    mode: EnumProperty(
        name='Mode',
        items=(
            ('ASSETS_ONLY', 'Assets Only', 'Invalidate only the assets cache'),
            ('ALL', 'Exports & Assets', 'Invalidate the export and asset cache'),
        ),
        default='ALL'
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        manifest = Manifest.from_repository(repository)

        match self.mode:
            case 'ASSETS_ONLY':
                for package in repository.runtime.packages:
                    manifest.invalidate_package_assets(package.path)
            case 'ALL':
                for package in repository.runtime.packages:
                    manifest.invalidate_package(package.path)

        manifest.write()

        # Update the runtime information.
        repository_runtime_update(repository)

        tag_redraw_all_windows(context)

        self.report({'INFO'}, 'Repository cache invalidated')

        return {'FINISHED'}


class BDK_OT_repository_link(Operator, ImportHelper):
    bl_idname = 'bdk.repository_link'
    bl_label = 'Link Repository'
    bl_options = {'INTERNAL'}

    filename_ext = '*.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})
    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):

        import json

        with open(self.filepath, 'r') as f:
            try:
                repository_data = json.load(f)
            except json.JSONDecodeError as e:
                self.report({'ERROR'}, f'Failed to load repository file: {e}')
                return {'CANCELLED'}

            required_keys = ['game_directory', 'mod', 'id']
            for key in required_keys:
                if key not in repository_data:
                    self.report({'ERROR'}, f'Invalid repository file (missing key: {key})')
                    return {'CANCELLED'}

            game_directory = Path(repository_data['game_directory'])
            mod = repository_data['mod']
            id_ = repository_data['id']

            # Make sure there isn't already a repository with the same ID.
            addon_prefs = get_addon_preferences(context)
            for repository in addon_prefs.repositories:
                if repository.id == id_:
                    self.report({'ERROR'}, f'A repository with the same ID already exists ({repository.name})')
                    return {'CANCELLED'}

            # Add the repository to the list.
            addon_prefs = get_addon_preferences(context)
            repository = addon_prefs.repositories.add()

            repository.id = id_
            repository.game_directory = str(game_directory)
            repository.mod = mod

            repository_name = game_directory.name
            if mod:
                repository_name += f' ({mod})'
            repository.name = repository_name
            repository.cache_directory = str(Path(self.filepath).parent)

            repository_metadata_read(repository)
            repository_runtime_update(repository)

            addon_prefs.repositories_index = len(addon_prefs.repositories) - 1

            # Add the repository's asset folder as an asset library in Blender.
            ensure_repository_asset_library(context, repository)

            ensure_default_repository_id(context)

            tag_redraw_all_windows(context)

            self.report({'INFO'}, f'Linked repository "{repository.name}"')

        return {'FINISHED'}


class BDK_OT_repository_create(Operator):
    bl_idname = 'bdk.repository_create'
    bl_label = 'Create Repository'
    bl_description = 'Create a new repository'
    bl_options = {'INTERNAL', 'UNDO'}

    game_directory: StringProperty(name='Game Directory', subtype='DIR_PATH', description='The game\'s root directory')
    use_mod: BoolProperty(name='Use Mod', default=False, description='Use a mod directory')
    mod: StringProperty(name='Mod', description='The name of the mod directory, relative to the game directory')
    use_custom_cache_directory: BoolProperty(name='Custom Cache Directory', default=False)
    use_custom_id: BoolProperty(name='Use Custom Identifier', default=False, description='Use a custom identifier for the repository. Do not use this unless you know what you are doing')
    custom_id: StringProperty(name='Custom ID', default='', description='Custom ID for the repository')
    custom_cache_directory: StringProperty(name='Cache Directory', subtype='DIR_PATH')
    use_defaults: BoolProperty(name='Use Defaults', default=True, description='Use default settings for the repository as defined in the bdk-default.json file within the game directory and mod directory')

    def invoke(self, context: Context, event: Event):
        self.custom_id = uuid.uuid4().hex
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow()
        flow.use_property_split = True
        flow.prop(self, 'game_directory')
        flow.prop(self, 'use_defaults')

        mod_header, mod_panel = layout.panel_prop(self, 'use_mod')
        mod_header.prop(self, 'use_mod', text='Mod')
        if mod_panel is not None:
            flow = mod_panel.grid_flow()
            flow.use_property_split = True
            flow.prop(self, 'mod', text='Mod Directory')

        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')
        if advanced_panel is not None:
            custom_id_header, custom_id_panel = advanced_panel.panel_prop(self, 'use_custom_id')
            custom_id_header.prop(self, 'use_custom_id', text='Custom ID')
            if custom_id_panel is not None:
                advanced_panel.prop(self, 'custom_id')

            custom_directory_header, custom_directory_panel = advanced_panel.panel_prop(self, 'use_custom_cache_directory')
            custom_directory_header.prop(self, 'use_custom_cache_directory', text='Custom Cache Directory')

            if custom_directory_panel is not None:
                flow = custom_directory_panel.grid_flow()
                flow.use_property_split = True
                flow.prop(self, 'custom_cache_directory')


    def execute(self, context):
        addon_prefs = get_addon_preferences(context)

        # Determine the name of the repository from the last folder of the game directory and mod.
        game_directory = Path(self.game_directory)

        if not game_directory.is_dir():
            self.report({'ERROR'}, 'Invalid game directory')
            return {'CANCELLED'}

        repository_name = game_directory.name

        mod = self.mod if self.use_mod else ''

        if mod:
            repository_name += f' ({mod})'

        if not is_game_directory_and_mod_valid(self.game_directory, mod):
            self.report({'ERROR'},
                        'Invalid game directory or mode configuration. Please check the values and try again.')
            return {'CANCELLED'}

        repository = addon_prefs.repositories.add()

        # By default, the ID should be generated from the mod name, or the game directory if no mod is specified.
        repository_id = mod if mod else game_directory.name

        if self.use_custom_id:
            repository_id = self.custom_id

        if not repository_id:
            self.report({'ERROR'}, 'Invalid repository ID. Please check the values and try again')
            return {'CANCELLED'}

        repository.id = repository_id
        repository.game_directory = self.game_directory
        repository.mod = mod
        repository.name = repository_name

        # Check for `bdk-repository-default.json` file in the game directory, then the mod directory.
        # These files contain default settings for the repository, and should be applied additively.
        repository_default_file_paths = [
            game_directory / 'bdk-default.json'
        ]
        if mod:
            repository_default_file_paths.append(game_directory / mod / 'bdk-default.json')

        for repository_default_file_paths in repository_default_file_paths:
            if not repository_default_file_paths.is_file():
                continue
            data = json.loads(repository_default_file_paths.read_text())
            repository_data = data.get('repository', None)
            if repository_data is None:
                continue
            if 'rules' in repository_data:
                for rule_data in repository_data['rules']:
                    rule = repository.rules.add()
                    rule.type = rule_data['type']
                    rule.pattern = rule_data['pattern']
                    if 'asset_directory' in rule_data:
                        rule.asset_directory = rule_data['asset_directory']

        # Cache directory.
        cache_directory = game_directory / '.bdk'

        if self.use_custom_cache_directory:
            # Make sure that the custom cache directory exists, throw an error if it can't be created.
            try:
                os.makedirs(self.custom_cache_directory)
            except Exception as e:
                self.report({'ERROR'}, f'Failed to create cache directory: {e}')
                return {'CANCELLED'}
            cache_directory = Path(self.custom_cache_directory)

        repository.cache_directory = str(cache_directory)

        addon_prefs.repositories_index = len(addon_prefs.repositories) - 1

        repository_runtime_update(repository)

        # Create the cache directory.
        repository_cache_directory = get_repository_cache_directory(repository)
        repository_cache_directory.mkdir(parents=True, exist_ok=True)

        repository_metadata_write(repository)
        ensure_repository_asset_library(context, repository)

        ensure_default_repository_id(context)

        # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_unlink(Operator):
    bl_idname = 'bdk.repository_unlink'
    bl_label = 'Unlink Repository'
    bl_description = 'Unlink the selected repository and unlink the asset library. This will not alter the files, and you can re-link the asset library later'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_has_repository_selected(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_asset_library_unlink(context, repository)
        repository_remove(context, addon_prefs.repositories_index)

        tag_redraw_all_windows(context)

        self.report({'INFO'}, f'Unlinked repository "{repository.name}"')

        return {'FINISHED'}


class BDK_OT_repository_delete(Operator):
    bl_idname = 'bdk.repository_delete'
    bl_label = 'Delete Repository...'
    bl_description = 'Remove the selected repository and delete all associated data. This operation cannot be undone'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_has_repository_selected(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_cache_delete(repository)
        repository_asset_library_unlink(context, repository)
        repository_metadata_delete(repository)
        repository_remove(context, addon_prefs.repositories_index)

        self.report({'INFO'}, f'Deleted repository "{repository.name}"')

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_set_default(Operator):
    bl_idname = 'bdk.repository_set_default'
    bl_label = 'Set Default Repository'
    bl_description = 'Set the default repository to use when the addon is loaded'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context: Context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        if addon_prefs.default_repository_id == repository.id:
            cls.poll_message_set('Repository is already the default')
            return False
        return True

    def execute(self, context: Context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        addon_prefs.default_repository_id = repository.id
        self.report({'INFO'}, f'Set default repository to {repository.name}')
        return {'FINISHED'}


class BDK_OT_repository_rule_add(Operator):
    bl_idname = 'bdk.repository_rule_add'
    bl_label = 'Add Repository Rule'
    bl_description = 'Add a rule to the selected repository'
    bl_options = {'INTERNAL', 'UNDO'}

    type: EnumProperty(name='Type', items=repository_rule_type_enum_items)
    pattern: StringProperty(name='Pattern', default='*', options={'SKIP_SAVE'})
    asset_directory: StringProperty(name='Asset Directory', default='', options={'SKIP_SAVE'})

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'type')
        layout.prop(self, 'pattern')

        if self.type == 'SET_ASSET_DIRECTORY':
            layout.prop(self, 'asset_directory')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context):
        return poll_has_repository_selected(context)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        rule = repository.rules.add()
        rule.repository_id = repository.id
        rule.type = self.type
        rule.pattern = self.pattern

        if self.type == 'SET_ASSET_DIRECTORY':
            rule.asset_directory = self.asset_directory

        repository_metadata_write(repository)
        repository_runtime_packages_update_rule_exclusions(repository)

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_rule_move(Operator):
    bl_idname = 'bdk.repository_rule_move'
    bl_label = 'Move Repository Rule'
    bl_description = 'Move the selected rule up or down in the list'
    bl_options = {'INTERNAL', 'UNDO'}

    direction: EnumProperty(name='Direction', items=(
        ('UP', 'Up', ''),
        ('DOWN', 'Down', ''),
    ))

    @classmethod
    def poll(cls, context):
        return poll_has_repository_rule_selected(context)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        if self.direction == 'UP':
            if repository.rules_index > 0:
                repository.rules.move(repository.rules_index, repository.rules_index - 1)
                repository.rules_index -= 1
        elif self.direction == 'DOWN':
            if repository.rules_index < len(repository.rules) - 1:
                repository.rules.move(repository.rules_index, repository.rules_index + 1)
                repository.rules_index += 1

        repository_metadata_write(repository)
        repository_runtime_packages_update_rule_exclusions(repository)

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_rule_remove(Operator):
    bl_idname = 'bdk.repository_rule_remove'
    bl_label = 'Remove Rule'
    bl_description = 'Remove the selected rule'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_has_repository_rule_selected(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository.rules.remove(repository.rules_index)

        repository_metadata_write(repository)
        repository_runtime_packages_update_rule_exclusions(repository)

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_purge_orphaned_assets(Operator):
    bl_idname = 'bdk.repository_purge_orphaned_assets'
    bl_label = 'Purge Orphaned Assets'
    bl_description = 'Purge assets that are no longer associated with any package'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not poll_has_repository_selected(context):
            return False

        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        if len(repository.runtime.orphaned_assets) == 0:
            cls.poll_message_set('No orphaned assets found')
            return False

        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        from .ui import BDK_UL_repository_orphaned_assets

        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        layout = self.layout
        layout.label(text=f'{len(repository.runtime.orphaned_assets)} orphaned assets')
        if len(repository.runtime.orphaned_assets) > 0:
            layout.template_list(BDK_UL_repository_orphaned_assets.bl_idname, '', repository.runtime, 'orphaned_assets',
                                 repository.runtime, 'orphaned_assets_index', rows=3)

    def execute(self, context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        # Create a file name to asset path map, then iterate over all the .blend files in the asset directory, removing
        # any that are not in the map.
        for orphaned_asset in repository.runtime.orphaned_assets:
            asset_file = get_repository_default_asset_library_directory(repository) / orphaned_asset.file_name
            asset_file.unlink(missing_ok=True)

        repository.runtime.orphaned_assets.clear()

        self.report({'INFO'}, f'Purged {len(repository.runtime.orphaned_assets)} orphaned assets')

        return {'FINISHED'}


classes = (
    BDK_OT_repository_scan,
    BDK_OT_repository_cache_delete,
    BDK_OT_repository_package_blend_open,
    BDK_OT_repository_package_build,
    BDK_OT_repository_package_cache_invalidate,
    BDK_OT_repository_rule_package_add,
    BDK_OT_repository_build_asset_library,
    BDK_OT_repository_cache_invalidate,
    BDK_OT_repository_purge_orphaned_assets,
    BDK_OT_repository_link,
    BDK_OT_repository_create,
    BDK_OT_repository_unlink,
    BDK_OT_repository_delete,
    BDK_OT_repository_set_default,
    BDK_OT_repository_rule_add,
    BDK_OT_repository_rule_remove,
    BDK_OT_repository_rule_move,
)
