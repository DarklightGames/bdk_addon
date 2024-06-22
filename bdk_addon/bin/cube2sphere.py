import sys
import bpy
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('front')
parser.add_argument('back')
parser.add_argument('right')
parser.add_argument('left')
parser.add_argument('top')
parser.add_argument('bottom')
parser.add_argument('--output', required=False, default='./output.png')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])

bpy.data.images['front'].filepath = args.front
bpy.data.images['back'].filepath = args.back
bpy.data.images['right'].filepath = args.right
bpy.data.images['left'].filepath = args.left
bpy.data.images['top'].filepath = args.top
bpy.data.images['bottom'].filepath = args.bottom

bpy.context.scene.render.filepath = args.output
bpy.context.scene.cycles.samples = 4
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 256
bpy.context.scene.render.resolution_percentage = 100
bpy.context.scene.render.image_settings.file_format = 'PNG'


bpy.ops.render.render(write_still=True)
