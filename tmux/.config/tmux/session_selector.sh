#!/bin/bash
export FZF_DEFAULT_OPTS=''

# 1. Fetch local tmux sessions
local_sessions=$(tmux list-sessions -F '#S (local)' 2>/dev/null)

# 2. Extract active SSH destination targets from running processes
ssh_hosts=$(ps aux | awk '
  /[s]sh/ && !/ssh-agent/ {
    for (i=1; i<=NF; i++) {
      if ($i ~ /^ssh$/) {
        for (j=i+1; j<=NF; j++) {
          if ($j ~ /^-/) continue;
          print $j;
          break;
        }
      }
    }
  }' | sort -u)

# 3. Query all detected remote hosts simultaneously
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

for host in $ssh_hosts; do
  (
    sessions=$(ssh -o ConnectTimeout=2 \
                   -o StrictHostKeyChecking=no \
                   -q "$host" \
                   "export PATH=\$PATH:/usr/local/bin:~/.local/bin:/usr/bin; tmux list-sessions -F '#S ($host)' 2>/dev/null")
    
    if [ -n "$sessions" ]; then
      safe_host=$(echo "$host" | tr -c 'a-zA-Z0-9_' '_')
      echo "$sessions" > "$tmp_dir/$safe_host"
    fi
  ) &
done

wait

# 4. Aggregate sessions & run fzf
remote_sessions=$(cat "$tmp_dir"/* 2>/dev/null)
all_sessions=$(printf "%s\n%s" "$local_sessions" "$remote_sessions" | sed '/^$/d')

[ -z "$all_sessions" ] && exit 0

preview_cmd='
  session=$(echo {} | awk "{print \$1}");
  host=$(echo {} | awk "{print \$2}" | tr -d "()");
  if [ "$host" = "local" ]; then
    tmux capture-pane -ep -t "$session" 2>/dev/null;
  else
    ssh -o ConnectTimeout=1 -q "$host" "tmux capture-pane -ep -t \"$session\"" 2>/dev/null;
  fi
'

selected=$(fzf \
  --prompt='Switch Session > ' \
  --preview="$preview_cmd" \
  --preview-window=bottom:60%:wrap <<< "$all_sessions")

[ -z "$selected" ] && exit 0

# 5. Switch client behavior (Option B)
read -r session host <<< "$(echo "$selected" | awk '{print $1, $2}')"

# Get current active client output device
current_client=$(tmux display-message -p '#{client_name}')

if [ "$host" = "(local)" ]; then
  tmux switch-client -c "$current_client" -t "$session"
else
  raw_host=$(echo "$host" | tr -d '()')
  # Sanitize host to create a valid local tmux session name (replace @ . - with _)
  clean_session_name=$(echo "${raw_host}_${session}" | tr -c 'a-zA-Z0-9_' '_')

  # If local runner session doesn't exist for this remote connection, create it
  if ! tmux has-session -t "$clean_session_name" 2>/dev/null; then
    tmux new-session -d -s "$clean_session_name" "ssh -t $raw_host tmux attach-session -t '$session'"
  fi

  # Switch active client to the remote runner session
  tmux switch-client -c "$current_client" -t "$clean_session_name"
fi
