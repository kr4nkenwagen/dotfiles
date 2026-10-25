// waybar for the Ubuntu profile. Rendered by sway-theme-set (theme colours in the
// calendar markup); waybar is started with -c on this file and -s on waybar.css.
// Clicking a module opens its sway-menu section, the fuzzel stand-in for the
// omarchy-shell panels; scrolling does what the panel's slider would.
{
  "layer": "top",
  "position": "top",
  "height": 26,
  "spacing": 4,
  "modules-left": ["sway/workspaces"],
  "modules-center": ["clock"],
  "modules-right": ["custom/weather", "tray", "backlight", "wireplumber", "network", "bluetooth", "battery"],

  "sway/workspaces": {
    "format": "{name}",
    "disable-scroll": true
  },

  "clock": {
    "format": "{:%A %H:%M}",
    "format-alt": "{:%d %B W%V %Y}",
    "tooltip-format": "<tt>{calendar}</tt>\n<span color='{{ dark_foreground }}'>{:Day %j of the year}</span>",
    "calendar": {
      "mode": "month",
      "weeks-pos": "left",
      "on-scroll": 1,
      "format": {
        "months":   "<span color='{{ bright_foreground }}'><b>{}</b></span>",
        "weekdays": "<span color='{{ accent }}'>{}</span>",
        "weeks":    "<span color='{{ muted }}'>W{:%V}</span>",
        "days":     "<span color='{{ foreground }}'>{}</span>",
        "today":    "<span color='{{ accent }}'><b><u>{}</u></b></span>"
      }
    },
    "actions": {
      "on-click-right": "mode",
      "on-scroll-up": "shift_up",
      "on-scroll-down": "shift_down"
    },
    "on-click-middle": "sway-menu timezone"
  },

  "custom/weather": {
    "exec": "sway-weather",
    "return-type": "json",
    "interval": 900,
    "signal": 8,
    "format": "{}",
    "tooltip": true,
    "on-click": "sway-menu weather",
    "on-click-middle": "sway-weather --refresh",
    "on-click-right": "notify-send Weather \"$(sway-weather --tooltip)\""
  },

  "tray": {
    "spacing": 8
  },

  "backlight": {
    "format": "{icon} {percent}%",
    "format-icons": ["󰃞", "󰃟", "󰃠"],
    "tooltip-format": "{device}",
    "on-click": "sway-menu display",
    "on-scroll-up": "brightnessctl set 5%+",
    "on-scroll-down": "brightnessctl set 5%-"
  },

  "wireplumber": {
    "format": "{icon} {volume}%",
    "format-muted": "󰝟",
    "format-icons": ["󰕿", "󰖀", "󰕾"],
    "tooltip-format": "{node_name}",
    "on-click": "sway-menu audio",
    "on-click-right": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
    "on-scroll-up": "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+",
    "on-scroll-down": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"
  },

  "network": {
    "interval": 2,
    "format-wifi": "󰤨 {essid}",
    "format-ethernet": "󰈀",
    "format-disconnected": "󰤭",
    "tooltip-format-wifi": "{essid}  {signalStrength}%  {frequency} GHz\n{ifname}  {ipaddr}/{cidr}\ngateway {gwaddr}\n↓ {bandwidthDownBytes}  ↑ {bandwidthUpBytes}",
    "tooltip-format-ethernet": "{ifname}  {ipaddr}/{cidr}\ngateway {gwaddr}\n↓ {bandwidthDownBytes}  ↑ {bandwidthUpBytes}",
    "tooltip-format-disconnected": "Disconnected",
    "on-click": "sway-menu network",
    "on-click-right": "nmcli radio wifi \"$(nmcli radio wifi | grep -q enabled && echo off || echo on)\""
  },

  "bluetooth": {
    "format": "󰂯",
    "format-connected": "󰂱 {num_connections}",
    "format-disabled": "󰂲",
    "format-off": "󰂲",
    "tooltip-format": "{controller_alias}  {status}",
    "tooltip-format-connected": "{controller_alias}\n{device_enumerate}",
    "tooltip-format-enumerate-connected": "󰂱 {device_alias}",
    "tooltip-format-enumerate-connected-battery": "󰂱 {device_alias}  {device_battery_percentage}%",
    "on-click": "sway-menu bluetooth",
    "on-click-right": "bluetoothctl power \"$(bluetoothctl show | grep -q 'Powered: yes' && echo off || echo on)\""
  },

  "battery": {
    "states": { "warning": 25, "critical": 10 },
    "format": "{icon} {capacity}%",
    "format-charging": "󰂄 {capacity}%",
    "format-icons": ["󰁺", "󰁼", "󰁾", "󰂀", "󰁹"],
    "tooltip-format": "{timeTo}\n{power:.1f} W"
  }
}
