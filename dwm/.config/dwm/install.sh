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

echo "==> Applying patches..."

# vanitygaps
if ! grep -q 'gappiv' config.def.h 2>/dev/null; then
  echo "    Applying vanitygaps..."
  curl -sL "https://dl.suckless.org/dwm/patches/vanitygaps/dwm-vanitygaps-${DWM_VERSION}.patch" | patch -p1 || true
else
  echo "    vanitygaps already applied"
fi

# roundcorners
if ! grep -q 'roundcorners' config.def.h 2>/dev/null; then
  echo "    Applying roundcorners..."
  curl -sL "https://dl.suckless.org/dwm/patches/roundcorners/dwm-roundcorners-${DWM_VERSION}.patch" | patch -p1 || true
else
  echo "    roundcorners already applied"
fi

# diminactive
if ! grep -q 'diminact' config.def.h 2>/dev/null; then
  echo "    Applying diminactive..."
  curl -sL "https://dl.suckless.org/dwm/patches/diminactive/dwm-diminactive-${DWM_VERSION}.patch" | patch -p1 || true
else
  echo "    diminactive already applied"
fi

echo "==> Copying config..."
cp "$DWM_CONFIG" .

echo "==> Building..."
sudo make clean install

echo "==> Done! dwm installed to /usr/local/bin/dwm"
echo "    Add 'exec dwm' to your .xinitrc or display manager to start"
