# The plain Hyprland profile's lock screen, rendered by sway-theme-set from the current theme
# and font (~/.config/hypr/hyprlock.conf sources it).
general {
    ignore_empty_input = true
}

background {
    monitor =
    color = rgb({{ background_strip }})
    path = ~/.local/state/omarchy/current/background
    blur_passes = 3
}

animations {
    enabled = false
}

input-field {
    monitor =
    size = 650, 100
    position = 0, 0
    halign = center
    valign = center
    inner_color = rgba({{ background_strip }}cc)
    outer_color = rgb({{ accent_strip }})
    outline_thickness = 4
    font_family = {{ font }}
    font_color = rgb({{ foreground_strip }})
    placeholder_text = Password
    check_color = rgb({{ accent_strip }})
    fail_color = rgb({{ red_strip }})
    fail_text = <i>$FAIL ($ATTEMPTS)</i>
    rounding = 0
    shadow_passes = 0
    fade_on_empty = false
}
