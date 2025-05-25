#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return
eval "$(starship init bash)"
if command -v tmux &> /dev/null && [ -n "$PS1" ] && [[ ! "$TERM" =~ screen ]] && [[ ! "$TERM" =~ tmux ]] && [ -z "$TMUX" ]; then
  tmux
fi
alias grep='grep --color=auto'
alias ls='eza -l -a --group-directories-first --total-size --git --git-repos'
alias cat='bat'
alias du='dust'
alias find='fd'
alias df='duf'
alias vim='nvim'
alias cd='z'
PS1='[\u@\h \W]\$ '
eval "$(zoxide init bash)"
colorscript random
