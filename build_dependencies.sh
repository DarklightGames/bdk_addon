#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to find an available container command (podman or docker)
find_container_cli() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

CONTAINER_CLI=$(find_container_cli)

if [ -z "$CONTAINER_CLI" ]; then
    echo "Error: Neither Podman nor Docker was found. Please install one of them to proceed."
    exit 1
fi

echo "Using container CLI: $CONTAINER_CLI"

# Build the image and capture its ID
# The '-q' flag is supported by both podman and docker build to suppress output and return only the image ID.
# IMAGE_ID=$($CONTAINER_CLI build -q .)

$CONTAINER_CLI run -it \
    --volume ./bdk_addon/wheels:/bdk_addon/bdk_addon/wheels:z \
    --volume ./bdk_addon/bin:/bdk_addon/bdk_addon/bin:z \
    $($CONTAINER_CLI build -q .)
