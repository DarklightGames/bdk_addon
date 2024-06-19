from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import shutil

import bpy.app
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import CollectionProperty, IntProperty, BoolProperty, PointerProperty
from bpy_extras.io_utils import ImportHelper

from .repository.kernel import repository_runtime_update, load_repository_manifest, is_game_directory_and_mod_valid, \
    repository_cache_delete
from .repository.properties import BDK_PG_repository, BDK_PG_repository_package
from .repository.ui import BDK_UL_repositories, BDK_UL_repository_packages, BDK_MT_repository_menu, \
    BDK_MT_repository_add

import uuid
from bpy.props import StringProperty
from bpy.types import Operator, Context, Event

import subprocess
import os


class BDK_OT_repository_init(Operator):
    bl_idname = 'bdk.repository_init'
    bl_label = 'Initialize Repository'

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        return len(addon_prefs.repositories) > 0

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        # selected_repository = addon_prefs.repositories[addon_prefs.repositories_index]
        return {'FINISHED'}


class BDK_OT_repository_scan(Operator):
    bl_idname = 'bdk.repository_scan'
    bl_label = 'Scan Repository'
    bl_description = 'Scan the repository and update the status of each package.'

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        return len(addon_prefs.repositories) > 0

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        # Update the runtime information.
        try:
            repository_runtime_update(repository)
        except Exception as e:
            self.report({'ERROR'}, f'Failed to scan repository: {e}')
            return {'CANCELLED'}

        return {'FINISHED'}


class BDK_OT_repository_cache_delete(Operator):
    bl_idname = 'bdk.repository_cache_delete'
    bl_label = 'Delete Cache'
    bl_description = 'Delete the repository cache. This will delete all exports, assets and the manifest. This action cannot be undone'

    def invoke(self, context, event):
        # TODO: probably want a more frightening warning.
        return context.window_manager.invoke_confirm(self, event)

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        return len(addon_prefs.repositories) > 0

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_cache_delete(repository)
        repository_runtime_update(repository)

        return {'FINISHED'}


class BDK_OT_repository_build_asset_library(Operator):
    bl_idname = 'bdk.repository_build_asset_library'
    bl_label = 'Build Asset Library'
    bl_description = 'Export and build all packages in the repository.\n\nDepending on the number of packages, this may take a while'

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        return len(addon_prefs.repositories) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_runtime_update(repository)

        # Find all the packages that need to be exported first.
        packages_to_export = [package for package in repository.runtime.packages if package.status == 'NEEDS_EXPORT']
        packages_to_build = [package for package in repository.runtime.packages if package.status != 'UP_TO_DATE']

        # Count the number of commands that will be executed.
        command_count = len(packages_to_export) + len(packages_to_build)

        if command_count == 0:
            self.report({'INFO'}, 'All packages are up to date')
            return {'CANCELLED'}

        progress = 0
        success_count = 0
        failure_count = 0

        context.window_manager.progress_begin(0, command_count)

        manifest = load_repository_manifest(repository)

        with ThreadPoolExecutor(max_workers=8) as executor:
            jobs = []
            for package in packages_to_export:
                jobs.append(executor.submit(repository_package_export, repository, package))
            for future in as_completed(jobs):
                process, package = future.result()
                if process.returncode != 0:
                    failure_count += 1
                    print(process.stdout.decode())
                else:
                    manifest.mark_package_as_exported(package.path)
                    success_count += 1
                progress += 1
                context.window_manager.progress_update(progress)

        if failure_count > 0:
            self.report({'ERROR'}, f'Failed to export {failure_count} packages. Aborting build step. Check the console for error information.')
            # TODO: just have the manifest object keep track of the path.
            manifest.write(Path(repository.cache_directory) / repository.id / 'manifest.json')
            repository_runtime_update(repository)
            return {'CANCELLED'}

        # We must write the manifest here because the build step will read from it when linking the assets.
        manifest.write(Path(repository.cache_directory) / repository.id / 'manifest.json')

        # Find all the packages that need to be built.
        # TODO: the build order is important, figure out a way to determine the order.
        #  In a perfect world, we would have a dependency graph.
        success_count = 0
        failure_count = 0

        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs = []
            for package in packages_to_build:
                jobs.append(executor.submit(repository_package_build, repository, package))
            for future in as_completed(jobs):
                process, package = future.result()
                if process.returncode != 0:
                    failure_count += 1
                else:
                    manifest.mark_package_as_built(package.path)
                    success_count += 1

                progress += 1
                context.window_manager.progress_update(progress)

        context.window_manager.progress_end()

        if failure_count > 0:
            self.report({'ERROR'}, f'Failed to build {failure_count} packages. Check the console for error information.')
            manifest.write(Path(repository.cache_directory) / repository.id / 'manifest.json')
            repository_runtime_update(repository)
            return {'CANCELLED'}

        manifest.write(Path(repository.cache_directory) / repository.id / 'manifest.json')

        repository_runtime_update(repository)

        self.report({'INFO'}, f'Built asset libraries for {success_count} packages, {failure_count} failed')

        tag_redraw_all_windows(context)

        return {'FINISHED'}


# Operator that allows the user to point to a `manifest.json` file and add the repository to the list.
def repository_asset_library_add(context, repository):
    assets_directory = Path(repository.cache_directory) / repository.id / 'assets'
    context.preferences.filepaths.asset_libraries.new(
        name=repository.name,
        directory=str(assets_directory)
    )

def tag_redraw_all_windows(context):
    for region in filter(lambda r: r.type == 'WINDOW', context.area.regions):
        region.tag_redraw()


class BDK_OT_repository_cache_invalidate(Operator):
    bl_idname = 'bdk.repository_cache_invalidate'
    bl_label = 'Invalidate Cache'
    bl_description = 'Invalidate the cache of the repository. This will mark all packages as needing to be exported and built, but will not delete any files. This action cannot be undone'

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        # Delete the manifest file.
        manifest_path = Path(repository.cache_directory) / repository.id / 'manifest.json'
        if manifest_path.exists():
            manifest_path.unlink()

        # Update the runtime information.
        repository_runtime_update(repository)

        tag_redraw_all_windows(context)

        self.report({'INFO'}, 'Repository cache invalidated')

        return {'FINISHED'}


class BDK_OT_repository_add_existing(Operator, ImportHelper):
    bl_idname = 'bdk.repository_add_existing'
    bl_label = 'Add Existing Repository'

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
            id = repository_data['id']

            # Make sure there isn't already a repository with the same ID.
            addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
            for repository in addon_prefs.repositories:
                if repository.id == id:
                    self.report({'ERROR'}, f'A repository with the same ID already exists ({repository.name})')
                    return {'CANCELLED'}

            # Add the repository to the list.
            addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
            repository = addon_prefs.repositories.add()

            repository.id = id
            repository.game_directory = str(game_directory)
            repository.mod = mod

            repository_name = game_directory.name
            if mod:
                repository_name += f' ({self.mod})'
            repository.name = repository_name

            # TODO: making an assumption that the name of the folder matches the ID for now, double check this.
            repository.cache_directory = str(Path(self.filepath).parent.parent)

            repository_runtime_update(repository)

            addon_prefs.repositories_index = len(addon_prefs.repositories) - 1

            # Add the repository's asset folder as an asset library in Blender.
            repository_asset_library_add(context, repository)

            tag_redraw_all_windows(context)

            self.report({'INFO'}, f'Added repository "{repository.name}"')

        return {'FINISHED'}


class BDK_OT_repository_add(Operator):
    bl_idname = 'bdk.repository_add'
    bl_label = 'Add New Repository'

    game_directory: StringProperty(name='Game Directory', subtype='DIR_PATH', description='The game\'s root directory')
    mod: StringProperty(name='Mod', description='The name of the mod directory (optional)')
    use_custom_cache_directory: BoolProperty(name='Custom Cache Directory', default=False)
    custom_cache_directory: StringProperty(name='Cache Directory', subtype='DIR_PATH')

    def invoke(self, context: Context, event: Event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow()
        flow.use_property_split = True
        flow.prop(self, 'game_directory')
        flow.prop(self, 'mod')

        custom_directory_header, custom_directory_panel = layout.panel_prop(self, 'use_custom_cache_directory')
        custom_directory_header.prop(self, 'use_custom_cache_directory', text='Custom Cache Directory')

        if custom_directory_panel is not None:
            flow = custom_directory_panel.grid_flow()
            flow.use_property_split = True
            flow.prop(self, 'custom_cache_directory')

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences

        # Determine the name of the repository from the last folder of the game directory and mod.
        game_directory = Path(self.game_directory)

        if not game_directory.is_dir():
            self.report({'ERROR'}, 'Invalid game directory')
            return {'CANCELLED'}

        repository_name = game_directory.name
        if self.mod:
            repository_name += f' ({self.mod})'

        if not is_game_directory_and_mod_valid(self.game_directory, self.mod):
            self.report({'ERROR'}, 'Invalid game directory or mode configuration. Please check the values and try again.')
            return {'CANCELLED'}

        repository = addon_prefs.repositories.add()
        repository.id = uuid.uuid4().hex
        repository.game_directory = self.game_directory
        repository.mod = self.mod
        repository.name = repository_name

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
        repository_cache_directory = Path(repository.cache_directory) / repository.id
        repository_cache_directory.mkdir(parents=True, exist_ok=True)

        # Write a repository.json file with the bare-bones information for recovery.
        import json
        with open(repository_cache_directory / 'repository.json', 'w') as f:
            data = {
                'id': repository.id,
                'game_directory': self.game_directory,
                'mod': self.mod,
            }
            json.dump(data, f, indent=2)

        repository_asset_library_add(context, repository)

        # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
        tag_redraw_all_windows(context)

        return {'FINISHED'}


def repository_asset_library_unlink(context, repository) -> int:
    removed_count = 0
    repository_asset_library_path = str((Path(repository.cache_directory) / repository.id / 'assets').resolve())
    for asset_library in context.preferences.filepaths.asset_libraries:
        if str(Path(asset_library.path).resolve()) == repository_asset_library_path:
            context.preferences.filepaths.asset_libraries.remove(asset_library)
            removed_count += 1
    return removed_count


class BDK_OT_repository_remove(Operator):
    bl_idname = 'bdk.repository_remove'
    bl_label = 'Remove Repository'
    bl_description = 'Remove the selected repository from the list'

    should_delete_cache: BoolProperty(name='Delete Cache From Disk', default=True, description='Delete the repository cache from disk. This action cannot be undone')
    should_unlink_asset_library: BoolProperty(name='Unlink Asset Library', default=True, description='Remove the asset library from Blender')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'should_delete_cache')

        row = layout.row()
        row.enabled = not self.should_delete_cache
        row.prop(self, 'should_unlink_asset_library')

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        if self.should_delete_cache:
            repository_cache_delete(repository)

        if self.should_unlink_asset_library:
            asset_libraries_removed = repository_asset_library_unlink(context, repository)

        addon_prefs.repositories.remove(addon_prefs.repositories_index)
        addon_prefs.repositories_index = min(addon_prefs.repositories_index, len(addon_prefs.repositories) - 1)

        self.report({'INFO'}, f'Removed repository. Unlinked {asset_libraries_removed} asset libraries.')

        tag_redraw_all_windows(context)

        return {'FINISHED'}


def get_addon_path() -> Path:
    import addon_utils
    import os

    for module in addon_utils.modules():
        if module.__name__ == BdkAddonPreferences.bl_idname:
            return Path(os.path.dirname(module.__file__))

    raise RuntimeError('Could not find addon path')

def get_umodel_path() -> Path:
    return get_addon_path() / 'bin' / 'umodel.exe'


def repository_package_export(repository: BDK_PG_repository, package: BDK_PG_repository_package):
    cache_directory = Path(repository.cache_directory).resolve()
    game_directory = Path(repository.game_directory).resolve()
    exports_directory = cache_directory / repository.id / 'exports'
    package_path = game_directory / package.path
    package_build_directory = os.path.join(str(exports_directory), os.path.dirname(os.path.relpath(str(package_path), str(game_directory))))
    umodel_path = str(get_umodel_path())
    args = [umodel_path, '-export', '-nolinked', f'-out="{package_build_directory}"', f'-path="{repository.game_directory}"', str(package_path)]

    process = subprocess.run(args, capture_output=True)

    return (process, package)


def repository_package_build(repository: BDK_PG_repository, package: BDK_PG_repository_package):
    # TODO: do not allow this if the package is not up-to-date.
    script_path = get_addon_path() / 'bin' / 'blend.py'
    cache_directory = Path(repository.cache_directory).resolve()
    input_directory = cache_directory / repository.id / 'exports' / os.path.splitext(package.path)[0]
    output_path = cache_directory / repository.id / 'assets' / f'{package.filename}.blend'
    args = [
        bpy.app.binary_path, '--background', '--python', str(script_path), '--',
        'build', str(input_directory), '--output_path', str(output_path)
    ]

    process = subprocess.run(args, capture_output=True)

    log_directory = Path(repository.cache_directory) / repository.id / 'assets' / 'logs'
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f'{package.filename}.log'

    with open(str(log_path), 'w') as f:
        f.write('=' * 80 + '\n')
        f.write('stdout\n')
        f.write('=' * 80 + '\n\n')
        f.write(process.stdout.decode())
        f.write('\n')

        f.write('=' * 80 + '\n')
        f.write('stderr\n')
        f.write('=' * 80 + '\n\n')
        f.write(process.stderr.decode())

    return process, package


class BDK_OT_repository_package_build(Operator):
    bl_idname = 'bdk.repository_package_build'
    bl_label = 'Build Package'

    index: IntProperty(name='Index', default=-1)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        # TODO: don't allow this operator to run unless all dependencies are built.
        package = repository.runtime.packages[self.index]
        process, _ = repository_package_build(repository, package)

        if process.returncode != 0:
            self.report({'ERROR'}, f'Failed to build package: {package.path}')
            return {'CANCELLED'}

        # Update the manifest.
        manifest = load_repository_manifest(repository)
        manifest.mark_package_as_built(package.path)
        manifest.write(Path(repository.cache_directory) / repository.id / 'manifest.json')

        # Update the runtime information.
        repository_runtime_update(repository)

        tag_redraw_all_windows(context)

        return {'FINISHED'}


class BDK_OT_repository_packages_export(Operator):
    bl_idname = 'bdk.repository_packages_export'
    bl_label = 'Export Packages'

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        context.window_manager.progress_begin(0, len(repository.runtime.packages))

        success_count = 0
        failure_count = 0

        manifest = load_repository_manifest(repository)

        jobs = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            for package in repository.runtime.packages:
                jobs.append(executor.submit(repository_package_export, repository, package))

            count = 0
            for future in as_completed(jobs):
                context.window_manager.progress_update(count)
                process, package = future.result()
                succeeded = process.returncode == 0
                if succeeded:
                    # Update the manifest.
                    manifest.mark_package_as_exported(package.path)
                    success_count += 1
                else:
                    failure_count += 1
                count += 1

        manifest.write(Path(repository.cache_directory) / repository.id / 'manifest.json')

        context.window_manager.progress_end()

        # Update the runtime information.
        repository_runtime_update(repository)

        self.report({'INFO'}, f'Exported {success_count} packages, {failure_count} failed')

        return {'FINISHED'}


class BDK_OT_repository_package_export(Operator):
    bl_idname = 'bdk.repository_package_export'
    bl_label = 'Export Package'

    index: IntProperty(name='Index', default=-1)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[self.index]

        # Build the export path.
        context.window_manager.progress_begin(0, 1)
        process, _ = repository_package_export(repository, package)

        if process.returncode != 0:
            self.report({'ERROR'}, f'Failed to export package: {package.path}')
            return {'CANCELLED'}
        else:
            context.window_manager.progress_update(1)

        context.window_manager.progress_end()

        # Update the runtime information.
        repository_runtime_update(repository)

        return {'FINISHED'}

class BDK_OT_check_umodel(Operator):
    bl_idname = 'bdk.check_umodel'
    bl_label = 'Check UModel'

    def execute(self, context):
        # Get this addon's directory using addon_utils.
        # This is the directory where the UModel executable should be located.
        umodel_path = get_umodel_path()

        import subprocess
        p = subprocess.run([str(umodel_path), '-version'], capture_output=True)

        preferences = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        preferences.runtime.umodel_status.status_code = p.returncode
        preferences.runtime.umodel_status.version_output = p.stdout.decode()

        return {'FINISHED'}


class BDK_PG_umodel_status(PropertyGroup):
    status_code: IntProperty(name='Status Code', default=0, options={'SKIP_SAVE'})
    version_output: StringProperty(default='', options={'SKIP_SAVE'})


class BDK_PG_preferences_runtime(PropertyGroup):
    umodel_status: PointerProperty(type=BDK_PG_umodel_status, options={'SKIP_SAVE'})


class BdkAddonPreferences(AddonPreferences):
    # NOTE: bl_idname is overridden in the __init__.py file.
    # This is because it has access to the correct __package__ value.
    bl_idname = 'bdk_addon'

    repositories: CollectionProperty(type=BDK_PG_repository)
    repositories_index: IntProperty()

    runtime: PointerProperty(type=BDK_PG_preferences_runtime, options={'SKIP_SAVE'})

    developer_extras: BoolProperty(name='Developer Extras', default=False,
                                   description='Enable developer extras such as debug panels and operators')

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, 'developer_extras')

        repositories_header, repositories_panel = layout.panel('Repositories', default_closed=False)
        repositories_header.label(text='Repositories')

        if repositories_panel is not None:
            row = repositories_panel.row()
            row.column().template_list(BDK_UL_repositories.bl_idname, '', self, 'repositories', self,
                                       'repositories_index', rows=3)
            col = row.column(align=True)
            col.menu(BDK_MT_repository_add.bl_idname, icon='ADD', text='')
            col.operator(BDK_OT_repository_remove.bl_idname, icon='REMOVE', text='')

            repository = self.repositories[
                self.repositories_index] if self.repositories_index >= 0 and self.repositories_index < len(
                self.repositories) else None

            if repository is not None:
                repository_header, repository_panel = repositories_panel.panel('Repository', default_closed=False)
                repository_header.label(text='Repository')

                if repository_panel is not None:
                    col = repository_panel.column()
                    col.enabled = False
                    col.use_property_split = True
                    col.prop(repository, 'id', emboss=False)
                    col.prop(repository, 'game_directory')
                    if repository.mod:
                        col.prop(repository, 'mod', emboss=False)
                    col.prop(repository, 'cache_directory')

                    # If we have not yet scanned the repository, we need to present the user with a button to scan it.
                    if repository.runtime.has_been_scanned:
                        row = repository_panel.row()
                        row.alignment = 'RIGHT'
                        row.label(text=f'{repository.runtime.up_to_date_package_count}', icon='CHECKMARK')
                        row.label(text=f'{repository.runtime.need_export_package_count + repository.runtime.need_build_package_count}', icon='TIME')

                        row = repository_panel.row()
                        row.column().template_list(BDK_UL_repository_packages.bl_idname, '',
                                                   repository.runtime, 'packages',
                                                   repository.runtime, 'packages_index',
                                                   rows=3)

                        col = row.column(align=True)

                        col.operator(BDK_OT_repository_scan.bl_idname, icon='FILE_REFRESH', text='')
                        col.separator()
                        col.operator(BDK_OT_repository_build_asset_library.bl_idname, icon='ASSET_MANAGER', text='')
                        col.separator()
                        col.menu(BDK_MT_repository_menu.bl_idname, icon='DOWNARROW_HLT', text='')

                        if repository.runtime.packages_index >= 0:
                            package_header, package_panel = repository_panel.panel('Package', default_closed=True)

                            package = repository.runtime.packages[repository.runtime.packages_index]

                            package_header.label(text='Package')

                            if package_panel is not None:
                                flow = package_panel.grid_flow(columns=2, row_major=True)
                                flow.label(text='Path')
                                flow.label(text=package.path)
                                flow.label(text='Modified Time')
                                flow.label(text=datetime.fromtimestamp(package.modified_time).isoformat())
                                flow.label(text='Exported Time')
                                flow.label(text=datetime.fromtimestamp(package.exported_time).isoformat() if package.exported_time > 0 else 'N/A')
                                flow.label(text='Build Time')
                                flow.label(text=datetime.fromtimestamp(package.build_time).isoformat() if package.build_time > 0 else 'N/A')

                                op = package_panel.operator(BDK_OT_repository_package_build.bl_idname, icon='ASSET_MANAGER')
                                op.index = repository.runtime.packages_index

                    else:
                        repository_panel.operator(BDK_OT_repository_scan.bl_idname, icon='FILE_REFRESH', text='Scan')

        if self.developer_extras:
            debug_header, debug_panel = layout.panel('Debug', default_closed=True)
            debug_header.label(text='Debug')

            if debug_panel is not None:
                debug_panel.operator(BDK_OT_check_umodel.bl_idname, text='Check UModel')

                lines = self.runtime.umodel_status.version_output.split('\n')
                for line in lines:
                    debug_panel.label(text=line)


classes = (
    BDK_PG_umodel_status,
    BDK_PG_preferences_runtime,
    BDK_OT_repository_package_export,
    BDK_OT_repository_packages_export,
    BDK_OT_repository_package_build,
    BDK_OT_repository_build_asset_library,
    BDK_OT_repository_cache_invalidate,
    BDK_OT_repository_cache_delete,
    BDK_OT_repository_scan,
    BDK_OT_repository_add,
    BDK_OT_repository_add_existing,
    BDK_OT_repository_remove,
    BDK_OT_check_umodel,
    BdkAddonPreferences,
)
