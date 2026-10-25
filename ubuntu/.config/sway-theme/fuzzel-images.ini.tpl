# fuzzel for the wallpaper and theme pickers: tall rows so the per-entry thumbnails
# (dmenu icons, PNG) are readable, and a large preview once the match list is short.
# Rendered by sway-theme-set next to fuzzel.ini.
[main]
font=Terminess Nerd Font Mono:size=12
line-height=42
prompt="❯ "
icons-enabled=yes
image-size-ratio=0.6
lines=10
width=70
horizontal-pad=16
vertical-pad=8
inner-pad=8

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
