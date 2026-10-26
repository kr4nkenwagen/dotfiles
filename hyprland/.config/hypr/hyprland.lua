-- Hyprland without Omarchy: the plain-Arch Hyprland profile (init.sh, DESKTOP=hyprland).
-- The same k4 desktop as on Omarchy (launcher, bar, notifications, OSD) with Hyprland's own
-- defaults; colours from the theme sway-theme-set renders into ~/.local/state/omarchy/current.
-- Same module layout as Omarchy's config, so looknfeel.lua and input.lua are shared with it.

local home = os.getenv("HOME") or ""

-- hyprctl reload re-runs this file: forget the modules so their changes load again.
for module in pairs(package.loaded) do
  if module == "hypr" or module:sub(1, 5) == "hypr." or module:sub(1, 22) == "omarchy.current.theme" then
    package.loaded[module] = nil
  end
end
package.path = home .. "/.local/state/?.lua;" .. home .. "/.config/?.lua;" .. package.path

-- The few helpers the shared files and Omarchy-format themes use (Omarchy has more).
o = o or {}
function o.bind(keys, description, dispatcher, options)
  local opts = options or {}
  opts.description = description
  if type(dispatcher) == "string" then dispatcher = hl.dsp.exec_cmd(dispatcher) end
  hl.bind(keys, dispatcher, opts)
end
function o.exec_on_start(command)
  hl.on("hyprland.start", function() hl.exec_cmd(command) end)
end
o.launch_on_start = o.exec_on_start
function o.window(match, rules)
  rules.match = rules.match or {}
  if type(match) == "string" then rules.match.class = match
  else for k, v in pairs(match) do rules.match[k] = v end end
  hl.window_rule(rules)
end

require("hypr.envs")
require("hypr.defaults")
require("hypr.monitors")
require("hypr.input")
require("hypr.bindings")
require("hypr.looknfeel")
require("hypr.windows")
require("hypr.autostart")

-- The theme's window colours (sway-theme-set renders hyprland.lua; some themes ship their own).
-- Only when there is one: a theme with a mistake in it still shows as a config error.
local theme = home .. "/.local/state/omarchy/current/theme/hyprland.lua"
local f = io.open(theme)
if f then f:close(); require("omarchy.current.theme.hyprland") end

-- What the k4 launcher changed live (Display › Scale, Style › Gaps, Setup › Input devices):
-- sway-menu keeps it in ~/.local/state/sway/hypr-*.lua, loaded last so it wins.
for _, name in ipairs({ "display", "look", "input" }) do
  local path = home .. "/.local/state/sway/hypr-" .. name .. ".lua"
  local kept = io.open(path)
  if kept then kept:close(); dofile(path) end
end
