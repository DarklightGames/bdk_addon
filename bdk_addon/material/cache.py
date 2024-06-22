from pathlib import Path
from typing import Dict, Optional

from .data import UMaterial
from .reader import read_material
from ..bdk.repository.kernel import Manifest

import os

from ..data import UReference


class MaterialCache:
    def __init__(self, root_directory: Path):
        self._root_directory = root_directory
        self._materials: Dict[str, UMaterial] = {}
        self._package_paths: Dict[str, Path] = {}

        self._build_package_paths()

    def _build_package_paths(self):
        # Read the list of packages managed by BDK in the manifest.
        manifest = Manifest.from_file(self._root_directory / 'manifest.json')

        # Register package name with package directory
        for package_path in manifest.packages.keys():
            package_name = os.path.splitext(os.path.basename(package_path))[0].upper()
            self._package_paths[package_name] = Path(package_path)

    def resolve_path_for_reference(self, reference: UReference) -> Optional[Path]:
        try:
            package_path = self._package_paths[reference.package_name.upper()]
            return (self._root_directory / 'exports' / os.path.splitext(package_path)[0] / reference.type_name / f'{reference.object_name}.props.txt').resolve()
        except KeyError:
            # The package could not be found in the material cache.
            print(f'Could not find package {reference.package_name} in material cache.')
            pass
        except RuntimeError:
            pass
        return None

    def load_material(self, reference: UReference) -> Optional[UMaterial]:
        if reference is None:
            return None
        key = str(reference)
        if key in self._materials:
            return self._materials[str(reference)]
        path = self.resolve_path_for_reference(reference)
        if path is None:
            return None
        material = read_material(str(path))
        self._materials[key] = material
        return material
