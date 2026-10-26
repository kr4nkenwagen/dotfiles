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

-- The k4 launcher (sway-menu, menus stow package): apps, then every menu of the suite.
hl.unbind("SUPER + SPACE")
o.bind("SUPER + SPACE", "Apps (k4)", "sway-menu apps")

hl.unbind("SUPER + ALT + SPACE")
o.bind("SUPER + ALT + SPACE", "Menu (k4)", "sway-menu")

hl.unbind("SUPER + CTRL + E")
o.bind("SUPER + CTRL + E", "Emoji (k4)", "emoji-menu")

-- Steam in the k4 launcher (steam-menu, menus stow package): games with cover art, status, store.
o.bind("SUPER + CTRL + G", "Steam", "steam-menu")
-- Every app integration (Steam, GitHub, Spotify, Docker, Ollama, Clipboard) in one k4 menu.
o.bind("SUPER + CTRL + M", "Apps (k4)", "k4-apps")

-- Media keys through k4-osd: k4's on-screen display while the k4 bar runs (Omarchy's otherwise).
for _, k in ipairs({ "XF86AudioRaiseVolume", "XF86AudioLowerVolume", "XF86AudioMute", "XF86AudioMicMute", "XF86MonBrightnessUp", "XF86MonBrightnessDown" }) do
	hl.unbind(k)
end
o.bind("XF86AudioRaiseVolume", "Volume up", "k4-osd volume up", { locked = true, repeating = true })
o.bind("XF86AudioLowerVolume", "Volume down", "k4-osd volume down", { locked = true, repeating = true })
o.bind("XF86AudioMute", "Mute", "k4-osd volume mute", { locked = true })
o.bind("XF86AudioMicMute", "Mute microphone", "k4-osd mic mute", { locked = true })
o.bind("XF86MonBrightnessUp", "Brightness up", "k4-osd brightness up", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "k4-osd brightness down", { locked = true, repeating = true })

-- Super+Tab: k4's overview of every workspace (it was "next workspace"; Super+Tab again closes it).
hl.unbind("SUPER + TAB")
o.bind("SUPER + TAB", "Overview (k4)", "k4-overview")

-- Super+Esc: k4's system menu (lock, suspend, hibernate, log out, reboot, shut down) in place of
-- Omarchy's; Super+Esc again closes it.
hl.unbind("SUPER + ESCAPE")
o.bind("SUPER + ESCAPE", "System menu (k4)", "k4-power")

-- Super+Ctrl+V: clipse's clipboard history in k4; Super+Ctrl+C: k4's Capture menu (screenshots,
-- recordings, the color picker), both in place of Omarchy's.
hl.unbind("SUPER + CTRL + V")
o.bind("SUPER + CTRL + V", "Clipboard (k4)", "clipse-menu")
hl.unbind("SUPER + CTRL + C")
o.bind("SUPER + CTRL + C", "Capture (k4)", "sway-menu capture")

-- Notifications through k4 (k4-notify; it replaces Omarchy's notification service): Super+N the
-- centre, and Omarchy's comma keys on k4's service.
o.bind("SUPER + N", "Notifications (k4)", "k4-notify center")
hl.unbind("SUPER + comma")
o.bind("SUPER + comma", "Dismiss last notification", "k4-notify dismiss")
hl.unbind("SUPER + SHIFT + comma")
o.bind("SUPER + SHIFT + comma", "Dismiss all notifications", "k4-notify clear")
hl.unbind("SUPER + CTRL + comma")
o.bind("SUPER + CTRL + comma", "Do not disturb", "k4-notify dnd")
hl.unbind("SUPER + ALT + comma")
o.bind("SUPER + ALT + comma", "Invoke last notification", "k4 --notify-ctl invoke-last")
hl.unbind("SUPER + SHIFT + ALT + comma")
o.bind("SUPER + SHIFT + ALT + comma", "Notification history", "k4-notify center")
