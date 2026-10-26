-- Extra autostart processes.
-- o.launch_on_start("my-service")
o.launch_on_start("~/scripts/windowrule.sh")
o.launch_on_start("clipse -listen")
-- k4's notifications (Omarchy's are off: disabledPlugins in ~/.config/omarchy/shell.json)
o.launch_on_start("~/.local/bin/k4-notify daemon")
-- The status bar: k4's (k4-bar hides Omarchy's) unless Toggle › Status bar picked Omarchy's
o.exec_on_start("~/.local/bin/sway-menu bar-start")
