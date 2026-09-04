#!/bin/bash
# dwm installer - clones, patches, and builds dwm with config
set -e

DWM_DIR="$HOME/dwm"
DWM_CONFIG="$HOME/.config/dwm/config.def.h"
DWM_VERSION="6.4"

echo "==> Cloning dwm..."
if [ -d "$DWM_DIR" ]; then
  echo "    dwm directory exists at $DWM_DIR, skipping clone"
else
  git clone https://git.suckless.org/dwm "$DWM_DIR"
fi

cd "$DWM_DIR"
git checkout "$DWM_VERSION" 2>/dev/null || echo "Using default branch"

echo "==> Resetting to clean state..."
git checkout -- .
rm -f config.h

echo "==> Copying config..."
cp "$DWM_CONFIG" .

echo "==> Building..."
sudo make clean install

echo "==> Done! dwm installed to /usr/local/bin/dwm"
echo "    Add 'exec dwm' to your .xinitrc or display manager to start"
