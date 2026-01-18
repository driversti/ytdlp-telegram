#!/bin/bash
set -e

REGISTRY="registry.yurii.live"
IMAGE_NAME="ytdlp-telegram"
VERSION="${1:-v0.1.0}"

echo "🚀 Building and pushing ${REGISTRY}/${IMAGE_NAME}:${VERSION}"

# Create/use buildx builder for multi-arch
docker buildx create --name multiarch --use 2>/dev/null || docker buildx use multiarch

# Build and push multi-arch image with both tags
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ${REGISTRY}/${IMAGE_NAME}:${VERSION} \
  -t ${REGISTRY}/${IMAGE_NAME}:latest \
  --push .

echo "✅ Done! Image pushed to ${REGISTRY}/${IMAGE_NAME}:${VERSION} and :latest"
