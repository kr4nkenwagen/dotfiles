#!/bin/sh

packages="stow tmux qutebrowser fish ghostty ttf-terminus-nerd"

mkdir ~/notes
mkdir ~/scripts
mkdir ~/repos

cd ~/repos
git clone https://github.com/kr4nkenwagen/dotfiles
cd dotfiles

yay -Syu --noconfirm
yay -S $packages --noconfirm

stow .
stow -t ~ fish
stow -t ~ ghostty
stow -t ~ hypr
stow -t ~ nvim
stow -t ~ omarchy
stow -t ~ qutebrowser
stow -t ~ tmux

mkdir ~/.config/tmux/plugins
cd ~/.config/tmux/plugins
git clone https://github.com/tmux-plugins/tpm
