-- Extra autostart processes.
-- o.launch_on_start("my-service")
o.launch_on_start("~/scripts/windowrule.sh")
o.launch_on_start("clipse -listen")
-- k4's notifications (Omarchy's are off: disabledPlugins in ~/.config/omarchy/shell.json)
o.launch_on_start("~/.local/bin/k4-notify daemon")
-- LocalSend for k4: receives from phones and computers nearby, sends from Super+Ctrl+S
o.launch_on_start("~/.local/bin/k4-share daemon")
-- The status bar: k4's (k4-bar hides Omarchy's) unless Toggle › Status bar picked Omarchy's
o.exec_on_start("~/.local/bin/sway-menu bar-start")

-- Screen positions set in k4 (Display › Arrangement, Arrange by dragging…): sway-menu keeps
-- them in ~/.local/state/sway/hypr-display.lua; loaded here, after monitors.lua, so they win.
local kept = (os.getenv("HOME") or "") .. "/.local/state/sway/hypr-display.lua"
local f = io.open(kept)
if f then f:close(); dofile(kept) end
