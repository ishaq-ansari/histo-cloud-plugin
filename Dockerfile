# Base image can be switched per-architecture (GPU for amd64, CPU for arm64)
ARG BASE_IMAGE=tensorflow/tensorflow:2.15.0-gpu
FROM ${BASE_IMAGE}

LABEL com.nvidia.volumes.needed="nvidia_driver"
LABEL maintainer="Brendon Lutnick - Sarder Lab. <brendonl@buffalo.edu>"
LABEL description="HistomicsTK with TensorFlow 2.x (compat.v1) support"

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV DEBIAN_FRONTEND=noninteractive

CMD echo "================ STARTING THE BUILD ================"

# Remove stale CUDA repo entries if present
RUN rm -f /etc/apt/sources.list.d/cuda.list || true

# ---------------------------
# System dependencies
# ---------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    ca-certificates \
    unzip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libssl-dev \
    libcurl4-openssl-dev \
    libexpat1-dev \
    libhdf5-dev \
    build-essential \
    cmake \
    autoconf \
    automake \
    libtool \
    pkg-config \
    libmemcached-dev \
    memcached \
    \
    # Image / WSI stack (matches conda env intent)
    libopenslide0 \
    openslide-tools \
    libtiff5 \
    libjpeg-turbo8 \
    libpng16-16 \
    \
    # GDAL / geospatial stack
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    \
    # pyvips runtime
    libvips \
    \
    # XML (used by lxml / girder stack)
    libxml2 \
    libxslt1.1 \
    \
    # Optional Qt runtime (headless-safe)
    libegl1 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

CMD echo "================ SYSTEM DEPS DONE ================"

# ---------------------------
# Python sanity check
# ---------------------------
RUN which python && python --version && pip --version

# ---------------------------
# HistomicsTK setup
# ---------------------------
WORKDIR /
ENV htk_path=/HistomicsTK
RUN mkdir -p $htk_path

COPY . $htk_path
WORKDIR $htk_path

# ---------------------------
# Python dependencies
# ---------------------------
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN pip install --no-cache-dir \
    tensorflow-addons \
    tf-keras==2.15.* \
    tf-slim>=1.1.0 \
    pillow-lut \
    six

RUN pip install --no-cache-dir \
    'large-image[memcached]' \
    large-image-source-tiff \
    large-image-source-openslide \
    large-image-source-vips \
    large-image-source-pil \
    girder-slicer-cli-web \
    girder-client \
    ctk-cli \
    sqlalchemy \
    nimfa \
    'opencv-python-headless<4.7' \
    pyvips \
    openpyxl \
    'xlrd<2' \
    termcolor \
    'dask[dataframe]' \
    distributed

# Force NumPy 1.x after all other dependencies (TensorFlow 2.15 is incompatible with NumPy 2.x)
# RUN pip install --no-cache-dir --force-reinstall 'numpy<2.0,>=1.23.5'

# Fix numcodecs/zarr compatibility issue for TIFF support
# The "deprecated" import error occurs with mismatched zarr/numcodecs versions
# Pin compatible versions to avoid the blosc.pyx "cannot import name deprecated" error
RUN pip install --no-cache-dir --force-reinstall 'numcodecs==0.11.0' 'zarr==2.13.6'

# Force NumPy 1.x again after numcodecs/zarr (they may have pulled in NumPy 2.x)
RUN pip install --no-cache-dir --force-reinstall 'numpy<2.0,>=1.23.5'

# Preload libstdc++ to fix mapnik TLS block error
ENV LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6


# ---------------------------
# TF-Slim compatibility shims
# ---------------------------
# Install tf_keras.legacy_tf_layers shim for tf-slim compatibility
# tf-slim expects legacy_tf_layers module which doesn't exist in tf-keras
RUN TF_KERAS_PATH=$(python -c "import tf_keras; print(tf_keras.__path__[0])") && \
    mkdir -p "$TF_KERAS_PATH/legacy_tf_layers" && \
    cp $htk_path/shims/tf_keras/legacy_tf_layers/__init__.py "$TF_KERAS_PATH/legacy_tf_layers/" && \
    cp $htk_path/shims/tf_keras/legacy_tf_layers/normalization.py "$TF_KERAS_PATH/legacy_tf_layers/"

# ---------------------------
# Install HistomicsTK (SCM-safe)
# ---------------------------
# Ensure scikit-build is available for building HistomicsTK
RUN pip install --no-cache-dir scikit-build
# Set version for setuptools-scm since .git folder may not be complete
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HISTOMICSTK=1.0.0 \
    pip install --no-cache-dir . --find-links https://girder.github.io/large_image_wheels
RUN rm -rf /root/.cache/pip/*


# ---------------------------
# Verification
# ---------------------------
RUN python - <<EOF
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()
print("TF version:", tf.__version__)
print("Eager:", tf.executing_eagerly())
EOF

# Pre-generate font cache
RUN python -c "from matplotlib import pylab"

# ---------------------------
# CLI entrypoints
# ---------------------------
WORKDIR $htk_path/histomicstk/cli

RUN python -m slicer_cli_web.cli_list_entrypoint --list_cli
RUN python -m slicer_cli_web.cli_list_entrypoint SegmentWSI --help
# RUN python -m slicer_cli_web.cli_list_entrypoint TrainNetwork --help
# RUN python -m slicer_cli_web.cli_list_entrypoint ExtractFeaturesFromAnnotations --help
# RUN python -m slicer_cli_web.cli_list_entrypoint IngestAperioXML --help

ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]
