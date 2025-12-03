#!/bin/fish
ssh-keygen -t ed25519 -C "github@jonf.xyz"
bat ~/.ssh/id_ed25519.pub | fish_clipboard_copy
