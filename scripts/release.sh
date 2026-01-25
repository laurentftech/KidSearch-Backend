#!/bin/bash
# Script to create a new release
# Usage: ./scripts/release.sh v1.0.0

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v1.0.0"
    exit 1
fi

# Validate version format
if [[ ! $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format vX.Y.Z (e.g., v1.0.0)"
    exit 1
fi

echo "Creating release $VERSION"
echo ""

# Check if git is clean
if [ -n "$(git status --porcelain)" ]; then
    echo "Error: Working directory is not clean. Commit or stash your changes first."
    exit 1
fi

# Fetch latest changes
echo "Fetching latest changes..."
git fetch --all --tags

# Check if tag already exists
if git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo "Error: Tag $VERSION already exists"
    exit 1
fi

# Get current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $BRANCH"

# Confirm
echo ""
read -p "Create tag $VERSION on branch $BRANCH? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted"
    exit 1
fi

# Create and push tag
echo "Creating tag $VERSION..."
git tag -a "$VERSION" -m "Release $VERSION"

echo "Pushing tag to origin..."
git push origin "$VERSION"

echo ""
echo "✅ Release $VERSION created successfully!"
echo ""
echo "GitHub Actions will now:"
echo "  1. Run tests"
echo "  2. Build Docker image"
echo "  3. Push to ghcr.io with tags:"
echo "     - ghcr.io/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | tr '[:upper:]' '[:lower:]'):$VERSION"
echo "     - ghcr.io/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | tr '[:upper:]' '[:lower:]'):${VERSION%.*}"
echo "     - ghcr.io/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | tr '[:upper:]' '[:lower:]'):${VERSION%%.*}"
if [ "$BRANCH" = "main" ]; then
    echo "     - ghcr.io/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | tr '[:upper:]' '[:lower:]'):latest"
fi
echo ""
echo "Monitor progress at: https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"
