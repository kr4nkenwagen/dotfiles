#!/bin/bash

hyprctl -i events | while read -r event; do
    if [[ "$event" == *"openwindow"* ]] ||
       [[ "$event" == *"closewindow"* ]] ||
       [[ "$event" == *"movewindow"* ]] ||
       [[ "$event" == *"focus"* ]]; then
        WS=$(hyprctl -j monitors | jq '.[] | select(.focused).activeWorkspace.id')
        COUNT=$(hyprctl -j clients | jq "[.[] | select(.workspace.id == $WS and .floating == false)] | length")
        if [ "$COUNT" -eq 1 ]; then
            WIN=$(hyprctl -j clients | jq -r ".[] | select(.workspace.id == $WS and .floating == false).address")
            hyprctl dispatch togglefloating $WIN
            hyprctl dispatch resizewindowpixel exact 50% 80% $WIN
            hyprctl dispatch centerwindow $WIN
        else
            for WIN in $(hyprctl -j clients | jq -r ".[] | select(.workspace.id == $WS and .floating == true).address"); do
                hyprctl dispatch togglefloating $WIN
            done
        fi
    fi
done

