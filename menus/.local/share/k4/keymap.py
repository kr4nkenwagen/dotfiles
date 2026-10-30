"""keymap.py: a QMK keymap.c read for k4 --keymap (k4-keymap runs it; no qmk CLI needed).

  python3 -I keymap.py data REPO [BOARD] [NAME]  the window's lines (see k4-keymap); BOARD: the
                                                 keyboard's USB name, NAME: the repo's
  python3 -I keymap.py peekd K4-KEYMAP            while the peek is on (~/.local/state/k4/keymap-peek):
                                                 a layer key pressed starts `K4-KEYMAP peek N` (the
                                                 small overlay); one of these at a time
  python3 -I keymap.py watch                     the keyboard's layer as it changes: "layer N"
                                                 lines (QMK raw HID, usage page 0xFF60; the
                                                 firmware sends 'K' '4' LAYER), else
                                                 "nolive REASON" and an end

Each `[N] = LAYOUT_…(…)` block of keymaps[] is split at its top-level commas; the key positions
come from keymap-layouts.json (QMK's info.json, per LAYOUT macro, in argument order).
"""
import json, os, re, select, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))

SIMPLE = {
    "SCLN": ";", "QUOT": "'", "COMM": ",", "DOT": ".", "SLSH": "/", "MINS": "-", "EQL": "=", "LBRC": "[", "RBRC": "]",
    "BSLS": "\\", "GRV": "`", "EXLM": "!", "AT": "@", "HASH": "#", "DLR": "$", "PERC": "%", "CIRC": "^", "AMPR": "&",
    "ASTR": "*", "LPRN": "(", "RPRN": ")", "UNDS": "_", "PLUS": "+", "LCBR": "{", "RCBR": "}", "PIPE": "|", "TILD": "~",
    "COLN": ":", "DQUO": "\"", "DQT": "\"", "LT": "<", "GT": ">", "QUES": "?", "LABK": "<", "RABK": ">",
    "TAB": "Tab", "ESC": "Esc", "ESCAPE": "Esc", "BSPC": "⌫", "BACKSPACE": "⌫", "ENT": "↵", "ENTER": "↵", "SPC": "Space", "SPACE": "Space",
    "DEL": "Del", "DELETE": "Del", "INS": "Ins", "LEFT": "←", "DOWN": "↓", "UP": "↑", "RIGHT": "→", "RGHT": "→",
    "HOME": "Home", "END": "End", "PGUP": "PgUp", "PGDN": "PgDn", "PSCR": "PrtSc", "PRINT_SCREEN": "PrtSc", "CAPS": "Caps", "CAPS_LOCK": "Caps",
    "APP": "Menu", "UNDO": "Undo", "CUT": "Cut", "COPY": "Copy", "PASTE": "Paste", "AGAIN": "Redo", "FIND": "Find",
}
MODKEY = {"LCTL": "Ctrl", "RCTL": "Ctrl", "LSFT": "Shift", "RSFT": "Shift", "LALT": "Alt", "RALT": "AltGr", "LGUI": "Super", "RGUI": "Super",
          "LCMD": "Super", "RCMD": "Super", "LOPT": "Alt", "ROPT": "AltGr"}
MEDIA = {"VOLU": "Vol+", "AUDIO_VOL_UP": "Vol+", "VOLD": "Vol−", "AUDIO_VOL_DOWN": "Vol−", "MUTE": "Mute", "AUDIO_MUTE": "Mute",
         "BRIU": "Bri+", "BRIGHTNESS_UP": "Bri+", "BRID": "Bri−", "BRIGHTNESS_DOWN": "Bri−", "MPLY": "Play", "MEDIA_PLAY_PAUSE": "Play",
         "MNXT": "Next", "MEDIA_NEXT_TRACK": "Next", "MPRV": "Prev", "MEDIA_PREV_TRACK": "Prev", "MSTP": "Stop", "MEDIA_STOP": "Stop"}
MOUSE = {"CURSOR_LEFT": "M←", "CURSOR_RIGHT": "M→", "CURSOR_UP": "M↑", "CURSOR_DOWN": "M↓", "WHEEL_UP": "Wh↑", "WHEEL_DOWN": "Wh↓",
         "WHEEL_LEFT": "Wh←", "WHEEL_RIGHT": "Wh→", "BUTTON_1": "Click L", "BUTTON_2": "Click R", "BUTTON_3": "Click M",
         "MS_L": "M←", "MS_R": "M→", "MS_U": "M↑", "MS_D": "M↓", "WH_U": "Wh↑", "WH_D": "Wh↓", "BTN1": "Click L", "BTN2": "Click R", "BTN3": "Click M",
         "MS_LEFT": "M←", "MS_RGHT": "M→", "MS_UP": "M↑", "MS_DOWN": "M↓", "MS_WHLU": "Wh↑", "MS_WHLD": "Wh↓", "MS_BTN1": "Click L", "MS_BTN2": "Click R"}
MODS = {"LCTL": "Ctrl", "RCTL": "Ctrl", "LSFT": "Shift", "RSFT": "Shift", "LALT": "Alt", "RALT": "AltGr", "LGUI": "Super", "RGUI": "Super",
        "CTL": "Ctrl", "SFT": "Shift", "ALT": "Alt", "GUI": "Super", "MEH": "Meh", "HYPR": "Hyper"}


def clean(s):
    return str(s).replace("\t", " ").replace("\n", " ")


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", " ", src)


def split_top(s):
    """Split at commas not inside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


def mods_of(expr):
    """MOD_LCTL | MOD_LSFT -> Ctrl+Shift"""
    names = []
    for m in re.split(r"[|\s]+", expr):
        m = m.replace("MOD_", "")
        if m in MODS and MODS[m] not in names: names.append(MODS[m])
    return "+".join(names) or expr


def legend(code, layer_of):
    """(tap, hold, kind, target layer or -1)"""
    c = code.strip()
    if c in ("_______", "KC_TRNS", "KC_TRANSPARENT"): return "", "", "trans", -1
    if c in ("XXXXXXX", "KC_NO"): return "", "", "none", -1
    m = re.fullmatch(r"(MO|TG|TO|OSL|TT|DF)\((\w+)\)", c)
    if m:
        n = layer_of(m.group(2)); verb = {"MO": "hold", "TG": "toggle", "TO": "go to", "OSL": "one shot", "TT": "tap-toggle", "DF": "default"}[m.group(1)]
        return f"L{n}", verb, "layer", n
    m = re.fullmatch(r"LT\((\w+),\s*(.+)\)", c)
    if m:
        n = layer_of(m.group(1)); tap = legend(m.group(2), layer_of)[0]
        return tap, f"L{n}", "layer", n
    m = re.fullmatch(r"MT\(([^,]+),\s*(.+)\)", c)
    if m: return legend(m.group(2), layer_of)[0], mods_of(m.group(1)), "mod", -1
    m = re.fullmatch(r"([LR]?(?:CTL|SFT|ALT|GUI|CMD|OPT)|MEH|HYPR|ALL)_T\((.+)\)", c)
    if m: return legend(m.group(2), layer_of)[0], mods_of(m.group(1).replace("CMD", "GUI").replace("OPT", "ALT")), "mod", -1
    m = re.fullmatch(r"(LCTL|RCTL|LSFT|RSFT|LALT|RALT|LGUI|RGUI|C|S|A|G)\((.+)\)", c)
    if m:
        short = {"C": "Ctrl", "S": "Shift", "A": "Alt", "G": "Super"}
        return f"{short.get(m.group(1), MODS.get(m.group(1), m.group(1)))}+{legend(m.group(2), layer_of)[0]}", "", "key", -1
    if c in ("QK_BOOT", "RESET", "QK_BOOTLOADER"): return "Boot", "", "key", -1
    for p in ("QK_MOUSE_", "KC_MS_", "MS_", "KC_"):
        if c.startswith(p):
            rest = c[len(p):]
            if p in ("QK_MOUSE_",) or (p == "KC_" and rest in MOUSE) or p in ("KC_MS_", "MS_"):
                if rest in MOUSE: return MOUSE[rest], "", "mouse", -1
                if (p + rest).replace("KC_", "") in MOUSE: return MOUSE[(p + rest).replace("KC_", "")], "", "mouse", -1
    if c.startswith("KC_"):
        r = c[3:]
        if re.fullmatch(r"[A-Z]", r) or re.fullmatch(r"[0-9]", r): return r, "", "key", -1
        if re.fullmatch(r"F\d{1,2}", r): return r, "", "key", -1
        if r in SIMPLE: return SIMPLE[r], "", "key", -1
        if r in MODKEY: return MODKEY[r], "", "mod", -1
        if r in MEDIA: return MEDIA[r], "", "media", -1
        return r.replace("_", " ").title(), "", "key", -1
    if c.startswith(("RGB_", "UG_", "RM_")): return "RGB " + c.split("_", 1)[1].replace("_", " ").title(), "", "media", -1
    return c, "", "key", -1


def parse(path):
    src = strip_comments(open(path, encoding="utf-8", errors="replace").read())
    enums = {}
    for body in re.findall(r"enum\s+\w*\s*\{([^}]*)\}", src):  # enum layers { _BASE, _NUM, … }
        n = 0
        for e in split_top(body):
            name, _, val = e.partition("=")
            name = name.strip()
            if not name: continue
            if val.strip().isdigit(): n = int(val)
            enums.setdefault(name, n); n += 1
    def layer_of(tok):
        tok = tok.strip()
        return int(tok) if tok.isdigit() else enums.get(tok, -1)
    m = re.search(r"keymaps\s*\[\s*\]\s*\[[^\]]*\]\s*\[[^\]]*\]\s*=\s*\{", src)
    if not m: raise ValueError("no keymaps[] in keymap.c")
    i = m.end()
    layers = []
    for lm in re.finditer(r"\[\s*(\w+)\s*\]\s*=\s*(LAYOUT\w*)\s*\(", src[i:]):
        start = i + lm.end()
        depth, j = 1, start
        while depth and j < len(src):
            if src[j] == "(": depth += 1
            elif src[j] == ")": depth -= 1
            j += 1
        layers.append((layer_of(lm.group(1)), lm.group(1), lm.group(2), split_top(src[start:j - 1])))
    names = {v: k for k, v in enums.items()}
    return layers, names, layer_of


def nice(name, n):
    """_BASE -> Base, _NUM -> Num; a number -> Base / Layer N"""
    if name and not name.isdigit():
        return name.strip("_").replace("_", " ").title()
    return "Base" if n == 0 else f"Layer {n}"


def data(repo, product="", name=""):
    path = None
    for root, _, files in os.walk(repo):
        if ".git" in root: continue
        if "keymap.c" in files: path = os.path.join(root, "keymap.c"); break
    if not path:
        print("S\terror\tNo keymap.c in the repo"); return
    try:
        layers, names, layer_of = parse(path)
    except (ValueError, OSError) as e:
        print(f"S\terror\t{clean(e)}"); return
    if not layers:
        print("S\terror\tkeymaps[] has no layers"); return
    geo = json.load(open(os.path.join(HERE, "keymap-layouts.json")))
    layout = layers[0][2]
    board, positions = "", None
    for b in geo["boards"].values():
        if layout in b["layouts"]: board, positions = b["name"], b["layouts"][layout]; break
    if positions is None:
        print(f"S\terror\tNo key positions for {layout} (keymap-layouts.json)"); return
    commit = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h"], capture_output=True, text=True).stdout.strip()
    print("S\tok\t")
    print("\t".join(map(clean, ["B", product or board, layout, name or os.path.basename(repo.rstrip("/")), commit, os.path.relpath(path, repo)])))
    for k, (x, y, w, h) in enumerate(positions):
        print(f"G\t{k}\t{x}\t{y}\t{w}\t{h}")
    have = {n for n, _, _, _ in layers}
    refs = set()
    rows = []
    for n, tok, lay, keys in layers:
        for k, code in enumerate(keys[:len(positions)]):
            tap, hold, kind, target = legend(code, layer_of)
            if target >= 0: refs.add(target)
            rows.append("\t".join(map(clean, ["K", n, k, tap, hold, kind, target, code])))
    for n, tok, lay, keys in sorted(layers):
        print("\t".join(map(clean, ["Y", n, nice(names.get(n, tok), n), "", len(keys)])))
    for r in sorted(refs - have):
        print(f"Y\t{r}\tLayer {r}\tmissing\t0")
    for r in rows: print(r)


# ---------- the live layer: QMK raw HID ----------

def find_raw():
    """The keyboard's raw HID node (usage page 0xFF60): (path, why not)."""
    found = False
    for d in sorted(os.listdir("/sys/class/hidraw")):
        try:
            ev = open(f"/sys/class/hidraw/{d}/device/uevent").read()
        except OSError: continue
        if "00004653:00000004" not in ev.upper().replace("0X", ""): continue
        found = True
        desc = open(f"/sys/class/hidraw/{d}/device/report_descriptor", "rb").read()
        if b"\x06\x60\xff" in desc: return f"/dev/{d}", ""
    return "", "no raw hid" if found else "not connected"


def watch():
    path, why = find_raw()
    if not path:
        print(f"nolive\t{why}", flush=True); return
    try:
        fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    except PermissionError:
        print("nolive\tno permission", flush=True); return
    except OSError as e:
        print(f"nolive\t{clean(e)}", flush=True); return
    ask = b"\x00K4" + bytes(30)  # (report id 0, then the 32-byte report: "K4" asks which layer)
    try: os.write(fd, ask)
    except OSError: pass
    # the window: our parent (the runner's shell), or the one above it (k4 itself), whichever
    # goes first means it closed; the shell can outlive k4, so both are watched
    parent = os.getppid()
    try: above = int(open(f"/proc/{parent}/stat").read().rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError): above = parent
    last = None
    while os.getppid() == parent and os.path.exists(f"/proc/{above}"):  # the window closed: so do we
        r, _, _ = select.select([fd], [], [], 1.0)
        if not r: continue
        try: rep = os.read(fd, 64)
        except BlockingIOError: continue
        except OSError:
            print("nolive\tnot connected", flush=True); return
        if len(rep) >= 3 and rep[0:2] == b"K4" and rep[2] != last:
            last = rep[2]
            print(f"layer\t{last}", flush=True)


PEEK_STATE = os.path.expanduser("~/.local/state/k4/keymap-peek")


def peek_on():
    try: return open(PEEK_STATE).read().strip() == "on"
    except OSError: return False


def peekd(cmd):
    """The keyboard's layer, read for as long as the peek is on: a layer other than the base starts
    the peek (when none shows; one that shows follows the keyboard itself). Reconnects when the
    keyboard comes back; one daemon at a time (a lock in $XDG_RUNTIME_DIR)."""
    import fcntl
    lock = open(os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "k4-keymap-peekd.lock"), "w")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: return  # (one runs already)
    while peek_on():
        path, _ = find_raw()
        if not path:
            time.sleep(3); continue
        try: fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            time.sleep(3); continue
        last = 0
        while peek_on():
            r, _, _ = select.select([fd], [], [], 2.0)
            if not r: continue
            try: rep = os.read(fd, 64)
            except BlockingIOError: continue
            except OSError: break  # unplugged: look for it again
            if len(rep) < 3 or rep[0:2] != b"K4" or rep[2] == last: continue
            last = rep[2]
            showing = subprocess.run(["pgrep", "-f", "^k4 --keymap --peek"], capture_output=True).returncode == 0
            if last != 0 and not showing:
                subprocess.Popen([cmd, "peek", str(last)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try: os.close(fd)
        except OSError: pass


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "data": data(a[1], a[2] if len(a) > 2 else "", a[3] if len(a) > 3 else "")
    elif a and a[0] == "watch": watch()
    elif a and a[0] == "peekd": peekd(a[1] if len(a) > 1 else "k4-keymap")
    else: print(__doc__.strip(), file=sys.stderr); sys.exit(2)
