ARG PYTHON_VERSION=3.11

FROM --platform=linux/amd64 python:${PYTHON_VERSION}

ARG BLENDER_VERSION=4.4

RUN apt update

# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN apt install -y mingw-w64
RUN rustup target add x86_64-pc-windows-gnu
RUN rustup toolchain install nightly
RUN rustup default nightly

# Install Maturin and Zig (for cross-compilation)
RUN pip install maturin
RUN pip install ziglang

# Install Blender
RUN apt-get update -y && \
    apt-get install -y libxxf86vm-dev libxfixes3 libxi-dev libxkbcommon-x11-0 libgl1 libglx-mesa0 python3 python3-pip \
    libxrender1 libsm6

RUN pip install --upgrade pip
RUN pip install pytest-blender
RUN pip install blender-downloader

# Set BLENDER_EXECUTABLE and BLENDER_PYTHON as environment variables
RUN BLENDER_EXECUTABLE=$(blender-downloader $BLENDER_VERSION --extract --remove-compressed --print-blender-executable) && \
    BLENDER_PYTHON=$(pytest-blender --blender-executable "${BLENDER_EXECUTABLE}") && \
    echo "export BLENDER_EXECUTABLE=${BLENDER_EXECUTABLE}" >> /etc/environment && \
    echo "export BLENDER_PYTHON=${BLENDER_PYTHON}" >> /etc/environment && \
    echo $BLENDER_EXECUTABLE > /blender_executable_path

# Persist BLENDER_EXECUTABLE as an environment variable
RUN echo $(cat /blender_executable_path) > /tmp/blender_executable_path_env && \
    export BLENDER_EXECUTABLE=$(cat /tmp/blender_executable_path_env)
ENV BLENDER_EXECUTABLE /tmp/blender_executable_path_env

RUN apt-get install -y libsdl2-dev

RUN rustup target add x86_64-unknown-linux-gnu
RUN rustup target add x86_64-pc-windows-gnu

ENV PATH="${BLENDER_EXECUTABLE}:${PATH}"

ADD . /bdk_addon

# Build the addon.
WORKDIR /bdk_addon
ENTRYPOINT ["./build.sh"]
CMD ["linux"]
