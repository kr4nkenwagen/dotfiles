# Window colours, rendered by sway-theme-set from the current theme.
# Included by ~/.config/sway/config; also applied live over swaymsg on theme switch.
#                       border          background      text            indicator       child_border
client.focused          {{ accent }}  {{ accent }}  {{ background }}  {{ accent }}  {{ accent }}
client.focused_inactive {{ muted }}  {{ muted }}  {{ foreground }}  {{ muted }}  {{ muted }}
client.unfocused        {{ muted }}  {{ background }}  {{ foreground }}  {{ muted }}  {{ muted }}
client.urgent           {{ red }}  {{ red }}  {{ background }}  {{ red }}  {{ red }}
