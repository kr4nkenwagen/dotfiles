# App launcher. Rendered by sway-theme-set; fuzzel 1.9 has no include, so the whole
# file is generated and passed with --config.
[main]
font={{ font }}:size=12
terminal=ghostty -e
prompt="❯ "
icons-enabled=no
lines=12
width=50
horizontal-pad=16
vertical-pad=8

[colors]
background={{ background_strip }}ee
text={{ foreground_strip }}ff
match={{ accent_strip }}ff
selection={{ selection_strip }}ff
selection-text={{ bright_foreground_strip }}ff
selection-match={{ accent_strip }}ff
border={{ accent_strip }}ff

[border]
width=2
radius=0
