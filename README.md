# bdk_addon

![bdk-logo-02](https://github.com/DarklightGames/bdk_addon/assets/5035660/c7d1d277-2c85-4e6f-8e9b-2afb0a658235)

The Blender addon for the BDK (Blender Development Kit) project. The project is currently in a usable state for both Linux and Windows, although some features are not completed.

# Motivation
The primary motivation behind the BDK is to provide level artists a stable, feature-rich alternative to the Unreal SDK for creating maps for Darkest Hour: Europe '44-'45. There were two overarching reasons for doing so:

* The Unreal SDK is woefully unstable, having fallen victim to the deficiencies in it's initial construction and software rot that made the program almost unusable as a creative tool on modern machines.
* A complete lack of higher-order procedural tools meant that every aspect of a level must be painstaking and laboriously hand-crafted (i.e., instead of defining a road as a spline, roads need to be hand-painted and hand-sculpted).

# Features
* Powerful procedural terrain sculpting and painting functionality.
* Create and build level geometry with BSP brushes directly in Blender.
* Unreal Materials recreated with Blender's material node system (e.g., `Combiners`, `TexOscillators` etc.)
* All game/mod assets exported to easy-to-use asset libraries, allowing for drag & drop placement of static meshes.
* Copy & paste Unreal objects (static meshes, terrain etc.) between the Blender (BDK) and the Unreal 2 SDK using T3D serialization.

# In Development
* BSP Texturing
* Projectors

# Related Projects
* [bdk-blender](https://projects.blender.org/cmbasnett/bdk-blender) - Custom fork of Blender that adds native functionality necessary for the functioning of the BDK.
* [UEViewer](https://github.com/DarklightGames/UEViewer) - Custom fork of UEViewer that exports more data
* [io_scene_psk_psa](https://github.com/DarklightGames/io_scene_psk_psa) - Blender addon used for importing PSKs into Blender
* [t3d-python](https://github.com/DarklightGames/t3d-python)

[![PyPi version](https://badgen.net/pypi/v/t3dpy/)](https://pypi.org/project/t3dpy)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/t3dpy.svg)](https://pypi.python.org/pypi/t3dpy/)
