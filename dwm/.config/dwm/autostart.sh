#!/bin/bash
# dwm autostart
# Run this from .xinitrc or your display manager

# NVIDIA env vars (from hyprland.lua)
export LIBVA_DRIVER_NAME=nvidia
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export NVD_BACKEND=direct
export GDK_SCALE=1

# Compositor (optional, for transparency/blur)
# picom &

# Bar (if using a separate bar like polybar/dwm-bar)
# dwm-bar &

# Wallpaper
# feh --bg-scale ~/.config/omarchy/current/background &

# Notifications
# dunst &

# Keepalive - prevents dwm from crashing on parent death
while true; do
  dwm 2>/dev/null
done
