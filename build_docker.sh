#!/bin/bash
# Build Docker image for HistomicsTK with TensorFlow 2.x

set -e

# Configuration
IMAGE_NAME="ishaqansari/histocloud-tf2"
IMAGE_TAG="GlomSegmentation_v1"
DOCKERFILE="Dockerfile"
PLATFORM=${PLATFORM:-linux/amd64}

# Select base image per platform
if [[ "$PLATFORM" == "linux/arm64" ]]; then
    BASE_IMAGE="tensorflow/tensorflow:2.15.0" # CPU-only for arm64
else
    BASE_IMAGE="tensorflow/tensorflow:2.15.0-gpu" # GPU for amd64
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Building HistomicsTK Docker Image${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "Image: ${YELLOW}${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "Platform: ${YELLOW}${PLATFORM}${NC}"
echo -e "Base: ${YELLOW}${BASE_IMAGE}${NC}"
echo -e "Dockerfile: ${YELLOW}${DOCKERFILE}${NC}"
echo ""

# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}Error: Dockerfile not found!${NC}"
    exit 1
fi

# Build the Docker image (use buildx if available)
echo -e "${GREEN}Starting Docker build...${NC}"
echo ""

if docker buildx version >/dev/null 2>&1; then
    # Ensure a builder exists
    docker buildx create --name htk-builder --use >/dev/null 2>&1 || docker buildx use htk-builder
    docker buildx inspect --bootstrap >/dev/null 2>&1 || true
    docker buildx build \
        --platform="${PLATFORM}" \
        --build-arg BASE_IMAGE="${BASE_IMAGE}" \
        --load \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        -f "${DOCKERFILE}" \
        . 2>&1 | tee docker_build.log
else
    # Fallback to regular build; platform must match host
    docker build \
        --platform="${PLATFORM}" \
        --build-arg BASE_IMAGE="${BASE_IMAGE}" \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        -f "${DOCKERFILE}" \
        . 2>&1 | tee docker_build.log
fi

# Check if build was successful
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Docker build completed successfully!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo -e "Image: ${YELLOW}${IMAGE_NAME}:${IMAGE_TAG}${NC}"
    echo ""
        echo "You can run the container with:"
        if [[ "$PLATFORM" == "linux/arm64" ]]; then
            echo -e "${YELLOW}docker run -it ${IMAGE_NAME}:${IMAGE_TAG} /bin/bash${NC}"
        else
            echo -e "${YELLOW}docker run --gpus all -it ${IMAGE_NAME}:${IMAGE_TAG} /bin/bash${NC}"
        fi
    echo ""
    echo "Build log saved to: docker_build.log"
else
    echo ""
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}Docker build failed!${NC}"
    echo -e "${RED}======================================${NC}"
    echo ""
    echo "Check docker_build.log for details"
    exit 1
fi
