#!/bin/sh
set -eu

DOTFILES_DIR="$HOME/repos/dotfiles"
DOTFILES_REPO="https://github.com/kr4nkenwagen/dotfiles"

info() { printf "\033[1;34m:: %s\033[0m\n" "$1"; }
ok()   { printf "\033[1;32m:: %s\033[0m\n" "$1"; }
err()  { printf "\033[1;31m:: %s\033[0m\n" "$1" >&2; }

packages="
  stow
  tmux
  qutebrowser
  fish
  ghostty
  ttf-terminus-nerd
  ttf-space-mono-nerd
  ttf-bigblueterminal-nerd
  python-adblock
  uv
  ollama
  nodejs
  python-pip
  libffi
  openssl
  platformio
  rtorrent
  adw-gtk-theme
  mpv
  steam
  clipse
  ranger
  aerc
  gdb
  tenere
  mcfly
  discordo
  yq
  python-libtmux
  ripgrep
  youtube-dl
"

stow_dirs="
  fish
  ghostty
  hypr
  nvim
  omarchy
  qutebrowser
  tmux
  vesktop
  aerc
"

stow_files="
  .XCompose
"

##########
# SETUP  #
##########
info "Creating directories"
mkdir -p ~/notes ~/scripts ~/repos

omarchy-snapshot create

##########
# DOTFILES#
##########
info "Cloning dotfiles"
if [ -d "$DOTFILES_DIR" ]; then
  err "Dotfiles directory already exists at $DOTFILES_DIR — skipping clone"
else
  git clone "$DOTFILES_REPO" "$DOTFILES_DIR"
fi
cd "$DOTFILES_DIR"

cp scripts/* ~/scripts/

##########
# PACKAGES#
##########
info "Installing packages"
yay -Syu --noconfirm
yay -S $packages --noconfirm

###########
# CHRONOS #
###########
info "Building chronos"
if [ -d chronos ]; then
  err "chronos directory exists — skipping clone"
else
  git clone https://github.com/samuelstranges/chronos
fi
cd chronos
go build .
mkdir -p ~/.config/chronos/calendars/

########
# STOW #
########
info "Stowing dotfiles"
cd "$DOTFILES_DIR"

for dir in $stow_dirs; do
  stow --adopt -t ~ "$dir"
done
for file in $stow_files; do
  stow --adopt -t ~ -S "$file"
done

git reset --hard

for dir in $stow_dirs; do
  stow -t ~ "$dir"
done
for file in $stow_files; do
  stow -t ~ -S "$file"
done

########
# TMUX #
########
info "Setting up tmux"
mkdir -p ~/.config/tmux/plugins
if [ ! -d ~/.config/tmux/plugins/tpm ]; then
  git clone https://github.com/tmux-plugins/tpm ~/.config/tmux/plugins/tpm
fi

grep -qxF 'fish' ~/.bashrc || printf "fish\n" >> ~/.bashrc

##########
# THEMES #
##########
info "Setting up themes"
curl -fsSL https://imbypass.github.io/omarchy-theme-hook/install.sh | bash

cp ~/repos/dotfiles/omarchy/.config/omarchy/hooks/* ~/.config/omarchy/hooks/
cp ~/repos/dotfiles/nord_wallpapers/* ~/.config/omarchy/themes/nord/backgrounds/
cp ~/repos/dotfiles/catppuccin_wallpapers/* ~/.config/omarchy/themes/catppuccin/backgrounds/

omarchy-font-set "Terminess Nerd Font Mono"
omarchy-theme-set osaka-jade
omarchy-theme-bg-next
omarchy-theme-bg-next

##########
# REPOS  #
##########
info "Cloning personal repos"
cd ~/repos
for repo in cherryscript kr4nkenserver astrokr4nk ai-docstring.nvim; do
  if [ ! -d "$repo" ]; then
    git clone "git@github.com:kr4nkenwagen/$repo"
  else
    err "$repo already exists — skipping"
  fi
done

ok "Done — restarting alacritty"
pkill alacritty || true
