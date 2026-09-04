# Required patches for dwm (applied to match hyprland config)

Run these from the dwm source directory after cloning dwm:

```bash
# Clone dwm
git clone https://git.suckless.org/dwm ~/dwm && cd ~/dwm

# Apply patches in order (download from suckless.org)
# 1. vanitygaps - for gaps_in / gaps_out
curl -sL https://dl.suckless.org/dwm/patches/vanitygaps/dwm-vanitygaps-6.4.patch | patch -p1

# 2. roundcorners - for rounding = 5
curl -sL https://dl.suckless.org/dwm/patches/roundcorners/dwm-roundcorners-6.4.patch | patch -p1

# 3. diminactive - for dim_inactive = true
curl -sL https://dl.suckless.org/dwm/patches/diminactive/dwm-diminactive-6.4.patch | patch -p1

# Copy config
cp ~/.config/dwm/config.def.h .

# Build and install
sudo make clean install
```

To round corners to 5px, edit config.def.h after patching and add:

```c
static const unsigned int roundcornersradius = 5;
```

Then rebuild: `sudo make clean install`
