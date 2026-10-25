# fuzzel for the wallpaper and theme pickers: tall rows so the per-entry thumbnails
# (square PNGs, dmenu icons) are readable. The large preview that fuzzel draws when few
# rows match is off: it overlaps the list. Rendered by sway-theme-set next to fuzzel.ini.
[main]
font={{ font }}:size=12
line-height=40
prompt="❯ "
icons-enabled=yes
image-size-ratio=0
lines=10
width=70
horizontal-pad=16
vertical-pad=8
inner-pad=10

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
