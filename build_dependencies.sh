docker run -it \
    --mount type=bind,src=./bdk_addon/wheels,dst=/bdk_addon/bdk_addon/wheels \
    --mount type=bind,src=./bdk_addon/bin,dst=/bdk_addon/bdk_addon/bin \
    $(docker build -q .)
