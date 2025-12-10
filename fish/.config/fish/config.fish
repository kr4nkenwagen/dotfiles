if not status is-interactive
    return
end

set -g SCRIPTS "$HOME/scripts"
set -g NOTES "$HOME/notes"
set -g REPOS "$HOME/repos"
set -g CONFIG "$HOME/.config"

alias grep='rg'
alias ls='eza -lh -a --group-directories-first --total-size --icons=auto'
alias lt='eza -a --tree --level=2 --long --icons --git'
alias cat='bat'
alias du='dust'
alias find='fd'
alias df='duf'
alias vim='nvim'
alias cd='z'
alias ff='fzf --preview="bat  --style=numbers --color=always {}"'

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

alias clear='clear && omarchy-show-logo'

alias nvp='nvim ~/.config/nvim/lua/plugins/plugins.lua'

if not pgrep -u (whoami) ssh-agent >/dev/null
    eval (ssh-agent -c) >/dev/null
end
ssh-add ~/.ssh/id_ed25519 ^/dev/null
zoxide init fish | source
starship init fish | source
tmux
set -U fish_greeting ""
set -g fish_key_bindings fish_vi_key_bindings
set -Ux CARAPACE_BRIDGES 'zsh,fish,inshellisense'
carapace _carapace | source

source ~/.local/share/omarchy/default/bash/rc
clear
omarchy-show-logo
