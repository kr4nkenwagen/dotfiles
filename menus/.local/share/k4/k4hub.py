#!/usr/bin/env python3
"""k4hub.py: the Pi's API for the k4 phone launcher (k4-hub is its front). HTTPS on the home address
(the phone reaches it on home Wi-Fi, or away through the router's WireGuard), a token per paired
device, a self-signed certificate the phone pins (its SHA-256 is in the pairing code). It serves what
the k4 scripts on the Pi keep: the calendar (k4-cal's cache), todos (todo.py), Pi-hole (pihole.py),
parcels, what the event finder added; and does the few things the launcher's cards do.

  k4hub.py serve [PORT]            the service (k4-hub.service)
  k4hub.py pair NAME [HOST]        a new device: prints its pairing code (and the token's hash is kept)
  k4hub.py unpair NAME | devices

API (Authorization: Bearer TOKEN; JSON):
  GET  /api/home                   the launcher's cards: agenda (today, tomorrow), todos, pihole, parcels,
                                   events (added this week), finder
  GET  /api/calendar?days=N        events from today on
  GET  /api/todos                  open todos (and the done ones of this week)
  POST /api/todo/done {id} · /api/todo/undone {id} · /api/todo/add {text}
  POST /api/pihole/pause {seconds} · /api/pihole/resume
  GET  /api/search?q=TEXT          todos, calendar, parcels and actions that match
  GET  /api/pihole                 status, unbound, the last 100 queries (the KAndroid Pi-hole page)
  POST /api/pihole/allow {domain} · /api/pihole/block {domain} · /api/pihole/restart-ftl · /api/pihole/restart-unbound
  GET  /api/agenda                 the week's events, todos, what the event finder added (with its ids)
  POST /api/events/remove {id}     undo one the finder added (out of the calendar again)
  GET  /api/theme[?wait=KEY]       the desktop's theme: its colours, the wallpaper and the theme's backgrounds (ids);
                                   with the key the phone has, held until it changes (up to 25 s)
  GET  /api/cards?since=SEQ        k4's cards after SEQ (Pi-hole down, a parcel ready, events added): app, title,
                                   body, urgency, tag, actions; the wait below says cards_seq and ends on a new one
  GET  /api/releases               upcoming movies, TV, games, books (releases.py json) and what you follow
  GET  /api/releases/poster/NAME   a title's poster (the name the list gives)
  POST /api/releases/follow {kind,id} · /api/releases/cal {kind,id}   follow it · its date into the calendar
  GET  /api/router                 the OpenWrt router (k4-router json): WAN, radios, clients (the phone asking is YOU)
  POST /api/router/do {verb,args}  radio NAME on|off · retry · wanip · reboot
  GET  /api/messenger/rooms         Messenger (k4-messengerd on this Pi): the bridge's state, the chats
  GET  /api/messenger/room/ID[?limit=N]   a chat's last N messages (40); marks it read
  GET  /api/messenger/media/EVENT[?thumb=1]   a photo's or video's preview, or the whole file
  GET  /api/messenger/people?q=NAME  people on Messenger (to start a chat)
  GET  /api/messenger/wait?since=SEQ new messages and reads after SEQ, held until there are some (up to 25 s)
  POST /api/messenger/send {room, text} · /api/messenger/read {room} · /api/messenger/start {person, name}
  POST /api/messenger/send-image?room=ID&w=W&h=H   a JPEG as the body (15 MB at most)
  GET  /api/bg/ID.jpg              one of those backgrounds, phone-sized (the desktop sends them: k4-pi pull)

Paths (tests: K4_HUB_DIR holds config, tokens and the certificate; the data paths follow the scripts'
own K4_* variables).
"""
import base64, datetime as dt, hashlib, http.server, json, os, re, secrets, socketserver, ssl, subprocess, sys, threading, time, urllib.parse

HOME = os.path.expanduser("~")
SHARE = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("K4_HUB_DIR") or os.path.join(HOME, ".config/k4/hub")
CAL = os.environ.get("K4_CAL_DIR") or os.path.join(HOME, ".cache/k4/cal")
PARCELS = os.environ.get("K4_PARCELS_STATE_FILE") or os.path.join(HOME, ".local/state/k4/parcels.json")
EVENTS = os.environ.get("K4_EVENTS_STATE") or os.path.join(HOME, ".local/state/k4/events")
PORT = 8740
THEME = os.environ.get("K4_HUB_THEME") or os.path.join(HOME, ".cache/k4/hub/theme")
sys.path.insert(0, SHARE)


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd = os.open(p + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(data, f)
    os.replace(p + ".tmp", p)


# ---------- the certificate and the devices ----------

CERT, KEY, TOKENS = os.path.join(D, "cert.pem"), os.path.join(D, "key.pem"), os.path.join(D, "tokens.json")


def ensure_cert():
    if os.path.exists(CERT) and os.path.exists(KEY): return
    os.makedirs(D, exist_ok=True)
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-days", "3650",
                    "-subj", "/CN=k4-hub", "-keyout", KEY, "-out", CERT], check=True, capture_output=True)
    os.chmod(KEY, 0o600)


def cert_fp():
    der = ssl.PEM_cert_to_DER_cert(open(CERT).read())
    return hashlib.sha256(der).hexdigest()


def pair(name, host):
    ensure_cert()
    tok = secrets.token_urlsafe(32)
    t = jload(TOKENS, {})
    t[name] = {"sha256": hashlib.sha256(tok.encode()).hexdigest(), "at": int(time.time())}
    jsave(TOKENS, t)
    code = {"url": "https://%s:%d" % (host, PORT), "token": tok, "fp": cert_fp(), "name": name}
    return "k4hub:" + base64.urlsafe_b64encode(json.dumps(code, separators=(",", ":")).encode()).decode()


def device_of(header):
    if not header or not header.startswith("Bearer "): return None
    h = hashlib.sha256(header[7:].strip().encode()).hexdigest()
    for name, v in jload(TOKENS, {}).items():
        if secrets.compare_digest(v.get("sha256", ""), h): return name
    return None


# ---------- what the cards show ----------

def today(): return dt.date.today()


def calendar(days=14):
    t = today()
    out = []
    for e in jload(os.path.join(CAL, "events.json"), []):
        try: d = dt.date.fromisoformat(e.get("date", ""))
        except ValueError: continue
        if t <= d <= t + dt.timedelta(days=days):
            out.append({"id": e.get("id", ""), "date": e["date"], "start": e.get("s") or "", "end": e.get("e") or "", "title": e.get("title", ""),
                        "place": e.get("loc") or "", "meet": e.get("meet") or "", "calendar": e.get("cal", "")})
    return sorted(out, key=lambda x: (x["date"], x["start"] or "00:00"))


def todos(done_too=False):
    import todo
    c = todo.cache()
    mine = todo.mine()
    out = []
    for x in todo.order([t for t in c["tasks"] if t["status"] != "completed"]):
        k = mine.get(x["id"])
        out.append({"id": x["id"], "title": x["title"], "due": x["due"], "notes": x["notes"].split("\n")[0], "list": x["list"], "k4": bool(k),
                    "from": (k or {}).get("who") or "", "sub": bool(x["parent"])})
    if done_too:
        week = time.time() - 7 * 86400
        for x in c["tasks"]:
            if x["status"] == "completed" and x["completed"] > week:
                out.append({"id": x["id"], "title": x["title"], "due": x["due"], "done": True, "k4": x["id"] in mine})
    return out


def pihole():
    try:
        import pihole as P
        st = P.state()
        if not st: return {"state": "none"}
        on, left = P.blocking(st)
        q = (st.get("summary") or {}).get("queries") or {}
        u = st.get("unbound") or {}
        return {"state": st.get("state", "ok"), "blocking": bool(on), "left": left or 0, "total": q.get("total") or 0, "blocked": q.get("blocked") or 0,
                "percent": q.get("percent_blocked") or 0, "unbound": "ok" if u.get("ok") else ("not watched" if u.get("nossh") or not u else "failing"), "at": st.get("at", 0)}
    except Exception as e: return {"state": "error", "why": str(e)[:120]}


def parcels():
    s = jload(PARCELS, {})
    out = []
    for k, p in (s.get("parcels") or {}).items():
        if p.get("archived") or p.get("status") == "delivered": continue
        out.append({"key": k, "status": p.get("status", ""), "shop": p.get("shop") or p.get("carrier", "").title(), "carrier": p.get("carrier", ""),
                    "code": p.get("code") or "", "point": p.get("point") or "", "window": p.get("window") or "", "last": p.get("last") or 0})
    order = {"ready": 0, "out": 1, "problem": 2, "transit": 3, "registered": 4}
    return sorted(out, key=lambda p: order.get(p["status"], 9))


def events_added():
    s = jload(os.path.join(EVENTS, "suggestions.json"), {"items": [], "runs": []})
    week = time.time() - 7 * 86400
    added = [{"title": g["title"], "date": g["date"], "start": g.get("start") or "", "from": g.get("who") or g.get("source", ""), "state": g["state"]}
             for g in s.get("items", []) if g.get("state") in ("added", "cancelled") and max(g.get("added", 0), g.get("cancelled", 0)) > week]
    runs = s.get("runs") or []
    last = runs[-1] if runs else {}
    return added[-10:][::-1], {"at": last.get("at", 0), "by": last.get("asked") or ""}


_cache = {}
def cached(key, ttl, fn):
    """A slow answer (the bus, the weather), kept TTL seconds."""
    v = _cache.get(key)
    if v and time.time() - v[0] < ttl: return v[1]
    try: r = fn()
    except Exception: r = v[1] if v else None
    _cache[key] = (time.time(), r)
    return r


def bus():
    """The next departures from the stop k4-bus keeps (k4-bus data: S and D lines)."""
    def get():
        out = subprocess.run(["k4-bus", "data"], capture_output=True, text=True, timeout=20).stdout
        stop, deps = "", []
        for line in out.splitlines():
            f = line.split("\t")
            if f[0] == "S" and len(f) > 3: stop = f[3]
            elif f[0] == "D" and len(f) > 10:
                try: at = int(f[10])
                except ValueError: continue
                deps.append({"line": f[1], "dest": f[2], "at": at, "platform": f[8], "realtime": f[9] == "1"})
        return {"stop": stop, "deps": deps[:6]} if stop else None
    b = cached("bus", 60, get)
    if not b: return None
    now = time.time()
    return {"stop": b["stop"], "deps": [dict(d, mins=max(0, int((d["at"] - now) // 60))) for d in b["deps"] if d["at"] > now - 30][:4]}


def weather():
    def get():
        j = json.loads(subprocess.run(["sway-weather"], capture_output=True, text=True, timeout=20).stdout or "{}")
        tip = (j.get("tooltip") or "").split("\n")
        place = re.sub(r"^\S+\s+", "", tip[0]).split(",")[0] if tip else ""
        now_ = re.sub(r"^\S+\s+", "", tip[1]) if len(tip) > 1 else ""
        desc = re.split(r"\s{2,}", now_)[0] if now_ else (j.get("alt") or "")
        temp = (j.get("text") or "").split(" ")[-1]
        return {"temp": temp, "desc": desc.lower(), "place": place, "stale": j.get("class") == "stale"}
    return cached("weather", 600, get)


def theme(wait=""):
    """The desktop's theme with its key; given the key the phone has (wait=KEY), held up to 25 s
    until it changes, so the phone follows a theme change within a second or two."""
    f = os.path.join(THEME, "theme.json")
    def now():
        try: raw = open(f, "rb").read()
        except OSError: raw = b""
        return raw, hashlib.sha1(raw).hexdigest()[:16]
    raw, key = now()
    end = time.time() + 25
    while wait and key == wait and time.time() < end:
        time.sleep(0.5); raw, key = now()
    try: j = json.loads(raw)
    except ValueError: j = {"name": "", "colors": {}, "background": "", "backgrounds": []}
    j["key"] = key
    return j

# ---------- Messenger: k4-messengerd's service on this Pi (k4-pi messenger), over its socket ----------

MSOCK = os.environ.get("K4_MESSENGER_SOCK") or os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid(), "k4-messenger.sock")
MEDIA = os.path.join(HOME, ".cache/k4/messenger/media")

def msgr(*args, inp="", timeout=60):
    """One command to the Messenger service; its reply (None: it isn't running here)."""
    import socket
    line = "\t".join(str(a).replace("\t", " ").replace("\n", " ") for a in args)
    if inp: line += "\x1eK4_INPUT=" + inp.replace("\n", "\r")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(MSOCK)
        s.sendall((line + "\n").encode()); s.shutdown(socket.SHUT_WR)
        out = b""
        while True:
            b = s.recv(65536)
            if not b: break
            out += b
        return out.decode(errors="replace")
    except OSError: return None
    finally: s.close()

def mjson(*args, **kw):
    out = msgr(*args, **kw)
    if out is None: return None
    try: return json.loads(out)
    except ValueError: return {"error": out.strip()[:200]}

def messenger_rooms():
    j = mjson("j-rooms", timeout=10)
    return j if j is not None else {"state": "none", "rooms": [], "unread": 0, "seq": 0}

def messenger_wait(since):
    """New messages after SINCE, held up to 25 s; a new k4 card ends the wait too (cards_seq: the
    phone fetches /api/cards when it grows)."""
    end = time.time() + 25
    card_mtime = cards_mtime()
    while True:
        j = mjson("j-events", since, timeout=5) or {"seq": since, "events": []}
        if j.get("events") or time.time() > end or not since or cards_mtime() != card_mtime:
            j["cards_seq"] = cards_seq()
            return j
        time.sleep(0.4)

# ---------- k4 cards for the phone (k4host.card keeps them) ----------
import k4host

def cards_mtime():
    try: return os.stat(k4host.CARDS).st_mtime_ns
    except OSError: return 0

def cards_seq():
    rows = k4host.cards()
    return rows[-1]["seq"] if rows else 0

def cards_since(since):
    """Cards after SINCE as the phone shows them (at most the last 20: a phone away for long gets the newest)."""
    rows = k4host.cards(since)[-20:]
    return {"seq": rows[-1]["seq"] if rows else max(since, cards_seq()), "cards": [dict(k4host.parse(r["line"]), seq=r["seq"], at=r["at"]) for r in rows]}

def messenger_home():
    j = mjson("j-rooms", timeout=5)
    if not j or j.get("state") == "none": return None
    top = next((r for r in j.get("rooms", []) if r.get("unread")), None) or next(iter(j.get("rooms", [])), None)
    return {"state": j.get("state"), "unread": j.get("unread", 0), "chats": sum(1 for r in j.get("rooms", []) if r.get("unread")),
            "top": {"room": top["id"], "name": top["name"], "line": ("%s: " % top["who"] if top.get("who") else "You: " if top.get("mine") else "") + top["last"], "unread": top["unread"]} if top else None}

def home():
    ag = calendar(1)
    ev, fin = events_added()
    return {"now": int(time.time()), "agenda": ag, "todos": todos()[:12], "pihole": pihole(), "parcels": parcels(), "events": ev, "finder": fin,
            "bus": bus(), "weather": weather(), "messenger": messenger_home()}


def pihole_page():
    import pihole as P
    st = P.state()
    base = pihole()
    u = st.get("unbound") or {}
    qs = [{"domain": x.get("domain", ""), "blocked": x.get("status") in P.BLOCKED,
           "why": {"GRAVITY": "ADLIST", "REGEX": "REGEX", "DENYLIST": "YOUR DENY"}.get(x.get("status"), ""),
           "client": ((x.get("client") or {}).get("name") or (x.get("client") or {}).get("ip") or "").split(".")[0] if (x.get("client") or {}).get("name") else (x.get("client") or {}).get("ip", ""),
           "time": time.strftime("%H:%M", time.localtime(x.get("time") or 0))} for x in st.get("queries") or []]
    g = (st.get("summary") or {}).get("gravity") or {}
    cl = (st.get("summary") or {}).get("clients") or {}
    v = st.get("version") or {}
    return dict(base, queries=qs, clients=cl.get("active") or 0, gravity_age=P.ago(g.get("last_update")) if g.get("last_update") else "never",
                version=v.get("core", ""), down_since=time.strftime("%H:%M", time.localtime(st.get("down_since") or 0)) if st.get("down_since") else "",
                unbound_detail={"resolves": u.get("resolves"), "dnssec": u.get("dnssec"), "ms": u.get("ms", 0), "hit": u.get("hit", 0), "watched": bool(u) and not u.get("nossh")})


def agenda():
    s = jload(os.path.join(EVENTS, "suggestions.json"), {"items": []})
    week = time.time() - 7 * 86400
    added = [{"id": g["id"], "title": g["title"], "date": g["date"], "start": g.get("start") or "", "from": g.get("who") or "", "source": g.get("source", ""), "state": g["state"]}
             for g in s.get("items", []) if g.get("state") == "added" and g.get("added", 0) > week][::-1]
    mine = {(a["date"], a["title"].lower()) for a in added}
    evs = calendar(7)
    for e in evs: e["k4"] = any(e["date"] == d and t.split(" · ")[0] in e["title"].lower() for d, t in mine)
    return {"events": evs, "todos": todos(), "added": added}


def search(q):
    q = q.strip().lower()
    if len(q) < 2: return []
    words = q.split()
    hit = lambda s: all(w in s.lower() for w in words)
    out = []
    for t in todos():
        if hit(t["title"]): out.append({"kind": "todo", "id": t["id"], "title": t["title"], "sub": ("due " + t["due"]) if t["due"] else "todo", "act": "done"})
    for e in calendar(60):
        if hit(e["title"] + " " + e["place"]): out.append({"kind": "event", "id": e["id"], "title": e["title"], "sub": "%s %s" % (e["date"], e["start"]), "act": ""})
    for p in parcels():
        if hit("%s %s %s parcel" % (p["shop"], p["carrier"], p["point"])): out.append({"kind": "parcel", "id": p["key"], "title": p["shop"], "sub": p["status"] + (" · code " + p["code"] if p["code"] else ""), "act": ""})
    for c in messenger_rooms().get("rooms", []):
        if hit(c["name"] + " " + " ".join(c.get("members") or [])):
            out.append({"kind": "chat", "id": c["id"], "title": c["name"], "sub": "Messenger · " + (("%d new" % c["unread"]) if c["unread"] else c["last"][:60]), "act": "open"})
    for it in releases_cached():
        if hit(it.get("title", "")): out.append({"kind": "release", "id": "%s:%s" % (it["kind"], it["id"]), "title": it["title"], "sub": "%s · %s" % (it["kind"].title(), it.get("when") or it.get("date") or "no date"), "act": ""})
    for words_, title, act in (("pause ads adblock pihole pi-hole", "Pause ad blocking · 5 min", "pihole-pause"), ("resume ads adblock pihole pi-hole", "Resume ad blocking", "pihole-resume")):
        if all(any(w2.startswith(w) for w2 in words_.split()) for w in words): out.append({"kind": "action", "id": act, "title": title, "sub": "Pi-hole", "act": act})
    return out[:30]


# ---------- actions ----------

def front(*args):
    """A k4 front script on this machine (they know their own state and cards)."""
    r = subprocess.run(list(args), capture_output=True, text=True, timeout=60)
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith("k4:")]
    return lines[-1] if lines else ("done" if r.returncode == 0 else "failed")


def act(path, body):
    if path == "/api/todo/done" or path == "/api/todo/undone":
        import todo
        ok = todo.set_status(str(body.get("id", "")), path.endswith("/done"))
        return {"ok": ok}
    if path == "/api/todo/add":
        import todo
        text = str(body.get("text", "")).strip()
        if not text: return {"ok": False, "why": "empty"}
        title, due = todo.split_text(text)
        return {"ok": True, "id": todo.add(title, due), "title": title, "due": due}
    if path == "/api/messenger/send":
        room, text = str(body.get("room", "")), str(body.get("text", ""))
        if not room or not text.strip(): return {"ok": False, "say": "Nothing to send"}
        out = (msgr("send", room, inp=text) or "Messenger isn't running on the hub").strip()
        return {"ok": out == "Sent", "say": out}
    if path == "/api/messenger/read":
        return {"ok": msgr("read", str(body.get("room", ""))) is not None}
    if path == "/api/messenger/start":
        out = (msgr("start", str(body.get("person", "")), str(body.get("name", ""))) or "error\tMessenger isn't running").strip().split("\t")
        return {"ok": out[0] == "ok", "room": out[1] if out[0] == "ok" and len(out) > 1 else "", "say": out[-1]}
    if path == "/api/pihole/pause": return {"ok": True, "say": front("k4-pihole", "pause", str(int(body.get("seconds", 300))))}
    if path in ("/api/pihole/allow", "/api/pihole/block"):
        d = str(body.get("domain", "")).strip().lower()
        if not re.fullmatch(r"[a-z0-9_.-]+\.[a-z0-9-]+", d): return {"ok": False, "say": "not a domain"}
        return {"ok": True, "say": front("k4-pihole", path.rsplit("/", 1)[1], d)}
    if path == "/api/pihole/restart-ftl": return {"ok": True, "say": front("k4-pihole", "restart-ftl")}
    if path == "/api/pihole/restart-unbound": return {"ok": True, "say": front("k4-pihole", "restart-unbound")}
    if path == "/api/events/remove":
        i = str(body.get("id", ""))
        if not re.fullmatch(r"[0-9a-f]{6,40}", i): return {"ok": False, "say": "no such event"}
        return {"ok": True, "say": front("k4-events", "remove", i)}
    if path == "/api/pihole/resume": return {"ok": True, "say": front("k4-pihole", "resume")}
    if path in ("/api/releases/follow", "/api/releases/cal"):
        kind, ident = str(body.get("kind", "")), str(body.get("id", ""))
        if kind not in RELEASE_KINDS or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", ident): return {"ok": False, "say": "no such title"}
        return {"ok": True, "say": front(sys.executable, "-I", os.path.join(SHARE, "releases.py"), "act", path.rsplit("/", 1)[1], kind, ident)}
    if path == "/api/router/do":
        verb, args = str(body.get("verb", "")), [str(a) for a in body.get("args") or []]
        ok = (verb in ("reboot", "retry", "wanip") and not args) or (verb == "radio" and len(args) == 2 and re.fullmatch(r"[a-z0-9_]{1,20}", args[0]) and args[1] in ("on", "off"))
        if not ok: return {"ok": False, "say": "not something the router page does"}
        return {"ok": True, "say": front(ROUTER, "do", verb, *args)}
    return None


# ---------- releases and the router (releases.py and k4-router on this Pi) ----------

RELEASE_KINDS = ("movies", "tv", "games", "books")
RELEASES_CACHE = os.environ.get("K4_RELEASES_CACHE") or os.path.join(HOME, ".cache/k4/releases")
ROUTER = os.environ.get("K4_ROUTER") or os.path.join(HOME, ".local/bin/k4-router")

def releases():
    r = subprocess.run([sys.executable, "-I", os.path.join(SHARE, "releases.py"), "json"], capture_output=True, text=True, timeout=90)
    try: return json.loads(r.stdout)
    except ValueError: return {"error": "Releases didn't answer · " + (r.stderr.strip().splitlines() or ["no output"])[-1][:160]}

def releases_cached():
    """The titles of the cached lists (for search: never fetched here)."""
    out = []
    for kind in RELEASE_KINDS:
        out += [dict(it, kind=kind) for it in jload(os.path.join(RELEASES_CACHE, "list-%s.json" % kind), {}).get("items", [])]
    return out

def router(client_ip):
    """The router's state; the Pi's own lease says HUB, and the phone asking is YOU."""
    r = subprocess.run([ROUTER, "json"], capture_output=True, text=True, timeout=30)
    try: j = json.loads(r.stdout)
    except ValueError: return {"status": "unreach", "err": "k4-router didn't answer"}
    for c in j.get("clients") or []:
        if c.get("tag") == "YOU": c["tag"] = "HUB"
        if c.get("ip") == client_ip: c["tag"] = "YOU"
    return j


# ---------- the server ----------

class H(http.server.BaseHTTPRequestHandler):
    server_version = "k4-hub"

    def log_message(self, f, *a): pass

    def send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def auth(self):
        if device_of(self.headers.get("Authorization")): return True
        self.send(401, {"error": "not paired"})
        return False

    def do_GET(self):
        if not self.auth(): return
        u = urllib.parse.urlparse(self.path)
        m = re.fullmatch(r"/api/bg/([0-9a-f]{16})\.jpg", u.path)
        if m:
            f = os.path.join(THEME, "bg", m.group(1) + ".jpg")
            if not os.path.isfile(f): return self.send(404, {"error": "no such background"})
            data = open(f, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(data)
            return
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/theme": return self.send(200, theme(q.get("wait", [""])[0]))
        m = re.fullmatch(r"/api/messenger/media/(\$[A-Za-z0-9_+/=.:-]+)", urllib.parse.unquote(u.path))
        if m:
            j = mjson("j-media", m.group(1), "thumb" if q.get("thumb") else "full", timeout=120) or {"error": "Messenger isn't running"}
            path = os.path.realpath(j.get("path") or "")
            if not path.startswith(os.path.realpath(MEDIA) + os.sep) or not os.path.isfile(path): return self.send(404, {"error": j.get("error") or "no such file"})
            return self.send_file(path, j.get("mime") or "application/octet-stream")
        try:
            if u.path == "/api/messenger/rooms": return self.send(200, messenger_rooms())
            m = re.fullmatch(r"/api/messenger/room/(![A-Za-z0-9_.:=-]+)", urllib.parse.unquote(u.path))
            if m: return self.send(200, mjson("j-messages", m.group(1), int(q.get("limit", ["40"])[0])) or {"error": "Messenger isn't running"})
            if u.path == "/api/messenger/people":
                out = msgr("search", q.get("q", [""])[0]) or ""
                return self.send(200, {"people": [{"id": l.split("\t")[1], "name": l.split("\t")[2]} for l in out.splitlines() if l.startswith("P\t") and l.count("\t") >= 2],
                                       "error": out.split("\t", 1)[1].strip() if out.startswith("error") else ""})
            if u.path == "/api/messenger/wait": return self.send(200, messenger_wait(int(q.get("since", ["0"])[0] or 0)))

            if u.path == "/api/home": return self.send(200, home())
            if u.path == "/api/calendar": return self.send(200, {"events": calendar(min(int(q.get("days", ["14"])[0]), 90))})
            if u.path == "/api/todos": return self.send(200, {"todos": todos(True)})
            if u.path == "/api/search": return self.send(200, {"results": search(q.get("q", [""])[0])})
            if u.path == "/api/pihole": return self.send(200, pihole_page())
            if u.path == "/api/agenda": return self.send(200, agenda())
            if u.path == "/api/cards": return self.send(200, cards_since(int(q.get("since", ["0"])[0] or 0)))
            if u.path == "/api/releases": return self.send(200, releases())
            m = re.fullmatch(r"/api/releases/poster/([0-9a-f]{16}\.jpg)", u.path)
            if m:
                f = os.path.join(RELEASES_CACHE, "img", m.group(1))
                return self.send_file(f, "image/jpeg") if os.path.isfile(f) else self.send(404, {"error": "no such poster"})
            if u.path == "/api/router": return self.send(200, router(self.client_address[0]))
        except Exception as e: return self.send(500, {"error": str(e)[:200]})
        self.send(404, {"error": "no such thing"})

    def send_file(self, path, mime):
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "private, max-age=2592000")
        self.end_headers()
        with open(path, "rb") as f:
            while True:
                b = f.read(1 << 16)
                if not b: break
                self.wfile.write(b)

    def do_POST(self):
        if not self.auth(): return
        n = int(self.headers.get("Content-Length") or 0)
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/messenger/send-image":   # the photo itself is the body
            q = urllib.parse.parse_qs(u.query)
            if not 0 < n <= 15 << 20: return self.send(413, {"error": "15 MB at most"})
            data = self.rfile.read(n)
            if not data.startswith((b"\xff\xd8", b"\x89PNG")): return self.send(400, {"error": "a JPEG or PNG"})
            import tempfile
            d = tempfile.mkdtemp(prefix="k4-hub-")
            f = os.path.join(d, "photo.jpg" if data.startswith(b"\xff\xd8") else "photo.png")
            try:
                with open(f, "wb") as fh: fh.write(data)
                out = (msgr("send-file", q.get("room", [""])[0], f, q.get("w", ["0"])[0], q.get("h", ["0"])[0], timeout=150) or "Messenger isn't running on the hub").strip()
            finally:
                try: os.unlink(f); os.rmdir(d)
                except OSError: pass
            return self.send(200, {"ok": out == "Sent", "say": out})
        try: body = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
        except ValueError: return self.send(400, {"error": "not JSON"})
        try: r = act(urllib.parse.urlparse(self.path).path, body if isinstance(body, dict) else {})
        except Exception as e: return self.send(500, {"error": str(e)[:200]})
        self.send(404, {"error": "no such thing"}) if r is None else self.send(200, r)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):   # (HTTPServer's own asks DNS for this host's full name: slow, and not needed)
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "k4-hub", self.server_address[1]


def serve(port):
    ensure_cert()
    srv = Server(("0.0.0.0", port), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(CERT, KEY)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print("k4-hub on :%d · SHA-256 %s" % (port, cert_fp()), flush=True)
    srv.serve_forever()


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "serve": serve(int(argv[2]) if len(argv) > 2 else PORT)
    elif cmd == "pair" and len(argv) > 2:
        host = argv[3] if len(argv) > 3 else subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()[0]
        print(pair(argv[2], host))
    elif cmd == "unpair" and len(argv) > 2:
        t = jload(TOKENS, {}); t.pop(argv[2], None); jsave(TOKENS, t); print("Unpaired %s" % argv[2])
    elif cmd == "devices":
        for n, v in jload(TOKENS, {}).items(): print("%s\tpaired %s" % (n, time.strftime("%Y-%m-%d", time.localtime(v.get("at", 0)))))
    else: print(__doc__.strip()); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
