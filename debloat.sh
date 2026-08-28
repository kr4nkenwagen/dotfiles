#!/usr/bin/env bash
# Script to remove specified Omarchy webapp desktop files and uninstall packages via pacman

DESKTOP_DIR="$HOME/.local/share/applications"

# List of webapp desktop entries to remove
WEB_APPS=(
  "Google Youtube"
  "Google Discord"
  "Google Messages"
  "Google Maps"
  "Google Contacts"
  "Google Photos"
  "Zoom"
  "WhatsApp"
  "X"
  "HEY"
)

# List of pacman packages to uninstall
PACKAGES=(
  "moonlight-qt"   # Package name for Moonlight on Arch
  "kdenlive"
  "obs-studio"
  "obsidian"
  "pinga"
  "xournalpp"      # Package name for Xournal++ on Arch
)

echo "=== 1. Removing Webapp Desktop Entries ==="

for app in "${WEB_APPS[@]}"; do
  # Convert application name to lower-case with hyphens (e.g. "Google Youtube" -> "google-youtube")
  formatted_name=$(echo "$app" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

  # List possible filename matching patterns
  files=(
    "$DESKTOP_DIR/$formatted_name.desktop"
    "$DESKTOP_DIR/$app.desktop"
    "$DESKTOP_DIR/omarchy-$formatted_name.desktop"
  )

  removed=0
  for file in "${files[@]}"; do
    if [ -f "$file" ]; then
      rm "$file"
      echo "  [✓] Removed desktop entry: $file"
      removed=1
    fi
  done

  if [ $removed -eq 0 ]; then
    echo "  [-] Desktop file not found: $app"
  fi
done

# Refresh local desktop database
if command -v update-desktop-database &> /dev/null; then
  update-desktop-database "$DESKTOP_DIR"
  echo "Desktop application database updated."
fi

echo ""
echo "=== 2. Uninstalling Packages via Pacman ==="

# Filter list to only include installed packages
TO_REMOVE=()
for pkg in "${PACKAGES[@]}"; do
  if pacman -Qs "^${pkg}$" > /dev/null 2>&1; then
    TO_REMOVE+=("$pkg")
  else
    echo "  [-] Package not installed, skipping: $pkg"
  fi
done

# Run pacman if there are matching installed packages
if [ ${#TO_REMOVE[@]} -gt 0 ]; then
  echo "Uninstalling installed packages: ${TO_REMOVE[*]}"
  sudo pacman -Rs "${TO_REMOVE[@]}"
else
  echo "No target packages are currently installed."
fi

echo ""
echo "Cleanup complete."
