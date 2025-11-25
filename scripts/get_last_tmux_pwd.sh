
#!/bin/sh
if ! tmux info &>/dev/null; then
    # Not in tmux, just use current directory
    printf "%s" "$PWD"
    exit 0
fi
dir=$(tmux display -p '#{?last_window,#{last_window.pane_current_path},#{pane_current_path}}' 2>/dev/null)
if [ -z "$dir" ]; then
    dir="$PWD"
fi
printf "%s" "$dir"

