#!/bin/bash
FONTSIZE="$(printf "8\n9\n10\n11\n12\n13\n14\n15\n16\n17\n18\n19\n20\n21\n22\n" | dmenu -b -l 0)"
echo "${FONTSIZE}"
sed -ie "s/^.*font-size: .*/  font-size: ${FONTSIZE}px;/" .config/waybar/style.css
sed -ie "s/^font-size = .*/font-size = ${FONTSIZE}/" .config/ghostty/config
