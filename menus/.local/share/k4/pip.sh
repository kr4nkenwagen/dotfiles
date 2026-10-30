# pip.sh: the corner player shared by k4-youtube and k4-jellyfin: one mpv (Wayland app id k4-pip, the
# Hyprland rule pins it top left on every workspace), driven over one socket. Whichever starts a
# video stops what played: at most one player. Sourced; needs $LUA (the mpv script) and bg (lib.sh).
SOCK="${XDG_RUNTIME_DIR:-/tmp}/k4-youtube.sock"

ipc() {  # ipc JSON…: one command each; their replies, one a line, as soon as all came (2 s at most;
  # mpv's events in between are skipped)
  python3 -c '
import json, socket, sys, time
s = socket.socket(socket.AF_UNIX); s.settimeout(2); s.connect(sys.argv[1])
s.sendall(("\n".join(sys.argv[2:]) + "\n").encode())
need, buf, out, end = len(sys.argv) - 2, b"", [], time.time() + 2
while need and time.time() < end:
    try: d = s.recv(65536)
    except socket.timeout: break
    if not d: break
    buf += d
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        try: j = json.loads(line)
        except ValueError: continue
        if "error" in j: out.append(line.decode()); need -= 1
print("\n".join(out))' "$SOCK" "$@" 2>/dev/null; }
PIP_RE='^mpv --wayland-app-id=k4-pi[p]'   # the player's own processes (the bracket: never this script's)
running() {  # the player answers (any other one, lost from it, is stopped); none does: all go
  local pid p
  pid=$([ -S "$SOCK" ] && ipc '{"command":["get_property","pid"]}' | jq -r 'select(.error == "success") | .data' 2>/dev/null)
  if [ -n "$pid" ]; then
    for p in $(pgrep -f "$PIP_RE"); do [ "$p" = "$pid" ] || kill "$p" 2>/dev/null; done
    return 0
  fi
  stop_all; return 1; }
stop_all() {  # every player, gone (it said nothing, or a new one starts): at most one plays
  pkill -f "$PIP_RE" 2>/dev/null
  local n=0; while [ $n -lt 20 ] && pgrep -f "$PIP_RE" >/dev/null; do sleep 0.1; n=$((n + 1)); done
  pkill -9 -f "$PIP_RE" 2>/dev/null
  rm -f "$SOCK"; }
cmd() { local a=() x; for x in "$@"; do a+=("$(jq -Rn --arg x "$x" '$x')"); done; local IFS=,; ipc "{\"command\":[${a[*]}]}" >/dev/null; }
prop() { ipc "{\"command\":[\"get_property\",\"$1\"]}" | jq -r 'select(.error == "success") | .data // empty' 2>/dev/null | head -1; }

start() {  # start URL [SECONDS] [TITLE]: the player, in its corner (the window rule), not focused; any old one goes first
  stop_all
  bg mpv --wayland-app-id=k4-pip --title='${media-title}' --input-ipc-server="$SOCK" \
    --force-window=immediate --geometry=600x338 --idle=no --keep-open=no --no-terminal \
    --ytdl-format='bestvideo[height<=720]+bestaudio/best[height<=720]' --hwdec=auto-safe \
    ${2:+--start=$2} ${3:+"--force-media-title=$3"} --script="$LUA" "$1"
  local n=0; while [ $n -lt 30 ] && ! [ -S "$SOCK" ]; do sleep 0.1; n=$((n + 1)); done; }

# The player's window (hyprctl): its address, pinned, workspace name.
win() { hyprctl -j clients 2>/dev/null | jq -r '.[] | select(.class == "k4-pip") | "\(.address)\t\(.pinned)\t\(.workspace.name)"' | head -1; }
hidden() { local ws; IFS=$'\t' read -r _ _ ws <<<"$(win)"; [ "${ws#special:}" != "$ws" ]; }
hypr() {  # hypr LUA CLASSIC: Omarchy's Lua dispatch, the classic one where that is not there
  hyprctl dispatch "$1" 2>/dev/null | grep -qi '^ok' || hyprctl dispatch $2 >/dev/null 2>&1; }

pip_toggle() {  # hidden: on a special workspace (it still plays); shown: here, pinned, on top
  local a pinned ws; IFS=$'\t' read -r a pinned ws <<<"$(win)"
  [ -n "$a" ] || return 1
  if [ "${ws#special:}" != "$ws" ]; then
    local here; here=$(hyprctl -j activeworkspace | jq -r .id)
    hypr "hl.dsp.window.move({ workspace = \"$here\", window = \"address:$a\", follow = false })" "movetoworkspacesilent $here,address:$a"
    hypr "hl.dsp.window.pin({ window = \"address:$a\" })" "pin address:$a"
    hyprctl dispatch alterzorder "top,address:$a" >/dev/null 2>&1
    echo "Player shown · top left"
  else
    [ "$pinned" = true ] && hypr "hl.dsp.window.pin({ window = \"address:$a\" })" "pin address:$a"   # (a pinned window does not move)
    hypr "hl.dsp.window.move({ workspace = \"special:k4pip\", window = \"address:$a\", follow = false })" "movetoworkspacesilent special:k4pip,address:$a"
    echo "Player hidden · audio keeps playing · Super+Alt+Y anywhere"
  fi; }

