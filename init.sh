#!/bin/sh

packages="stow tmux qutebrowser fish ghostty ttf-terminus-nerd ttf-space-mono-nerd ttf-bigblueterminal-nerd"

omarchy-snapshot create

mkdir ~/notes
mkdir ~/scripts
mkdir ~/repos

cd ~/repos
git clone https://github.com/kr4nkenwagen/dotfiles
cd dotfiles

yay -Syu --noconfirm
yay -S $packages --noconfirm

stow .
stow --adopt -t ~ fish
stow --adopt -t ~ ghostty
stow --adopt -t ~ hypr
stow --adopt -t ~ nvim
stow --adopt -t ~ omarchy
stow --adopt -t ~ qutebrowser
stow --adopt -t ~ tmux
git reset --hard
stow -t ~ fish
stow -t ~ ghostty
stow -t ~ hypr
stow -t ~ nvim
stow -t ~ omarchy
stow -t ~ qutebrowser
stow -t ~ tmux

mkdir ~/.config/tmux/plugins
git clone https://github.com/tmux-plugins/tpm ~/.config/tmux/plugins

echo "fish" > ~/.bashrc

cp ~/repos/dotfiles/omarchy/.config/omarchy/hooks/* ~/.config/omarchy/hooks/

omarchy-font-set BigBlueTermPlusNerdFont
omarchy-theme-set Nord
cp ~/repos/dotfiles/nord-balloons.png ~/.config/omarchy/themes/nord/backgrounds/
omarchy-theme-bg-next
omarchy-theme-bg-next

pkill alacritty
