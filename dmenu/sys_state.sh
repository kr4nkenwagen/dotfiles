#!/bin/sh

case "$(printf "Shutdown\nReboot\nLock\nKill Sway\n" | dmenu -b -l 4 -i -p "system:")" in
  "Shutdown") systemctl poweroff ;;
  "Reboot") systemctl reboot ;;
  "Lock") systemctl soft-reboot;;
  "Kill Sway") pkill sway ;;
  *) exit 1 ;;
esac
