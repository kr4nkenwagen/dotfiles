#!/usr/bin/env python3
"""k4's Jellyfin (k4-jellyfin is its front): your server in the YouTube window (k4 --jellyfin): a home
page (continue watching, next up, recently added), a search over movies, shows and episodes, a show's
episodes; it plays in the corner player k4-youtube uses (pip.sh), and tells the server where you are,
so resuming and "watched" follow you to the TV and phone.

  jellyfin.py data                 the window's lines (S T Q C V F W N P H); the player's state comes in
                                   $K4_JF_PLAYER (mpv's answers) and $K4_JF_HIDDEN from k4-jellyfin
  jellyfin.py home [--bg] | search QUERY | channel ID [NAME] | back | clear | forget
  jellyfin.py url ID [resume]      what to play: URL<TAB>start seconds<TAB>title
  jellyfin.py report start|progress|stop ID POS PAUSED   (the player: youtube-mpv.lua)
  jellyfin.py setup-key | setup-url | user ID | status | page | find | library [--bg] | browser ID

The server and your user: ~/.config/k4/jellyfin.json; the API key (Dashboard › API Keys) in the
keyring: k4-secret token jellyfin. Tests: K4_JELLYFIN_FAKE=DIR answers from DIR/<path>.json (/ as _),
logs what is sent to DIR/log; the key is $K4_JELLYFIN_KEY there.
"""
import base64, json, os, re, secrets, shlex, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
FAKE = os.environ.get("K4_JELLYFIN_FAKE")
CONF = os.environ.get("K4_JELLYFIN_CONF") or (os.path.join(FAKE, "jellyfin.json") if FAKE else os.path.join(HOME, ".config/k4/jellyfin.json"))
C = os.environ.get("K4_JELLYFIN_CACHE") or (os.path.join(FAKE, "cache") if FAKE else os.path.join(HOME, ".cache/k4/jellyfin"))
ST = os.environ.get("K4_JELLYFIN_STATE") or (os.path.join(FAKE, "state") if FAKE else os.path.join(HOME, ".local/state/k4/jellyfin"))
FRONT = os.environ.get("K4_JELLYFIN_FRONT") or shutil.which("k4-jellyfin") or "k4-jellyfin"
DEFAULT_URL = "http://jellyfin.kr4nk.net"
TYPES = "Movie,Series,Episode,Video"
FIELDS = "ProductionYear,RunTimeTicks,UserData,SeriesName,ParentIndexNumber,IndexNumber,Overview,ImageTags,BackdropImageTags,SeriesId,ChildCount"
HOME_TTL = 300
for d in (C, os.path.join(C, "thumbs"), ST): os.makedirs(d, exist_ok=True)


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def flag(s): return field(s).replace(";", ",")


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


# ---------- the server ----------

def conf():
    c = jload(CONF, {})
    c.setdefault("url", DEFAULT_URL)
    if not c.get("device"): c["device"] = secrets.token_hex(8); save_conf(c)
    return c


def save_conf(c):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    jsave(CONF, c)


def key():
    if FAKE: return os.environ.get("K4_JELLYFIN_KEY", "")
    try:
        r = subprocess.run(["k4-secret", "lookup", "token", "jellyfin"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired): return ""


class Refused(Exception): pass
class Offline(Exception): pass


def api(path, query=None, method="GET", body=None, k=None, url=None):
    c = conf()
    k = k if k is not None else key()
    if FAKE:
        if body is not None or method != "GET":
            with open(os.path.join(FAKE, "log"), "a") as f: f.write("%s %s %s\n" % (method, path, json.dumps(body, sort_keys=True) if body else ""))
            return {}
        if os.path.exists(os.path.join(FAKE, "offline")): raise Offline("offline")
        if k != os.environ.get("K4_JELLYFIN_KEY", "x"): raise Refused("the API key was refused")
        p = os.path.join(FAKE, path.strip("/").replace("/", "_") + ".json")
        if query and query.get("searchTerm"): p = os.path.join(FAKE, "search.json")
        return jload(p, {"Items": []})
    q = ("?" + urllib.parse.urlencode(query)) if query else ""
    req = urllib.request.Request((url or c["url"]).rstrip("/") + path + q, data=json.dumps(body).encode() if body is not None else None, method=method)
    req.add_header("Authorization", 'MediaBrowser Token="%s", Client="k4", Device="k4", DeviceId="%s", Version="1.0"' % (k, c["device"]))
    req.add_header("Accept", "application/json")
    if body is not None: req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            out = r.read()
            return json.loads(out) if out else {}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): raise Refused("the API key was refused")
        raise Offline("the server said %d" % e.code)
    except (urllib.error.URLError, OSError, ValueError) as e: raise Offline(str(getattr(e, "reason", e)))


def status():
    """nokey (no key yet), nouser (a key, the user not picked), ok"""
    if not key(): return "nokey"
    if not conf().get("user_id"): return "nouser"
    return "ok"


def uid(): return conf().get("user_id", "")


# ---------- items as the window's tiles ----------

def tile(it, in_show=False):
    """(id, title, sub, secs, pos, kind) of a Jellyfin item."""
    secs = int((it.get("RunTimeTicks") or 0) / 1e7)
    pos = int(((it.get("UserData") or {}).get("PlaybackPositionTicks") or 0) / 1e7)
    t = it.get("Type")
    name = it.get("Name") or ""
    if t == "Episode":
        se = "S%s · E%s" % (it.get("ParentIndexNumber", "?"), it.get("IndexNumber", "?"))
        if in_show: return it["Id"], name, se, secs, pos, t
        return it["Id"], "%s · %s" % (it.get("SeriesName") or "", name), se, secs, pos, t
    if t == "Series":
        n = (it.get("UserData") or {}).get("UnplayedItemCount")
        return it["Id"], name, " · ".join(x for x in (str(it.get("ProductionYear") or ""), "%d unwatched" % n if n else "") if x), 0, 0, t
    return it["Id"], name, " · ".join(x for x in (str(it.get("ProductionYear") or ""), "Movie" if t == "Movie" else t or "") if x), secs, pos, t


def remember(items):
    """meta.tsv: what k4 knows of each item (the queue and history show it): id title sub secs"""
    m = jload(os.path.join(C, "meta.json"), {})
    for it in items:
        i, title, sub, secs, _, kind = tile(it)
        m[i] = [title, sub, secs, kind]
    jsave(os.path.join(C, "meta.json"), m)


def thumb(it_or_id, kind=None):
    """The tile's picture, once fetched (16:9: an episode's own, a movie's backdrop, a show's poster);
    "" meanwhile (it is fetched in the background)."""
    i = it_or_id if isinstance(it_or_id, str) else it_or_id["Id"]
    f = os.path.join(C, "thumbs", i + ".jpg")
    if os.path.exists(f) and os.path.getsize(f) > 0: return f
    return ""


def want_thumbs(items):
    """Fetch the pictures not here yet, in the background (one process for them all)."""
    need = []
    for it in items:
        f = os.path.join(C, "thumbs", it["Id"] + ".jpg")
        if os.path.exists(f) or os.path.exists(f + ".part"): continue
        t = it.get("Type")
        kind = "Backdrop" if t == "Movie" and it.get("BackdropImageTags") else "Primary"
        if t == "Episode" and not (it.get("ImageTags") or {}).get("Primary") and it.get("SeriesId"): need.append((it["Id"], it["SeriesId"], "Backdrop"))
        else: need.append((it["Id"], it["Id"], kind))
    if not need or FAKE: return
    for i, _, _ in need: open(os.path.join(C, "thumbs", i + ".jpg.part"), "w").close()
    subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "thumbs", json.dumps(need)], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fetch_thumbs(need):
    c, k = conf(), key()
    for i, src, kind in need:
        f = os.path.join(C, "thumbs", i + ".jpg")
        url = "%s/Items/%s/Images/%s?maxWidth=480&format=Jpg&quality=85&api_key=%s" % (c["url"].rstrip("/"), src, kind, k)
        try:
            with urllib.request.urlopen(url, timeout=10) as r, open(f + ".part", "wb") as out: shutil.copyfileobj(r, out)
            os.replace(f + ".part", f)
        except (OSError, urllib.error.URLError):
            try: os.remove(f + ".part")
            except OSError: pass


# ---------- the home page, the search, a show ----------

def home_fetch():
    u = uid()
    out = {"at": time.time(), "state": "ok", "why": "", "resume": [], "nextup": [], "latest": []}
    try:
        out["resume"] = api("/UserItems/Resume", {"userId": u, "limit": 12, "fields": FIELDS, "mediaTypes": "Video"}).get("Items", [])
        out["nextup"] = api("/Shows/NextUp", {"userId": u, "limit": 12, "fields": FIELDS}).get("Items", [])
        latest = api("/Items/Latest", {"userId": u, "limit": 16, "fields": FIELDS, "includeItemTypes": "Movie,Episode", "groupItems": "false"})
        out["latest"] = latest if isinstance(latest, list) else latest.get("Items", [])
    except Refused as e: out.update(state="signedout", why="Jellyfin refused the API key · Apps › Jellyfin sets a new one")
    except Offline as e: out.update(state="error", why="can’t reach %s (%s)" % (conf()["url"], e))
    old = jload(os.path.join(C, "home.json"), {})
    if out["state"] != "ok" and old.get("state") == "ok":   # keep what was there, say why it is old
        old.update(state="ok", why=out["why"], at=old.get("at", 0)); out = old
    jsave(os.path.join(C, "home.json"), out)
    remember(out["resume"] + out["nextup"] + out["latest"])
    want_thumbs(out["resume"] + out["nextup"] + out["latest"])
    return out


def home_maybe(force=False):
    """In the background when older than 5 minutes (force: now), once at a time."""
    lock = os.path.join(C, "home.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 60: return
    h = jload(os.path.join(C, "home.json"), {})
    if not force and time.time() - h.get("at", 0) < HOME_TTL: return
    if FAKE: home_fetch(); return
    open(lock, "w").close()
    subprocess.Popen(["sh", "-c", '"$0" -I "$1" home; rm -f "$2"', sys.executable, os.path.abspath(__file__), lock], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def search(q):
    t0 = time.time()
    with open(os.path.join(C, "query"), "w") as f: f.write(q)
    for n in ("view", "results.search.json"):
        try: os.remove(os.path.join(C, n))
        except OSError: pass
    try:
        items = api("/Items", {"userId": uid(), "searchTerm": q, "recursive": "true", "includeItemTypes": TYPES, "fields": FIELDS, "limit": 40}).get("Items", [])
    except (Refused, Offline) as e:
        with open(os.path.join(C, "error"), "w") as f: f.write("%s\n%s\n" % ("offline" if isinstance(e, Offline) else "error", e))
        jsave(os.path.join(C, "results.json"), [])
        say("Search failed · %s" % e); say("k4:tone yellow"); return
    try: os.remove(os.path.join(C, "error"))
    except OSError: pass
    items.sort(key=lambda it: {"Series": 0, "Movie": 1}.get(it.get("Type"), 2))   # shows first (they open), then movies, episodes
    jsave(os.path.join(C, "results.json"), items)
    with open(os.path.join(C, "took"), "w") as f: f.write("%.1f" % (time.time() - t0))
    remember(items); want_thumbs(items)
    say("%d found · %.1f s" % (len(items), time.time() - t0) if items else "Nothing for “%s”" % q)


def channel(sid, name=""):
    """A show's episodes in place of the search (back: the search again)."""
    try:
        eps = api("/Shows/%s/Episodes" % sid, {"userId": uid(), "fields": FIELDS}).get("Items", [])
    except (Refused, Offline) as e: say("Could not open the show · %s" % e); say("k4:tone yellow"); return
    rs = os.path.join(C, "results.search.json")
    if not os.path.exists(rs): shutil.copy(os.path.join(C, "results.json"), rs) if os.path.exists(os.path.join(C, "results.json")) else jsave(rs, [])
    if not name: name = (jload(os.path.join(C, "meta.json"), {}).get(sid) or [""])[0]
    jsave(os.path.join(C, "results.json"), eps)
    with open(os.path.join(C, "view"), "w") as f: f.write("channel\t%s\t%s\n" % (sid, name))
    remember(eps); want_thumbs(eps)
    say("%s · %d episodes · Esc goes back" % (name, len(eps)))


def clear():
    for n in ("query", "results.json", "error", "took", "view", "results.search.json", "from-launcher"):
        try: os.remove(os.path.join(C, n))
        except OSError: pass


# ---------- what the window shows ----------

def player():
    """What k4-jellyfin read from the player: (playlist, paused, pos, dur, title), or None."""
    raw = os.environ.get("K4_JF_PLAYER", "")
    if not raw: return None
    got = {}
    for line in raw.splitlines():
        try: j = json.loads(line)
        except ValueError: continue
        got[j.get("request_id")] = j.get("data")
    return got.get(1) or [], bool(got.get(2)), got.get(3) or 0, got.get(4) or 0, got.get(5) or ""


def item_of(filename):
    m = re.search(r"/Videos/([0-9a-fA-F-]{32,36})/stream", filename or "")
    return m.group(1).replace("-", "") if m else ""


def history(n=40):
    """Watched here, newest first, each once: (time, id, pos, dur)."""
    seen, out = set(), []
    try: lines = open(os.path.join(ST, "history.log")).read().splitlines()
    except OSError: return []
    for line in reversed(lines):
        f = line.split("\t")
        if len(f) < 4 or f[1] in seen: continue
        seen.add(f[1]); out.append((int(float(f[0])), f[1], int(float(f[2])), int(float(f[3]))))
        if len(out) >= n: break
    return out


def data():
    st = status()
    c = conf()
    srv = re.sub(r"^https?://", "", c["url"]).rstrip("/")
    err = open(os.path.join(C, "error")).read().split("\n", 2) if os.path.exists(os.path.join(C, "error")) else None
    state, note = ("ok", "") if not err else (err[0], err[1] if len(err) > 1 else "")
    print("S\t%s\t%s\t\t" % (state, field(note)))
    print("T\tJellyfin\tSearch Jellyfin…\tFROM YOUR SERVER · %s\t%s\tSHOW\tepisodes\tmovies, shows and episodes on %s" % (field(srv).upper(), field(srv), field(srv)))
    q = open(os.path.join(C, "query")).read() if os.path.exists(os.path.join(C, "query")) else ""
    view = (open(os.path.join(C, "view")).read().strip("\n").split("\t") + ["", "", ""])[:3] if os.path.exists(os.path.join(C, "view")) else ["search", "", ""]
    results = jload(os.path.join(C, "results.json"), [])
    meta = jload(os.path.join(C, "meta.json"), {})
    if q:
        took = open(os.path.join(C, "took")).read() if os.path.exists(os.path.join(C, "took")) else ""
        print("Q\t%s\t%d\t%s\t%s\t%s" % (field(q), len(results), took, view[0] or "search", field(view[2])))
        for it in results:
            i, title, sub, secs, pos, kind = tile(it, in_show=view[0] == "channel")
            if kind == "Series": print("C\t%s\t%s\t%s\t0\t%s" % (i, field(title), field(sub), thumb(it)))
            else: print("V\t%s\t%s\t%s\t%d\t0\t%s" % (i, field(title), field(sub), secs, thumb(it)))
    elif st == "ok" and state == "ok":
        h = jload(os.path.join(C, "home.json"), None)
        if h is None: home_maybe(); print("F\tloading\t\t")
        else:
            home_maybe()
            print("F\t%s\t\t%s" % (h.get("state", "ok"), field(h.get("why"))))
            shown = set()
            for sec in ("resume", "nextup", "latest"):
                for it in h.get(sec, []):
                    if it["Id"] in shown: continue
                    shown.add(it["Id"])
                    i, title, sub, secs, pos, _ = tile(it)
                    print("W\t%s\t%s\t%s\t%d\t0\t%s\t%s\t%d" % (i, field(title), field(sub), secs, thumb(it), sec, pos if sec == "resume" else 0))
    p = player()
    if p:
        pl, paused, pos, dur, mtitle = p
        cur = ""
        for n, e in enumerate(pl):
            i = item_of(e.get("filename", ""))
            m = meta.get(i) or [e.get("title") or (mtitle if e.get("current") else e.get("filename", "")), "", 0]
            if e.get("current"): cur = i or "url"
            print("P\t%d\t%s\t%s\t%s\t%d\t%d\t%s" % (n, i or "url%d" % n, field(m[0]), field(m[1]), int(m[2] or 0), 1 if e.get("current") else 0, thumb(i) if i else ""))
        if cur:
            m = meta.get(cur) or [mtitle, "", 0]
            print("N\t%s\t%s\t%s\t%s\t%d\t%d\t%s\t%s" % (cur, field(m[0] or mtitle), field(m[1]), "pause" if paused else "play", int(pos or 0), int(dur or 0),
                                                      os.environ.get("K4_JF_HIDDEN") or "shown", thumb(cur) if cur != "url" else ""))
    for ts, i, pos, dur in history():
        m = meta.get(i) or [i, "", dur]
        print("H\t%d\t%s\t%s\t%s\t%d\t%s\t%d" % (ts, i, field(m[0]), field(m[1]), dur or int(m[2] or 0), thumb(i), pos))
    print("R\t%s act\nL\t%s data" % (FRONT, FRONT))


# ---------- playing, and telling the server ----------

def url(i, resume=False):
    c, k = conf(), key()
    meta = jload(os.path.join(C, "meta.json"), {})
    at = 0
    if resume:
        try:
            it = api("/Items/%s" % i, {"userId": uid(), "fields": FIELDS})
            at = int(((it.get("UserData") or {}).get("PlaybackPositionTicks") or 0) / 1e7)
            remember([it])
            meta = jload(os.path.join(C, "meta.json"), {})
        except (Refused, Offline): pass
    title = (meta.get(i) or [""])[0]
    print("%s/Videos/%s/stream?static=true&api_key=%s\t%s\t%s" % (c["url"].rstrip("/"), i, k, at if at > 10 else "", field(title)))


def report(what, i, pos, paused):
    """The player's word to the server (start, every 15 s, pause, stop) and k4's own history."""
    ticks = int(float(pos or 0) * 1e7)
    body = {"ItemId": i, "PositionTicks": ticks, "IsPaused": paused == "1", "CanSeek": True, "PlayMethod": "DirectStream"}
    path = {"start": "/Sessions/Playing", "progress": "/Sessions/Playing/Progress", "stop": "/Sessions/Playing/Stopped"}[what]
    if what == "progress": body["EventName"] = "pause" if paused == "1" else "timeupdate"
    try: api(path, method="POST", body=body)
    except (Refused, Offline): pass
    dur = (jload(os.path.join(C, "meta.json"), {}).get(i) or ["", "", 0])[2]
    with open(os.path.join(ST, "history.log"), "a") as f: f.write("%d\t%s\t%d\t%d\n" % (time.time(), i, float(pos or 0), int(dur or 0)))


# ---------- the Apps page, the launcher ----------

def setup_rows(out, rid, me):
    st = status()
    c = conf()
    out.append("D\tyour Jellyfin server · plays in the corner player\tnot set up\tSearch Jellyfin…")
    out.append("Y\t↑↓\tStep\t↵\tDo it\t⌃V\tPaste\t⌫\tBack")
    out.append("N\tConnect Jellyfin\tk4 searches your server and plays in the corner player, and tells Jellyfin where you stopped. It needs an API key: Dashboard › API Keys › +.\taccent\t")
    out.append("A\t%s\tServer · %s\t↵ changes it\t\tstay;mark=1;markc=accent;input=Jellyfin server|%s" % (rid("%s setup-url" % me), field(c["url"]), DEFAULT_URL))
    out.append("A\t%s\tPaste the API key\tDashboard › API Keys\t\tstay;mark=2;markc=%s;input=Jellyfin API key|Dashboard › API Keys · kept in the keyring|password" % (rid("%s setup-key" % me), "accent" if st == "nokey" else "green"))
    if st == "nouser":
        try: users = api("/Users")
        except (Refused, Offline) as e: out.append("E\tCan’t list the users · %s" % field(e)); return
        out.append("H\tWho are you?\t%d" % len(users))
        for u in users: out.append("A\t%s\t%s\tpick · its progress and Continue watching\t\tstay;mark=3;markc=accent" % (rid("%s user %s" % (me, u["Id"])), field(u.get("Name"))))


def page():
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    rid = lambda act: b64("k4-jellyfin run " + b64(act))
    me = shlex.quote(FRONT)
    out = []
    if status() != "ok":
        setup_rows(out, rid, me); print("\n".join(out)); return
    h = jload(os.path.join(C, "home.json"), {})
    home_maybe()
    c = conf()
    out.append("D\t%s · as %s · plays in the corner player\t%d to continue\tSearch Jellyfin…" % (field(re.sub(r"^https?://", "", c["url"])), field(c.get("user", "you")), len(h.get("resume", []))))
    out.append("Y\t↑↓\tMove\t↵\tPlay\t⌫\tBack")
    out.append("A\t%s\tOpen Jellyfin…\tthe window · Super+Alt+J\t\tmark=›;markc=accent" % rid("bg %s window" % me))
    p = player()
    if p and os.environ.get("K4_JF_NOW"):
        out.append("A\t%s\t%s PiP\tSuper+Alt+Y · audio keeps playing\t\tstay;mark=▭;markc=accent" % (rid("%s act pip" % me), "Show" if os.environ.get("K4_JF_HIDDEN") == "hidden" else "Hide"))
    for sec, head in (("resume", "Continue watching"), ("nextup", "Next up")):
        items = h.get(sec, [])[:5]
        if not items: continue
        out.append("H\t%s\t%d" % (head, len(h.get(sec, []))))
        for it in items:
            i, title, sub, secs, pos, _ = tile(it)
            pc = " · %d%%" % (pos * 100 // secs) if secs and pos else ""
            th = thumb(it)
            out.append("A\t%s\t%s\t%s%s\t\tsub=  %s%s" % (rid("%s act play %s resume" % (me, i)), field(title), "%d min" % (secs // 60) if secs else "", pc, flag(sub), ";thumb=" + th if th else ""))
    if h.get("why"): out.append("E\t%s" % field(h["why"]))
    print("\n".join(out))


def library(bg=False):
    """Movies and shows, for the launcher's search: lib.json, again after 6 hours (in the background)."""
    p = os.path.join(C, "lib.json")
    if bg:
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 21600: return
        lock = os.path.join(C, "lib.lock")
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 300: return
        open(lock, "w").close()
        subprocess.Popen(["sh", "-c", '"$0" -I "$1" library; rm -f "$2"', sys.executable, os.path.abspath(__file__), lock], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    try: items = api("/Items", {"userId": uid(), "recursive": "true", "includeItemTypes": "Movie,Series", "fields": "ProductionYear,RunTimeTicks", "limit": 5000}).get("Items", [])
    except (Refused, Offline): return
    jsave(p, [[it["Id"], it.get("Name", ""), it.get("Type", ""), it.get("ProductionYear") or "", int((it.get("RunTimeTicks") or 0) / 1e7)] for it in items])


def find_rows():
    if status() != "ok": return
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    for i, name, kind, year, secs in jload(os.path.join(C, "lib.json"), []):
        if kind == "Series": act, meta = "bg %s window channel %s %s" % (me, i, shlex.quote(name)), "show%s · ↵ its episodes" % (" · %s" % year if year else "")
        else: act, meta = "%s act play %s resume" % (me, i), "movie%s%s" % (" · %s" % year if year else "", " · %d min" % (secs // 60) if secs else "")
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=88;tag=Jellyfin;icon=󰼁;find=%s" % (b64("k4-jellyfin run " + b64(act)), field(name), field(meta), flag("%s %s" % (name, year))))
    library(bg=True)


def main(argv):
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if cmd == "data": data()
    elif cmd == "home": h = home_fetch(); say("Home · %d to continue · %d next up · %d new" % (len(h.get("resume", [])), len(h.get("nextup", [])), len(h.get("latest", []))) if h["state"] == "ok" else h["why"])
    elif cmd == "home-maybe": home_maybe("--force" in rest)
    elif cmd == "search": search(" ".join(rest))
    elif cmd == "channel" and rest: channel(rest[0], " ".join(rest[1:]))
    elif cmd == "back":
        if os.path.exists(os.path.join(C, "from-launcher")): clear(); say("Your home page"); return
        rs = os.path.join(C, "results.search.json")
        if os.path.exists(rs): os.replace(rs, os.path.join(C, "results.json"))
        try: os.remove(os.path.join(C, "view"))
        except OSError: pass
        say("Back to “%s”" % (open(os.path.join(C, "query")).read() if os.path.exists(os.path.join(C, "query")) else ""))
    elif cmd == "clear": clear(); say("Your home page")
    elif cmd == "forget": open(os.path.join(ST, "history.log"), "w").close(); say("History cleared (Jellyfin keeps its own)")
    elif cmd == "url" and rest: url(rest[0], len(rest) > 1 and rest[1] == "resume")
    elif cmd == "report" and len(rest) >= 3: report(rest[0], rest[1], rest[2], rest[3] if len(rest) > 3 else "0")
    elif cmd == "thumbs" and rest: fetch_thumbs(json.loads(rest[0]))
    elif cmd == "browser" and rest:
        c = conf()
        u = "%s/web/#/details?id=%s" % (c["url"].rstrip("/"), rest[0])
        if not FAKE: subprocess.Popen(["xdg-open", u], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        say("Opened in Jellyfin’s web page")
    elif cmd == "setup-url":
        u = (os.environ.get("K4_INPUT") or (rest[0] if rest else "")).strip().rstrip("/")
        if not u: return say("Type the server’s address")
        if "://" not in u: u = "http://" + u
        try: info = api("/System/Info/Public", k="", url=u)
        except (Refused, Offline) as e: say("No Jellyfin at %s · %s" % (u, e)); say("k4:tone yellow"); return
        c = conf(); c["url"] = u; c.pop("user_id", None); save_conf(c)
        say("%s · Jellyfin %s" % (info.get("ServerName", u), info.get("Version", "")))
    elif cmd == "setup-key":
        k = (os.environ.get("K4_INPUT") or "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{32}", k): say("That isn’t an API key · 32 letters and digits (Dashboard › API Keys)"); say("k4:tone yellow"); return
        try: users = api("/Users", k=k)
        except Refused: say("Jellyfin refused that key"); say("k4:tone red"); return
        except Offline as e: say("Can’t reach the server · %s" % e); say("k4:tone yellow"); return
        if not FAKE: subprocess.run(["k4-secret", "store", "token", "jellyfin"], input=k, text=True, capture_output=True, timeout=20)
        c = conf()
        if len(users) == 1: c["user_id"], c["user"] = users[0]["Id"], users[0].get("Name", "")
        save_conf(c)
        say("Key saved%s" % (" · signed in as %s" % c["user"] if c.get("user_id") else " · now pick who you are"))
    elif cmd == "user" and rest:
        try: u = next(x for x in api("/Users") if x["Id"] == rest[0])
        except (StopIteration, Refused, Offline): return say("No such user")
        c = conf(); c["user_id"], c["user"] = u["Id"], u.get("Name", ""); save_conf(c)
        home_maybe(True)
        say("Signed in as %s" % c["user"])
    elif cmd == "status": say(status())
    elif cmd == "page": page()
    elif cmd == "find": find_rows()
    elif cmd == "library": library()
    else: say(__doc__.strip()); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
