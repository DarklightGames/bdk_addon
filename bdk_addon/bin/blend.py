import sys
import warnings
from pathlib import Path
from typing import List

import bpy
import os
import glob
import addon_utils
from argparse import ArgumentParser

material_class_names = [
    'ColorModifier',
    'Combiner',
    'ConstantColor',
    'Cubemap',
    'FinalBlend',
    'Shader',
    'TexCoordSource',
    'TexOscillator',
    'TexPanner',
    'TexScaler',
    'TexRotator',
    'Texture',
    'TexEnvMap',
    'VertexColor',
]


def build(args):
    if not os.path.isdir(args.input_directory):
        raise RuntimeError(f'{args.input_directory} is not a directory')

    input_directory = Path(args.input_directory).resolve()

    package_name = input_directory.parts[-1]

    # TODO: There is a new bug where a SM in a Texture package references a Texture package
    #  that has not yet been built.
    #  It may be wise to do make a dependency graph or simply do the .blend file building
    #  in two passes (first materials, then statics)

    # Packages can hold basically any kind of asset in them.
    # As a result, static meshes can reference textures residing in the same package.
    # Because the PSK importer tries to link existing materials from the same file
    # first before loading it from an asset library, we must make sure all the materials
    # are in the .blend file before it evaluates any static meshes.
    material_files = []
    static_mesh_files = []
    new_ids: List[bpy.types.ID] = []

    for file in glob.glob('**/*.props.txt', root_dir=args.input_directory):
        # The class type of the object is the directory name of the parent folder.
        class_type = Path(os.path.join(args.input_directory, file)).parent.parts[-1]

        if class_type == 'StaticMesh':
            static_mesh_files.append(file)
        elif class_type in material_class_names:
            material_files.append(file)
        else:
            warnings.warn(f'Unhandled class type: {class_type}')

    # Materials.
    for file in material_files:
        filepath = os.path.join(args.input_directory, file)
        object_name = os.path.basename(file).replace('.props.txt', '')

        try:
            bpy.ops.bdk.import_material(filepath=filepath)
        except Exception as e:
            print(e)
            continue

        new_material = bpy.data.materials[object_name]
        new_ids.append(new_material)

    # TODO: add support for Unreal 1 VertMeshes

    # Static Meshes.
    for file in static_mesh_files:
        object_name = os.path.basename(file).replace('.props.txt', '')
        extensions = ['.pskx', '.psk']
        filenames = [os.path.join(args.input_directory, 'StaticMesh', f'{object_name}{extension}') for extension in extensions]

        for filename in filenames:
            if not os.path.isfile(filename):
                continue
            try:
                bpy.ops.import_scene.psk(
                    filepath=filename,
                    should_import_skeleton=False,
                    should_import_materials=True
                )
            except Exception as e:
                print(e)
                continue

            package_reference = f'StaticMesh\'{package_name}.{object_name}\''

            new_object = bpy.data.objects[object_name]
            new_object.data.name = package_reference

            # Provide a "stable" reference to the object in the package.
            # The name of the data block is not stable because the object & data can be duplicated in Blender fairly
            # easily, thus changing the name of the data block.
            new_object.bdk.package_reference = package_reference

            new_object['Class'] = 'StaticMeshActor'

            new_ids.append(new_object)
            break

    # Generate previews.
    for new_id in new_ids:
        new_id.asset_mark()
        new_id.asset_generate_preview()

    # Save the file to disk.
    if args.output_path is None:
        args.output_path = os.path.join(args.input_directory, f'{package_name}.blend')

    output_directory = os.path.join(os.path.dirname(args.output_path))
    os.makedirs(output_directory, exist_ok=True)

    if len(new_ids):
        bpy.ops.wm.save_as_mainfile(
            filepath=os.path.abspath(args.output_path),
            copy=True
            )


if __name__ == '__main__':
    # TODO: these won't work because the key of the addon is unpredictable.
    # addon_utils.enable('io_scene_psk_psa')
    # addon_utils.enable('bdk_addon')

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title='command')
    build_subparser = subparsers.add_parser('build')
    build_subparser.add_argument('input_directory')
    build_subparser.add_argument('--output_path', required=False, default=None)
    build_subparser.set_defaults(func=build)
    args = sys.argv[sys.argv.index('--')+1:]
    args = parser.parse_args(args)
    args.func(args)
