#!/usr/bin/env bash
# Bootstrap a machine from this dotfiles repo. Detects Omarchy, Arch or Ubuntu. Safe to re-run.
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/repos/dotfiles}"
DOTFILES_REPO="${DOTFILES_REPO:-https://github.com/kr4nkenwagen/dotfiles}"
SRC_DIR="$HOME/.local/src"

info() { printf '\033[1;34m:: %s\033[0m\n' "$1"; }
ok()   { printf '\033[1;32m:: %s\033[0m\n' "$1"; }
warn() { printf '\033[1;33m:: %s\033[0m\n' "$1" >&2; }
die()  { printf '\033[1;31m:: %s\033[0m\n' "$1" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

##########
# DETECT #
##########
detect_os() {
  local id="" id_like=""
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    id="${ID:-}"
    id_like="${ID_LIKE:-}"
  fi

  if have omarchy-snapshot || [ -d "$HOME/.local/share/omarchy" ]; then
    echo omarchy
  elif [ "$id" = arch ] || [[ " $id_like " == *" arch "* ]]; then
    echo arch
  elif [ "$id" = ubuntu ] || [[ " $id_like " == *" ubuntu "* ]] || [[ " $id_like " == *" debian "* ]]; then
    echo ubuntu
  else
    die "Unsupported distro (ID=$id). Need Omarchy, Arch or Ubuntu."
  fi
}

OS="$(detect_os)"
info "Detected: $OS"
[ "$(id -u)" -ne 0 ] || die "Run as your normal user, not root."

###########
# PACKAGES #
###########
# Common set for pacman/AUR (arch, omarchy).
arch_packages=(
  stow tmux qutebrowser fish ghostty
  ttf-terminus-nerd ttf-space-mono-nerd ttf-bigblueterminal-nerd
  python-adblock uv ollama nodejs python-pip libffi openssl platformio
  rtorrent adw-gtk-theme mpv steam clipse ranger aerc gdb tenere mcfly
  discordo yq python-libtmux ripgrep youtube-dl go git neovim
)

# Ubuntu: only what exists in apt. The rest is handled in ubuntu_extras.
ubuntu_packages=(
  stow tmux qutebrowser fish python3-pip python3-libtmux nodejs libffi-dev
  libssl-dev rtorrent mpv ranger aerc gdb yq ripgrep golang-go git curl
  build-essential neovim fonts-terminus
)

stow_dirs=(fish nvim qutebrowser tmux aerc)
case "$OS" in
  omarchy) stow_dirs+=(ghostty hypr omarchy vesktop) ;;
  arch)    stow_dirs+=(ghostty) ;;
  ubuntu)  stow_dirs+=(ghostty) ;;
esac

personal_repos=(CherryScript2 kr4nkengine pass astrokr4nk ai-docstring.nvim)

ensure_yay() {
  have yay && return
  info "Installing yay"
  sudo pacman -S --needed --noconfirm git base-devel
  local tmp
  tmp="$(mktemp -d)"
  git clone https://aur.archlinux.org/yay-bin.git "$tmp/yay-bin"
  (cd "$tmp/yay-bin" && makepkg -si --noconfirm)
  rm -rf "$tmp"
}

ubuntu_extras() {
  info "Installing extras not in apt"
  sudo apt-get install -y cargo || true
  have uv || curl -LsSf https://astral.sh/uv/install.sh | sh || warn "uv install failed"
  # Community-maintained .deb builds (linked from ghostty.org); review the script before trusting it.
  have ghostty || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/mkasberg/ghostty-ubuntu/HEAD/install.sh)" \
    || warn "ghostty install failed; see https://github.com/mkasberg/ghostty-ubuntu"
  have ollama || curl -fsSL https://ollama.com/install.sh | sh || warn "ollama install failed"
  have mcfly || cargo install mcfly || warn "mcfly install failed"
  for tool in clipse; do
    have "$tool" || go install "github.com/savedra1/clipse@latest" || warn "$tool install failed"
  done
}

install_packages() {
  case "$OS" in
    omarchy|arch)
      ensure_yay
      yay -Syu --noconfirm
      yay -S --needed --noconfirm "${arch_packages[@]}"
      ;;
    ubuntu)
      sudo apt-get update
      sudo apt-get install -y "${ubuntu_packages[@]}"
      ubuntu_extras
      ;;
  esac
}

########
# MAIN #
########
for cmd in git curl; do
  have "$cmd" || {
    [ "$OS" = ubuntu ] && sudo apt-get install -y "$cmd" || die "$cmd is required"
  }
done

info "Creating directories"
mkdir -p ~/notes ~/scripts ~/repos "$SRC_DIR" ~/.local/bin

if [ "$OS" = omarchy ]; then
  info "Creating snapshot"
  omarchy-snapshot create || warn "snapshot failed, continuing"
fi

info "Fetching dotfiles"
if [ -d "$DOTFILES_DIR/.git" ]; then
  warn "Dotfiles already at $DOTFILES_DIR, skipping clone"
else
  git clone "$DOTFILES_REPO" "$DOTFILES_DIR"
fi
cd "$DOTFILES_DIR"

info "Installing packages"
install_packages

info "Installing scripts"
cp -p scripts/* ~/scripts/

if [ "$OS" = omarchy ]; then
  info "Removing Omarchy bloat"
  bash "$DOTFILES_DIR/debloat.sh"
fi

info "Building chronos"
if [ ! -d "$SRC_DIR/chronos/.git" ]; then
  git clone https://github.com/samuelstranges/chronos "$SRC_DIR/chronos"
fi
(cd "$SRC_DIR/chronos" && go build -o "$HOME/.local/bin/chronos" .) || warn "chronos build failed"
mkdir -p ~/.config/chronos/calendars

info "Stowing dotfiles: ${stow_dirs[*]}"
# --adopt pulls existing files into the repo so stow can link over them;
# only safe when the repo is clean, since the restore below discards changes.
if [ -z "$(git status --porcelain)" ]; then
  stow --adopt -t ~ "${stow_dirs[@]}"
  git checkout -- .
else
  warn "Repo has uncommitted changes, stowing without --adopt"
fi
stow -R -t ~ "${stow_dirs[@]}"
ln -sfn "$DOTFILES_DIR/.XCompose" ~/.XCompose

info "Setting up tmux"
mkdir -p ~/.config/tmux/plugins
if [ ! -d ~/.config/tmux/plugins/tpm ]; then
  git clone https://github.com/tmux-plugins/tpm ~/.config/tmux/plugins/tpm
fi
~/.config/tmux/plugins/tpm/bin/install_plugins || warn "tmux plugin install failed"

if have fish && ! grep -qxF 'fish' ~/.bashrc 2>/dev/null; then
  printf 'fish\n' >> ~/.bashrc
fi

if [ "$OS" = omarchy ]; then
  info "Setting up Omarchy themes"
  mkdir -p ~/.config/omarchy/hooks
  if ! ls ~/.config/omarchy/hooks | grep -qi theme; then
    curl -fsSL https://imbypass.github.io/omarchy-theme-hook/install.sh | bash
  fi
  for theme in nord catppuccin; do
    if [ -d "$DOTFILES_DIR/${theme}_wallpapers" ]; then
      mkdir -p ~/.config/omarchy/themes/$theme/backgrounds
      cp -n "$DOTFILES_DIR/${theme}_wallpapers"/* ~/.config/omarchy/themes/$theme/backgrounds/
    fi
  done
  omarchy-font-set "Terminess Nerd Font Mono"
  omarchy-theme-set osaka-jade
  omarchy-theme-bg-next
fi

info "Cloning personal repos"
for repo in "${personal_repos[@]}"; do
  if [ -d ~/repos/$repo ]; then
    warn "$repo already exists, skipping"
  else
    git clone "git@github.com:kr4nkenwagen/$repo" ~/repos/"$repo" \
      || warn "could not clone $repo (is your SSH key set up?)"
  fi
done

ok "Done ($OS). Log out and back in to pick up all changes."
