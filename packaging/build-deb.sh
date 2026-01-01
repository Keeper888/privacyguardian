#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="1.0.0"
ARCH=$(dpkg --print-architecture 2>/dev/null || echo "arm64")

PKG_NAME="privacyguardian_${VERSION}_${ARCH}"
BUILD_DIR="$PROJECT_DIR/dist/build-$$"
PKG_DIR="$BUILD_DIR/$PKG_NAME"

echo "Building PrivacyGuardian $VERSION for $ARCH"
echo "==========================================="

rm -rf "$BUILD_DIR"
mkdir -p "$PKG_DIR"

echo "Copying package structure..."
cp -r "$SCRIPT_DIR/debian/DEBIAN" "$PKG_DIR/"
cp -r "$SCRIPT_DIR/debian/usr" "$PKG_DIR/"
mkdir -p "$PKG_DIR/opt/privacyguardian"

sed -i "s/Architecture: arm64/Architecture: $ARCH/" "$PKG_DIR/DEBIAN/control"

echo "Copying application files..."
cp "$PROJECT_DIR/guardian" "$PKG_DIR/opt/privacyguardian/"
cp "$PROJECT_DIR/pg-wrapper" "$PKG_DIR/opt/privacyguardian/"
cp "$PROJECT_DIR/requirements.txt" "$PKG_DIR/opt/privacyguardian/"
cp -r "$PROJECT_DIR/code" "$PKG_DIR/opt/privacyguardian/"

rm -rf "$PKG_DIR/opt/privacyguardian/code/__pycache__"
rm -rf "$PKG_DIR/opt/privacyguardian/code/gui/__pycache__"

echo "Setting permissions..."
chmod 755 "$PKG_DIR/DEBIAN/postinst"
chmod 755 "$PKG_DIR/DEBIAN/prerm"
chmod 755 "$PKG_DIR/opt/privacyguardian/guardian"
chmod 755 "$PKG_DIR/opt/privacyguardian/pg-wrapper"
chmod 644 "$PKG_DIR/DEBIAN/control"
chmod 644 "$PKG_DIR/usr/share/applications/privacyguardian.desktop"

SIZE=$(du -sk "$PKG_DIR/opt" | cut -f1)
sed -i "s/Installed-Size: .*/Installed-Size: $SIZE/" "$PKG_DIR/DEBIAN/control"

echo "Building .deb package..."
mkdir -p "$PROJECT_DIR/dist"
DEB_FILE="$PROJECT_DIR/dist/${PKG_NAME}.deb"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$DEB_FILE"

rm -rf "$BUILD_DIR"

echo ""
echo "Build complete!"
echo "Package: $DEB_FILE"
echo "Size: $(du -h "$DEB_FILE" | cut -f1)"
echo ""
echo "Install with: sudo apt install ./$PKG_NAME.deb"
