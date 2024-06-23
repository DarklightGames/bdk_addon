import os.path
from configparser import NoOptionError
from glob import glob
from .properties import BDK_PG_repository
from pathlib import Path
from typing import Optional, List, Dict
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


import datetime

datetime.datetime.utcnow().isoformat()

class Manifest:
    class Package:
        def __init__(self):
            self.exported_time: Optional[datetime.datetime] = None
            self.build_time: Optional[datetime.datetime] = None
            self.is_enabled: bool = True

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
        package.exported_time = datetime.datetime.utcnow()
        package.status = 'NEEDS_BUILD'

    def mark_package_as_built(self, package_path: str):
        package = self.packages.setdefault(package_path, Manifest.Package())
        package.build_time = datetime.datetime.utcnow()
        package.status = 'UP_TO_DATE'

    def set_package_enabled(self, package_path: str, enabled: bool):
        package = self.packages.setdefault(package_path, Manifest.Package())
        package.is_enabled = enabled

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
                        package.exported_time = datetime.datetime.fromisoformat(exported_time)
                    build_time = package_data.get('build_time', None)
                    if isinstance(build_time, str):
                        package.build_time = datetime.datetime.fromisoformat(build_time)
                    package.is_enabled = package_data.get('is_enabled', True)
        return manifest

    def write(self):
        data = {
            'packages': {
                package_name: {
                    'exported_time': package.exported_time.isoformat() if package.exported_time is not None else None,
                    'build_time': package.build_time.isoformat() if package.build_time is not None else None,
                    'is_enabled': package.is_enabled,
                }
                for package_name, package in self.packages.items()
            }
        }
        # Make sure the directory exists.
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)


def load_repository_manifest(repository: BDK_PG_repository) -> Manifest:
    manifest_path = Path(repository.cache_directory) / repository.id / 'manifest.json'
    # if not manifest_path.exists():
    #     return Manifest(manifest_path)
    return Manifest.from_file(manifest_path)


def update_repository_package_patterns(repository: BDK_PG_repository):
    repository.runtime.package_patterns.clear()
    repository.runtime.packages.clear()

    manifest = load_repository_manifest(repository)

    for pattern in read_repository_package_patterns(Path(repository.game_directory), repository.mod):
        package_pattern = repository.runtime.package_patterns.add()
        package_pattern.pattern = str(pattern)

    for package_pattern in repository.runtime.package_patterns:
        for package_path in glob(package_pattern.pattern):
            index = len(repository.runtime.packages)
            package = repository.runtime.packages.add()
            package.repository_id = repository.id
            package.index = index
            package.path = Path(package_path).resolve().relative_to(Path(repository.game_directory).resolve()).as_posix()
            package.filename = Path(package_path).name

            # Get the modified time of the package file.
            modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(package_path))
            package.modified_time = int(modified_time.timestamp())

            if manifest.has_package(package.path):
                # Get the modified time of the package from the manifest.
                exported_time = None
                if manifest.has_package(package.path):
                    manifest_package = manifest.get_package(package.path)
                    exported_time = manifest_package.exported_time
                package.exported_time = int(exported_time.timestamp()) if exported_time is not None else 0

                build_time = None
                if manifest.has_package(package.path):
                    manifest_package = manifest.get_package(package.path)
                    build_time = manifest_package.build_time
                package.build_time = int(build_time.timestamp()) if build_time is not None else 0

                is_enabled = True
                if manifest.has_package(package.path):
                    is_enabled = manifest.get_package(package.path).is_enabled
                package.is_enabled = is_enabled

                # If the package has been exported more recently than the package file has been modified, mark it as up to date.
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
    runtime.disabled_package_count = 0
    runtime.up_to_date_package_count = 0
    runtime.need_export_package_count = 0
    runtime.need_build_package_count = 0
    for package in runtime.packages:
        if not package.is_enabled:
            runtime.disabled_package_count += 1
        else:
            match package.status:
                case 'UP_TO_DATE':
                    runtime.up_to_date_package_count += 1
                case 'NEEDS_EXPORT':
                    runtime.need_export_package_count += 1
                case 'NEEDS_BUILD':
                    runtime.need_build_package_count += 1


def repository_runtime_update(repository: BDK_PG_repository):
    update_repository_package_patterns(repository)
    repository_runtime_update_aggregate_stats(repository)
    repository.runtime.has_been_scanned = True


def repository_cache_delete(repository: BDK_PG_repository):
    import shutil

    cache_directory = (Path(repository.cache_directory) / repository.id).resolve()

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
