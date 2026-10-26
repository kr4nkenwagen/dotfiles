-- Window colours for the plain Hyprland profile, rendered by sway-theme-set from the current
-- theme (Omarchy themes that ship their own hyprland.lua use theirs instead).
hl.config({
  general = {
    col = { active_border = "rgb({{ accent_strip }})", inactive_border = "rgba({{ background_strip }}aa)" },
  },
  group = {
    col = { border_active = "rgb({{ accent_strip }})", border_inactive = "rgba({{ background_strip }}aa)" },
  },
})
