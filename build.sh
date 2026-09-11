#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VERSION="$(tr -d '[:space:]' < "$PROJECT_DIR/version.md")"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "Nieprawidłowa wersja w version.md: $VERSION" >&2
    exit 1
fi

ICON_SOURCE="$PROJECT_DIR/resources/webapp-gen.ico"
DESKTOP_TEMPLATE="$PROJECT_DIR/resources/webapp-gen.desktop.in"
DESKTOP_OUTPUT="$PROJECT_DIR/resources/webapp-gen.desktop"
INSTALL_BIN="${XDG_BIN_HOME:-$HOME/.local/bin}/webapp-gen"
INSTALL_ICON="$HOME/.local/share/icons/webapp-ico/webapp-gen.ico"

[[ -f "$ICON_SOURCE" ]] || {
    echo "Brak ikony: $ICON_SOURCE" >&2
    exit 1
}

python -m nuitka \
    --onefile \
    --enable-plugin=pyside6 \
    --include-data-file=resources/webapp-gen.ico=webapp-gen.ico \
    --include-data-file=version.md=version.md \
    --output-filename=webapp-gen \
    webapp-gen.py

sed \
    -e "s|@EXEC@|$INSTALL_BIN|g" \
    -e "s|@ICON@|$INSTALL_ICON|g" \
    -e "s|@VERSION@|$VERSION|g" \
    "$DESKTOP_TEMPLATE" > "$DESKTOP_OUTPUT"

echo "Built webapp-gen $VERSION:"
echo "  $PROJECT_DIR/webapp-gen"
echo "  $DESKTOP_OUTPUT"
