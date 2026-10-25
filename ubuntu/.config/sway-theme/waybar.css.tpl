/* Rendered by sway-theme-set from the current theme; waybar is started with -s on this file. */
@define-color bg     {{ background }};
@define-color fg     {{ foreground }};
@define-color blue   {{ accent }};
@define-color gray   {{ muted }};
@define-color green  {{ green }};
@define-color yellow {{ yellow }};
@define-color red    {{ red }};

* {
  font-family: "Terminess Nerd Font Mono", monospace;
  font-size: 13px;
  min-height: 0;
}

window#waybar {
  background: alpha(@bg, 0.85);
  color: @fg;
}

#workspaces button {
  padding: 0 6px;
  color: @gray;
  background: transparent;
  border: none;
  border-radius: 0;
}

#workspaces button.focused {
  color: @blue;
}

#workspaces button.urgent {
  color: @red;
}

#clock,
#tray,
#wireplumber,
#network,
#bluetooth,
#battery {
  padding: 0 8px;
}

#wireplumber.muted,
#network.disconnected {
  color: @gray;
}

#battery.charging {
  color: @green;
}

#battery.warning:not(.charging) {
  color: @yellow;
}

#battery.critical:not(.charging) {
  color: @red;
}

tooltip {
  background: @bg;
  border: 1px solid @blue;
}

tooltip label {
  color: @fg;
}
