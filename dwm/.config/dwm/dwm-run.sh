#!/bin/bash
# dwm helper - launch apps via dmenu/rofi (replaces omarchy-menu)
case "$1" in
    terminal)  exec ghostty ;;
    browser)   exec qutebrowser ;;
    editor)    exec nvim ;;
    spotify)   exec spotify ;;
    obsidian)  exec obsidian ;;
    btop)      exec ghostty -e btop ;;
    cmus)      exec ghostty -e cmus ;;
    lazygit)   exec ghostty -e lazygit ;;
    ranger)    exec ghostty -e ranger ;;
    discordo)  exec ghostty -e discordo ;;
    clipse)    exec ghostty -e clipse ;;
    bluetui)   exec ghostty -e bluetui ;;
    impala)    exec ghostty -e impala ;;
    aerc)      exec ghostty -e aerc ;;
    wifi)      exec nmcli dev wifi list | dmenu -l 10 | awk '{print $1}' | xargs -I{} nmcli dev wifi connect "{}" ;;
    *)         echo "Usage: dwm-run {terminal|browser|editor|spotify|btop|cmus|lazygit|ranger|discordo|clipse|bluetui|impala|aerc|wifi}" ;;
esac
