import pprint
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import json

import bpy.app
import networkx
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import CollectionProperty, IntProperty, BoolProperty, PointerProperty
from bpy_extras.io_utils import ImportHelper

from .repository.kernel import repository_runtime_update, load_repository_manifest, is_game_directory_and_mod_valid, \
    repository_cache_delete
from .repository.properties import BDK_PG_repository, BDK_PG_repository_package
from .repository.ui import BDK_UL_repositories, BDK_UL_repository_packages, BDK_MT_repository_special, \
    BDK_MT_repository_add, BDK_MT_repository_remove

import uuid
from bpy.props import StringProperty
from bpy.types import Operator, Context, Event

import subprocess
import os

from ..data import UReference


class BDK_OT_repository_scan(Operator):
    bl_idname = 'bdk.repository_scan'
    bl_label = 'Scan Repository'
    bl_description = 'Scan the repository and update the status of each package'
    bl_options = {'INTERNAL'}

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
    bl_options = {'INTERNAL'}

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


def get_repository_package_dependency_graph(repository: BDK_PG_repository) -> networkx.DiGraph:
    """
    Returns the build order of the packages in the repository, as well as any cycles that are detected.
    Note that cycles are removed from the graph by severing all the edges that create the cycle.
    Note that the names of the packages are converted to uppercase for comparison since Unreal packages (and all names
    in Unreal) are case-insensitive.
    """
    from ..package.reader import get_package_dependencies
    import networkx

    graph = networkx.DiGraph()

    for package in repository.runtime.packages:
        package_name = os.path.splitext(os.path.basename(package.path))[0].upper()
        graph.add_node(package_name)

    for package in repository.runtime.packages:
        package_name = os.path.splitext(os.path.basename(package.path))[0].upper()
        package_path = Path(repository.game_directory) / package.path
        # TODO: Reading these from the packages is expensive, especially with lots of packages. We should cache this
        #  information in the manifest.
        dependencies = get_package_dependencies(str(package_path))
        for dependency in dependencies:
            dependency = dependency.upper()
            graph.add_edge(package_name, dependency)

    # Find any cycles in the graph and remove them.
    cycles = list(networkx.simple_cycles(graph))
    edges = set()
    for cycle in cycles:
        edges |= set([(cycle[i], cycle[i + 1]) for i in range(len(cycle) - 1)] + [(cycle[-1], cycle[0])])
    for u, v in edges:
        graph.remove_edge(u, v)

    return graph


def _get_build_order_from_package_dependency_graph(repository: BDK_PG_repository, graph: networkx.DiGraph) -> list[BDK_PG_repository_package]:
    topographical_order = list(reversed(list(networkx.topological_sort(graph))))

    # Create a dictionary of case-insensitive package names to the package objects.
    package_name_to_package = {os.path.splitext(os.path.basename(package.path))[0].upper(): package for package in repository.runtime.packages}

    return [package_name_to_package[package_name.upper()] for package_name in topographical_order]


class BDK_OT_repository_packages_set_enabled_by_pattern(Operator):
    bl_idname = 'bdk.repository_packages_set_enabled_by_pattern'
    bl_label = 'Set Enabled By Pattern'
    bl_options = {'INTERNAL'}

    pattern: StringProperty(name='Pattern', default='*')
    is_enabled: BoolProperty(name='Is Enabled', default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'pattern')
        layout.prop(self, 'is_enabled')

    def execute(self, context):
        import fnmatch
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        manifest = load_repository_manifest(repository)

        count = 0
        for package in repository.runtime.packages:
            if fnmatch.fnmatch(os.path.basename(package.path), self.pattern):
                manifest.set_package_enabled(package.path, self.is_enabled)
                count += 1

        manifest.write()

        repository_runtime_update(repository)

        if count == 0:
            self.report({'INFO'}, 'No packages matched the pattern')
            return {'CANCELLED'}

        if self.is_enabled:
            self.report({'INFO'}, f'{count} packages have been enabled')
        else:
            self.report({'INFO'}, f'{count} packages have been disabled')

        return {'FINISHED'}


def layered_topographical_sort(graph: networkx.DiGraph) -> list[set]:
    # Compute out-degree for each node.
    out_degree = {node: graph.out_degree(node) for node in graph.nodes()}

    # Find nodes with zero out-degree.
    zero_out_degree = [node for node in out_degree if out_degree[node] == 0]

    levels = defaultdict(set)
    level = 0

    while zero_out_degree:
        next_zero_out_degree = []
        for node in zero_out_degree:
            levels[level].add(node)
            for predecessor in graph.predecessors(node):
                out_degree[predecessor] -= 1
                if out_degree[predecessor] == 0:
                    next_zero_out_degree.append(predecessor)
        zero_out_degree = next_zero_out_degree
        level += 1

    return [levels[level] for level in range(level)]


class BDK_OT_repository_package_build(Operator):
    bl_idname = 'bdk.repository_package_build'
    bl_label = 'Build Package'
    bl_description = 'Build the selected package'
    bl_options = {'INTERNAL'}

    index: IntProperty(name='Index', default=-1)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[self.index]

        # Build the export path.
        context.window_manager.progress_begin(0, 1)
        process, _ = repository_package_build(repository, package.path, package.filename)

        if process.returncode != 0:
            self.report({'ERROR'}, f'Failed to build package: {package.path}')
            return {'CANCELLED'}
        else:
            context.window_manager.progress_update(1)

        context.window_manager.progress_end()

        # Update the runtime information.
        repository_runtime_update(repository)

        return {'FINISHED'}


class BDK_OT_repository_package_cache_invalidate(Operator):
    bl_idname = 'bdk.repository_package_cache_invalidate'
    bl_label = 'Invalidate Package Cache'
    bl_description = 'Invalidate the cache of the selected package. This will mark the package as needing to be exported and built, but will not delete any files. This action cannot be undone'
    bl_options = {'INTERNAL'}

    index: IntProperty(name='Index', default=-1)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        package = repository.runtime.packages[self.index]

        manifest = load_repository_manifest(repository)
        manifest.invalidate_package_cache(package.path)
        manifest.write()

        repository_runtime_update(repository)

        return {'FINISHED'}

class BDK_OT_repository_build_asset_library(Operator):
    bl_idname = 'bdk.repository_build_asset_library'
    bl_label = 'Build Asset Library'
    bl_description = 'Export and build all packages in the repository.\n\nDepending on the number of packages, this may take a while'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        if len(addon_prefs.repositories) > 0:
            return False
        repository = addon_prefs.repositories[addon_prefs.repositories_index]
        count = repository.runtime.need_export_package_count + repository.runtime.need_build_package_count
        if count == 0:
            cls.poll_message_set('All packages are up to date')
            return False
        return True


    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        # Write the enabled status of the packages to the manifest.
        manifest = load_repository_manifest(repository)
        for package in repository.runtime.packages:
            manifest.set_package_enabled(package.path, package.is_enabled)
        manifest.write()

        repository_runtime_update(repository)

        # Find all the packages that need to be exported first.
        packages_to_export = {package for package in repository.runtime.packages if package.status == 'NEEDS_EXPORT' and package.is_enabled}
        packages_to_build = {package for package in repository.runtime.packages if package.status != 'UP_TO_DATE' and package.is_enabled}

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
        package_name_to_package = {os.path.splitext(os.path.basename(package.path))[0].upper(): package for package in repository.runtime.packages}
        package_name_keys = set(package_name_to_package.keys())

        # Some packages in the build levels may not be in the runtime packages, so we need to filter them out.
        package_build_levels = [level & package_name_keys for level in package_build_levels]

        # Convert the build levels to the package objects.
        package_build_levels = [{package_name_to_package[package_name.upper()] for package_name in level} for level in package_build_levels]

        # Remove the packages that do not need to be built from the build levels.
        for level in package_build_levels:
            level &= packages_to_build

        # Remove any empty levels.
        package_build_levels = [level for level in package_build_levels if level]

        # Convert package_build_levels to a list of path and filename tuples.
        package_build_levels = [[(x.path, x.filename) for x in level] for level in package_build_levels]

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

        packages_that_failed_to_export = []

        with ThreadPoolExecutor(max_workers=8) as executor:
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
            self.report({'ERROR'}, f'Failed to export {failure_count} packages. Aborting build step. Check the console for error information.')
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
                    jobs.append(executor.submit(repository_package_build, repository, package_path, package_filename))
                for future in as_completed(jobs):
                    process, package_path = future.result()
                    if process.returncode != 0:
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
            self.report({'ERROR'}, f'Failed to build {failure_count} packages. Check the console for error information.')
            manifest.write()
            repository_runtime_update(repository)
            return {'CANCELLED'}

        manifest.write()
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
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        manifest = load_repository_manifest(repository)

        for package in repository.runtime.packages:
            manifest.invalidate_package_cache(package.path)

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
                repository_name += f' ({mod})'
            repository.name = repository_name
            repository.cache_directory = str(Path(self.filepath).parent)

            repository_runtime_update(repository)

            addon_prefs.repositories_index = len(addon_prefs.repositories) - 1

            # Add the repository's asset folder as an asset library in Blender.
            repository_asset_library_add(context, repository)

            tag_redraw_all_windows(context)

            self.report({'INFO'}, f'Linked repository "{repository.name}"')

        return {'FINISHED'}


class BDK_OT_repository_create(Operator):
    bl_idname = 'bdk.repository_create'
    bl_label = 'Create Repository'
    bl_description = 'Create a new repository'
    bl_options = {'INTERNAL', 'UNDO'}

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
        with open(Path(repository.cache_directory) / f'{repository.id}.json', 'w') as f:
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


def repository_metadata_delete(repository):
     repository_metadata_file = (Path(repository.cache_directory) / f'{repository.id}.id').resolve()
     if repository_metadata_file.exists():
         repository_metadata_file.unlink()


def poll_has_repository_selected(context):
    addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
    return (len(addon_prefs.repositories) > 0 and
            addon_prefs.repositories_index >= 0 and
            addon_prefs.repositories_index < len(addon_prefs.repositories))


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
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_asset_library_unlink(context, repository)

        addon_prefs.repositories.remove(addon_prefs.repositories_index)
        addon_prefs.repositories_index = min(addon_prefs.repositories_index, len(addon_prefs.repositories) - 1)

        tag_redraw_all_windows(context)

        self.report({'INFO'}, f'Unlinked repository "{repository.name}"')

        return {'FINISHED'}


class BDK_OT_repository_delete(Operator):
    bl_idname = 'bdk.repository_delete'
    bl_label = 'Delete Repository'
    bl_description = 'Remove the selected repository and delete all associated data. This operation cannot be undone'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_has_repository_selected(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        repository_cache_delete(repository)
        repository_asset_library_unlink(context, repository)
        repository_metadata_delete(repository)

        addon_prefs.repositories.remove(addon_prefs.repositories_index)
        addon_prefs.repositories_index = min(addon_prefs.repositories_index, len(addon_prefs.repositories) - 1)

        self.report({'INFO'}, f'Deleted repository "{repository.name}"')

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


def build_cubemap(cubemap_file_path: Path, exports_directory: Path):
    import re
    with open(cubemap_file_path, 'r') as f:
        contents = f.read()
        textures = re.findall(r'Faces\[\d] = ([\w\d]+\'[\w\d_\-.]+\')', contents)
        face_paths: list[Path] = []
        for texture in textures:
            face_reference = UReference.from_string(texture)
            image_path = exports_directory / face_reference.type_name / f'{face_reference.object_name}.tga'
            face_paths.append(image_path)
        pprint.pprint(face_paths)
        output_path = cubemap_file_path.parent / cubemap_file_path.name.replace('.props.txt', '.png')
        print(output_path)
        cube2sphere_blend_path = get_addon_path() / 'bin' / 'cube2sphere.blend'
        cube2sphere_script_path = get_addon_path() / 'bin' / 'cube2sphere.py'
        args = [
            bpy.app.binary_path,
            cube2sphere_blend_path,
            '--background',
            '--python',
            cube2sphere_script_path,
            '--'
        ]
        args.extend([str(face_path) for face_path in face_paths])
        args.extend(['--output', str(output_path)])
        process = subprocess.run(args, capture_output=True)
        print(process.stdout.decode())
        return process, output_path


def write_process_log_to_file(process: subprocess.CompletedProcess, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'w') as f:
        f.write('=' * 80 + '\n')
        f.write('stdout\n')
        f.write('=' * 80 + '\n\n')
        try:
            f.write(process.stdout.decode())
        except UnicodeDecodeError:
            f.write('Failed to decode stdout')
        f.write('\n')

        f.write('=' * 80 + '\n')
        f.write('stderr\n')
        f.write('=' * 80 + '\n\n')
        try:
            f.write(process.stderr.decode())
        except UnicodeDecodeError:
            f.write('Failed to decode stderr')


def repository_package_export(repository: BDK_PG_repository, package: BDK_PG_repository_package):
    cache_directory = Path(repository.cache_directory).resolve()
    game_directory = Path(repository.game_directory).resolve()
    exports_directory = cache_directory / repository.id / 'exports'
    package_path = game_directory / package.path
    package_build_directory = os.path.join(str(exports_directory), os.path.dirname(os.path.relpath(str(package_path), str(game_directory))))
    umodel_path = str(get_umodel_path())
    args = [umodel_path, '-export', '-nolinked', f'-out="{package_build_directory}"', f'-path="{repository.game_directory}"', str(package_path)]
    process = subprocess.run(args, capture_output=True)

    log_directory = Path(repository.cache_directory) / repository.id / 'exports' / 'logs' / f'{package_path.stem}.log'
    write_process_log_to_file(process, log_directory)

    # Build any cube maps that were exported.
    cubemap_file_paths = []

    package_exports_directory = Path(package_build_directory) / os.path.splitext(package.filename)[0]

    print(package_exports_directory)

    for cubemap_file_path in Path(package_exports_directory).glob('**/Cubemap/*.props.txt'):
        cubemap_file_paths.append(cubemap_file_path)

    print(f'Building {len(cubemap_file_paths)} cubemaps')
    for cubemap_file_path in cubemap_file_paths:
        process, output = build_cubemap(cubemap_file_path, package_exports_directory)

    return (process, package)


def repository_package_build(repository: BDK_PG_repository, package_path: str, package_filename: str):
    # TODO: do not allow this if the package is not up-to-date.
    script_path = get_addon_path() / 'bin' / 'blend.py'
    cache_directory = Path(repository.cache_directory).resolve()
    input_directory = cache_directory / repository.id / 'exports' / os.path.splitext(package_path)[0]
    output_path = cache_directory / repository.id / 'assets' / f'{package_filename}.blend'
    args = [
        bpy.app.binary_path, '--background', '--python', str(script_path), '--',
        'build', str(input_directory), repository.id, '--output_path', str(output_path)
    ]

    process = subprocess.run(args, capture_output=True)

    log_directory = Path(repository.cache_directory) / repository.id / 'assets' / 'logs'
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f'{package_filename}.log'

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

    return process, package_path


class BDK_PG_preferences_runtime(PropertyGroup):
    pass


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
            col.menu(BDK_MT_repository_remove.bl_idname, icon='REMOVE', text='')
            col.separator()
            col.operator(BDK_OT_scene_repository_set.bl_idname, icon='SCENE_DATA', text='')

            repository = self.repositories[
                self.repositories_index] if self.repositories_index >= 0 and self.repositories_index < len(
                self.repositories) else None

            if repository is not None:
                repository_header, repository_panel = repositories_panel.panel('Repository', default_closed=False)
                repository_header.label(text='Repository')

                if repository_panel is not None:

                    paths_header, paths_panel = repository_panel.panel('Paths', default_closed=True)
                    paths_header.label(text='Paths')

                    if paths_panel is not None:
                    col = repository_panel.column()
                    col.enabled = False
                    col.use_property_split = True
                    col.prop(repository, 'id', emboss=False)
                    col.prop(repository, 'game_directory')
                    if repository.mod:
                        col.prop(repository, 'mod', emboss=False)
                    col.prop(repository, 'cache_directory')

                    # If we have not yet scanned the repository, we need to present the user with a button to scan it.
                    packages_header, packages_panel = repository_panel.panel('Packages', default_closed=True)
                    row = packages_header.row()
                    row.label(text='Packages')
                    col = row.column(align=True)
                    col.alignment = 'RIGHT'
                    col.operator(BDK_OT_repository_scan.bl_idname, icon='FILE_REFRESH', text='Scan')

                    if packages_panel is not None:
                        if not repository.runtime.has_been_scanned:
                            flow = packages_panel.grid_flow(columns=1, row_major=True)
                            row = flow.row(align=True)
                            row.alignment = 'CENTER'
                            row.enabled = False
                            row.label(text='Packages have not been scanned.')
                            row = flow.row(align=True)
                            row.alignment = 'CENTER'
                            col = row.column()
                            col.enabled = False
                            col.label(text='Click the')
                            row.operator(BDK_OT_repository_scan.bl_idname, icon='FILE_REFRESH', text='Scan')
                            col = row.column()
                            col.enabled = False
                            col.label(text='button to scan the repository.')

                        else:
                            row = repository_panel.row()

                            col = row.column()
                            col.alignment = 'LEFT'

                            row = col.row()
                            row.label(text=f'{repository.runtime.disabled_package_count}', icon='CHECKBOX_DEHLT')
                            row.label(text=f'{repository.runtime.need_export_package_count}', icon='EXPORT')
                            row.label(text=f'{repository.runtime.need_build_package_count}', icon='MOD_BUILD')
                            row.label(text=f'{repository.runtime.up_to_date_package_count}', icon='CHECKMARK')

                            row = row.column()
                            row.alignment = 'RIGHT'
                            row.operator(BDK_OT_repository_build_asset_library.bl_idname, icon='BLENDER', text='Build Assets')

                            row = repository_panel.row()
                            row.column().template_list(BDK_UL_repository_packages.bl_idname, '',
                                                       repository.runtime, 'packages',
                                                       repository.runtime, 'packages_index',
                                                       rows=5)

                            col = row.column(align=True)

                            if self.developer_extras:
                                op = col.operator(BDK_OT_repository_package_cache_invalidate.bl_idname, icon='ERROR', text='')
                                op.index = repository.runtime.packages_index
                                col.separator()

                            col.menu(BDK_MT_repository_special.bl_idname, icon='DOWNARROW_HLT', text='')

                            if repository.runtime.packages_index >= 0:
                                package_header, package_panel = repository_panel.panel('Package', default_closed=True)

                                package = repository.runtime.packages[repository.runtime.packages_index]

                                package_header.label(text='Package')

                                if package_panel is not None:
                                    flow = package_panel.grid_flow(columns=2, row_major=True)
                                    flow.enabled = False
                                    flow.label(text='Modified Time')
                                    flow.label(text=datetime.fromtimestamp(package.modified_time).isoformat())
                                    flow.label(text='Exported Time')
                                    flow.label(text=datetime.fromtimestamp(package.exported_time).isoformat() if package.exported_time > 0 else 'N/A')
                                    flow.label(text='Build Time')
                                    flow.label(text=datetime.fromtimestamp(package.build_time).isoformat() if package.build_time > 0 else 'N/A')

                                    op = package_panel.operator(BDK_OT_repository_package_build.bl_idname, text='Debug Build')
                                    op.index = repository.runtime.packages_index


class BDK_OT_scene_repository_set(Operator):
    bl_idname = 'bdk.scene_repository_set'
    bl_label = 'Set Scene Repository'
    bl_description = 'Set the repository for the current scene'
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context: Context):
        addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        context.scene.bdk.repository_id = repository.id

        self.report({'INFO'}, f'Scene repository set to {repository.name}')

        tag_redraw_all_windows(context)

        return {'FINISHED'}


classes = (
    BDK_PG_preferences_runtime,
    BDK_OT_scene_repository_set,
    BDK_OT_repository_package_build,
    BDK_OT_repository_build_asset_library,
    BDK_OT_repository_cache_invalidate,
    BDK_OT_repository_cache_delete,
    BDK_OT_repository_scan,
    BDK_OT_repository_create,
    BDK_OT_repository_link,
    BDK_OT_repository_delete,
    BDK_OT_repository_unlink,
    BDK_OT_repository_package_cache_invalidate,
    BDK_OT_repository_packages_set_enabled_by_pattern,
    BdkAddonPreferences,
)
