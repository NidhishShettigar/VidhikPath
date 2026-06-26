#!/usr/bin/env bash
# build.sh - Render build script for VidhikPath

set -e  # Exit on error

echo "==> Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-kan \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0

echo "==> Tesseract version:"
tesseract --version

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ">== Removing stale collected static files..."
rm -rf staticfiles
mkdir -p staticfiles

echo ">== Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "==> Applying database migrations..."
python manage.py migrate --noinput

echo "==> Build complete!"
