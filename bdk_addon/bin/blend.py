import sys
import warnings
from pathlib import Path
from typing import List

import bpy
import os
import glob
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
    input_directory = Path(args.input_directory).resolve()

    package_name = input_directory.parts[-1]

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
            bpy.ops.bdk.import_material(filepath=filepath, repository_id=args.repository_id)
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
        filename = next((filename for filename in filenames if os.path.isfile(filename)), None)

        if filename is None:
            warnings.warn(f'Could not find a static mesh file for {object_name}')
            continue

        bpy.ops.import_scene.psk(
            filepath=filename,
            should_import_skeleton=False,
            should_import_materials=True,
            bdk_repository_id=args.repository_id
        )

        package_reference = f'StaticMesh\'{package_name}.{object_name}\''

        new_object = bpy.data.objects[object_name]
        new_object.data.name = package_reference

        # Provide a "stable" reference to the object in the package.
        # The name of the data block is not stable because the object & data can be duplicated in Blender fairly
        # easily, thus changing the name of the data block.
        new_object.bdk.package_reference = package_reference

        new_object['Class'] = 'StaticMeshActor'

        # Add the object to a collection with the name of the object.
        collection = bpy.data.collections.new(name=object_name)

        # Link the object to the collection.
        collection.objects.link(new_object)

        # Link the collection to the scene.
        bpy.context.scene.collection.children.link(collection)

        # Add the collection to the new_ids list.
        new_ids.append(collection)

    # Generate previews.
    for new_id in new_ids:
        new_id.asset_mark()
        new_id.asset_data.catalog_id = args.catalog_id
        new_id.asset_generate_preview()

    # Save the file to disk.
    if args.output_path is None:
        args.output_path = os.path.join(args.input_directory, f'{package_name}.blend')

    output_directory = os.path.join(os.path.dirname(args.output_path))
    os.makedirs(output_directory, exist_ok=True)

    # Note that even if there are no new objects, we still save the file.
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.abspath(args.output_path),
        copy=True
    )


if __name__ == '__main__':
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title='command')
    build_subparser = subparsers.add_parser('build')
    build_subparser.add_argument('input_directory')
    build_subparser.add_argument('repository_id')
    build_subparser.add_argument('catalog_id')
    build_subparser.add_argument('--output_path', required=False, default=None)
    build_subparser.set_defaults(func=build)
    args = sys.argv[sys.argv.index('--')+1:]
    args = parser.parse_args(args)

    try:
        args.func(args)
    except Exception as e:
        # Write to stderr.
        print(e, file=sys.stderr)
        sys.exit(1)
