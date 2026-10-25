if not status is-interactive
    return
end

# Where init.sh puts things that are not in the distro's package manager.
for p in ~/.local/bin ~/go/bin ~/.cargo/bin /usr/local/go/bin /snap/bin
    if test -d $p; and not contains $p $PATH
        set -gx PATH $p $PATH
    end
end

set -gx FZF_DEFAULT_OPTS ''

set -g SCRIPTS "$HOME/scripts"
set -g NOTES "$HOME/notes"
set -g REPOS "$HOME/repos"
set -g CONFIG "$HOME/.config"

# Only shadow the coreutils when the replacement is actually installed.
command -q rg; and alias grep='rg'
command -q eza; and alias ls='eza -lh -a --group-directories-first --total-size --icons=auto'
command -q eza; and alias lt='eza -a --tree --level=2 --long --icons --git'
command -q bat; and alias cat='bat'
command -q dust; and alias du='dust'
command -q fd; and alias find='fd'
command -q duf; and alias df='duf'
command -q nvim; and alias vim='nvim'
command -q fzf; and alias ff='fzf --preview="bat  --style=numbers --color=always {}"'

alias notes="cd $NOTES"
alias scripts="cd $SCRIPTS"
alias repos="cd $REPOS"
alias config="cd $CONFIG"
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias :q='exit && exit'

alias g='git'
alias gc='git checkout'
alias gp='git pull'
alias gph='git pull'
alias gcm='git commit -m'

alias clear='clear'

alias nvp='nvim ~/.config/nvim/lua/plugins/plugins.lua'

alias music='jellyfin-tui'

if command -q keychain
    # keychain picks its output syntax from $SHELL, which is bash here (bash starts fish
    # from .bashrc); without this it prints sh syntax that fish cannot source.
    env SHELL=(command -s fish) keychain --eval --quiet id_ed25519 | source
end
# --cmd cd makes cd itself use zoxide (and adds cdi). Aliasing cd to z instead
# recurses forever on older zoxide (0.9.2 on Ubuntu 24.04), whose jump calls cd.
if command -q zoxide
    zoxide init --cmd cd fish | source
end
if command -q starship
    starship init fish | source
end
# mise: per-project tool versions (odin for ~/repos/k4, node, python, …)
if command -q mise
    mise activate fish | source
end

if not set -q TMUX; and not set -q SSH_CONNECTION
    tmux
end
set -U fish_greeting ""
set -g fish_key_bindings fish_vi_key_bindings
set -Ux CARAPACE_BRIDGES 'zsh,fish,inshellisense'
if command -q carapace
    carapace _carapace | source
end

# Omarchy only
if test -f ~/.local/share/omarchy/default/bash/rc
    source ~/.local/share/omarchy/default/bash/rc
end
clear
