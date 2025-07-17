#!/bin/sh
sock=$(ls /run/user/1000 | grep sway-ipc)
set -Ux SWAYSOCK ${sock}
