if not status is-interactive
  return
end

alias grep='grep --color=auto'
alias ls='eza -l -a --group-directories-first --total-size --git --git-repos'
alias cat='bat'
alias du='dust'
alias find='fd'
alias df='duf'
alias vim='nvim'
alias cd='z'
alias fzf='fzf --preview="bat {}"'
alias :q='exit && exit'
zoxide init fish | source
starship init fish | source
tmux 
clear
colorscript random
set -U fish_greeting ""
set -g fish_key_bindings fish_vi_key_bindings
set -Ux CARAPACE_BRIDGES 'zsh,fish,inshellisense'
carapace _carapace | source 
