#!/bin/bash
set -e

REGISTRY="registry.yurii.live"
IMAGE_NAME="ytdlp-telegram"

# Read version from config.py (single source of truth)
VERSION="v$(grep '__version__' config.py | cut -d'"' -f2)"

echo "🚀 Building and pushing ${REGISTRY}/${IMAGE_NAME}:${VERSION}"

# Create/use buildx builder for multi-arch
docker buildx create --name multiarch --use 2>/dev/null || docker buildx use multiarch

# Build and push multi-arch image with both tags
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ${REGISTRY}/${IMAGE_NAME}:${VERSION} \
  -t ${REGISTRY}/${IMAGE_NAME}:latest \
  --push .

# Update docker-compose.yml with the new version
sed -i '' "s|image: ${REGISTRY}/${IMAGE_NAME}:v[0-9.]*|image: ${REGISTRY}/${IMAGE_NAME}:${VERSION}|" docker-compose.yml

echo "✅ Done! Image pushed to ${REGISTRY}/${IMAGE_NAME}:${VERSION} and :latest"
echo "📝 docker-compose.yml updated to use ${VERSION}"
