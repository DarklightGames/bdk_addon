import sys
import bpy
import argparse

faces = ['front', 'back', 'right', 'left', 'top', 'bottom']

parser = argparse.ArgumentParser()
for face in faces:
    parser.add_argument(f'--{face}', required=False, default=None)
parser.add_argument('--output', required=False, default='./output.png')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])

images = bpy.data.images

for face in faces:
    images[face].filepath = getattr(args, face)

scene = bpy.context.scene
assert scene
scene.render.filepath = args.output
scene.render.resolution_x = 512
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
assert scene.render.engine == 'CYCLES'
assert scene.cycles
scene.cycles.samples = 4

bpy.ops.render.render(write_still=True)
