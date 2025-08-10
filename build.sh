#!/usr/bin/env bash

# Build UEViewer.
pushd extern/UEViewer
./build.sh
popd

mkdir -p out/bin
mkdir -p out/wheels

cp  ./extern/UEViewer/umodel ./bdk_addon/bin/umodel -v

export PYTHON_VERSION="3.11"

# Build bdk_py.
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
maturin build --release --interpreter python$(PYTHON_VERSION) --manifest-path extern/bdk_py/Cargo.toml --out bdk_addon/wheels

# Build t3d-python.
maturin build --release --interpreter python$(PYTHON_VERSION) --manifest-path extern/t3d-python/Cargo.toml --out bdk_addon/wheels

# Read the path to the Blender executable from /tmp/blender_executable_path_env.
# This is set by the Dockerfile.
if [ -f /tmp/blender_executable_path_env ]; then
    export BLENDER_EXECUTABLE_PATH=$(cat /tmp/blender_executable_path_env)
    echo "Blender executable path: $BLENDER_EXECUTABLE_PATH"
else
    echo "Error: /tmp/blender_executable_path_env not found."
    exit 1
fi

ls -la ./bdk_addon/wheels

# Build the extension.
pushd bdk_addon
$BLENDER_EXECUTABLE_PATH --command extension build
popd
