#!/usr/bin/env bash
# Bootstrap a machine from this dotfiles repo. Detects Omarchy, Arch or Ubuntu. Safe to re-run.
#
# Fresh machine:
#   curl -fsSL https://raw.githubusercontent.com/kr4nkenwagen/dotfiles/main/init.sh | bash
# Already cloned:
#   ./init.sh
#
# Ubuntu is the work-laptop profile: dev tools, shell, Sway desktop, ghostty, nvim, qutebrowser.
# Tokyo Night everywhere, no games, chat, media or personal repos. Sway is used
# instead of Hyprland because Ubuntu LTS (24.04) has no Hyprland in apt.
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/repos/dotfiles}"
DOTFILES_REPO="${DOTFILES_REPO:-https://github.com/kr4nkenwagen/dotfiles}"
SRC_DIR="$HOME/.local/src"

# Tools installed below land in these; make them visible for the rest of this run.
export PATH="$HOME/.local/bin:$HOME/go/bin:/usr/local/go/bin:$PATH"
export DEBIAN_FRONTEND=noninteractive

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

case "$(uname -m)" in
  x86_64)  DEB_ARCH=amd64; GO_ARCH=amd64; NVIM_ARCH=x86_64; RUST_TARGET=x86_64-unknown-linux-gnu ;;
  aarch64) DEB_ARCH=arm64; GO_ARCH=arm64; NVIM_ARCH=arm64;  RUST_TARGET=aarch64-unknown-linux-gnu ;;
  *) die "Unsupported CPU architecture: $(uname -m)" ;;
esac

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

# Ubuntu dev tools and shell. Go, Neovim, fonts and a few binaries apt lacks
# are handled in ubuntu_extras. Packages missing on a release are skipped with a warning.
ubuntu_packages=(
  stow tmux fish git curl wget unzip jq yq ripgrep fzf fd-find bat eza zoxide duf keychain
  qutebrowser python3-adblock
  nodejs npm python3-pip python3-venv python3-libtmux
  build-essential pkg-config libffi-dev libssl-dev gdb
  fontconfig wl-clipboard btop lazygit ranger
)

# Ubuntu Sway desktop. Pairs with the ubuntu stow package (sway/swaylock/waybar/fuzzel/mako, Tokyo Night).
ubuntu_desktop_packages=(
  sway swaylock swayidle swaybg xdg-desktop-portal-wlr xdg-desktop-portal-gtk lxpolkit
  waybar mako-notifier fuzzel xdg-terminal-exec wireplumber
  brightnessctl playerctl pavucontrol grim slurp network-manager-gnome blueman ghostty
)

stow_dirs=(fish nvim tmux)
case "$OS" in
  omarchy) stow_dirs+=(qutebrowser aerc ghostty hypr omarchy vesktop) ;;
  arch)    stow_dirs+=(qutebrowser aerc ghostty) ;;
  ubuntu)  stow_dirs+=(ghostty qutebrowser ubuntu) ;;
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

apt_has() { apt-cache show "$1" >/dev/null 2>&1; }

# Install only the packages apt actually knows about on this release.
apt_install_available() {
  local pkgs=() missing=() p
  for p in "$@"; do
    if apt_has "$p"; then pkgs+=("$p"); else missing+=("$p"); fi
  done
  [ ${#missing[@]} -eq 0 ] || warn "Not in apt on this release, skipping: ${missing[*]}"
  [ ${#pkgs[@]} -eq 0 ] || sudo apt-get install -y "${pkgs[@]}"
}

# chronos needs Go 1.23, clipse needs 1.24; apt's golang-go is older on LTS releases.
ubuntu_go() {
  if have go; then
    local v maj min
    v="$(go version | sed -E 's/.*go([0-9]+)\.([0-9]+).*/\1 \2/')"
    read -r maj min <<<"$v"
    if [ "$maj" -gt 1 ] || [ "$min" -ge 24 ]; then return; fi
  fi
  local want tmp
  want="$(curl -fsSL 'https://go.dev/VERSION?m=text' | head -1)" || { warn "could not look up Go version"; return; }
  info "Installing $want to /usr/local/go"
  tmp="$(mktemp)"
  curl -fsSL "https://go.dev/dl/${want}.linux-${GO_ARCH}.tar.gz" -o "$tmp" || { warn "Go download failed"; rm -f "$tmp"; return; }
  sudo rm -rf /usr/local/go
  sudo tar -C /usr/local -xzf "$tmp"
  rm -f "$tmp"
}

# LazyVim needs Neovim 0.11+; apt ships older. Use the official release tarball.
ubuntu_neovim() {
  if have nvim; then
    local min
    min="$(nvim --version | head -1 | sed -E 's/.*v[0-9]+\.([0-9]+).*/\1/')"
    [ "${min:-0}" -ge 11 ] && return
  fi
  info "Installing Neovim (latest release) to /opt/nvim"
  local tmp
  tmp="$(mktemp -d)"
  if curl -fsSL "https://github.com/neovim/neovim/releases/latest/download/nvim-linux-${NVIM_ARCH}.tar.gz" -o "$tmp/nvim.tar.gz"; then
    sudo rm -rf /opt/nvim
    sudo mkdir -p /opt/nvim
    sudo tar -C /opt/nvim --strip-components=1 -xzf "$tmp/nvim.tar.gz"
    ln -sfn /opt/nvim/bin/nvim ~/.local/bin/nvim
  else
    warn "Neovim download failed"
  fi
  rm -rf "$tmp"
}

# Nerd Fonts used by ghostty/tmux/swaylock configs. Not packaged for Ubuntu.
ubuntu_fonts() {
  local dir="$HOME/.local/share/fonts/nerd-fonts" font
  for font in Terminus SpaceMono BigBlueTerminal FiraCode; do
    [ -d "$dir/$font" ] && continue
    info "Installing $font Nerd Font"
    mkdir -p "$dir/$font"
    curl -fsSL "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${font}.tar.xz" \
      | tar -xJ -C "$dir/$font" || { warn "$font download failed"; rm -rf "$dir/$font"; }
  done
  fc-cache -f >/dev/null
}

# URL of the first asset in a repo's latest GitHub release matching a regex.
gh_latest_asset() {
  curl -fsSL "https://api.github.com/repos/$1/releases/latest" \
    | grep -o "https://[^\"]*$2" | head -1
}

ubuntu_carapace() {
  local url tmp
  url="$(gh_latest_asset carapace-sh/carapace-bin "carapace-bin_[^\"]*_linux_${DEB_ARCH}\.deb")" || true
  [ -n "$url" ] || { warn "could not find carapace .deb"; return; }
  tmp="$(mktemp --suffix=.deb)"
  curl -fsSL "$url" -o "$tmp" && sudo apt-get install -y "$tmp" || warn "carapace install failed"
  rm -f "$tmp"
}

# dust (du replacement used by the fish aliases) is not in apt; take the release binary.
ubuntu_dust() {
  local url tmp
  url="$(gh_latest_asset bootandy/dust "dust-v[^\"]*-${RUST_TARGET}\.tar\.gz")" || true
  [ -n "$url" ] || { warn "could not find dust release"; return; }
  tmp="$(mktemp -d)"
  curl -fsSL "$url" | tar -xz --strip-components=1 -C "$tmp" && install -m755 "$tmp/dust" ~/.local/bin/dust \
    || warn "dust install failed"
  rm -rf "$tmp"
}

ubuntu_extras() {
  info "Installing extras not in apt"

  # Ubuntu renames these; the fish aliases expect bat/fd.
  have bat || { have batcat && ln -sfn "$(command -v batcat)" ~/.local/bin/bat; }
  have fd  || { have fdfind && ln -sfn "$(command -v fdfind)" ~/.local/bin/fd; }

  ubuntu_go
  ubuntu_neovim
  ubuntu_fonts

  have starship || curl -sS https://starship.rs/install.sh | sh -s -- -y -b "$HOME/.local/bin" || warn "starship install failed"
  have uv || curl -LsSf https://astral.sh/uv/install.sh | sh || warn "uv install failed"
  have carapace || ubuntu_carapace
  have dust || ubuntu_dust
  have clipse || go install github.com/savedra1/clipse@latest || warn "clipse install failed"
}

ubuntu_desktop() {
  info "Installing Sway desktop"
  apt_install_available "${ubuntu_desktop_packages[@]}"
  # Community-maintained .deb builds (linked from ghostty.org) for releases without ghostty in apt.
  have ghostty || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/mkasberg/ghostty-ubuntu/HEAD/install.sh)" \
    || warn "ghostty install failed; see https://github.com/mkasberg/ghostty-ubuntu"
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
      apt_install_available "${ubuntu_packages[@]}"
      ubuntu_extras
      ubuntu_desktop
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
  cd "$DOTFILES_DIR"
  if [ -z "$(git status --porcelain)" ]; then
    info "Updating existing clone at $DOTFILES_DIR"
    git pull --ff-only || warn "could not fast-forward $DOTFILES_DIR, using it as is"
  else
    warn "Dotfiles at $DOTFILES_DIR have local changes, not pulling"
  fi
else
  git clone "$DOTFILES_REPO" "$DOTFILES_DIR"
  cd "$DOTFILES_DIR"
fi

info "Installing packages"
install_packages

info "Installing scripts"
install -m755 scripts/* ~/scripts/

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

# Drop dangling links into this repo left by packages that no longer ship a file.
find ~ ~/.config -maxdepth 1 -xtype l -lname "*${DOTFILES_DIR##*/}*" -print -delete 2>/dev/null | sed 's/^/:: removed stale link /' || true

# Unstow packages that belong to other profiles. An older init.sh stowed the
# Omarchy hypr config everywhere, which breaks a non-Omarchy machine.
all_stow_dirs=(fish nvim tmux aerc qutebrowser ghostty hypr omarchy vesktop ubuntu)
unstow=()
for d in "${all_stow_dirs[@]}"; do
  [ -d "$d" ] || continue
  [[ " ${stow_dirs[*]} " == *" $d "* ]] || unstow+=("$d")
done
# One package per stow call throughout: stow 2.4.1 mis-plans when several
# packages in one invocation share a directory (ghostty and ubuntu both own
# .config/ghostty), failing with conflicts or "unstow_contents() called with
# invalid target".
if [ ${#unstow[@]} -gt 0 ]; then
  info "Unstowing other profiles' packages: ${unstow[*]}"
  for d in "${unstow[@]}"; do
    stow -D -t ~ "$d" || warn "could not unstow $d"
  done
fi

info "Stowing dotfiles: ${stow_dirs[*]}"
# --adopt pulls existing files into the repo so stow can link over them;
# only safe when the repo is clean, since the restore below discards changes.
if [ -z "$(git status --porcelain)" ]; then
  for d in "${stow_dirs[@]}"; do
    stow --adopt -t ~ "$d"
  done
  git checkout -- .
else
  warn "Repo has uncommitted changes, stowing without --adopt"
fi
for d in "${stow_dirs[@]}"; do
  stow -R -t ~ "$d"
done
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

if [ "$OS" = ubuntu ] && have fish; then
  info "Setting fish theme"
  fish -c 'fish_config theme save "TokyoNight Night"' || warn "fish theme not set"
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

if [ "$OS" = ubuntu ]; then
  info "Skipping personal repos on the work profile"
else
  info "Cloning personal repos"
  for repo in "${personal_repos[@]}"; do
    if [ -d ~/repos/$repo ]; then
      warn "$repo already exists, skipping"
    else
      git clone "git@github.com:kr4nkenwagen/$repo" ~/repos/"$repo" \
        || warn "could not clone $repo (is your SSH key set up?)"
    fi
  done
fi

ok "Done ($OS). Log out and back in to pick up all changes."
[ "$OS" = ubuntu ] && info "Pick the Sway session on the login screen."
exit 0
