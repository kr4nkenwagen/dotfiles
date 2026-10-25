/* Rendered by sway-theme-set from the current theme; waybar is started with -s on this file.
   Each module gets its own palette colour so the bar reads at a glance:
   text only, no coloured backgrounds: workspaces accent · clock foreground · weather orange · backlight yellow ·
   audio magenta · network cyan · bluetooth blue · battery green/yellow/red by state. */
@define-color bg        {{ background }};
@define-color bg_light  {{ lighter_background }};
@define-color fg        {{ foreground }};
@define-color fg_bright {{ bright_foreground }};
@define-color fg_dim    {{ dark_foreground }};
@define-color accent    {{ accent }};
@define-color selection {{ selection }};
@define-color muted     {{ muted }};
@define-color red       {{ red }};
@define-color orange    {{ orange }};
@define-color yellow    {{ yellow }};
@define-color green     {{ green }};
@define-color cyan      {{ cyan }};
@define-color blue      {{ blue }};
@define-color magenta   {{ magenta }};

* {
  font-family: "{{ font }}", monospace;
  font-size: 13px;
  min-height: 0;
  border: none;
  border-radius: 0;
}

window#waybar {
  background: alpha(@bg, 0.85);
  color: @fg;
}

/* Workspaces: no coloured backgrounds anywhere on the bar, state is carried by the text colour. */
#workspaces {
  margin: 0 6px;
}
#workspaces button {
  padding: 0 8px;
  margin: 0 2px;
  color: @fg_dim;
  background: transparent;
}
#workspaces button:hover {
  color: @fg_bright;
  background: transparent;
  box-shadow: none;
  text-shadow: none;
}
#workspaces button.focused {
  color: @accent;
  font-weight: bold;
}
#workspaces button.urgent {
  color: @red;
  font-weight: bold;
}

#clock {
  color: @fg_bright;
  font-weight: bold;
  padding: 0 10px;
}

/* Right side: one colour per module, dimmed when inactive. */
#custom-weather,
#tray,
#backlight,
#wireplumber,
#network,
#bluetooth,
#battery {
  padding: 0 8px;
  margin: 3px 0;
}
#tray > .passive { -gtk-icon-effect: dim; }
#tray > .needs-attention { -gtk-icon-effect: highlight; }

#custom-weather { color: @orange; }
#custom-weather.stale { color: @muted; }

#backlight { color: @yellow; }

#wireplumber { color: @magenta; }
#wireplumber.muted { color: @muted; }

#network { color: @cyan; }
#network.disconnected { color: @muted; }

#bluetooth { color: @blue; }
#bluetooth.connected { color: @blue; font-weight: bold; }
#bluetooth.off, #bluetooth.disabled { color: @muted; }

#battery { color: @green; }
#battery.charging, #battery.plugged { color: @green; }
#battery.warning:not(.charging) { color: @yellow; }
#battery.critical:not(.charging) {
  color: @red;
  animation: blink 1s steps(2) infinite;
}
@keyframes blink {
  to { color: @muted; }
}

tooltip {
  background: @bg;
  border: 1px solid @accent;
  border-radius: 6px;
}
tooltip label {
  color: @fg;
}
