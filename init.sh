#!/bin/sh

cd ~

packages="stow \
  tmux \
  qutebrowser \
  fish \
  ghostty \
  ttf-terminus-nerd \
  ttf-space-mono-nerd \
  ttf-bigblueterminal-nerd \
  python-adblock \
  uv \
  python-adblock \
  ollama \
  nodejs \
  python-pip \
  libffi \
  openssl \
  platformio \
  rtorrent \
  adw-gtk-theme \
  mpv \
  steam \
  clipse \
  ranger \
  aerc \
  gdb \
  tenere \
  mcfly \
  discordo \
  yq \
  python-libtmux"


omarchy-snapshot create

mkdir ~/notes
mkdir ~/scripts
mkdir ~/repos

cd ~/repos
rm -rdf dotfiles
git clone https://github.com/kr4nkenwagen/dotfiles
cd dotfiles

cp scripts/* ~/scripts/

yay -Syu --noconfirm
yay -S $packages --noconfirm

###########
# CHRONOS #
###########
git clone https://github.com/samuelstranges/chronos
cd chronos
go build .
mkdir -p ~/.config/chronos/calendars/

########
# STOW #
########
stow --adopt -t ~ fish
stow --adopt -t ~ ghostty
stow --adopt -t ~ hypr
stow --adopt -t ~ nvim
stow --adopt -t ~ omarchy
stow --adopt -t ~ qutebrowser
stow --adopt -t ~ tmux
stow --adopt -t ~ vesktop
git reset --hard
stow -t ~ fish
stow -t ~ ghostty
stow -t ~ hypr
stow -t ~ nvim
stow -t ~ omarchy
stow -t ~ qutebrowser
stow -t ~ tmux
stow -t ~ vesktop

########
# TMUX #
########
mkdir -p ~/.config/tmux/plugins
git clone https://github.com/tmux-plugins/tpm ~/.config/tmux/plugins/tpm

printf "fish" >> ~/.bashrc


##########
# THEMES #
##########
curl -fsSL https://imbypass.github.io/omarchy-theme-hook/install.sh | bash

cp ~/repos/dotfiles/omarchy/.config/omarchy/hooks/* ~/.config/omarchy/hooks/

cp ~/repos/dotfiles/nord_wallpapers/* ~/.config/omarchy/themes/nord/backgrounds/
cp ~/repos/dotfiles/catppuccin_wallpapers/* ~/.config/omarchy/themes/catppuccin/backgrounds/
omarchy-font-set "Terminess Nerd Font Mono"
omarchy-theme-set osaka-jade
omarchy-theme-bg-next
omarchy-theme-bg-next

pkill alacritty
