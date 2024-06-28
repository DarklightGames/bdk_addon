FROM --platform=linux/amd64 python:3.11
WORKDIR /bdk_addon
RUN apt update

# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN cargo --help
RUN apt install -y mingw-w64
RUN rustup target add x86_64-pc-windows-gnu
RUN rustup toolchain install nightly
RUN rustup default nightly

# Install Maturin
RUN pip install maturin

# Install Blender
ARG BLENDER_PATH="blender-4.2.0-beta+v42.4bde68cdd672-linux.x86_64-release"
ARG BLENDER_URL=https://cdn.builder.blender.org/download/daily/${BLENDER_PATH}.tar.xz
RUN mkdir blender
RUN curl -L $BLENDER_URL -o blender.tar.xz
RUN tar -xf blender.tar.xz
RUN apt install libxxf86vm-dev -y
RUN apt install libxfixes3 -y
RUN apt install libxi-dev -y
RUN apt install libxkbcommon-x11-0 -y
RUN apt install libgl1-mesa-glx -y
ENV PATH="/bdk_addon/${BLENDER_PATH}:${PATH}"

VOLUME /bdk_addon/wheels
ADD . /bdk_addon

# Build the addon.
ENTRYPOINT ["./build.sh"]
