#!/usr/bin/env bash
maturin build --release --interpreter python3.11 --manifest-path extern/bdk_py/Cargo.toml --out bdk_addon/wheels
maturin build --release --interpreter python3.11 --manifest-path extern/t3d-python/Cargo.toml --out bdk_addon/wheels
pushd bdk_addon
blender --command extension build
popd
