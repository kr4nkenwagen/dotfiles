#!/usr/bin/env python3
"""wow.py: k4 around World of Warcraft (k4-wow runs it). Forever by default (the _forever_ folder;
~/.config/k4/wow: flavor=_classic_beta_, region=eu, reset=Wed 04:00 UTC, realm=<name> override).

  wow.py data                  the window's lines (src/wow.odin): S P C L K R T
  wow.py chars                 the characters (TSV) from the companion addon's SavedVariables
  wow.py watch                 while the game runs: the session's time, new screenshots as cards
  wow.py tick                  every minute (k4-wow.timer): reset and raid-night reminders, realm and token
  wow.py reset [--short]       the next weekly reset (unix time, or "2 d 4 h")
  wow.py play                  the game, straight into the flavour (Battle.net under umu)
  wow.py addons                the installed addons (TSV): folder title version author source update
  wow.py act VERB …            install-companion, update [FOLDER|all], undo, add github OWNER/REPO,
                               add wago|curseforge ID, remove FOLDER, search Q, raid add DAY HH:MM NAME,
                               raid remove N, token, realm, open-screens, open-logs, client
  wow.py bar | find | info     the bar module (JSON), the launcher's rows, the Apps page's lines

Never touches the game while it runs (addons), never reads anything but WoW's own folders and
the APIs named. Blizzard's API: your own client (develop.battle.net), id in
~/.config/k4/blizzard-client.json, secret in the keyring (k4-secret token blizzard).
"""
import datetime as dt, glob, io, json, os, re, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request, zipfile

HOME = os.path.expanduser("~")
STATE = os.environ.get("K4_WOW_STATE") or os.path.join(HOME, ".local/state/k4/wow")
CACHE = os.environ.get("K4_WOW_CACHE") or os.path.join(HOME, ".cache/k4/wow")
CONF = os.path.join(HOME, ".config/k4/wow")
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
SELF = os.path.realpath(__file__)
FRONT = os.environ.get("K4_WOW_FRONT") or "k4-wow"
COMPANION = os.path.join(os.path.dirname(SELF), "wow-companion")
FAKE = os.environ.get("K4_WOW_FAKE")   # tests: API answers from files, no game, no notifications
UA = "k4-wow/1 (+https://github.com/kr4nkenwagen/k4)"


def field(s): return re.sub(r"[\t\r\n]+", " ", str(s if s is not None else "")).strip()


def say(*lines):
    for ln in lines: print(ln, flush=True)


def jload(path, default):
    try:
        with open(path) as f: return json.load(f)
    except (OSError, ValueError): return default


def jsave(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(data, f)
    os.replace(path + ".tmp", path)


def conf():
    c = {"flavor": "_forever_", "region": "eu", "reset": "Wed 04:00", "realm": ""}
    try:
        with open(CONF) as f:
            for ln in f:
                k, sep, v = ln.partition("=")
                if sep and not ln.lstrip().startswith("#"): c[k.strip()] = v.strip()
    except OSError: pass
    return c


# ---------- where WoW is ----------

def root():
    """World of Warcraft's folder: K4_WOW_DIR, else the Battle.net prefix's."""
    if os.environ.get("K4_WOW_DIR"): return os.environ["K4_WOW_DIR"]
    for p in (os.path.join(HOME, "Games/battlenet/drive_c/Program Files (x86)/World of Warcraft"),
              os.path.join(HOME, "Games/battlenet/drive_c/Program Files/World of Warcraft")):
        if os.path.isdir(p): return p
    return ""


def flavor_dir():
    r = root()
    return os.path.join(r, conf()["flavor"]) if r else ""


def product():
    """The flavour's product code from its .flavor.info (wowf for Forever)."""
    try:
        with open(os.path.join(flavor_dir(), ".flavor.info")) as f: return f.read().split()[-1]
    except (OSError, IndexError): return "wowf"


def build_version():
    """The client's version from .build.info (1.60.1.70685), for the companion's Interface number."""
    try:
        with open(os.path.join(root(), ".build.info")) as f: rows = [ln.rstrip("\n").split("|") for ln in f]
        head = rows[0]
        vi, pi = next(i for i, h in enumerate(head) if h.startswith("Version")), next(i for i, h in enumerate(head) if h.startswith("Product"))
        for r in rows[1:]:
            if len(r) > max(vi, pi) and r[pi] == product(): return r[vi]
    except (OSError, StopIteration, IndexError): pass
    return ""


def interface_number():
    v = build_version().split(".")
    try: return "%d%02d%02d" % (int(v[0]), int(v[1]), int(v[2]))
    except (ValueError, IndexError): return "16001"


def addons_dir(): return os.path.join(flavor_dir(), "Interface", "AddOns")


def running():
    """The game runs (Wow.exe / WowClassic.exe under Wine)."""
    if FAKE: return os.environ.get("K4_WOW_RUNNING") == "1"
    r = subprocess.run(["pgrep", "-fi", r"[\\/]_forever_[\\/]Wow|Wow(Classic|B)?\.exe"], capture_output=True)
    return r.returncode == 0


# ---------- the companion addon's SavedVariables ----------

def lua_table(text):
    """The first `NAME = { … }` of a SavedVariables file as Python (tables: dicts, or lists when
    every key is 1…n)."""
    i = text.find("{")
    if i < 0: return {}
    pos = [i]

    def ws():
        while pos[0] < len(text):
            c = text[pos[0]]
            if c in " \t\r\n,;": pos[0] += 1
            elif text.startswith("--", pos[0]):
                j = text.find("\n", pos[0]); pos[0] = len(text) if j < 0 else j
            else: break

    def string():
        q = text[pos[0]]; pos[0] += 1; out = []
        while pos[0] < len(text) and text[pos[0]] != q:
            c = text[pos[0]]
            if c == "\\":
                pos[0] += 1; e = text[pos[0]]
                out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(e, e))
            else: out.append(c)
            pos[0] += 1
        pos[0] += 1
        return "".join(out)

    def value():
        ws()
        c = text[pos[0]]
        if c == "{": return table()
        if c in "\"'": return string()
        m = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|true|false|nil").match(text, pos[0])
        if not m: raise ValueError("bad value at %d" % pos[0])
        pos[0] = m.end(); t = m.group()
        return True if t == "true" else False if t == "false" else None if t == "nil" else (float(t) if "." in t or "e" in t.lower() else int(t))

    def table():
        pos[0] += 1; d, n = {}, 1
        while True:
            ws()
            if text[pos[0]] == "}": pos[0] += 1; break
            if text[pos[0]] == "[":
                pos[0] += 1; ws(); k = value(); ws(); pos[0] += 1; ws(); pos[0] += 1   # [key] =
                d[k] = value()
            else:
                m = re.compile(r"[A-Za-z_]\w*\s*=").match(text, pos[0])
                if m: pos[0] = m.end(); d[m.group()[:-1].strip()] = value()
                else: d[n] = value(); n += 1
        if d and all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)): return [d[k] for k in sorted(d)]
        return d
    try: return table()
    except (ValueError, IndexError): return {}


def chars():
    """Every character the companion has seen, newest first."""
    out = []
    for f in glob.glob(os.path.join(flavor_dir(), "WTF", "Account", "*", "SavedVariables", "K4CompanionDB.lua")):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh: db = lua_table(fh.read())
        except OSError: continue
        if isinstance(db, dict):
            for c in db.values():
                if isinstance(c, dict) and c.get("name"): out.append(c)
    out.sort(key=lambda c: -int(c.get("seen", 0)))
    return out


def companion_installed(): return os.path.isfile(os.path.join(addons_dir(), "K4Companion", "K4Companion.toc"))


def install_companion():
    if not flavor_dir() or not os.path.isdir(flavor_dir()): say("WoW is not installed here"); say("k4:tone red"); return
    dest = os.path.join(addons_dir(), "K4Companion")
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(COMPANION):
        with open(os.path.join(COMPANION, name)) as f: body = f.read()
        if name.endswith(".toc"): body = re.sub(r"(?m)^## Interface:.*$", "## Interface: %s" % interface_number(), body)
        with open(os.path.join(dest, name), "w") as f: f.write(body)
    say("K4 Companion installed · log in once (or /reload) and k4 sees your character"); say("k4:tone green")


# ---------- money and time ----------

def money(copper):
    c = int(copper or 0)
    g, s, cc = c // 10000, c // 100 % 100, c % 100
    return "%dg %ds %dc" % (g, s, cc) if g else ("%ds %dc" % (s, cc) if s else "%dc" % cc)


def gold_short(copper):
    g = int(copper or 0) // 10000
    return "%dk" % (g // 1000) if g >= 10000 else "%dg" % g


def span(secs):
    s = max(int(secs), 0)
    d, h, m = s // 86400, s // 3600 % 24, s // 60 % 60
    return "%d d %d h" % (d, h) if d else ("%d h %d m" % (h, m) if h else "%d m" % m)


def now(): return int(os.environ.get("K4_WOW_NOW") or time.time())


def next_reset(t=None):
    """The next weekly reset: the earliest raid lockout's own reset when the companion has one,
    else the region's (conf reset=Wed 04:00, UTC)."""
    t = t or now()
    resets = [int(l["reset"]) for c in chars() for l in (c.get("lockouts") or []) if l.get("raid") and int(l.get("reset", 0)) > t]
    if resets: return min(resets)
    day, _, hm = conf()["reset"].partition(" ")
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    wd = days.index(day[:3].lower()) if day[:3].lower() in days else 2
    h, _, mi = (hm or "04:00").partition(":")
    base = dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(hour=int(h), minute=int(mi or 0), second=0, microsecond=0)
    base += dt.timedelta(days=(wd - base.weekday()) % 7)
    if base.timestamp() <= t: base += dt.timedelta(days=7)
    return int(base.timestamp())


def sessions():
    out = []
    try:
        with open(os.path.join(STATE, "sessions.tsv")) as f:
            for ln in f:
                a, _, b = ln.strip().partition("\t")
                if a.isdigit(): out.append((int(a), int(b) if b.isdigit() else now()))
    except OSError: pass
    return out


def played_since(t0):
    return sum(max(0, min(b, now()) - max(a, t0)) for a, b in sessions() if b > t0)


def today_start():
    d = dt.datetime.fromtimestamp(now()).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


def week_start():
    d = dt.datetime.fromtimestamp(today_start())
    return int((d - dt.timedelta(days=d.weekday())).timestamp())


# ---------- notifications ----------

def post(title, body, acts, image="", tag="", warn=False, ident="0"):
    if FAKE:
        with open(os.path.join(FAKE, "posts.log"), "a") as f: f.write("%s | %s | %s | %s\n" % (title, body, acts, image))
        return
    line = "\t".join(["post", ident, "WoW", field(title), field(body)[:300], "warn" if warn else "1", "-1", "-1", tag, "󰺵", "",
                      acts, "%s note" % FRONT] + ([image] if image else []))
    subprocess.run(["k4", "--notify-ctl", line], capture_output=True, timeout=5)


def note(key, card):
    """A card's button: copy and folder (screenshots), play (raid night), the window."""
    shot = jload(os.path.join(STATE, "cards.json"), {}).get("last", "")   # (the newest screenshot's card)
    if key == "copy" and shot:
        with open(shot, "rb") as f: subprocess.run(["wl-copy", "--type", "image/png"], stdin=f)
    elif key == "folder": subprocess.Popen(["xdg-open", os.path.dirname(shot) if shot else os.path.join(flavor_dir(), "Screenshots")], start_new_session=True)
    elif key == "play": play()
    elif key in ("default", "open"): subprocess.Popen(["setsid", "-f", FRONT, "window"])


# ---------- the game ----------

def play():
    """Battle.net straight into the flavour (its --exec), else Battle.net as it is."""
    if FAKE: say("(play %s)" % product()); return
    if running(): say("WoW is already running"); return
    pre = os.path.join(HOME, "Games/battlenet")
    exe = os.path.join(pre, "drive_c/Program Files (x86)/Battle.net/Battle.net.exe")
    env = dict(os.environ, WINEPREFIX=pre, PROTONPATH="GE-Proton", GAMEID="umu-battlenet", PROTON_VERB="run")
    if os.path.exists(exe) and shutil.which("umu-run"):
        subprocess.Popen(["umu-run", exe, "--exec=launch %s" % product().upper()], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["omarchy-launch-battlenet"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(["setsid", "-f", sys.executable, "-I", SELF, "watch"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say("Starting World of Warcraft · Battle.net opens it"); say("k4:close")


def watch():
    """While the game runs: its session in sessions.tsv, screenshots as cards. One at a time."""
    import fcntl
    fd = os.open(os.path.join(RUN, "k4-wow-watch.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: return
    for _ in range(180):   # (the game takes a while to start: up to 6 minutes)
        if running(): break
        time.sleep(2)
    else: return
    start = now()
    os.makedirs(STATE, exist_ok=True)
    shots = os.path.join(flavor_dir(), "Screenshots")
    seen = set(os.listdir(shots)) if os.path.isdir(shots) else set()
    log = os.path.join(STATE, "sessions.tsv")
    with open(log, "a") as f: f.write("%d\t\n" % start)
    try:
        while running():
            time.sleep(2)
            if os.path.isdir(shots):
                for name in sorted(set(os.listdir(shots)) - seen):
                    seen.add(name)
                    if name.lower().endswith((".jpg", ".jpeg", ".tga", ".png")): screenshot(os.path.join(shots, name))
    finally:
        rows = open(log).read().rstrip("\n").split("\n")
        if rows and rows[-1].startswith("%d\t" % start): rows[-1] = "%d\t%d" % (start, now())
        with open(log, "w") as f: f.write("\n".join(rows) + "\n")


def screenshot(path):
    """A new screenshot: a card with the picture (TGA made PNG), Copy, Send to…, the folder."""
    time.sleep(0.5)   # (written in one go, but give it a moment)
    pic = path
    if path.lower().endswith(".tga"):
        os.makedirs(os.path.join(CACHE, "shots"), exist_ok=True)
        pic = os.path.join(CACHE, "shots", os.path.splitext(os.path.basename(path))[0] + ".png")
        subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-i", path, pic])
    jsave(os.path.join(STATE, "cards.json"), {"last": pic})
    post("Screenshot", os.path.basename(path), "copy:Copy,folder:Open folder,default:", image=pic)


# ---------- Blizzard's API ----------

def blizzard_client():
    c = jload(os.path.join(HOME, ".config/k4/blizzard-client.json"), {})
    if not c.get("client_id"): return None
    try:
        sec = subprocess.run(["k4-secret", "lookup", "token", "blizzard"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError): sec = ""
    return (c["client_id"], sec) if sec else None


def bz_token():
    cache = os.path.join(RUN, "k4-wow-bz.json")
    t = jload(cache, {})
    if t.get("expires", 0) > time.time() + 60: return t["token"]
    cl = blizzard_client()
    if not cl: raise PermissionError("no Blizzard client")
    import base64
    req = urllib.request.Request("https://oauth.battle.net/token", data=b"grant_type=client_credentials",
                                 headers={"Authorization": "Basic " + base64.b64encode(("%s:%s" % cl).encode()).decode(), "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r: j = json.load(r)
    fd = os.open(cache, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump({"token": j["access_token"], "expires": time.time() + j.get("expires_in", 3600)}, f)
    return j["access_token"]


def bz(path, namespace, query=None):
    if FAKE:
        name = re.sub(r"[^A-Za-z0-9]+", "_", "%s %s" % (namespace, path)).strip("_") + ".json"
        try:
            with open(os.path.join(FAKE, name)) as f: return json.load(f)
        except OSError: raise urllib.error.HTTPError(path, 404, "not found", {}, None)
    reg = conf()["region"]
    q = dict(query or {}, namespace=namespace, locale="en_GB")
    req = urllib.request.Request("https://%s.api.blizzard.com%s?%s" % (reg, path, urllib.parse.urlencode(q)),
                                 headers={"Authorization": "Bearer " + bz_token(), "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r: return json.load(r)


def namespaces(kind):
    reg = conf()["region"]
    return ["%s-%s-%s" % (kind, product(), reg), "%s-classic1x-%s" % (kind, reg), "%s-classic-%s" % (kind, reg), "%s-%s" % (kind, reg)]


def world(force=False):
    """Realm status and the token price, cached 10 minutes: {realms: [...], token, ns, why}."""
    path = os.path.join(CACHE, "world.json")
    w = jload(path, {})
    if not force and time.time() - w.get("at", 0) < 600: return w
    out = {"at": int(time.time()), "realms": [], "token": None, "ns": "", "why": ""}
    if not FAKE and not blizzard_client():
        out["why"] = "noclient"; jsave(path, out); return out
    try:
        for ns in namespaces("dynamic"):
            try: idx = bz("/data/wow/connected-realm/index", ns)
            except urllib.error.HTTPError as e:
                if e.code == 404: continue
                raise
            out["ns"] = ns
            want = {c.get("realm", "").lower() for c in chars()} | ({conf()["realm"].lower()} if conf()["realm"] else set())
            for ref in idx.get("connected_realms", [])[:200]:
                cid = re.search(r"connected-realm/(\d+)", ref.get("href", ""))
                if not cid or not want: continue
                cr = bz("/data/wow/connected-realm/%s" % cid.group(1), ns)
                names = [r.get("name", "") for r in cr.get("realms", [])]
                if any(n.lower() in want for n in names):
                    out["realms"].append({"name": " / ".join(names), "status": cr.get("status", {}).get("type", ""),
                                          "population": cr.get("population", {}).get("type", ""), "queue": bool(cr.get("has_queue"))})
            try: out["token"] = bz("/data/wow/token/index", ns).get("price")
            except urllib.error.HTTPError: pass
            break
        else:
            out["why"] = "notinapi"
    except PermissionError: out["why"] = "noclient"
    except (urllib.error.URLError, OSError, TimeoutError) as e: out["why"] = "offline"; out["note"] = field(e)[:80]
    old = {r["name"]: r["status"] for r in w.get("realms", [])}
    for r in out["realms"]:   # a realm back up: say so
        if old.get(r["name"]) == "DOWN" and r["status"] == "UP": post("%s is up again" % r["name"], "The realm is back", "play:Play,default:")
    jsave(path, out)
    return out


# ---------- addons ----------

def toc(folder):
    """A folder's .toc fields (## Key: value)."""
    d = os.path.join(addons_dir(), folder)
    tocs = [f for f in os.listdir(d) if f.lower().endswith(".toc")] if os.path.isdir(d) else []
    pick = next((f for f in tocs if f.lower() in (folder.lower() + ".toc",)), tocs[0] if tocs else "")
    out = {}
    if not pick: return out
    with open(os.path.join(d, pick), encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = re.match(r"##\s*([^:]+):\s*(.*)", ln)
            if m: out[m.group(1).strip()] = re.sub(r"\|c[0-9a-fA-F]{8}|\|r", "", m.group(2).strip())
    return out


def tracked(): return jload(os.path.join(STATE, "addons.json"), {})


def toc_at(d):
    """A folder's .toc fields wherever it is (the undo copy)."""
    out = {}
    for f in (os.listdir(d) if os.path.isdir(d) else []):
        if f.lower().endswith(".toc"):
            with open(os.path.join(d, f), encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    m = re.match(r"##\s*([^:]+):\s*(.*)", ln)
                    if m: out[m.group(1).strip()] = m.group(2).strip()
            break
    return out


def addons():
    """Installed addons: folder, title, version, author, source, update (a newer version, or "")."""
    d = addons_dir()
    if not os.path.isdir(d): return []
    tr, ups = tracked(), jload(os.path.join(CACHE, "updates.json"), {})
    out = []
    for folder in sorted(os.listdir(d), key=str.lower):
        if folder.startswith(".") or not os.path.isdir(os.path.join(d, folder)): continue
        t = toc(folder)
        parent = next((k for k, v in tr.items() if folder in v.get("folders", [])), "")
        if parent and parent != folder: continue   # (a module of a tracked addon: listed under it)
        src = tr.get(folder, {}).get("source", "") or ("wago" if t.get("X-Wago-ID") else "curseforge" if t.get("X-Curse-Project-ID") else "")
        out.append({"folder": folder, "title": t.get("Title", folder), "version": tr.get(folder, {}).get("version") or t.get("Version", ""),
                    "author": t.get("Author", ""), "notes": t.get("Notes", ""), "source": "k4" if folder == "K4Companion" else src, "update": ups.get(folder, "")})
    return out


def key_of(src):
    if FAKE: return "" if src in os.environ.get("K4_WOW_NOKEYS", "").split(",") else "test"
    r = subprocess.run(["k4-secret", "lookup", "token", src], capture_output=True, text=True, timeout=15)
    return r.stdout if r.returncode == 0 else ""


def http_json(url, headers=None):
    if FAKE:
        name = re.sub(r"[^A-Za-z0-9]+", "_", url).strip("_")[:150] + ".json"
        with open(os.path.join(FAKE, name)) as f: return json.load(f)
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)


def http_bytes(url, headers=None):
    if FAKE:
        with open(os.path.join(FAKE, os.path.basename(urllib.parse.urlparse(url).path)), "rb") as f: return f.read()
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()


def latest(src, ident):
    """(version, zip URL, headers) of an addon's newest release for this flavour."""
    if src == "github":
        rel = http_json("https://api.github.com/repos/%s/releases/latest" % ident)
        assets = [a for a in rel.get("assets", []) if a.get("name", "").lower().endswith(".zip")]
        pref = [a for a in assets if any(k in a["name"].lower() for k in ("forever", "classic", "vanilla", "era"))] or assets
        if not pref: raise ValueError("no .zip in the latest release")
        return rel.get("tag_name", ""), pref[0]["browser_download_url"], {}
    if src == "wago":
        k = key_of("wago")
        if not k: raise PermissionError("wago")
        d = http_json("https://addons.wago.io/api/external/addons/%s?game_version=classic" % ident, {"Authorization": "Bearer " + k})
        rel = (d.get("recent_release") or {}).get("classic") or next(iter((d.get("recent_release") or {}).values()), {})
        return rel.get("label", ""), rel.get("download_link", ""), {"Authorization": "Bearer " + k}
    if src == "curseforge":
        k = key_of("curseforge")
        if not k: raise PermissionError("curseforge")
        d = http_json("https://api.curseforge.com/v1/mods/%s/files?pageSize=10" % ident, {"x-api-key": k})
        files = sorted(d.get("data", []), key=lambda f: f.get("fileDate", ""), reverse=True)
        if not files: raise ValueError("no files")
        return files[0].get("displayName", ""), files[0].get("downloadUrl", ""), {}
    raise ValueError("unknown source " + src)


def install(src, ident):
    """Download, unpack in a scratch folder, swap into AddOns (the old copy kept for one undo)."""
    if running(): say("Close WoW first · it keeps its addons in memory"); say("k4:tone yellow"); return
    try: ver, url, hdr = latest(src, ident)
    except PermissionError as e: say("%s needs an API key of your own · k4-secret store token %s" % (str(e).title(), e)); say("k4:tone yellow"); return
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e: say("Could not find it · %s" % field(e)[:80]); say("k4:tone red"); return
    blob = http_bytes(url, hdr)
    tmp = tempfile.mkdtemp(prefix="k4-wow-", dir=CACHE if os.path.isdir(CACHE) else None)
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for n in z.namelist():   # (no paths out of the folder)
                if n.startswith("/") or ".." in n.split("/"): raise ValueError("unsafe path in the zip")
            z.extractall(tmp)
        folders = [f for f in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, f))]
        if not folders: raise ValueError("no addon folder in the zip")
        os.makedirs(addons_dir(), exist_ok=True)
        undo = os.path.join(STATE, "undo")
        shutil.rmtree(undo, ignore_errors=True); os.makedirs(undo)
        for f in folders:
            dest = os.path.join(addons_dir(), f)
            if os.path.exists(dest): shutil.move(dest, os.path.join(undo, f))
            shutil.move(os.path.join(tmp, f), dest)
        main = sorted(folders, key=len)[0]
        tr = tracked()
        tr[main] = {"source": src, "id": ident, "version": ver, "folders": folders, "at": int(time.time())}
        jsave(os.path.join(STATE, "addons.json"), tr)
        old = toc_at(os.path.join(undo, main)).get("Version", "")
        jsave(os.path.join(STATE, "undo.json"), {"folders": folders, "main": main, "title": toc(main).get("Title", main), "old": old, "new": ver, "at": int(time.time())})
        ups = jload(os.path.join(CACHE, "updates.json"), {}); ups.pop(main, None); jsave(os.path.join(CACHE, "updates.json"), ups)
        say("%s %s installed%s" % (toc(main).get("Title", main), ver, " · %d folders" % len(folders) if len(folders) > 1 else "")); say("k4:tone green")
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        say("Not installed · %s" % field(e)[:80]); say("k4:tone red")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def undo():
    u = jload(os.path.join(STATE, "undo.json"), {})
    keep = os.path.join(STATE, "undo")
    if not u or not os.path.isdir(keep): say("Nothing to undo"); return
    if running(): say("Close WoW first"); say("k4:tone yellow"); return
    for f in u["folders"]:
        shutil.rmtree(os.path.join(addons_dir(), f), ignore_errors=True)
        if os.path.exists(os.path.join(keep, f)): shutil.move(os.path.join(keep, f), os.path.join(addons_dir(), f))
    os.remove(os.path.join(STATE, "undo.json"))
    say("Put back the version from before"); say("k4:tone green")


def check_updates():
    """Which tracked addons have a newer release (updates.json), at most once an hour."""
    path = os.path.join(CACHE, "updates.json")
    if not FAKE and os.path.exists(path) and time.time() - os.path.getmtime(path) < 3600: return jload(path, {})
    ups = {}
    for folder, t in tracked().items():
        try:
            ver, _, _ = latest(t["source"], t["id"])
            if ver and ver != t.get("version"): ups[folder] = ver
        except (PermissionError, urllib.error.URLError, OSError, ValueError, KeyError): continue
    jsave(path, ups)
    return ups


def search(q):
    """Wago and CurseForge, each with a key of your own: the hits kept for the window (search.json)."""
    q = q.strip()
    hits, asked, why = [], [], ""
    if key_of("wago"):
        asked.append("Wago")
        try:
            d = http_json("https://addons.wago.io/api/external/addons/_search?query=%s&game_version=classic" % urllib.parse.quote(q), {"Authorization": "Bearer " + key_of("wago")})
            hits += [{"source": "wago", "id": str(x.get("id", "")), "name": field(x.get("display_name")), "summary": field(x.get("summary"))[:120]} for x in (d.get("data") or [])[:15]]
        except (urllib.error.URLError, OSError, ValueError) as e: why = field(e)[:60]
    if key_of("curseforge"):
        asked.append("CurseForge")
        try:
            d = http_json("https://api.curseforge.com/v1/mods/search?gameId=1&searchFilter=%s&pageSize=15" % urllib.parse.quote(q), {"x-api-key": key_of("curseforge")})
            hits += [{"source": "curseforge", "id": str(x.get("id", "")), "name": field(x.get("name")), "summary": field(x.get("summary"))[:120]} for x in d.get("data", [])]
        except (urllib.error.URLError, OSError, ValueError) as e: why = field(e)[:60]
    jsave(os.path.join(CACHE, "search.json"), {"q": q, "hits": hits})
    if not asked: say("Searching needs a Wago or CurseForge key · paste one in the card"); say("k4:tone yellow"); return
    say("%d found · %s%s" % (len(hits), " and ".join(asked), " · " + why if why else ""))


# ---------- raid nights ----------

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def raids(): return jload(os.path.join(STATE, "raids.json"), [])


def raid_next(r, t=None):
    """The next start of a weekly raid night (local time)."""
    t = t or now()
    h, _, m = r["time"].partition(":")
    d = dt.datetime.fromtimestamp(t).replace(hour=int(h), minute=int(m or 0), second=0, microsecond=0)
    d += dt.timedelta(days=(DAYS.index(r["day"]) - d.weekday()) % 7)
    if d.timestamp() <= t - 3600: d += dt.timedelta(days=7)
    return int(d.timestamp())


def raid_add(day, hm, name):
    day = day[:3].lower()
    if day not in DAYS or not re.match(r"^\d{1,2}:\d{2}$", hm): say("raid add DAY HH:MM NAME (Wed 20:00 Molten Core)"); return
    rs = raids(); rs.append({"day": day, "time": hm, "name": name})
    jsave(os.path.join(STATE, "raids.json"), rs)
    said = calendar_event(day, hm, name)
    full = dict(zip(DAYS, ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]))[day]
    say("%s on %s at %s%s" % (name, full, hm, " · in Calendar" if said else "")); say("k4:tone green")


def calendar_event(day, hm, name):
    """A weekly event in a WoW calendar through k4-cal's sign-in (google.py); False without one."""
    if FAKE: return False
    sys.path.insert(0, os.path.dirname(SELF))
    try:
        import google
        cal = google.Account("Google Calendar", "https://www.googleapis.com/auth/calendar", ["service", "k4-google-calendar"],
                             os.path.join(RUN, "k4-cal-token.json"), "https://www.googleapis.com/calendar/v3")
        if not cal.refresh_token(): return False
        cid = jload(os.path.join(STATE, "calendar.json"), {}).get("id")
        if not cid:
            cid = cal.request("POST", "/calendars", {"summary": "WoW"})["id"]
            jsave(os.path.join(STATE, "calendar.json"), {"id": cid})
        start = dt.datetime.fromtimestamp(raid_next({"day": day, "time": hm})).astimezone()
        tz = os.environ.get("TZ") or (os.path.realpath("/etc/localtime").split("zoneinfo/")[-1] if os.path.exists("/etc/localtime") else "UTC")
        cal.request("POST", "/calendars/%s/events" % urllib.parse.quote(cid, safe=""), {
            "summary": name, "start": {"dateTime": start.isoformat(), "timeZone": tz},
            "end": {"dateTime": (start + dt.timedelta(hours=3)).isoformat(), "timeZone": tz},
            "recurrence": ["RRULE:FREQ=WEEKLY"], "reminders": {"useDefault": False, "overrides": []}})
        subprocess.Popen(["k4-cal", "sync", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False


# ---------- every minute ----------

def tick():
    """Reminders (once each): the reset in 1 h, a raid night in 15 min; realm and token (10 min)."""
    done = jload(os.path.join(STATE, "said.json"), {})
    t = now()
    r = next_reset(t)
    if 0 < r - t <= 3600 and done.get("reset") != r:
        open_ = [l["name"] for c in chars() for l in (c.get("lockouts") or []) if l.get("raid") and int(l.get("killed", 0)) < int(l.get("bosses", 1))]
        post("Weekly reset in %s" % span(r - t), ("Still open: " + ", ".join(sorted(set(open_)))) if open_ else "Lockouts, cooldowns and the vendor reset", "play:Play,default:")
        done["reset"] = r
    for i, rd in enumerate(raids()):
        s = raid_next(rd, t)
        if 0 < s - t <= 900 and done.get("raid%d" % i) != s:
            post("%s in %s" % (rd["name"], span(s - t)), "Raid night · %s %s" % (rd["day"].title(), rd["time"]), "play:Launch WoW,default:")
            done["raid%d" % i] = s
    jsave(os.path.join(STATE, "said.json"), done)
    if running() and not FAKE:   # (started from Battle.net, not k4: the watch starts here; it keeps one at a time)
        subprocess.Popen(["setsid", "-f", sys.executable, "-I", SELF, "watch"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if blizzard_client() or FAKE: world()


# ---------- what k4 shows ----------

CLASS = {"WARRIOR": "C69B6D", "PALADIN": "F48CBA", "HUNTER": "AAD372", "ROGUE": "FFF468", "PRIEST": "FFFFFF", "SHAMAN": "0070DD",
         "MAGE": "3FC7EB", "WARLOCK": "8788EE", "DRUID": "FF7C0A", "DEATHKNIGHT": "C41E3A", "MONK": "00FF98", "DEMONHUNTER": "A330C9", "EVOKER": "33937F"}


def state_of():
    if not root(): return "missing"
    if not os.path.isdir(flavor_dir()): return "noflavor"
    return "ok"


def data():
    """S state version product running · P played today week last · C a character · X its lockouts ·
    K its cooldowns · W realms and token · T the reset · A addons summary (R and L are the panel's)"""
    st = state_of()
    w = jload(os.path.join(CACHE, "world.json"), {})
    say("S\t%s\t%s\t%s\t%d\t%d" % (st, build_version(), product(), running(), companion_installed()))
    last = max((b for a, b in sessions()), default=0)
    say("P\t%d\t%d\t%d" % (played_since(today_start()), played_since(week_start()), last))
    for c in chars():
        key = "%s-%s" % (c.get("name"), c.get("realm"))
        rested = int(c.get("rested") or 0); xpmax = int(c.get("xpMax") or 0)
        say("C\t%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t%d\t%d\t%s\t%d\t%s" % (key, field(c.get("name")), field(c.get("realm")), c.get("class", ""), CLASS.get(c.get("class", ""), "A9D3DE"),
            field(c.get("race")), int(c.get("level") or 0), field(c.get("className")), int(c.get("gold") or 0), int(rested * 100 / xpmax) if xpmax else -1,
            int(c.get("played") or 0), int(c.get("playedLevel") or 0), int(c.get("ilvl") or 0), field(c.get("zone")), field(c.get("subzone")),
            int(c.get("bagsFree") or 0), int(c.get("seen") or 0), "1" if c.get("resting") else "0", int(c.get("bagsTotal") or 0),
            field(" · ".join("%s %s" % (p.get("name", ""), p.get("rank", "")) for p in (c.get("professions") or [])))))
        for l in c.get("lockouts") or []:
            say("X\t%s\t%s\t%d\t%d\t%d\t%d" % (key, field(l.get("name")), int(l.get("killed") or 0), int(l.get("bosses") or 0), int(l.get("reset") or 0), 1 if l.get("raid") else 0))
        for k in c.get("cooldowns") or []:
            say("K\t%s\t%s\t%d" % (key, field(k.get("name")), int(k.get("ready") or 0)))
    for r in w.get("realms", []): say("W\trealm\t%s\t%s\t%s\t%d" % (field(r["name"]), r["status"], r["population"], r["queue"]))
    if w.get("token"): say("W\ttoken\t%d" % w["token"])
    if w.get("why"): say("W\twhy\t%s" % w["why"])
    say("T\t%d\t%d" % (next_reset(), now()))
    ups = jload(os.path.join(CACHE, "updates.json"), {})
    ads = addons()
    say("A\t%d\t%d" % (len(ads), len(ups)))
    for x in ads:
        say("N\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (x["folder"], field(x["title"]), field(x["version"]), field(x["author"]), field(x["notes"]), x["source"], x["update"]))
    sr = jload(os.path.join(CACHE, "search.json"), {})
    say("Q\t%s\t%d\t%d" % (field(sr.get("q", "")), bool(key_of("wago")), bool(key_of("curseforge"))))
    for h in sr.get("hits", []): say("H\t%s\t%s\t%s\t%s" % (h["source"], h["id"], field(h["name"]), field(h["summary"])))
    for i, r in enumerate(raids()): say("D\t%d\t%s\t%s\t%s\t%d" % (i, r["day"], r["time"], field(r["name"]), raid_next(r)))
    u = jload(os.path.join(STATE, "undo.json"), {})
    if u.get("title") and os.path.isdir(os.path.join(STATE, "undo")): say("U\t%s\t%s\t%s\t%d" % (field(u["title"]), field(u.get("old", "")), field(u.get("new", "")), u.get("at", 0)))
    print("R\t%s act" % FRONT); print("L\t%s data" % FRONT)


def bar():
    cs = chars()
    if not cs: print("{}"); return
    gold = sum(int(c.get("gold") or 0) for c in cs)
    ready = [k["name"] for c in cs for k in (c.get("cooldowns") or []) if int(k.get("ready") or 0) <= now()]
    w = jload(os.path.join(CACHE, "world.json"), {})
    down = [r["name"] for r in w.get("realms", []) if r.get("status") == "DOWN"]
    queue = [r["name"] for r in w.get("realms", []) if r.get("queue")]
    out = {"icon": "󰺵", "text": gold_short(gold), "tooltip": "WoW · %s across %d characters%s%s · reset in %s" % (
        money(gold), len(cs), (" · %d cooldowns ready" % len(ready)) if ready else "", (" · " + ", ".join(down) + " down") if down else "", span(next_reset() - now()))}
    if running():
        a = max((a for a, b in sessions() if b >= now() - 5), default=0)
        if a: out["text2"] = span(now() - a)
    if ready: out["badge"] = len(ready)
    if down: out["icon_tone"] = "red"
    elif queue: out["icon_tone"] = "yellow"
    print(json.dumps(out, ensure_ascii=False))


def find():
    for c in chars():
        print("\t".join([field(c.get("name")), field(c.get("realm")), field(c.get("className")), str(int(c.get("level") or 0)), money(c.get("gold"))]))


def info():
    """The Apps page's: S state played-today played-week reset companion running · C chars · W realms/token · A addons"""
    w = jload(os.path.join(CACHE, "world.json"), {})
    print("S\t%s\t%d\t%d\t%d\t%d\t%d" % (state_of(), played_since(today_start()), played_since(week_start()), next_reset() - now(), companion_installed(), running()))
    for c in chars():
        print("C\t%s\t%s\t%s\t%d\t%s\t%d" % (field(c.get("name")), field(c.get("realm")), field(c.get("className")), int(c.get("level") or 0), money(c.get("gold")), int(c.get("seen") or 0)))
    for r in w.get("realms", []): print("W\trealm\t%s\t%s\t%d" % (field(r["name"]), r["status"], r["queue"]))
    if w.get("token"): print("W\ttoken\t%s" % money(w["token"]))
    if w.get("why"): print("W\twhy\t%s" % w["why"])
    for a in addons(): print("A\t%s\t%s\t%s\t%s\t%s" % (a["folder"], field(a["title"]), field(a["version"]), a["source"], a["update"]))
    for i, r in enumerate(raids()): print("D\t%d\t%s\t%s\t%s\t%d" % (i, r["day"], r["time"], field(r["name"]), raid_next(r)))
    sr = jload(os.path.join(CACHE, "search.json"), {})
    for h in sr.get("hits", []): print("H\t%s\t%s\t%s\t%s\t%s" % (h["source"], h["id"], h["name"], h["summary"], field(sr.get("q"))))


def act(verb, a):
    a = a + [""] * 4
    if verb == "install-companion": install_companion()
    elif verb == "play": play()
    elif verb == "update":
        if a[0] and a[0] != "all":
            t = tracked().get(a[0])
            if not t: say("%s is not tracked · add it from GitHub, Wago or CurseForge" % a[0]); return
            install(t["source"], t["id"])
        else:
            ups = check_updates()
            if not ups: say("Every tracked addon is up to date"); return
            for f in list(ups): install(tracked()[f]["source"], tracked()[f]["id"])
    elif verb == "check": ups = check_updates(); say("%d update%s" % (len(ups), "" if len(ups) == 1 else "s"))
    elif verb == "undo": undo()
    elif verb == "add": install(a[0], a[1])
    elif verb == "remove":
        if running(): say("Close WoW first"); say("k4:tone yellow"); return
        tr = tracked(); folders = tr.pop(a[0], {}).get("folders", [a[0]])
        for f in folders: shutil.rmtree(os.path.join(addons_dir(), f), ignore_errors=True)
        jsave(os.path.join(STATE, "addons.json"), tr); say("Removed %s" % a[0])
    elif verb == "search": search(" ".join(x for x in a if x))
    elif verb == "raid":
        if a[0] == "add": raid_add(a[1], a[2], " ".join(x for x in a[3:] if x) or "Raid")
        elif a[0] == "remove":
            rs = raids()
            if a[1].isdigit() and int(a[1]) < len(rs): r = rs.pop(int(a[1])); jsave(os.path.join(STATE, "raids.json"), rs); say("Removed %s (Calendar keeps its event; delete it there)" % r["name"])
    elif verb in ("realm", "token", "world"):
        w = world(force=True)
        msg = {"noclient": "Blizzard's API needs a client of your own · develop.battle.net", "notinapi": "Forever is not in Blizzard's API yet",
               "offline": "Blizzard did not answer"}.get(w.get("why", ""), "")
        say(msg or ("Token %s · %s" % (money(w["token"]) if w.get("token") else "?", ", ".join("%s %s" % (r["name"], r["status"].lower()) for r in w["realms"]) or "no realm known yet")))
    elif verb == "apps": subprocess.Popen(["setsid", "-f", FRONT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); say("k4:close")
    elif verb == "open-screens": subprocess.Popen(["xdg-open", os.path.join(flavor_dir(), "Screenshots")], start_new_session=True); say("k4:noreload")
    elif verb == "open-logs": subprocess.Popen(["xdg-open", os.path.join(flavor_dir(), "Logs")], start_new_session=True); say("k4:noreload")
    elif verb == "key":   # key wago|curseforge (the key typed, $K4_INPUT)
        if a[0] not in ("wago", "curseforge") or not os.environ.get("K4_INPUT", "").strip(): say("Paste the key first"); say("k4:tone yellow"); return
        subprocess.run(["k4-secret", "store", "token", a[0]], input=os.environ["K4_INPUT"].strip(), text=True)
        say("%s key saved in the keyring" % ("Wago" if a[0] == "wago" else "CurseForge")); say("k4:tone green")
    elif verb == "calendar": subprocess.Popen(["xdg-open", "https://calendar.google.com/"], start_new_session=True); say("k4:noreload")
    elif verb == "client":   # client ID (the secret from $K4_INPUT, into the keyring)
        if not a[0] or not os.environ.get("K4_INPUT"): say("client ID, with the secret typed (K4_INPUT)"); return
        jsave(os.path.join(HOME, ".config/k4/blizzard-client.json"), {"client_id": a[0]})
        subprocess.run(["k4-secret", "store", "token", "blizzard"], input=os.environ["K4_INPUT"], text=True)
        say("Blizzard client saved"); say("k4:tone green")
    else: say("unknown: " + verb)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "data"
    rest = argv[2:]
    if cmd == "data": data()
    elif cmd == "chars":
        for c in chars(): print(json.dumps(c, ensure_ascii=False))
    elif cmd == "watch": watch()
    elif cmd == "tick": tick()
    elif cmd == "reset": r = next_reset(); print(span(r - now()) if "--short" in rest else r)
    elif cmd == "play": play()
    elif cmd == "addons":
        for x in addons(): print("\t".join([x["folder"], field(x["title"]), field(x["version"]), field(x["author"]), x["source"], x["update"]]))
    elif cmd == "act": act(rest[0] if rest else "", rest[1:])
    elif cmd == "note": note(rest[0], rest[1] if len(rest) > 1 else "")
    elif cmd == "bar": bar()
    elif cmd == "find": find()
    elif cmd == "info": info()
    else: print(__doc__, file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
