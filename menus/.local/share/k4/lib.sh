# Shared by the *-menu scripts (steam-menu, gh-menu, docker-menu, spotify-menu, ollama-menu,
# clipse-menu): each prints a k4 --menu section and runs its own actions.
#
# A script sets K4_NAME (its command name) and defines:
#   part      the S/L/V/G lines for its section (used by k4-apps and the Sway menu)
#   section   the section's A/H lines
#   view      (optional) the I lines of its view
#   available exit 0 when the app is installed
# then calls: k4_dispatch "$@"
#
# Action ids are base64 of "K4_NAME run <base64 of the shell action>", so any menu that
# hosts the section (k4-apps, sway-menu) can run them with k4-exec without knowing this
# script's functions.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/snap/bin:$PATH"
k4b64() { printf '%s' "$1" | base64 -w0; }
k4id() { k4b64 "$K4_NAME run $(k4b64 "$1")"; }
item() { printf 'A\t%s\t%s\t%s\t%s\t%s\n' "$(k4id "$2")" "$(k4clean "$1")" "$(k4clean "${3:-}")" "${4:-}" "${5:-}"; }  # item LABEL ACTION [META] [VIEW] [FLAGS]
stay() { item "$1" "$2" "${3:-}" "" "stay${4:+;$4}"; }                                    # runs in place, menu stays open
slider() { item "$1" "$2" "" "" "slider=${3:-0};step=${4:-5}"; }
hdr() { printf 'H\t%s\n' "$(k4clean "$1")"; }
iview() { printf 'I\t%s\t%s\t%s\t%s\n' "$(k4id "$2")" "$(k4clean "$1")" "${3:-}" "${4:-}"; }    # view item: LABEL ACTION [IMAGE] [current]
k4clean() { printf '%s' "$1" | tr '\t\n\r' '   '; }                                          # fields must stay on one line
notify() {  # inside k4-exec the message goes to k4's footer
  if [ -n "${K4_RUN:-}" ]; then printf '%s  %s\n' "$1" "${2:-}"
  else command -v notify-send >/dev/null && notify-send "$@"; fi; }
bg() { setsid -f "$@" >/dev/null 2>&1 </dev/null; }
open_url() { bg xdg-open "$1"; }
tui() {  # floating terminal (app id TUI.float: floated by the Sway and Hyprland window rules)
  if command -v ghostty >/dev/null; then bg ghostty --class=TUI.float -e "$@"
  else bg xdg-terminal-exec --app-id=TUI.float "$@"; fi; }
tui_wait() { tui sh -c "$1; printf '\n[done] press enter to close'; read -r _"; }
copy() { printf '%s' "$2" | wl-copy; notify "Copied  $1" "${3:-}"; }   # copy LABEL VALUE [SHOWN]
ask() {  # ask PROMPT [password] -> typed text on stdout (k4 when installed, else fuzzel)
  if command -v k4 >/dev/null; then k4 --prompt-only "$1 ❯ " ${2:+--password}
  else fuzzel --dmenu --prompt "$1 ❯ " --lines 0 ${2:+--password} </dev/null; fi; }
k4_tree() { part; printf 'R\tk4-exec\n'; }
k4_open() {  # k4_open SECTION_ID: standalone menu opened inside this section
  local out; out=$(k4_tree | k4 --menu --open "$1") || return 0
  case "$out" in url:*) open_url "${out#url:}" ;; *) k4-exec "$out" ;; esac; }
k4_dispatch() {
  case "${1:-}" in
    "") k4_open "$K4_NAME" ;;
    part) part ;;
    section) section ;;
    view) view ;;
    tree) k4_tree ;;
    available) available ;;
    run) eval "$(printf '%s' "${2:?id}" | base64 -d)" ;;
    *) printf 'usage: %s [part|section|view|tree|available|run ID]\n' "$K4_NAME" >&2; return 2 ;;
  esac; }
