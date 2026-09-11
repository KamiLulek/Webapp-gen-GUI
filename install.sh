#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_SOURCE="${1:-$PROJECT_DIR/webapp-gen}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="$HOME/.local/share/icons/webapp-ico"
DESKTOP_SOURCE="$PROJECT_DIR/resources/webapp-gen.desktop"

[[ -x "$BIN_SOURCE" ]] || {
    echo "Brak binarki: $BIN_SOURCE. Najpierw uruchom ./build.sh" >&2
    exit 1
}

[[ -f "$DESKTOP_SOURCE" ]] || {
    echo "Brak wygenerowanego pliku: $DESKTOP_SOURCE. Najpierw uruchom ./build.sh" >&2
    exit 1
}

install -Dm755 "$BIN_SOURCE" "$BIN_DIR/webapp-gen"
install -Dm644 "$PROJECT_DIR/resources/webapp-gen.ico" "$ICON_DIR/webapp-gen.ico"
install -Dm644 "$DESKTOP_SOURCE" "$APP_DIR/webapp-gen.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" || true
echo "Zainstalowano: $BIN_DIR/webapp-gen"
