-- What Omarchy's defaults provide and Hyprland's own don't: a layout, quick animations, no
-- logo, and the theme's colours as a fallback until sway-theme-set has run.

hl.config({
  general = {
    layout = "dwindle",
    resize_on_border = false,
    col = { active_border = "rgb(89b4fa)", inactive_border = "rgba(595959aa)" },
  },
  dwindle = { preserve_split = true },
  misc = {
    disable_hyprland_logo = true,
    disable_splash_rendering = true,
    focus_on_activate = true,
    anr_missed_pings = 3,
  },
  cursor = { hide_on_key_press = true },
  ecosystem = { no_update_news = true, no_donation_nag = true },
})

hl.curve("easeOutQuint", { type = "bezier", points = { { 0.23, 1 }, { 0.32, 1 } } })
hl.animation({ leaf = "global", enabled = true, speed = 10, bezier = "default" })
hl.animation({ leaf = "windows", enabled = true, speed = 4.79, bezier = "easeOutQuint" })
hl.animation({ leaf = "fade", enabled = true, speed = 3.03, bezier = "easeOutQuint" })
hl.animation({ leaf = "layers", enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 1.94, bezier = "easeOutQuint" })
