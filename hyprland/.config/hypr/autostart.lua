-- Session services: the k4 bar, notifications, LocalSend, the wallpaper, idle lock, polkit.
hl.on("hyprland.start", function()
  hl.exec_cmd("dbus-update-activation-environment --systemd --all")
  hl.exec_cmd("systemctl --user start hyprpolkitagent")
  hl.exec_cmd("hypridle")
  hl.exec_cmd("hyprsunset")
  hl.exec_cmd("gnome-keyring-daemon --start --components=secrets")
  hl.exec_cmd("sway-menu wallpaper-restore")
  hl.exec_cmd("sway-menu bar-start")
  -- notifications: k4's (popups, the Super+N centre), mako without k4
  hl.exec_cmd("sh -c 'command -v k4 >/dev/null && exec k4-notify daemon || exec mako -c ~/.local/state/omarchy/current/theme/mako.ini'")
  hl.exec_cmd("k4-share daemon")
  hl.exec_cmd("sway-menu displays-watch") -- each set of screens gets the layout it had last time
  hl.exec_cmd("clipse -listen")
end)
