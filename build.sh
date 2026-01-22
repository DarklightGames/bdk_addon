#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Parse arguments
TARGET_OS="${1:-linux}"  # Default to linux if not specified

echo "Building for target OS: $TARGET_OS"

# Build UEViewer (Linux only)
if [ "$TARGET_OS" = "linux" ]; then
    pushd extern/UEViewer
    ./build.sh
    popd
    cp ./extern/UEViewer/umodel ./bdk_addon/bin/umodel -v
fi

mkdir -p out/bin
mkdir -p out/wheels

export PYTHON_VERSION="3.11"
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1

# Set maturin target based on OS
if [ "$TARGET_OS" = "windows" ]; then
    MATURIN_TARGET="x86_64-pc-windows-gnu"
    MATURIN_EXTRA_FLAGS="--zig"
    # Don't link to Python for Windows cross-compilation
    export PYO3_NO_PYTHON=1
    echo "Building for Windows (MinGW with Zig)"
else
    MATURIN_TARGET="x86_64-unknown-linux-gnu"
    MATURIN_EXTRA_FLAGS=""
    unset PYO3_NO_PYTHON
    echo "Building for Linux"
fi

# Build bdk_py
maturin build --release \
    --target "$MATURIN_TARGET" \
    --interpreter python${PYTHON_VERSION} \
    --manifest-path extern/bdk_py/Cargo.toml \
    --out bdk_addon/wheels \
    $MATURIN_EXTRA_FLAGS

# Build t3d-python
maturin build --release \
    --target "$MATURIN_TARGET" \
    --interpreter python${PYTHON_VERSION} \
    --manifest-path extern/t3d-python/Cargo.toml \
    --out bdk_addon/wheels \
    $MATURIN_EXTRA_FLAGS

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

# Build the extension (Linux only)
if [ "$TARGET_OS" = "linux" ]; then
    pushd bdk_addon
    $BLENDER_EXECUTABLE_PATH --command extension build
    popd
fi
