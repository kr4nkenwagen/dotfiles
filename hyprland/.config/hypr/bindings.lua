-- Keys: the Omarchy profile's (hypr/bindings.lua) and Omarchy's own window keys, with plain
-- tools where Omarchy has its omarchy-* commands. The k4 tools are the same everywhere.
local terminal = "ghostty"
local browser = "qutebrowser"
local tui = "xdg-terminal-exec --app-id=TUI.float -e "

-- Applications
o.bind("SUPER + RETURN", "Terminal", terminal)
o.bind("SUPER + SHIFT + B", "Browser", browser)
o.bind("SUPER + SHIFT + ALT + B", "Browser (private)", browser .. " --private")
o.bind("SUPER + SHIFT + N", "Editor", terminal .. " -e nvim")
o.bind("SUPER + SHIFT + T", "Activity", tui .. "btop")
o.bind("SUPER + SHIFT + F", "Audio", tui .. "wiremix")
o.bind("SUPER + SHIFT + E", "Files", tui .. "ranger")
o.bind("SUPER + SHIFT + D", "Discordo", tui .. "discordo")
o.bind("SUPER + SHIFT + V", "clipse", tui .. "clipse")
o.bind("SUPER + SHIFT + G", "Lazygit", tui .. [[sh -c 'cd "$(~/scripts/get_last_tmux_pwd.sh)" && exec lazygit']])
o.bind("SUPER + SHIFT + Q", "Bluetooth", tui .. "bluetui")
o.bind("SUPER + SHIFT + W", "Wi-Fi", "sh -c 'systemctl is-active -q iwd && exec " .. tui .. "impala || exec sway-menu wifi'")
o.bind("SUPER + SHIFT + R", "aerc", tui .. "aerc")
o.bind("SUPER + SHIFT + M", "Music", tui .. "cmus")

-- k4
o.bind("SUPER + SPACE", "Apps (k4)", "sway-menu apps")
o.bind("SUPER + ALT + SPACE", "Menu (k4)", "sway-menu")
o.bind("SUPER + SHIFT + CTRL + SPACE", "Next theme", "sway-menu theme-next")
o.bind("SUPER + CTRL + E", "Emoji (k4)", "emoji-menu")
o.bind("SUPER + CTRL + V", "Clipboard (k4)", "k4-clip")
o.bind("SUPER + CTRL + C", "Capture (k4)", "sway-menu capture")
o.bind("SUPER + CTRL + S", "Send to a nearby device (k4, LocalSend)", "k4-share send clipboard")
o.bind("SUPER + CTRL + G", "Steam", "steam-menu")
o.bind("SUPER + CTRL + M", "Apps (k4)", "k4-apps")
o.bind("SUPER + TAB", "Overview (k4)", "k4-overview")
o.bind("SUPER + ESCAPE", "System menu (k4)", "k4-power")
o.bind("SUPER + SHIFT + ESCAPE", "System performance (k4)", "k4-perf popup")
o.bind("SUPER + SHIFT + S", "SSH hosts, server and keys (k4)", "k4-ssh open")
o.bind("SUPER + N", "Notifications (k4)", "k4-notify center")
o.bind("SUPER + COMMA", "Dismiss notification", "k4-notify dismiss")
o.bind("SUPER + SHIFT + COMMA", "Dismiss all notifications", "k4-notify clear")
o.bind("SUPER + CTRL + COMMA", "Do not disturb", "k4-notify dnd")
o.bind("SUPER + PERIOD", "Tray (k4)", "k4-tray popup")
o.bind("SUPER + CTRL + R", "Reload Hyprland", "hyprctl reload")

-- Windows
o.bind("SUPER + X", "Close window", hl.dsp.window.close())
o.bind("SUPER + J", "Toggle window split", hl.dsp.layout("togglesplit"))
o.bind("SUPER + T", "Toggle floating", hl.dsp.window.float({ action = "toggle" }))
o.bind("SUPER + F", "Full screen", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
o.bind("SUPER + ALT + F", "Full width", hl.dsp.window.fullscreen({ mode = "maximized" }))
for key, dir in pairs({ LEFT = "l", RIGHT = "r", UP = "u", DOWN = "d" }) do
  o.bind("SUPER + " .. key, "Focus " .. dir, hl.dsp.focus({ direction = dir }))
  o.bind("SUPER + SHIFT + " .. key, "Swap window " .. dir, hl.dsp.window.swap({ direction = dir }))
end
o.bind("SUPER + code:20", "Narrower", hl.dsp.window.resize({ x = -100, y = 0, relative = true }))
o.bind("SUPER + code:21", "Wider", hl.dsp.window.resize({ x = 100, y = 0, relative = true }))
o.bind("SUPER + SHIFT + code:20", "Shorter", hl.dsp.window.resize({ x = 0, y = -100, relative = true }))
o.bind("SUPER + SHIFT + code:21", "Taller", hl.dsp.window.resize({ x = 0, y = 100, relative = true }))
o.bind("SUPER + mouse:272", "Move window", hl.dsp.window.drag(), { mouse = true })
o.bind("SUPER + mouse:273", "Resize window", hl.dsp.window.resize(), { mouse = true })
o.bind("ALT + TAB", "Next window", hl.dsp.window.cycle_next())
o.bind("ALT + SHIFT + TAB", "Previous window", hl.dsp.window.cycle_next({ next = false }))

-- Workspaces
for workspace = 1, 10 do
  local key = "code:" .. tostring(workspace + 9)
  o.bind("SUPER + " .. key, "Workspace " .. workspace, hl.dsp.focus({ workspace = tostring(workspace) }))
  o.bind("SUPER + SHIFT + " .. key, "Move to workspace " .. workspace, hl.dsp.window.move({ workspace = tostring(workspace) }))
  o.bind("SUPER + SHIFT + ALT + " .. key, "Move silently to workspace " .. workspace, hl.dsp.window.move({ workspace = tostring(workspace), follow = false }))
end
o.bind("SUPER + S", "Scratchpad", hl.dsp.workspace.toggle_special("scratchpad"))
o.bind("SUPER + ALT + S", "Move to scratchpad", hl.dsp.window.move({ workspace = "special:scratchpad", follow = false }))
o.bind("SUPER + CTRL + TAB", "Former workspace", hl.dsp.focus({ workspace = "previous" }))
o.bind("SUPER + mouse_down", "Next workspace", hl.dsp.focus({ workspace = "e+1" }))
o.bind("SUPER + mouse_up", "Previous workspace", hl.dsp.focus({ workspace = "e-1" }))

-- Screenshots (the Capture menu, Super+Ctrl+C, has the rest)
o.bind("PRINT", "Screenshot of an area", [[sh -c 'grim -g "$(slurp)" - | wl-copy']])
o.bind("SHIFT + PRINT", "Screenshot", "sh -c 'grim - | wl-copy'")

-- Media and brightness, with k4's on-screen display
o.bind("XF86AudioRaiseVolume", "Volume up", "k4-osd volume up", { locked = true, repeating = true })
o.bind("XF86AudioLowerVolume", "Volume down", "k4-osd volume down", { locked = true, repeating = true })
o.bind("XF86AudioMute", "Mute", "k4-osd volume mute", { locked = true })
o.bind("XF86AudioMicMute", "Mute microphone", "k4-osd mic mute", { locked = true })
o.bind("XF86MonBrightnessUp", "Brightness up", "k4-osd brightness up", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "k4-osd brightness down", { locked = true, repeating = true })
o.bind("XF86AudioPlay", "Play", "playerctl play-pause", { locked = true })
o.bind("XF86AudioPause", "Pause", "playerctl play-pause", { locked = true })
o.bind("XF86AudioNext", "Next track", "playerctl next", { locked = true })
o.bind("XF86AudioPrev", "Previous track", "playerctl previous", { locked = true })
