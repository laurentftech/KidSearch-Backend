#!/bin/bash
# Cleanup script for KidSearch project
# Removes temporary files, caches, and build artifacts

set -e

echo "🧹 Cleaning up KidSearch project..."
echo ""

# Count files before cleanup
BEFORE=$(find . -type f \( -name "*.pyc" -o -name ".DS_Store" -o -name "*.coverage" -o -name ".coverage" -o -name "*.pyo" -o -name "*.db-journal" \) | grep -v ".venv" | wc -l | tr -d ' ')

echo "📊 Found $BEFORE temporary files to remove"
echo ""

# Remove Python cache files
echo "🐍 Removing Python cache files..."
find . -type f -name "*.pyc" ! -path "./.venv/*" -delete
find . -type f -name "*.pyo" ! -path "./.venv/*" -delete
find . -type d -name "__pycache__" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

# Remove .DS_Store files (macOS)
echo "🍎 Removing .DS_Store files..."
find . -type f -name ".DS_Store" -delete

# Remove coverage files
echo "📊 Removing coverage files..."
find . -type f -name ".coverage" ! -path "./.venv/*" -delete
find . -type f -name "*.coverage" ! -path "./.venv/*" -delete
rm -f coverage.xml
rm -rf htmlcov

# Remove pytest cache
echo "🧪 Removing pytest cache..."
rm -rf .pytest_cache
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove mypy cache
echo "📝 Removing mypy cache..."
rm -rf .mypy_cache

# Remove ruff cache
echo "🔍 Removing ruff cache..."
rm -rf .ruff_cache

# Remove build artifacts
echo "📦 Removing build artifacts..."
rm -rf build dist *.egg-info

# Remove database journal files
echo "💾 Removing database journal files..."
find . -type f -name "*.db-journal" ! -path "./.venv/*" -delete

# Remove log files (but keep the logs directory)
echo "📝 Removing old log files..."
find data/logs -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true

echo ""
echo "✅ Cleanup complete!"

# Count files after cleanup
AFTER=$(find . -type f \( -name "*.pyc" -o -name ".DS_Store" -o -name "*.coverage" -o -name ".coverage" -o -name "*.pyo" -o -name "*.db-journal" \) | grep -v ".venv" | wc -l | tr -d ' ')
REMOVED=$((BEFORE - AFTER))

echo "📊 Removed $REMOVED files"
echo ""
echo "💡 To also clean Docker artifacts, run:"
echo "   docker system prune -a"
