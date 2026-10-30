-- Override Omarchy's default-opacity rule (default/hypr/windows.lua:25).
-- The Omarchy default tags all windows and sets opacity = "0.985 0.96";
-- this later rule flips it back to fully opaque.
o.window({ tag = "default-opacity" }, { opacity = "1 1" })

-- Let CS2 request tearing for lowest input latency (needs general.allow_tearing = true).
o.window("cs2", { immediate = true })

-- k4's corner player (k4-youtube, k4-jellyfin): small, in the top-left corner of every workspace (pinned),
-- never taking focus. Its own app id keeps it out of mpv's centered floating rules.
o.window({ class = "^k4-pip$" }, {
  tag = "-default-opacity",
  float = true,
  pin = true,
  no_initial_focus = true,
  no_dim = true,
  size = { 600, 338 },
  keep_aspect_ratio = true,
  border_size = 0,
  opacity = "1 1",
  move = { "40", "(monitor_h*0.04)" },
})
