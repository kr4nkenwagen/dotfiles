# Shared by the *-menu scripts (steam-menu, gh-menu, docker-menu, spotify-menu, ollama-menu,
# clipse-menu): each prints a k4 --menu section and runs its own actions.
#
# A script sets K4_NAME (its command name) and K4_ID / K4_TITLE / K4_KEY / K4_ICON / K4_DESC
# (its section), and defines:
#   section   the section's lines (A/H/E/N/K/C/B/D/Y/Q, see k4's src/menu.odin)
#   available exit 0 when the app is installed
#   summary   one line for the Apps menu ("3 running"), fast
#   missing   (optional) the "not installed" body: install, site, hide
#   extra     (optional) more records after the section: G views, P pages
#   skeleton  (optional) static lines shown until the loader's output replaces them
#   view      (optional) the I lines of its view
# then calls: k4_dispatch "$@"
#
# Action ids are base64 of "K4_NAME run <base64 of the shell action>", so any menu that
# hosts the section (k4-apps, sway-menu) can run them with k4-exec without knowing this
# script's functions. With K4_AS_PAGE=1 (the Sway menu) the section is a page under Apps
# instead of a left-pane section of its own.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/snap/bin:$PATH"
K4_STATE="$HOME/.local/state/k4"
K4_CACHE="$HOME/.cache/k4"
k4b64() { printf '%s' "$1" | base64 -w0; }
k4id() { k4b64 "$K4_NAME run $(k4b64 "$1")"; }
k4clean() { printf '%s' "$1" | tr '\t\n\r' '   '; }                                          # fields must stay on one line
k4flag() { k4clean "$1" | tr ';' ','; }                                                      # flag values must not hold ';'
item() { printf 'A\t%s\t%s\t%s\t%s\t%s\n' "$(k4id "$2")" "$(k4clean "$1")" "$(k4clean "${3:-}")" "${4:-}" "${5:-}"; }  # item LABEL ACTION [META] [VIEW] [FLAGS]
stay() { item "$1" "$2" "${3:-}" "" "stay${4:+;$4}"; }                                    # runs in place, menu stays open
slider() { item "$1" "$2" "" "" "slider=${3:-0};step=${4:-5}"; }
choice() { item "$1" "$2" "$3" "" "choice=$4${5:+;$5}"; }   # choice LABEL ACTION VALUE 'A|B|C' [FLAGS]: ← → runs ACTION with $K4_VALUE
hdr() { printf 'H\t%s\t%s\n' "$(k4clean "$1")" "${2:-}"; }                                # hdr TEXT [COUNT]
empty() { printf 'E\t%s\n' "$(k4clean "$1")"; }                                           # "Nothing to review" under a heading
notice() { printf 'N\t%s\t%s\t%s\t%s\n' "$(k4clean "$1")" "$(k4clean "$2")" "${3:-accent}" "${4:-}"; }   # notice TITLE BODY [TONE] [slow]
bars() { printf 'K\t%s\n' "${1:-2}"; }                                                     # loading placeholders
card() { printf 'C\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$(k4clean "$3")" "$(k4clean "$4")" "$(k4clean "${5:-}")" "${6:-}"; }  # card GLYPH STATE TITLE LINE [FLAGS] [active]
progress() { printf 'B\t%s\t%s\t%s\n' "$(k4clean "$1")" "$2" "$(k4clean "$3")"; }        # progress LABEL PERCENT META
desc() { printf 'D\t%s\t%s\t%s\n' "$(k4clean "$1")" "$(k4clean "${2:-}")" "$(k4clean "${3:-}")"; }   # desc TEXT [COUNT] [PLACEHOLDER]
hints() { local IFS=$'\t'; printf 'Y\t%s\n' "$*"; }                                       # hints KEY LABEL [KEY LABEL]...
query() { printf 'Q\t%s\n' "$(k4id "$1")"; }                                              # typing is input for ACTION ($K4_INPUT)
iview() { printf 'I\t%s\t%s\t%s\t%s\t%s\n' "$(k4id "$2")" "$(k4clean "$1")" "${3:-}" "${4:-}" "${5:-}"; }   # view item: LABEL ACTION [IMAGE] [current] [FLAGS]
notify() {  # inside k4-exec the message goes to k4's footer: "Verb  object"
  if [ -n "${K4_RUN:-}" ]; then printf '%s  %s\n' "$1" "${2:-}"
  else command -v notify-send >/dev/null && notify-send "$@"; fi; }
bg() { setsid -f "$@" >/dev/null 2>&1 </dev/null; }
open_url() { bg xdg-open "$1"; }
tui() {  # floating terminal (app id TUI.float: floated by the Sway and Hyprland window rules)
  if command -v ghostty >/dev/null; then bg ghostty --class=TUI.float -e "$@"
  else bg xdg-terminal-exec --app-id=TUI.float "$@"; fi; }
tui_wait() { tui sh -c "$1; printf '\n[done] press enter to close'; read -r _"; }
copy() { printf '%s' "$2" | wl-copy; notify "Copied" "${3:-$1}"; }   # copy LABEL VALUE [SHOWN]
close_k4() { [ -n "${K4_RUN:-}" ] && echo k4:close; return 0; }       # after launching something: k4 gets out of the way
ask() {  # ask PROMPT [password] -> typed text on stdout (outside k4)
  if command -v k4 >/dev/null; then k4 --prompt-only "$1 ❯ " ${2:+--password}
  else fuzzel --dmenu --prompt "$1 ❯ " --lines 0 ${2:+--password} </dev/null; fi; }
ago() {  # ago EPOCH -> "3 min ago", "2 h ago", "yesterday", "5 d ago", "3 w ago", "2 mo ago", "1 y ago"
  local s=$(( $(date +%s) - ${1:-0} ))
  if [ "$s" -lt 60 ]; then echo "just now"; elif [ "$s" -lt 3600 ]; then echo "$(( s / 60 )) min ago"
  elif [ "$s" -lt 86400 ]; then echo "$(( s / 3600 )) h ago"; elif [ "$s" -lt 172800 ]; then echo yesterday
  elif [ "$s" -lt 1209600 ]; then echo "$(( s / 86400 )) d ago"; elif [ "$s" -lt 5184000 ]; then echo "$(( s / 604800 )) w ago"
  elif [ "$s" -lt 31536000 ]; then echo "$(( s / 2592000 )) mo ago"; else echo "$(( s / 31536000 )) y ago"; fi; }
plural() { [ "$1" = 1 ] && printf '1 %s' "$(printf '%s' "$2" | sed 's/ies$/y/; t; s/s$//')" || printf '%s %s' "$1" "$2"; }   # plural 1 models -> "1 model"
thousands() { printf '%s' "$1" | sed ':a;s/\B[0-9]\{3\}\>/ &/;ta'; }   # 12182 -> "12 182"
install_cmd() {  # install_cmd ARCH_PKG APT_PKG [OTHER]: the command for this machine
  if command -v pacman >/dev/null; then
    if pacman -Si "$1" >/dev/null 2>&1; then echo "sudo pacman -S $1"; elif command -v yay >/dev/null; then echo "yay -S $1"; else echo "${3:-sudo pacman -S $1}"; fi
  elif command -v apt >/dev/null && [ -n "$2" ]; then echo "sudo apt install $2"
  else echo "${3:-}"; fi; }
hidden() { grep -qxF "$1" "$K4_STATE/hidden-apps" 2>/dev/null; }

# The "not installed" body (design: Combined, partly installed). missing_body PURPOSE INSTALL SITE
missing_body() {
  notice "$K4_TITLE isn't installed" "Install it to $1." muted
  [ -n "$2" ] && item "Install $K4_TITLE" "tui_wait $(printf %q "$2")" "opens terminal"
  item "Open ${3#https://}" "open_url '$3'" "opens browser"
  stay "Hide from this menu" "mkdir -p '$K4_STATE'; echo $K4_NAME >> '$K4_STATE/hidden-apps'; notify Hidden '$K4_TITLE · gone next time'"
}

# The section's records: a left-pane section (k4-apps) or a page under Apps (Sway menu).
part() {
  local dim="${1:-}"
  if [ -n "${K4_AS_PAGE:-}" ]; then printf 'P\t%s\t%s\t%s\t%s section\n' "$K4_ID" "$K4_TITLE" "$K4_DESC" "$K4_NAME"
  else printf 'S\t%s\t%s\t%s\t%s\t%s\t%s\n' "$K4_ID" "$K4_TITLE" "$K4_KEY" "$K4_DESC" "$K4_ICON" "${dim:+dim;group=Not installed}"
    [ -n "$dim" ] || printf 'L\t%s section\n' "$K4_NAME"; fi
  if [ -n "$dim" ]; then missing; return; fi
  declare -F skeleton >/dev/null && skeleton
  declare -F extra >/dev/null && extra
  return 0
}
missing() { missing_body "use it from here" "" "https://example.com"; }
k4_tree() { part; printf 'R\tk4-exec\n'; }
k4_open() {  # k4_open SECTION_ID: standalone menu opened inside this section
  local out; out=$(k4_tree | k4 --menu --open "$1") || return 0
  case "$out" in url:*) open_url "${out#url:}" ;; *) k4-exec "$out" ;; esac; }
k4_dispatch() {
  case "${1:-}" in
    "") k4_open "$K4_ID" ;;
    part) if available && [ "${2:-}" != dim ]; then part; else part dim; fi ;;   # part dim: as if not installed (tests)
    section) if available; then section; else missing; fi ;;
    summary) if available; then summary; else echo "not installed"; fi ;;
    view) view ;;
    tree) k4_tree ;;
    available) available ;;
    run) eval "$(printf '%s' "${2:?id}" | base64 -d)" ;;
    *) printf 'usage: %s [part|section|summary|view|tree|available|run ID]\n' "$K4_NAME" >&2; return 2 ;;
  esac; }
