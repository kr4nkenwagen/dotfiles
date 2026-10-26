-- Wayland for toolkits, and ~/.local/bin (k4, sway-menu) on the PATH binds run with.
local home = os.getenv("HOME") or ""

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_QPA_PLATFORMTHEME", "gtk3")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("XCOMPOSEFILE", home .. "/.XCompose")
hl.env("PATH", home .. "/.local/bin:" .. home .. "/.cargo/bin:" .. home .. "/go/bin:" .. (os.getenv("PATH") or "/usr/local/bin:/usr/bin"))
