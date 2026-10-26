-- Change the default Omarchy look'n'feel.

-- https://wiki.hypr.land/Configuring/Basics/Variables/#general
hl.config({
	general = {
		--     -- No gaps between windows or borders.
		gaps_in = 0,
		gaps_out = 0,
		border_size = 2,
		--
		--     -- Change to niri-like side-scrolling layout.
		--     layout = "scrolling",
	},
})

-- https://wiki.hypr.land/Configuring/Basics/Variables/#decoration
hl.config({
	decoration = {
		--     -- Use round window corners.
		rounding = 0,
		--
		--     -- Dim unfocused windows (0.0 = no dim, 1.0 = fully dimmed).
		dim_inactive = false,
		dim_strength = 0.5,
		active_opacity = 1.0,
		inactive_opacity = 1.0,
		fullscreen_opacity = 1.0,
	},
})

-- https://wiki.hypr.land/Configuring/Basics/Variables/#animations
-- hl.config({
--   animations = {
--     -- Disable all animations.
--     enabled = false,
--   },
-- })

-- https://wiki.hypr.land/Configuring/Basics/Variables/#layout
hl.config({
	layout = {
		--     -- Avoid overly wide single-window layouts on wide screens.
		single_window_aspect_ratio = { 1.5, 1 },
	},
})

-- https://wiki.hypr.land/Configuring/Layouts/Scrolling-Layout/
-- hl.config({
--   scrolling = {
--     -- See only one column per screen instead of two.
--     column_width = 0.97,
--   },
-- })

-- See-through windows show the wallpaper, never the windows behind them. Hyprland only has
-- that as blur's xray (it samples the wallpaper and the bottom layers), so blur is on with no
-- passes and no colour change: the wallpaper as it is, not blurred.
-- https://wiki.hypr.land/Configuring/Basics/Variables/#blur
hl.config({
	decoration = {
		blur = {
			enabled = true,
			xray = true,
			new_optimizations = true,
			size = 0,
			passes = 0,
			noise = 0.0,
			contrast = 1.0,
			brightness = 1.0,
			vibrancy = 0.0,
			vibrancy_darkness = 0.0,
			popups = true,
		},
	},
})

-- k4's launcher, popups, system menu, notifications, OSD and the bar's tooltip and hover preview do the same (their clear
-- parts left alone). The overview and the click catcher are not blurred: they cover the whole
-- output and their dimming should show the windows.
hl.layer_rule({ match = { namespace = "^(k4|k4-osd|k4-bar|k4-power|k4-notify)$" }, blur = true, ignore_alpha = 0.05 })

-- The bar and the notification popups change size as tooltips, the workspace preview and
-- notifications come and go: no layer animation, or Hyprland draws them stretched while it
-- animates the new size (Omarchy does the same for its own bar).
hl.layer_rule({ match = { namespace = "^(k4-bar|k4-notify)$" }, no_anim = true, animation = "none" })
