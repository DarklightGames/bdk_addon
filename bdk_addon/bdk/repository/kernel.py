import fnmatch
from uuid import uuid5, NAMESPACE_OID
from datetime import datetime

import bpy
import os.path
import subprocess
from collections import defaultdict
from configparser import NoOptionError
from glob import glob

import networkx
from bpy.types import Context

from .properties import BDK_PG_repository, BDK_PG_repository_package
from pathlib import Path
from typing import Optional, List, Dict

from ...data import UReference
from ...helpers import get_addon_preferences
from ...io.config import ConfigParserMultiOpt
import json


def is_game_directory_and_mod_valid(game_directory: Path, mod: Optional[str]) -> bool:
    try:
        read_repository_package_patterns(game_directory, mod)
        return True
    except FileNotFoundError:
        return False


def read_repository_package_patterns(game_directory: Path, mod: Optional[str]) -> List[Path]:
    # Determine the asset paths.
    game_directory = Path(game_directory)
    game_system_directory = game_directory / 'System'
    game_default_config_path = game_system_directory / 'Default.ini'

    package_patterns = set()

    def parse_config_package_patterns(path: Path):
        game_default_config = ConfigParserMultiOpt()
        game_default_config.read(path)

        patterns_to_add = []
        patterns_to_remove = []

        try:
            patterns_to_add.extend(game_default_config.get('Core.System', 'paths'))
        except NoOptionError:
            pass

        try:
            # Mod paths are prefixed with a '+' or '-' to indicate whether they should be added or removed.
            patterns_to_add.extend(game_default_config.get('Core.System', '+paths'))
        except NoOptionError:
            pass

        try:
            patterns_to_remove.extend(game_default_config.get('Core.System', '-paths'))
        except NoOptionError:
            pass

        for pattern in patterns_to_add:
            package_patterns.add((game_system_directory / pattern).resolve().absolute())

        for pattern in patterns_to_remove:
            try:
                package_patterns.remove((game_system_directory / pattern).resolve().absolute())
            except KeyError:
                # If the pattern doesn't exist, just ignore it.
                pass

    # Add the game's default config to the list of config files to be parsed.
    config_paths = [game_default_config_path]

    if mod is not None:
        # If the mod is specified, add the mod's Default.ini to the list of config files to be parsed.
        config_paths.append(game_directory / mod / 'System' / 'Default.ini')

    for config_path in config_paths:
        if not config_path.exists():
            raise FileNotFoundError(f'Config file not found: {config_path}')
        parse_config_package_patterns(config_path)

    # Sort the package patterns alphabetically so that we have a predictable order.
    package_patterns = sorted(list(package_patterns))

    return package_patterns


class Manifest:
    class Package:
        def __init__(self):
            self.exported_time: Optional[datetime] = None
            self.build_time: Optional[datetime] = None

    def __init__(self, path: str):
        self.path = path
        self.packages: Dict[str, Manifest.Package] = dict()

    def has_package(self, package_path: str) -> bool:
        return package_path in self.packages

    def get_package(self, package_path: str) -> Package:
        return self.packages[package_path]

    def invalidate_package(self, package_path: str):
        package = self.packages.setdefault(package_path, Manifest.Package())
        package.exported_time = None
        package.build_time = None
        package.status = 'NEEDS_EXPORT'

    def invalidate_package_assets(self, package_path: str):
        package = self.packages.setdefault(package_path, Manifest.Package())
        package.build_time = None
        package.status = 'NEEDS_BUILD'

    def mark_package_as_exported(self, package_path: str):
        package = self.packages.setdefault(package_path, Manifest.Package())
        package.exported_time = datetime.utcnow()
        package.status = 'NEEDS_BUILD'

    def mark_package_as_built(self, package_path: str):
        package = self.packages.setdefault(package_path, Manifest.Package())
        package.build_time = datetime.utcnow()
        package.status = 'UP_TO_DATE'

    # Read and write the manifest to a JSON file.
    @staticmethod
    def from_file(path: Path):
        manifest = Manifest(str(path))
        if path.is_file():
            with open(path) as f:
                data = json.load(f)
                for package_name, package_data in data['packages'].items():
                    package = manifest.packages.setdefault(package_name, Manifest.Package())
                    exported_time = package_data.get('exported_time', None)
                    if isinstance(exported_time, str):
                        package.exported_time = datetime.fromisoformat(exported_time)
                    build_time = package_data.get('build_time', None)
                    if isinstance(build_time, str):
                        package.build_time = datetime.fromisoformat(build_time)
        return manifest

    @staticmethod
    def from_repository(repository: BDK_PG_repository):
        return Manifest.from_file(get_repository_manifest_path(repository))

    def write(self):
        data = {
            'packages': {
                package_name: {
                    'exported_time': package.exported_time.isoformat() if package.exported_time is not None else None,
                    'build_time': package.build_time.isoformat() if package.build_time is not None else None,
                }
                for package_name, package in self.packages.items()
            }
        }
        # Make sure the directory exists.
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)


def get_repository_manifest_path(repository: BDK_PG_repository) -> Path:
    return get_repository_cache_directory(repository) / 'manifest.json'


def update_repository_package_patterns(repository: BDK_PG_repository):
    repository.runtime.package_patterns.clear()
    repository.runtime.packages.clear()

    manifest = Manifest.from_repository(repository)

    for pattern in read_repository_package_patterns(Path(repository.game_directory), repository.mod):
        package_pattern = repository.runtime.package_patterns.add()
        package_pattern.pattern = str(pattern)

    for package_pattern in repository.runtime.package_patterns:
        for package_path in glob(package_pattern.pattern):
            index = len(repository.runtime.packages)
            package = repository.runtime.packages.add()
            package.repository_id = repository.id
            package.index = index
            package.path = Path(package_path).resolve().relative_to(
                Path(repository.game_directory).resolve()).as_posix()
            package.filename = Path(package_path).name

            # Get the modified time of the package file.
            modified_time = datetime.fromtimestamp(os.path.getmtime(package_path))
            package.modified_time = int(modified_time.timestamp())

            if manifest.has_package(package.path):
                # Get the modified time of the package from the manifest.
                exported_time = None
                if manifest.has_package(package.path):
                    manifest_package = manifest.get_package(package.path)
                    exported_time = manifest_package.exported_time
                package.exported_time = int(exported_time.timestamp()) if exported_time is not None else 0

                build_time = None
                # Make sure the package actually exists in the repository cache.
                if manifest.has_package(package.path) and get_repository_package_asset_path(repository,
                                                                                            package.path).is_file():
                    manifest_package = manifest.get_package(package.path)
                    build_time = manifest_package.build_time
                package.build_time = int(build_time.timestamp()) if build_time is not None else 0

                # If the package has been exported more recently than the package file has been modified, mark it as
                # up-to-date.
                if exported_time is None or modified_time > exported_time:
                    package.status = 'NEEDS_EXPORT'
                elif build_time is None or modified_time > build_time:
                    package.status = 'NEEDS_BUILD'
                else:
                    package.status = 'UP_TO_DATE'
            else:
                package.status = 'NEEDS_EXPORT'


def repository_runtime_update_aggregate_stats(repository: BDK_PG_repository):
    runtime = repository.runtime
    runtime.excluded_package_count = 0
    runtime.up_to_date_package_count = 0
    runtime.need_export_package_count = 0
    runtime.need_build_package_count = 0
    for package in runtime.packages:
        if package.is_excluded_by_rule:
            runtime.excluded_package_count += 1
        else:
            match package.status:
                case 'UP_TO_DATE':
                    runtime.up_to_date_package_count += 1
                case 'NEEDS_EXPORT':
                    runtime.need_export_package_count += 1
                case 'NEEDS_BUILD':
                    runtime.need_build_package_count += 1

    # Populate the orphaned assets list.
    asset_library_directory = get_repository_default_asset_library_directory(repository)
    package_names = {os.path.splitext(package.filename)[0].upper() for package in repository.runtime.packages}
    repository.runtime.orphaned_assets.clear()
    for asset_file in asset_library_directory.glob('*.blend'):
        if os.path.splitext(asset_file.name)[0].upper() not in package_names:
            orphaned_asset = repository.runtime.orphaned_assets.add()
            orphaned_asset.file_name = asset_file.name


def repository_runtime_packages_update_rule_exclusions(repository):
    """
    Apply the rules to the packages in the repository.
    """
    # Clear the exclusion flags.
    for package in repository.runtime.packages:
        package.is_excluded_by_rule = False

    # Apply the rules to the packages.
    for rule in filter(lambda x: not x.mute, repository.rules):
        match rule.type:
            case 'EXCLUDE':
                for package in repository.runtime.packages:
                    if fnmatch.fnmatch(package.path, rule.pattern):
                        package.is_excluded_by_rule = True
            case 'INCLUDE':
                for package in filter(lambda x: x.is_excluded_by_rule, repository.runtime.packages):
                    if fnmatch.fnmatch(package.path, rule.pattern):
                        package.is_excluded_by_rule = False

    repository_runtime_update_aggregate_stats(repository)


def repository_runtime_update(repository: BDK_PG_repository):
    update_repository_package_patterns(repository)
    repository_runtime_packages_update_rule_exclusions(repository)
    repository_runtime_update_aggregate_stats(repository)
    repository.runtime.has_been_scanned = True


def repository_cache_delete(repository: BDK_PG_repository):
    import shutil

    cache_directory = get_repository_cache_directory(repository).resolve()

    # Because this is a destructive file system operation, we want to only delete files and directories that we
    # expect to be there. This is a safety measure to prevent accidental deletion of important files if the cache
    # directory is misconfigured (for example, if the cache directory is set to the root of the drive).

    # Delete the manifest file.
    manifest_path = cache_directory / 'manifest.json'
    if manifest_path.exists():
        manifest_path.unlink()

    # Delete the exports and assets directories.
    exports_directory = cache_directory / 'exports'
    if exports_directory.exists():
        shutil.rmtree(exports_directory)

    assets_directory = cache_directory / 'assets'
    if assets_directory.exists():
        shutil.rmtree(assets_directory)

    # Delete the cache directory.
    if cache_directory.exists():
        cache_directory.rmdir()


def repository_asset_library_add(context, repository):
    assets_directory = get_repository_default_asset_library_directory(repository)
    asset_library = context.preferences.filepaths.asset_libraries.new(
        name=repository.name,
        directory=str(assets_directory)
    )
    asset_library.import_method = 'LINK'


def repository_asset_library_unlink(context, repository) -> int:
    removed_count = 0
    repository_asset_library_path = str(get_repository_default_asset_library_directory(repository).resolve())
    for asset_library in context.preferences.filepaths.asset_libraries:
        if str(Path(asset_library.path).resolve()) == repository_asset_library_path:
            context.preferences.filepaths.asset_libraries.remove(asset_library)
            removed_count += 1
    return removed_count


def get_repository_metadata_file_path(repository: BDK_PG_repository) -> Path:
    return Path(repository.cache_directory) / f'{repository.id}.json'


def repository_metadata_read(repository):
    repository_metadata_file = get_repository_metadata_file_path(repository).resolve()
    if not repository_metadata_file.exists():
        return

    with open(repository_metadata_file, 'r') as f:
        data = json.load(f)
        repository.game_directory = data['game_directory']
        repository.mod = data['mod']
        repository.rules.clear()
        if 'rules' in data:
            for rule_data in data['rules']:
                rule = repository.rules.add()
                rule.repository_id = repository.id
                rule.pattern = rule_data['pattern']
                rule.type = rule_data['type']
                rule.mute = rule_data['mute']
                rule.asset_directory = rule_data.get('asset_directory', '')


def repository_metadata_write(repository):
    with open(get_repository_metadata_file_path(repository).resolve(), 'w') as f:
        rules = []
        for rule in repository.rules:
            rule_data = {
                'pattern': rule.pattern,
                'type': rule.type,
                'mute': rule.mute,
            }
            if rule.type == 'SET_ASSET_DIRECTORY':
                rule_data['asset_directory'] = rule.asset_directory
            rules.append(rule_data)
        data = {
            'id': repository.id,
            'game_directory': repository.game_directory,
            'mod': repository.mod,
            'rules': rules,
        }
        json.dump(data, f, indent=2)


def repository_metadata_delete(repository):
    repository_metadata_file = get_repository_metadata_file_path(repository).resolve()
    if repository_metadata_file.exists():
        repository_metadata_file.unlink()


def ensure_default_repository_id(context: Context):
    """
    Ensure that the default repository is valid. If the default repository is not valid, it will be set to the first
    repository in the list, or cleared if there are no repositories.
    """
    addon_prefs = get_addon_preferences(context)
    exists = False
    if addon_prefs.default_repository_id != '':
        for repository in addon_prefs.repositories:
            if repository.id == addon_prefs.default_repository_id:
                exists = True
                break

    if not exists:
        if len(addon_prefs.repositories) > 0:
            addon_prefs.default_repository_id = addon_prefs.repositories[0].id
        else:
            addon_prefs.default_repository_id = ''


def repository_remove(context: Context, repositories_index: int):
    """
    Remove a repository entry from the addon preferences.
    """
    addon_prefs = get_addon_preferences(context)
    addon_prefs.repositories.remove(repositories_index)
    addon_prefs.repositories_index = min(repositories_index, len(addon_prefs.repositories) - 1)

    ensure_default_repository_id(context)


def get_repository_package_dependency_graph(repository: BDK_PG_repository) -> networkx.DiGraph:
    """
    Returns the build order of the packages in the repository, as well as any cycles that are detected.
    Note that cycles are removed from the graph by severing all the edges that create the cycle.
    Note that the names of the packages are converted to uppercase for comparison since Unreal packages (and all names
    in Unreal) are case-insensitive.
    """
    from ...package.reader import get_package_dependencies
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


def _get_build_order_from_package_dependency_graph(repository: BDK_PG_repository, graph: networkx.DiGraph) -> \
        list[BDK_PG_repository_package]:
    topographical_order = list(reversed(list(networkx.topological_sort(graph))))

    # Create a dictionary of case-insensitive package names to the package objects.
    package_name_to_package = {os.path.splitext(os.path.basename(package.path))[0].upper(): package for package in
                               repository.runtime.packages}

    return [package_name_to_package[package_name.upper()] for package_name in topographical_order]


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


def get_addon_path() -> Path:
    import addon_utils
    import os
    from ..preferences import BdkAddonPreferences

    for module in addon_utils.modules():
        if module.__name__ == BdkAddonPreferences.bl_idname:
            return Path(os.path.dirname(module.__file__))

    raise RuntimeError('Could not find addon path')


def get_umodel_path() -> Path:
    return get_addon_path() / 'bin' / 'umodel.exe'


def build_cube_map(cube_map_file_path: Path, exports_directory: Path):
    import re
    with open(cube_map_file_path, 'r') as f:
        contents = f.read()
        textures = re.findall(r'Faces\[\d] = (\w+\'[\w_\-.]+\')', contents)
        face_paths: list[Path] = []
        for texture in textures:
            face_reference = UReference.from_string(texture)
            image_path = exports_directory / face_reference.type_name / f'{face_reference.object_name}.tga'
            face_paths.append(image_path)
        output_path = cube_map_file_path.parent / cube_map_file_path.name.replace('.props.txt', '.png')
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
    package_build_directory = os.path.join(str(exports_directory),
                                           os.path.dirname(os.path.relpath(str(package_path), str(game_directory))))
    umodel_path = str(get_umodel_path())
    args = [umodel_path, '-export', '-nolinked', f'-out="{package_build_directory}"',
            f'-path="{repository.game_directory}"', str(package_path)]
    process = subprocess.run(args, capture_output=True)

    log_directory = get_repository_cache_directory(repository) / 'exports' / 'logs' / f'{package_path.stem}.log'
    write_process_log_to_file(process, log_directory)

    # Build any cube maps that were exported.
    cubemap_file_paths = []

    package_exports_directory = Path(package_build_directory) / os.path.splitext(package.filename)[0]

    for cubemap_file_path in Path(package_exports_directory).glob('**/Cubemap/*.props.txt'):
        cubemap_file_paths.append(cubemap_file_path)

    print(f'Building {len(cubemap_file_paths)} cubemaps')
    for cubemap_file_path in cubemap_file_paths:
        process, output = build_cube_map(cubemap_file_path, package_exports_directory)

    return process, package


def get_repository_cache_directory(repository: BDK_PG_repository) -> Path:
    return Path(repository.cache_directory) / repository.id


def get_repository_default_asset_library_directory(repository: BDK_PG_repository) -> Path:
    return get_repository_cache_directory(repository) / 'assets'


def get_repository_package_asset_directory(repository: BDK_PG_repository, package_path: str) -> Path:
    for rule in filter(lambda x: x.type == 'SET_ASSET_DIRECTORY' and not x.mute, repository.rules):
        if fnmatch.fnmatch(package_path, rule.pattern):
            rule_asset_directory = Path(rule.asset_directory)
            if rule_asset_directory.is_absolute():
                return rule_asset_directory
            else:
                return get_repository_cache_directory(repository) / rule_asset_directory
    return get_repository_default_asset_library_directory(repository)


def get_repository_package_asset_path(repository: BDK_PG_repository, package_path: str) -> Path:
    package_filename = os.path.splitext(os.path.basename(package_path))[0]
    return get_repository_package_asset_directory(repository, package_path) / f'{package_filename}.blend'


def get_repository_package_export_directory(repository: BDK_PG_repository, package_path: str) -> Path:
    package_filename = os.path.splitext(package_path)[0]
    return get_repository_export_directory(repository) / package_filename


def get_repository_export_directory(repository: BDK_PG_repository):
    return get_repository_cache_directory(repository) / 'exports'


def get_repository_package_catalog_id(repository: BDK_PG_repository, package_path: str) -> str:
    # Salt the package path with the repository ID.
    return str(uuid5(NAMESPACE_OID, repository.id + package_path))


def repository_package_build(repository: BDK_PG_repository, package_path: str):
    # TODO: do not allow this if the package is not up-to-date.
    script_path = get_addon_path() / 'bin' / 'blend.py'
    input_directory = get_repository_package_export_directory(repository, package_path)
    assets_directory = get_repository_package_asset_directory(repository, package_path)
    output_path = get_repository_package_asset_path(repository, package_path)
    catalog_id = get_repository_package_catalog_id(repository, package_path)

    # TODO: It is relative expensive to spin up an entire Blender instance for each package build. We should consider
    #  refactoring this so that package builds are dispatched to a pool of processes. This would likely be faster, but
    #  would add quite a bit of complexity.
    args = [
        bpy.app.binary_path, '--background', '--python', str(script_path), '--',
        'build', str(input_directory), repository.id, catalog_id, '--output_path', str(output_path)
    ]

    process = subprocess.run(args, capture_output=True)

    log_directory = assets_directory / 'logs'
    log_directory.mkdir(parents=True, exist_ok=True)
    package_filename = os.path.splitext(os.path.basename(package_path))[0]
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
