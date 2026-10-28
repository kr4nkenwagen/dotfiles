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
o.bind("SUPER + ALT + M", "Messenger (k4)", "k4-messenger window")
o.bind("SUPER + ALT + N", "Notifications: keyboard", "k4-notify focus") -- ↑↓ ↵ 1–3 Del Space r(eply) Esc on the popups
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

-- ---------------------------------------------------------------------------------------------
-- The rest of Omarchy's keys, with plain tools in place of its omarchy-* commands
-- ---------------------------------------------------------------------------------------------
local menu = "sway-menu"

-- Universal copy and paste: Ctrl+C/V, or Ctrl/Shift+Insert in a terminal. Sent through Hyprland
-- (a virtual keyboard would merge the held Super into the chord), down then up.
local function send_once(mods, key)
  return function()
    hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
    hl.timer(function() hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" })) end, { timeout = 50, type = "oneshot" })
  end
end
local function in_terminal()
  local w = hl.get_active_window()
  local class = w and (w.class or w.initialClass or "") or ""
  return class:find("ghostty") or class:find("kitty") or class:find("foot") or class:find("Alacritty") or class:find("TUI")
end
o.bind("SUPER + C", "Universal copy", function() if in_terminal() then send_once("CTRL", "Insert")() else send_once("CTRL", "C")() end end)
o.bind("SUPER + V", "Universal paste", function() if in_terminal() then send_once("SHIFT", "Insert")() else send_once("CTRL", "V")() end end)

-- Applications
o.bind("SUPER + ALT + RETURN", "Tmux", terminal .. " -e tmux new-session -A -s main")
o.bind("SUPER + SHIFT + RETURN", "Browser", browser)
o.bind("SUPER + SHIFT + C", "Chronos", tui .. "chronos")
o.bind("SUPER + SHIFT + O", "Obsidian", "obsidian")
o.bind("SUPER + SHIFT + Z", "Spotify", "spotify")
o.bind("SUPER + SHIFT + SLASH", "Passwords", "1password")
o.bind("SUPER + CTRL + P", "Passwords (k4, pass)", "pass-menu")
o.bind("SUPER + CTRL + T", "Activity", tui .. "btop")
o.bind("SUPER + SHIFT + A", "Gemini", browser .. " https://gemini.google.com")
o.bind("SUPER + SHIFT + ALT + A", "Grok", browser .. " https://grok.com")
o.bind("SUPER + SHIFT + Y", "YouTube", browser .. " https://youtube.com/")
o.bind("SUPER + SHIFT + P", "Google Photos", browser .. " https://photos.google.com/")
o.bind("SUPER + SHIFT + X", "X", browser .. " https://x.com/")
o.bind("SUPER + SHIFT + ALT + X", "X Post", browser .. " https://x.com/compose/post")
o.bind("SUPER + SHIFT + ALT + G", "WhatsApp", browser .. " https://web.whatsapp.com/")
o.bind("SUPER + SHIFT + CTRL + G", "Google Messages", browser .. " https://messages.google.com/web")

-- The launcher's pages and toggles, where Omarchy has its own menus
o.bind("SUPER + K", "Keybindings", menu .. " keybindings")
o.bind("SUPER + CTRL + A", "Audio", menu .. " audio")
o.bind("SUPER + CTRL + B", "Bluetooth", menu .. " bluetooth")
o.bind("SUPER + CTRL + W", "Network", menu .. " network")
o.bind("SUPER + CTRL + D", "Display", menu .. " display")
o.bind("SUPER + CTRL + ALT + D", "Calendar", menu .. " calendar")
o.bind("SUPER + CTRL + ALT + B", "Battery", menu .. " battery")
o.bind("SUPER + CTRL + ALT + W", "Weather", menu .. " weather")
o.bind("SUPER + CTRL + SPACE", "Background switcher", menu .. " wallpaper")
o.bind("SUPER + SHIFT + SPACE", "Toggle the bar", menu .. " call toggle_bar")
o.bind("SUPER + SHIFT + BACKSPACE", "Toggle window gaps", menu .. " call toggle_gaps")
o.bind("SUPER + CTRL + L", "Lock", "loginctl lock-session")
o.bind("SUPER + CTRL + N", "Night light", menu .. " call toggle_night")
o.bind("SUPER + CTRL + I", "Idle lock", menu .. " call toggle_idle")
o.bind("SUPER + ALT + COMMA", "Invoke last notification", "k4 --notify-ctl invoke-last")
o.bind("SUPER + SHIFT + ALT + COMMA", "Notification history", "k4-notify center")
o.bind("SUPER + PRINT", "Color picker", menu .. " call color_picker")
o.bind("ALT + PRINT", "Screen recording", menu .. " call record_toggle")

-- Windows: pop out, pseudo, transparency, tiled full screen
o.bind("SUPER + O", "Pop window out (float & pin)", function()
  hl.dispatch(hl.dsp.window.float({ action = "toggle" }))
  hl.dispatch(hl.dsp.window.pin())
end)
o.bind("SUPER + P", "Pseudo window", hl.dsp.window.pseudo())
o.bind("SUPER + L", "Toggle workspace layout", hl.dsp.layout("togglesplit"))
o.bind("SUPER + BACKSPACE", "Toggle window transparency", hl.dsp.window.set_prop({ prop = "opaque", value = "toggle" }))
o.bind("SUPER + CTRL + F", "Tiled full screen", hl.dsp.window.fullscreen({ mode = "maximized" }))
o.bind("CTRL + ALT + DELETE", "Close all windows", function()
  for _, w in ipairs(hl.get_windows() or {}) do hl.dispatch(hl.dsp.window.close({ window = "address:" .. w.address })) end
end)

-- Groups (Hyprland's tabs)
o.bind("SUPER + G", "Toggle window grouping", hl.dsp.group.toggle())
o.bind("SUPER + ALT + G", "Move window out of group", hl.dsp.window.move({ out_of_group = true }))
for key, dir in pairs({ LEFT = "l", RIGHT = "r", UP = "u", DOWN = "d" }) do
  o.bind("SUPER + ALT + " .. key, "Move window into group " .. dir, hl.dsp.window.move({ into_group = dir }))
  o.bind("SUPER + SHIFT + ALT + " .. key, "Move workspace to monitor " .. dir, hl.dsp.workspace.move({ monitor = dir }))
end
o.bind("SUPER + ALT + TAB", "Next window in group", hl.dsp.group.next())
o.bind("SUPER + ALT + SHIFT + TAB", "Previous window in group", hl.dsp.group.prev())
o.bind("SUPER + CTRL + LEFT", "Group focus left", hl.dsp.group.prev())
o.bind("SUPER + CTRL + RIGHT", "Group focus right", hl.dsp.group.next())
o.bind("SUPER + ALT + mouse_down", "Next window in group", hl.dsp.group.next())
o.bind("SUPER + ALT + mouse_up", "Previous window in group", hl.dsp.group.prev())
for index = 1, 5 do
  o.bind("SUPER + ALT + code:" .. tostring(index + 9), "Group window " .. index, hl.dsp.group.active({ index = index }))
end

-- Workspaces and monitors
o.bind("SUPER + SHIFT + TAB", "Previous workspace", hl.dsp.focus({ workspace = "e-1" }))
o.bind("CTRL + ALT + TAB", "Next monitor", hl.dsp.focus({ monitor = "+1" }))
o.bind("CTRL + ALT + SHIFT + TAB", "Previous monitor", hl.dsp.focus({ monitor = "-1" }))
o.bind("SUPER + CTRL + DELETE", "Toggle the laptop display", menu .. " call laptop_toggle")

-- Finer and coarser resize
o.bind("SUPER + ALT + code:20", "Narrower a little", hl.dsp.window.resize({ x = -25, y = 0, relative = true }))
o.bind("SUPER + ALT + code:21", "Wider a little", hl.dsp.window.resize({ x = 25, y = 0, relative = true }))
o.bind("SUPER + SHIFT + ALT + code:20", "Shorter a little", hl.dsp.window.resize({ x = 0, y = -25, relative = true }))
o.bind("SUPER + SHIFT + ALT + code:21", "Taller a little", hl.dsp.window.resize({ x = 0, y = 25, relative = true }))
o.bind("SUPER + CTRL + code:20", "Narrower a lot", hl.dsp.window.resize({ x = -300, y = 0, relative = true }))
o.bind("SUPER + CTRL + code:21", "Wider a lot", hl.dsp.window.resize({ x = 300, y = 0, relative = true }))
o.bind("SUPER + CTRL + SHIFT + code:20", "Shorter a lot", hl.dsp.window.resize({ x = 0, y = -300, relative = true }))
o.bind("SUPER + CTRL + SHIFT + code:21", "Taller a lot", hl.dsp.window.resize({ x = 0, y = 300, relative = true }))

-- Media, brightness and hardware keys
o.bind("ALT + XF86AudioRaiseVolume", "Volume up precise", "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 1%+", { locked = true, repeating = true })
o.bind("ALT + XF86AudioLowerVolume", "Volume down precise", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 1%-", { locked = true, repeating = true })
o.bind("ALT + XF86MonBrightnessUp", "Brightness up precise", "brightnessctl set 1%+", { locked = true, repeating = true })
o.bind("ALT + XF86MonBrightnessDown", "Brightness down precise", "brightnessctl set 1%-", { locked = true, repeating = true })
o.bind("SHIFT + XF86MonBrightnessUp", "Brightness maximum", "brightnessctl set 100%", { locked = true })
o.bind("SHIFT + XF86MonBrightnessDown", "Brightness minimum", "brightnessctl set 1%", { locked = true })
o.bind("ALT + XF86AudioPlay", "Next track", "playerctl next", { locked = true })
o.bind("ALT + SHIFT + XF86AudioPlay", "Previous track", "playerctl previous", { locked = true })
o.bind("SHIFT + XF86AudioMute", "Switch audio output", menu .. " audio")
o.bind("XF86KbdBrightnessUp", "Keyboard brightness up", "brightnessctl -d '*::kbd_backlight' set 10%+", { locked = true, repeating = true })
o.bind("XF86KbdBrightnessDown", "Keyboard brightness down", "brightnessctl -d '*::kbd_backlight' set 10%-", { locked = true, repeating = true })
o.bind("XF86PowerOff", "Power menu", "k4-power")
o.bind("XF86Eject", "Eject media", "eject", { locked = true })
o.bind("switch:on:Lid Switch", nil, menu .. " call laptop_off", { locked = true })
o.bind("switch:off:Lid Switch", nil, menu .. " call laptop_on", { locked = true })
