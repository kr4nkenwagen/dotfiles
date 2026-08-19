-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")
--
-- Local variables
local terminal = "uwsm-app -- ghostty"
local browser = "qutebrowser"

-- Application bindings
-- Syntax: o.bind("MOD + KEY", "Description", "command")

hl.unbind("SUPER + RETURN")
o.bind("SUPER + RETURN", "Terminal", terminal .. ' --working-directory="$(omarchy-cmd-terminal-cwd)"')

hl.unbind("SUPER + SHIFT + B")
o.bind("SUPER + SHIFT + B", "Browser", browser)

hl.unbind("SUPER + SHIFT + Z")
o.bind("SUPER + SHIFT + Z", "Spotify", "spotify")

hl.unbind("SUPER + SHIFT + ALT + B")
o.bind("SUPER + SHIFT + ALT + B", "Browser (private)", browser .. " --private")

hl.unbind("SUPER + SHIFT + N")
o.bind("SUPER + SHIFT + N", "Editor", "omarchy-launch-editor")

hl.unbind("SUPER + SHIFT + O")
o.bind(
	"SUPER + SHIFT + O",
	"Obsidian",
	'omarchy-launch-or-focus "^obsidian$" "uwsm-app -- obsidian -disable-gpu --enable-wayland-ime"'
)

hl.unbind("SUPER + SHIFT + SLASH")
o.bind("SUPER + SHIFT + SLASH", "Passwords", "uwsm-app -- 1password")

-- Web apps
hl.unbind("SUPER + SHIFT + A")
o.bind("SUPER + SHIFT + A", "Gemini", 'omarchy-launch-webapp "https://gemini.google.com"')

hl.unbind("SUPER + SHIFT + S")
o.bind("SUPER + SHIFT + S", "Chess", 'omarchy-launch-webapp "https://chess.com"')

-- Window management
hl.unbind("SUPER + W")

hl.unbind("SUPER + X")
o.bind("SUPER + X", "Close window", hl.dsp.window.close())

-- TUI Applications
hl.unbind("SUPER + SHIFT + M")
o.bind("SUPER + SHIFT + M", "Music", "xdg-terminal-exec --app-id=TUI.float -e cmus")

hl.unbind("SUPER + SHIFT + T")
o.bind("SUPER + SHIFT + T", "Activity", "xdg-terminal-exec --app-id=TUI.float -e btop")

hl.unbind("SUPER + SHIFT + F")
o.bind("SUPER + SHIFT + F", "Activity", "xdg-terminal-exec --app-id=TUI.float -e wiremix")

hl.unbind("SUPER + SHIFT + E")
o.bind("SUPER + SHIFT + E", "ranger", "xdg-terminal-exec --app-id=TUI.float -e ranger")

hl.unbind("SUPER + SHIFT + D")
o.bind("SUPER + SHIFT + D", "Discordo", "xdg-terminal-exec --app-id=TUI.float -e discordo")

hl.unbind("SUPER + SHIFT + V")
o.bind("SUPER + SHIFT + V", "clipse", "xdg-terminal-exec --app-id=TUI.float -e clipse")

hl.unbind("SUPER + SHIFT + C")
o.bind("SUPER + SHIFT + C", "Chronos", "xdg-terminal-exec --app-id=TUI.float -e /home/kr4nk/.cargo/bin/jocalsend")

hl.unbind("SUPER + SHIFT + G")
o.bind(
	"SUPER + SHIFT + G",
	"Lazygit",
	[[xdg-terminal-exec --app-id=TUI.float -e sh -c 'cd "$(~/scripts/get_last_tmux_pwd.sh)" && exec lazygit']]
)

hl.unbind("SUPER + SHIFT + Q")
o.bind("SUPER + SHIFT + Q", "bluetui", "xdg-terminal-exec --app-id=TUI.float -e bluetui")

hl.unbind("SUPER + SHIFT + W")
o.bind("SUPER + SHIFT + W", "impala", "xdg-terminal-exec --app-id=TUI.float -e impala")

hl.unbind("SUPER + SHIFT + R")
o.bind("SUPER + SHIFT + R", "aerc", "xdg-terminal-exec --app-id=TUI.float -e aerc")

hl.unbind("SUPER + SPACE")
o.bind("SUPER + SPACE", "Omarchy menu applications", "omarchy-menu toggle applications")

hl.unbind("SUPER + ALT + SPACE")
o.bind("SUPER + ALT + SPACE", "Omarchy menu", "omarchy-menu toggle root")
