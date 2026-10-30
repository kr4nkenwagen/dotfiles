#!/usr/bin/env python3
"""k4 × Discord (k4-discord is its front), through the official desktop app's local RPC socket.

It needs a Discord application of your own (discord.com/developers › New Application; OAuth2 ›
add the redirect http://127.0.0.1; App Testers › add yourself): RPC works for an app's own testers.
Its client id lives in ~/.config/k4/discord-client.json, its secret and the refresh token in the
keyring (k4-secret: token discord, token discord-refresh). Nothing here ever prints a token.

  discord.py signin                  Discord asks you to allow k4 (once)
  discord.py watch                   while Discord runs: its notifications as k4 cards, voice for the bar
  discord.py mute | deafen | leave   your voice (Discord's own settings)
  discord.py join CHANNEL | open GUILD CHANNEL
  discord.py card GUILD/CHANNEL KEY ID   a card's button
  discord.py info | bar | find | act client ID | act seen

Tests: K4_DISCORD_FAKE=DIR (secrets and the token endpoint from files there, cards to DIR/posts.log),
K4_DISCORD_SOCK=PATH (a fake RPC socket), K4_DISCORD_STATE.
"""
import base64, json, os, re, shlex, shutil, socket, struct, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid

HOME = os.path.expanduser("~")
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
STATE = os.environ.get("K4_DISCORD_STATE") or os.path.join(HOME, ".local/state/k4/discord")
CACHE = os.path.join(STATE, "cache") if os.environ.get("K4_DISCORD_STATE") else os.path.join(HOME, ".cache/k4/discord")
CONF = os.path.join(HOME, ".config/k4/discord-client.json")
FAKE = os.environ.get("K4_DISCORD_FAKE")
FRONT = os.environ.get("K4_DISCORD_FRONT") or shutil.which("k4-discord") or "k4-discord"
LIVE = os.path.join(RUN, "k4-discord.live")   # (notifyd drops Discord's own notifications while this is fresh)
SCOPES = ["rpc", "rpc.notifications.read", "rpc.voice.read", "rpc.voice.write", "guilds"]
REDIRECT = "http://127.0.0.1"
API = "https://discord.com/api/v10"


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()


def jload(p, default):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return default


def jsave(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w") as f: json.dump(data, f)
    os.replace(p + ".tmp", p)


# ---------- secrets ----------

def client_id():
    if FAKE: return "1234"
    return str(jload(CONF, {}).get("client_id", ""))


def secret(name):
    if FAKE:
        try:
            with open(os.path.join(FAKE, "secret-" + name)) as f: return f.read()
        except OSError: return ""
    r = subprocess.run(["k4-secret", "lookup", "token", name], capture_output=True, text=True, timeout=15)
    return r.stdout if r.returncode == 0 else ""


def keep(name, value):
    if FAKE:
        with open(os.path.join(FAKE, "secret-" + name), "w") as f: f.write(value)
        return
    subprocess.run(["k4-secret", "store", "token", name], input=value, text=True, capture_output=True, timeout=20)


def oauth(form):
    """Discord's token endpoint (the code or the refresh token for an access token)."""
    if FAKE:
        return jload(os.path.join(FAKE, "token.json"), {})
    form = dict(form, client_id=client_id(), client_secret=secret("discord"))
    req = urllib.request.Request(API + "/oauth2/token", data=urllib.parse.urlencode(form).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "k4"})
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)


def access_token():
    """A fresh access token: the cached one, else from the refresh token; "" when not signed in."""
    p = os.path.join(RUN, "k4-discord-token.json")
    c = jload(p, {})
    if c.get("access") and c.get("exp", 0) > time.time() + 60: return c["access"]
    rt = secret("discord-refresh")
    if not rt: return ""
    try: j = oauth({"grant_type": "refresh_token", "refresh_token": rt})
    except Exception: return ""
    if j.get("refresh_token") and j["refresh_token"] != rt: keep("discord-refresh", j["refresh_token"])
    if not j.get("access_token"): return ""
    old = os.umask(0o077)
    try: jsave(p, {"access": j["access_token"], "exp": time.time() + int(j.get("expires_in", 3600))})
    finally: os.umask(old)
    return j["access_token"]


# ---------- the RPC socket ----------

def sock_path():
    if os.environ.get("K4_DISCORD_SOCK"): return os.environ["K4_DISCORD_SOCK"] if os.path.exists(os.environ["K4_DISCORD_SOCK"]) else ""
    for base in (RUN, os.path.join(RUN, "app/com.discordapp.Discord"), "/tmp"):
        for i in range(10):
            p = os.path.join(base, "discord-ipc-%d" % i)
            if os.path.exists(p): return p
    return ""


class Rpc:
    """One connection: handshake, then commands (answered by nonce) and events (queued)."""

    def __init__(self, timeout=10):
        p = sock_path()
        if not p: raise ConnectionError("Discord is not running")
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.settimeout(timeout)
        self.s.connect(p)
        self.events = []
        self.send(0, {"v": 1, "client_id": client_id()})
        op, data = self.recv()
        if op == 2 or data.get("evt") == "ERROR": raise ConnectionError(data.get("message") or data.get("data", {}).get("message") or "refused")
        self.user = (data.get("data") or {}).get("user", {})

    def send(self, op, data):
        b = json.dumps(data).encode()
        self.s.sendall(struct.pack("<II", op, len(b)) + b)

    def _read(self, n):
        out = b""
        while len(out) < n:
            c = self.s.recv(n - len(out))
            if not c: raise ConnectionError("Discord closed the connection")
            out += c
        return out

    def recv(self):
        op, n = struct.unpack("<II", self._read(8))
        data = json.loads(self._read(n) or b"{}")
        if op == 3: self.send(4, data); return self.recv()   # ping
        return op, data

    def cmd(self, cmd, args=None, evt=None):
        nonce = str(uuid.uuid4())
        m = {"cmd": cmd, "args": args or {}, "nonce": nonce}
        if evt: m["evt"] = evt
        self.send(1, m)
        while True:
            op, d = self.recv()
            if op == 2: raise ConnectionError(d.get("message", "closed"))
            if d.get("nonce") == nonce:
                if d.get("evt") == "ERROR": raise RuntimeError(d.get("data", {}).get("message", "error"))
                return d.get("data") or {}
            if d.get("evt"): self.events.append(d)

    def auth(self):
        tok = access_token()
        if not tok: raise PermissionError("not signed in")
        self.cmd("AUTHENTICATE", {"access_token": tok})
        return self

    def close(self):
        try: self.s.close()
        except OSError: pass


def signin():
    if not client_id(): return say("No Discord application yet · k4-discord act client ID (Discord developer portal)")
    if not secret("discord") and not FAKE: return say("The application's secret is missing · k4-discord act client ID asks for it")
    try:
        r = Rpc(timeout=120)
        code = r.cmd("AUTHORIZE", {"client_id": client_id(), "scopes": SCOPES}).get("code")
        j = oauth({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT})
        if not j.get("refresh_token"): return say("Discord did not give a token · check the redirect http://127.0.0.1")
        keep("discord-refresh", j["refresh_token"])
        try: os.remove(os.path.join(RUN, "k4-discord-token.json"))
        except OSError: pass
        r.auth()
        say("Signed in to Discord as %s" % (r.user.get("global_name") or r.user.get("username") or "you"))
        r.close()
    except urllib.error.HTTPError as e:
        try: why = json.loads(e.read() or b"{}").get("error", "")
        except ValueError: why = ""
        if why == "invalid_client" or e.code == 401: say("Discord refused the client secret · paste it again: Apps › Discord › Paste the client secret")
        elif why == "invalid_grant": say("Discord refused the sign-in · check OAuth2 › Redirects has http://127.0.0.1 exactly, then Allow again")
        else: say("Discord’s token exchange failed (%s%s)" % (e.code, " · " + why if why else ""))
    except (ConnectionError, OSError) as e: say("Discord: %s" % e)
    except RuntimeError as e: say("Discord refused: %s" % e)


# ---------- the state the bar and the page read ----------

def state(): return jload(os.path.join(STATE, "state.json"), {})
def save_state(s): s["at"] = time.time(); jsave(os.path.join(STATE, "state.json"), s); bar_file(s)


def bar_file(s): jsave(os.path.join(STATE, "bar.json"), bar_json(s))


def bar_json(s):
    """The bar module (BarModDiscord): the mark; an accent pill for mentions since you last looked; in
    voice "Raid · 5" with the mark in the accent (green while someone speaks: colour only, no motion),
    a red mic or headphones after it when you are muted or deafened."""
    if not s.get("live") or time.time() - s.get("at", 0) > 120: return {}
    out = {"icon": "󰙯", "tooltip": "Discord"}
    v = s.get("voice") or {}
    if v.get("channel"):
        ms = v.get("members", [])
        out.update(text="%s · %d" % (v["channel"], len(ms)), icon_tone="green" if any(m.get("speaking") for m in ms) else "accent")
        out["tooltip"] = " · ".join(x for x in ("Discord", "in " + v["channel"], v.get("guild", ""), "deafened" if s.get("deaf") else ("muted" if s.get("mute") else "")) if x)
        if s.get("deaf"): out.update(text2="󰟎", text2_tone="red")
        elif s.get("mute"): out.update(text2="󰍭", text2_tone="red")
    n = sum(1 for x in s.get("log", []) if x["at"] > s.get("seen_at", 0))
    if n: out["pill"] = "99+" if n > 99 else str(n)
    return out


def post(title, body, image="", ident="0"):
    if FAKE:
        with open(os.path.join(FAKE, "posts.log"), "a") as f: f.write("%s | %s | %s\n" % (title, body, ident))
        return
    line = "\t".join(["post", "0", "Discord", field(title), field(body)[:400], "1", "-1", "-1", "", "", "",
                      "open:Open,read:Mark read", "%s card %s" % (FRONT, ident)] + ([image] if image else []))
    subprocess.run(["k4", "--notify-ctl", line], capture_output=True, timeout=5)


def avatar(url):
    """A notification's icon, cached (the card's picture); "" when there is none."""
    if not url or FAKE: return ""
    p = os.path.join(CACHE, "av", re.sub(r"[^A-Za-z0-9]+", "_", url)[-80:] + ".png")
    if not os.path.exists(p):
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "k4"}), timeout=10) as r, open(p, "wb") as f: f.write(r.read())
        except Exception: return ""
    return p


# ---------- while Discord runs ----------

def member(vs):
    u = vs.get("user") or {}
    st = vs.get("voice_state") or {}
    return {"id": u.get("id", ""), "name": vs.get("nick") or u.get("global_name") or u.get("username", "?"),
            "mute": bool(st.get("mute") or st.get("self_mute")), "deaf": bool(st.get("deaf") or st.get("self_deaf")), "speaking": False}


def watch():
    """Connect while Discord runs (and you are signed in); follow notifications and voice."""
    import fcntl
    os.makedirs(STATE, exist_ok=True)
    lock = open(os.path.join(STATE, "watch.lock"), "w")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: return
    while True:
        try: follow()
        except (ConnectionError, OSError, PermissionError, RuntimeError, struct.error, ValueError) as e:
            s = state(); s.update(live=False, why=("signin" if isinstance(e, PermissionError) else "offline")); save_state(s)
            try: os.remove(LIVE)
            except OSError: pass
        if os.environ.get("K4_DISCORD_ONCE"): return
        time.sleep(5)


def follow():
    r = Rpc(timeout=30).auth()
    s = {"live": True, "why": "", "me": r.user.get("global_name") or r.user.get("username", ""), "me_id": r.user.get("id", ""), "unread": state().get("unread", 0), "seen_at": state().get("seen_at", 0),
         "voice": {}, "log": state().get("log", [])}
    vs = r.cmd("GET_VOICE_SETTINGS")
    s["mute"], s["deaf"] = bool(vs.get("mute")), bool(vs.get("deaf"))
    for e in ("NOTIFICATION_CREATE", "VOICE_CHANNEL_SELECT", "VOICE_SETTINGS_UPDATE"): r.cmd("SUBSCRIBE", {}, e)
    chans = {}

    def channel(cid):
        if cid not in chans:
            try: chans[cid] = r.cmd("GET_CHANNEL", {"channel_id": cid})
            except RuntimeError: chans[cid] = {}
        return chans[cid]

    def guild_name(gid):
        for g in guilds_cached():
            if g["id"] == gid: return g["name"]
        try: return r.cmd("GET_GUILD", {"guild_id": gid}).get("name", "") if gid else ""
        except RuntimeError: return ""

    def set_voice(cid):
        old = s["voice"].get("id")
        if old:
            for e in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE", "SPEAKING_START", "SPEAKING_STOP"):
                try: r.cmd("UNSUBSCRIBE", {"channel_id": old}, e)
                except RuntimeError: pass
        s["voice"] = {}
        if not cid: return
        c = r.cmd("GET_CHANNEL", {"channel_id": cid})
        s["voice"] = {"id": cid, "channel": c.get("name", ""), "guild_id": c.get("guild_id", ""), "guild": guild_name(c.get("guild_id", "")),
                      "members": [member(x) for x in c.get("voice_states", [])]}
        for e in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE", "SPEAKING_START", "SPEAKING_STOP"):
            r.cmd("SUBSCRIBE", {"channel_id": cid}, e)

    cur = r.cmd("GET_SELECTED_VOICE_CHANNEL")
    set_voice((cur or {}).get("id"))
    save_state(s)
    r.s.settimeout(20)
    while True:
        open(LIVE, "w").close()
        if r.events: d = r.events.pop(0)
        else:
            try: _, d = r.recv()
            except socket.timeout:
                save_state(s); continue
        evt, data = d.get("evt"), d.get("data") or {}
        if evt == "NOTIFICATION_CREATE":
            cid = data.get("channel_id", "")
            c = channel(cid) if cid else {}
            gid = c.get("guild_id", "")
            msg = data.get("message") or {}
            ident = "%s/%s" % (gid or "@me", cid)
            who, where = who_where(data.get("title") or "Discord")   # (DiscordNotify: "Maja Lind · #raid-signups · Ember Pact")
            post("%s · %s" % (who, where) if where else who, data.get("body") or msg.get("content", ""), avatar(data.get("icon_url", "")), ident)
            s["unread"] = s.get("unread", 0) + 1
            s["log"] = ([{"title": field(data.get("title")), "body": field(data.get("body") or msg.get("content", ""))[:200], "at": time.time(), "open": ident}] + s.get("log", []))[:50]
        elif evt == "VOICE_CHANNEL_SELECT": set_voice(data.get("channel_id"))
        elif evt == "VOICE_SETTINGS_UPDATE": s["mute"], s["deaf"] = bool(data.get("mute")), bool(data.get("deaf"))
        elif evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE"):
            m = member(data)
            ms = [x for x in s["voice"].get("members", []) if x["id"] != m["id"]]
            s["voice"]["members"] = ms + [m]
        elif evt == "VOICE_STATE_DELETE":
            uid = (data.get("user") or {}).get("id")
            s["voice"]["members"] = [x for x in s["voice"].get("members", []) if x["id"] != uid]
        elif evt in ("SPEAKING_START", "SPEAKING_STOP"):
            for x in s["voice"].get("members", []):
                if x["id"] == data.get("user_id"): x["speaking"] = evt == "SPEAKING_START"
        save_state(s)


# ---------- commands (each its own connection) ----------

def run(cmd, args=None):
    try:
        r = Rpc().auth()
        out = r.cmd(cmd, args)
        r.close()
        return out
    except PermissionError: say("Not signed in to Discord · k4-discord signin"); return None
    except (ConnectionError, OSError) as e: say("Discord: %s" % e); return None
    except RuntimeError as e: say("Discord refused: %s" % e); return None


def voice_toggle(which):
    cur = run("GET_VOICE_SETTINGS")
    if cur is None: return
    out = run("SET_VOICE_SETTINGS", {which: not cur.get(which)})
    if out is not None: say("%s %s" % ("Muted" if which == "mute" else "Deafened", "on" if out.get(which) else "off"))


def guilds(fresh=False):
    """Servers and their channels: [{id, name, channels: [{id, name, type 0 text | 2 voice}]}], cached 1 h."""
    p = os.path.join(CACHE, "guilds.json")
    c = jload(p, {})
    if not fresh and c.get("at", 0) > time.time() - 3600: return c.get("guilds", [])
    try:
        r = Rpc().auth()
        gs = [{"id": g["id"], "name": g["name"]} for g in r.cmd("GET_GUILDS").get("guilds", [])]
        for g in gs:
            try: g["channels"] = [{"id": x["id"], "name": x["name"], "type": x.get("type", 0)} for x in r.cmd("GET_CHANNELS", {"guild_id": g["id"]}).get("channels", [])]
            except RuntimeError: g["channels"] = []
        r.close()
        jsave(p, {"at": time.time(), "guilds": gs})
        return gs
    except (ConnectionError, OSError, PermissionError, RuntimeError): return c.get("guilds", [])


def guilds_cached(): return jload(os.path.join(CACHE, "guilds.json"), {}).get("guilds", [])


def open_channel(gid, cid):
    """The channel in Discord, its window to the front."""
    if run("SELECT_TEXT_CHANNEL", {"channel_id": cid}) is None and not FAKE:
        subprocess.Popen(["xdg-open", "discord://-/channels/%s/%s" % (gid or "@me", cid)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not FAKE and shutil.which("hyprctl"):
        subprocess.run(["hyprctl", "dispatch", "focuswindow", "class:discord"], capture_output=True)


def note(key, ident):
    if key in ("open", "default") and "/" in ident:
        g, c = ident.split("/", 1)
        open_channel("" if g == "@me" else g, c)


# ---------- what the page and the launcher read ----------

def status():
    sec = secret("discord").strip()
    if not client_id() or not sec or sec.isdigit(): return "nosetup"   # (a secret that is all digits is the application ID pasted twice)
    if not sock_path(): return "notrunning"
    if not secret("discord-refresh"): return "signin"
    return "ok"


COLORS = ["#3DF5FF", "#3DFF9E", "#FFC857", "#CBA6F7", "#6CA8FF", "#FF8FB1", "#C69B6D", "#F2F2F2"]


def initials(name):
    w = [x for x in re.split(r"[\s._-]+", name) if x]
    return (w[0][0] + w[1][0]).upper() if len(w) > 1 else name[:2].capitalize()


def color_of(name): return COLORS[sum(map(ord, name)) % len(COLORS)]


def who_where(title):
    """Discord's notification title "Maja Lind (#raid-signups, Ember Pact)" → ("Maja Lind", "#raid-signups · Ember Pact"); a DM → (name, "")."""
    m = re.match(r"^(.*?)\s*\((#[^,]+),\s*(.+)\)$", title)
    return (m.group(1), "%s · %s" % (m.group(2), m.group(3))) if m else (title, "")


def ago(t):
    d = time.time() - t
    if d < 60: return "now"
    if d < 3600: return "%d m" % (d // 60)
    if d < 86400: return "%d h" % (d // 3600)
    if d < 2 * 86400: return "yesterday"
    return time.strftime("%a", time.localtime(t))


def info():
    """The Apps page (KDiscord): S status me mute deaf unread · V channel server in-voice · M ini color state name
    (talk|mute|deaf|me…) · N ini color who where body ago open new · G guild · C kind id name guild-id."""
    s = state()
    st = status()
    log = s.get("log", [])
    seen = s.get("seen_at", 0)
    unread = sum(1 for n in log if n["at"] > seen)
    print("S\t%s\t%s\t%d\t%d\t%d" % (st, field(s.get("me")) or "-", s.get("mute", False), s.get("deaf", False), unread))
    v = s.get("voice") or {}
    if st == "ok" and s.get("live") and v.get("channel"):
        ms = v.get("members", [])
        print("V\t%s\t%s\t%d" % (field(v["channel"]), field(v.get("guild")) or "-", len(ms)))
        for m in ms:
            me = m["id"] == s.get("me_id")
            state_ = ("me" + ("-deaf" if s.get("deaf") else "-mute" if s.get("mute") else "")) if me else ("talk" if m.get("speaking") else "deaf" if m["deaf"] else "mute" if m["mute"] else "")
            print("M\t%s\t%s\t%s\t%s" % ("ME" if me else initials(m["name"]), "#6CA8FF" if me else color_of(m["name"]), state_ or "-", "you" if me else field(m["name"]).split(" ")[0]))
    for n in log[:10]:
        who, where = who_where(n["title"])
        print("N\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d" % (initials(who), color_of(who), field(who) or "-", field(where) or "-", field(n["body"]) or "-", ago(n["at"]), n["open"], 1 if n["at"] > seen else 0))
    if st == "ok":
        here = v.get("id", "") if s.get("live") else ""
        for g in guilds():
            print("G\t%s\t%s" % (g["id"], field(g["name"])))
            for c in g.get("channels", []):
                if c["type"] in (0, 2): print("C\t%s\t%s\t%s\t%s\t%d" % ("voice" if c["type"] == 2 else "text", c["id"], field(c["name"]), g["id"], 1 if c["id"] == here else 0))


def page():
    """The signed-in Apps page (the KDiscord board) as k4's records, built here (in bash it took
    seconds for a few hundred channels): voice, mentions & DMs, servers. A server's channels are
    listed for the one you are in voice on; the others are a row each (↵ opens Discord on it)."""
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    rid = lambda act: b64("k4-discord run " + b64(act))
    flag = lambda t: field(t).replace(";", ",")
    out = []
    def row(label, act, meta="", flags="", stay=False):
        out.append("A\t%s\t%s\t%s\t\t%s" % (rid(act), field(label), field(meta), ("stay;" + flags if stay else flags).strip(";")))
    s = state()
    log = s.get("log", [])
    seen = s.get("seen_at", 0)
    unread = sum(1 for n in log if n["at"] > seen)
    v = s.get("voice") or {} if s.get("live") else {}
    mute, deaf = bool(s.get("mute")), bool(s.get("deaf"))
    count = "%d new" % unread if unread else "idle"
    if v.get("channel"): count = "🔊 %s%s" % (v["channel"], " · deafened" if deaf else (" · muted" if mute else ""))
    out.append("D\tthrough the Discord app · mentions, DMs and voice · can’t read channels or send\t%s\tSearch Discord…" % count)
    out.append("Y\t" + "\t".join(["↑↓", "Move", "↵", "Open / join"] + (["⌃M", "Mute", "⌃D", "Deafen", "⌃L", "Leave"] if v.get("channel") else []) + ["⌫", "Back"]))
    row("Open Discord", "%s app" % me, "the app", "mark=󰙯;markc=#5865F2")
    if v.get("channel"):
        ms = v.get("members", [])
        people = []
        for m in ms:
            mine = m["id"] == s.get("me_id")
            st = ("me" + ("-deaf" if deaf else "-mute" if mute else "")) if mine else ("talk" if m.get("speaking") else "deaf" if m["deaf"] else "mute" if m["mute"] else "")
            people.append("%s~%s~%s~%s" % ("ME" if mine else initials(m["name"]), "#6CA8FF" if mine else color_of(m["name"]), st, "you" if mine else field(m["name"]).split(" ")[0]))
        tags = ("DEAFENED|" if deaf else "") + ("MUTED" if mute else "MIC ON")
        out.append("VP\t🔊 %s\t%s\t%s\t%s" % (field(v["channel"]), ("%s · %d" % (v.get("guild"), len(ms))) if v.get("guild") else str(len(ms)), tags, "|".join(people)))
        row("Mute", "%s mute" % me, "⌃M", "mark=%s;markc=%s;chip=%s;chipc=%s" % ("◌" if mute else "●", "red" if mute else "dim", "ON" if mute else "OFF", "red" if mute else "dim"), stay=True)
        row("Deafen", "%s deafen" % me, "⌃D", "mark=◎;markc=%s;chip=%s;chipc=%s" % ("red" if deaf else "dim", "ON" if deaf else "OFF", "red" if deaf else "dim"), stay=True)
        row("Leave voice", "%s leave" % me, "⌃L", "mark=⏏", stay=True)
        for k, act in (("^m", "mute"), ("^d", "deafen"), ("^l", "leave")): out.append("KB\t%s\t%s" % (k, rid("%s %s" % (me, act))))
    else:
        out.append("H\tVoice\t")
        row("Not in voice", ":", "", "mark=○;sub=  pick a channel to join;dim")
    out.append("H\tMentions & DMs\t%s" % (unread or ""))
    for n in log[:10]:
        who, where = who_where(n["title"])
        g, _, c = n["open"].partition("/")
        new = n["at"] > seen
        row(who, "bg %s open %s %s" % (me, g, c), ago(n["at"]), "av=%s;avc=%s;l2=%s;l2c=%s;sub=%s;subc=%s%s" % (initials(who), color_of(who), flag(n["body"]), "fg" if new else "dim",
            flag(" · " + where) if where else " · DM", "dim" if where else "#5865F2", ";chip=NEW;chipc=accent" if new else ""))
    if not log: out.append("E\tNothing yet · new mentions and DMs show here")
    gs = guilds_cached()
    here = v.get("id", "")
    out.append("H\tServers\t%d" % len(gs))
    for g in sorted(gs, key=lambda g: (g["id"] != v.get("guild_id"), g["name"].lower())):
        chs = [c for c in g.get("channels", []) if c["type"] in (0, 2)]
        open_ = g["id"] == v.get("guild_id")
        first = next((c for c in chs if c["type"] == 0), None)
        row(g["name"], ("bg %s open %s %s" % (me, g["id"], first["id"])) if first and not open_ else ":", "" if open_ else "%d channels · ↵ opens it" % len(chs), "mark=%s;markc=accent" % ("▾" if open_ else "▸"))
        if not open_: continue
        for c in chs:
            if c["type"] == 2: row("   🔊 %s" % c["name"], "%s join %s" % (me, c["id"]), "you’re here" if c["id"] == here else "↵ joins", "mark= ;metac=%s" % ("accent" if c["id"] == here else "dim"), stay=True)
            else: row("   # %s" % c["name"], "bg %s open %s %s" % (me, g["id"], c["id"]), "↵ opens", "mark= ")
    print("\n".join(out))
    if unread and not FAKE: subprocess.Popen([FRONT, "act", "seen"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_rows():
    """The launcher (SearchDiscord): text channels open, voice channels join (with who is in them), servers."""
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    s = state()
    v = s.get("voice") or {}
    def row(label, act, meta, find):
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=55;tag=Discord;icon=󰙯;find=%s" % (b64("k4-discord run " + b64(act)), field(label), meta, field(find).replace(";", ",")))
    row("Open Discord", "%s app" % me, "the app", "discord app open start")
    for g in guilds_cached():
        chs = g.get("channels", [])
        for c in chs:
            if c["type"] == 0: row("#%s · %s" % (c["name"], g["name"]), "%s open %s %s" % (me, g["id"], c["id"]), "↵ opens", "%s %s" % (c["name"].replace("-", " "), g["name"]))
            elif c["type"] == 2:
                n = len(v.get("members", [])) if s.get("live") and v.get("id") == c["id"] else 0
                row("🔊 %s · %s" % (c["name"], g["name"]), "%s join %s" % (me, c["id"]), ("%d in voice · ↵ joins" % n) if n else "↵ joins", "%s %s voice" % (c["name"], g["name"]))
        row(g["name"], "bg sway-menu discord", "server · %d channels" % sum(1 for c in chs if c["type"] in (0, 2)), g["name"] + " server")


def act(argv):
    v = argv[0] if argv else ""
    if v == "client":
        cid = argv[1] if len(argv) > 1 else ""
        if not cid.isdigit(): return say("The application ID is a number (Discord developer portal › General Information)")
        sec = os.environ.get("K4_INPUT", "")
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        jsave(CONF, {"client_id": cid})
        if sec: keep("discord", sec.strip())
        say("Discord application saved%s · now: k4-discord signin" % ("" if sec else " · the secret is still missing"))
    elif v == "seen":
        s = state(); s["unread"], s["seen_at"] = 0, time.time(); save_state(s)
    else: say("k4-discord act: unknown %s" % v)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    rest = argv[2:]
    if cmd == "signin": signin()
    elif cmd == "watch": watch()
    elif cmd == "mute": voice_toggle("mute")
    elif cmd == "deafen": voice_toggle("deaf")
    elif cmd == "leave":
        if run("SELECT_VOICE_CHANNEL", {"channel_id": None}) is not None: say("Left voice")
    elif cmd == "join" and rest:
        c = run("SELECT_VOICE_CHANNEL", {"channel_id": rest[0], "force": True})
        if c is not None: say("Joined %s" % c.get("name", "voice"))
    elif cmd == "open" and len(rest) >= 2: open_channel(rest[0], rest[1])
    elif cmd == "card": note(rest[1] if len(rest) > 1 else "", rest[0] if rest else "")   # card G/C KEY ID (notifyd adds the key and its id)
    elif cmd == "info": info()
    elif cmd == "bar": print(json.dumps(bar_json(state()), ensure_ascii=False))
    elif cmd == "find": find_rows()
    elif cmd == "page": page()
    elif cmd == "guilds": gs = guilds(fresh=True); say("%d servers" % len(gs))
    elif cmd == "status": say(status())
    elif cmd == "act": act(rest)
    else: say(__doc__.strip()); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
