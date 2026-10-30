#!/usr/bin/env python3
"""k4's Pi-hole (k4-pihole is its front): your Pi-hole v6 and the unbound behind it, watched every
minute (k4-pihole.timer: tick) and managed from Apps › Pi-hole and the bar: pause blocking, the query
log (allow or block a domain), adlists and gravity, your allow/deny entries; cards when something
changes (blocking off, Pi-hole or unbound not answering, DNSSEC failing, old gravity, Pi-hole's own
messages).

  pihole.py tick                    ask Pi-hole (and unbound over ssh, every 5 min) → state.json, the cards
  pihole.py page | bar | find       the Apps page, the bar module, the launcher's rows (from state.json)
  pihole.py pause SECONDS|0 | resume | allow DOMAIN | block DOMAIN | unlist TYPE DOMAIN
  pihole.py list-toggle ADDRESS | gravity | restart-unbound | restart-dns
  pihole.py setup-password ($K4_INPUT) | trust | setup-host-cmd | status

Pi-hole's API on https://HOST/api (v6), signed in with an app password (k4-secret token pihole); its
self-signed certificate is pinned the first time (~/.config/k4/pihole.json) and a different one is
refused until you trust it on the page. unbound: `ssh HOST` with your key, unbound-control through
sudo (k4-pihole setup-host allows just that). Tests: K4_PIHOLE_FAKE=DIR answers from DIR/<path>.json,
writes to DIR/log; DIR/down: Pi-hole doesn't answer; DIR/unbound.json is the ssh side.
"""
import base64, hashlib, http.client, json, os, re, shlex, shutil, socket, ssl, subprocess, sys, time, urllib.parse

HOME = os.path.expanduser("~")
FAKE = os.environ.get("K4_PIHOLE_FAKE")
CONF = os.environ.get("K4_PIHOLE_CONF") or (os.path.join(FAKE, "pihole.json") if FAKE else os.path.join(HOME, ".config/k4/pihole.json"))
C = os.environ.get("K4_PIHOLE_CACHE") or (os.path.join(FAKE, "cache") if FAKE else os.path.join(HOME, ".cache/k4/pihole"))
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
FRONT = os.environ.get("K4_PIHOLE_FRONT") or shutil.which("k4-pihole") or "k4-pihole"
DEFAULT_HOST = "kr4nkenhole"
BLOCKED = {"GRAVITY", "REGEX", "DENYLIST", "EXTERNAL_BLOCKED_IP", "EXTERNAL_BLOCKED_NULL", "EXTERNAL_BLOCKED_NXRA", "EXTERNAL_BLOCKED_EDE15",
           "GRAVITY_CNAME", "REGEX_CNAME", "DENYLIST_CNAME", "SPECIAL_DOMAIN"}
WHY = {"GRAVITY": "adlist", "REGEX": "regex", "DENYLIST": "your deny list", "GRAVITY_CNAME": "adlist (CNAME)", "REGEX_CNAME": "regex (CNAME)",
       "DENYLIST_CNAME": "deny list (CNAME)", "SPECIAL_DOMAIN": "special domain"}
UNBOUND_EVERY = 300
os.makedirs(C, exist_ok=True)


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def flag(s): return field(s).replace(";", ",")
def now(): return float(os.environ.get("K4_PIHOLE_NOW") or time.time())


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data, private=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if private else 0o644)
    with os.fdopen(fd, "w") as f: json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


def conf():
    c = jload(CONF, {})
    c.setdefault("host", DEFAULT_HOST)
    return c


def password():
    if FAKE: return os.environ.get("K4_PIHOLE_PASSWORD", "")
    try:
        r = subprocess.run(["k4-secret", "lookup", "token", "pihole"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired): return ""


# ---------- Pi-hole's API: pinned TLS, one session reused ----------

class Down(Exception): pass          # not answering
class Refused(Exception): pass       # the password
class CertChanged(Exception):        # not the certificate pinned
    def __init__(self, fp): super().__init__("the certificate changed"); self.fp = fp


def fingerprint(host):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, 443), timeout=5) as s, ctx.wrap_socket(s, server_hostname=host) as t:
            return hashlib.sha256(t.getpeercert(binary_form=True)).hexdigest()
    except OSError as e: raise Down(str(e))


def raw(method, path, body=None, sid=None, stream=None):
    """One request; the certificate must be the pinned one before anything is sent."""
    c = conf()
    if FAKE:
        if os.path.exists(os.path.join(FAKE, "down")): raise Down("no answer")
        if os.path.exists(os.path.join(FAKE, "certchanged")): raise CertChanged("ff" * 32)
        if method != "GET" or path == "/api/auth":
            if path == "/api/auth":
                if (body or {}).get("password") != os.environ.get("K4_PIHOLE_PASSWORD", "x"): raise Refused("wrong password")
                return {"session": {"valid": True, "sid": "fake-sid", "validity": 1800}}
            with open(os.path.join(FAKE, "log"), "a") as f: f.write("%s %s %s\n" % (method, path, json.dumps(body, sort_keys=True) if body else ""))
            if stream: stream("[✓] Done.")
            return {}
        return jload(os.path.join(FAKE, path.split("?")[0].replace("/api/", "", 1).replace("/", "_") + ".json"), {})
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection(c["host"], 443, timeout=20 if stream else 8, context=ctx)
    try:
        conn.connect()
        fp = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
        if c.get("pin") and fp != c["pin"]: raise CertChanged(fp)
        h = {"Accept": "application/json"}
        if sid: h["X-FTL-SID"] = sid
        data = json.dumps(body).encode() if body is not None else None
        if data: h["Content-Type"] = "application/json"
        conn.request(method, path, data, h)
        r = conn.getresponse()
        if stream:
            for line in r: stream(line.decode(errors="replace").rstrip())
            return {}
        out = r.read()
        if r.status == 401: raise Refused("signed out")
        if r.status >= 400: raise Down("Pi-hole said %d: %s" % (r.status, out[:120].decode(errors="replace")))
        return json.loads(out) if out else {}
    except (OSError, http.client.HTTPException, ValueError) as e: raise Down(str(e))
    finally: conn.close()


SESSION = os.path.join(RUN, "k4-pihole-session.json")


def session(fresh=False):
    s = jload(SESSION, {})
    if not fresh and s.get("sid") and s.get("until", 0) > time.time() + 30: return s["sid"]
    pw = password()
    if not pw: raise Refused("no password")
    a = raw("POST", "/api/auth", {"password": pw}).get("session", {})
    if not a.get("valid"): raise Refused("wrong password")
    jsave(SESSION, {"sid": a["sid"], "until": time.time() + (a.get("validity") or 300)}, private=True)
    return a["sid"]


def api(method, path, body=None, stream=None):
    try: return raw(method, path, body, session(), stream)
    except Refused:
        return raw(method, path, body, session(fresh=True), stream)   # the session ran out: once more, signed in again


# ---------- unbound, over ssh ----------

def unbound():
    """{ok, resolves, ms, dnssec, hit, queries, servfail, uptime, why}; ssh with your key (BatchMode)."""
    if FAKE: return jload(os.path.join(FAKE, "unbound.json"), {"ok": False, "why": "no ssh"})
    host = conf()["host"]
    script = ("S=$(sudo -n unbound-control stats_noreset 2>&1) || { echo NOSTATS; echo \"$S\" | head -1; }; echo \"$S\" | grep -E '^total\\.(num\\.(queries|cachehits|cachemiss)|recursion\\.time\\.avg)|^num\\.answer\\.rcode\\.SERVFAIL|^time\\.up';"
              "t0=$(date +%s%N); a=$(dig +short +time=3 +tries=1 @127.0.0.1 -p 5335 example.com A | head -1); echo \"resolve=$a ms=$(( ($(date +%s%N) - t0) / 1000000 ))\";"
              "echo \"sigok=$(dig +time=3 +tries=1 @127.0.0.1 -p 5335 sigok.verteiltesysteme.net A | grep -c 'status: NOERROR')\";"
              "echo \"sigfail=$(dig +time=3 +tries=1 @127.0.0.1 -p 5335 sigfail.verteiltesysteme.net A | grep -c 'status: SERVFAIL')\"")
    try: r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, script], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired): return {"ok": False, "why": "ssh timed out"}
    if r.returncode == 255: return {"ok": False, "nossh": True, "why": "ssh %s with your key didn't work" % host}
    kv = dict(re.findall(r"^([\w.]+)=(\S*)", r.stdout, re.M))
    out = {"resolves": bool(kv.get("resolve")), "ms": int(kv.get("ms") or 0), "dnssec": kv.get("sigok") == "1" and kv.get("sigfail") == "1", "nostats": "NOSTATS" in r.stdout}
    q = float(kv.get("total.num.queries") or 0)
    out.update(queries=int(q), hit=round(100 * float(kv.get("total.num.cachehits") or 0) / q) if q else 0,
               rec_ms=round(1000 * float(kv.get("total.recursion.time.avg") or 0)), servfail=int(float(kv.get("num.answer.rcode.SERVFAIL") or 0)),
               uptime=int(float(kv.get("time.up") or 0)))
    out["ok"] = out["resolves"] and out["dnssec"]
    out["why"] = "" if out["ok"] else ("doesn't resolve" if not out["resolves"] else "DNSSEC validation failing")
    return out


# ---------- tick: the state, the cards ----------

def post(title, body, kind="1", acts="open:Open", app="Pi-hole", tag="", stays=False, quote=""):
    """A card (the PiholeNotify board): kind 1, warn or done; tag the chip (OFF, DOWN, ON…); stays: until handled."""
    if FAKE:
        with open(os.path.join(FAKE, "posts.log"), "a") as f: f.write("%s | %s | %s\n" % (title, body, kind))
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import k4host
    k4host.post("\t".join(["post", "0", app, field(title), field(body), kind, "-1", "0" if stays else "-1", tag, "", field(quote), acts, "%s card" % FRONT]))


def fmt_n(n): return "{:,}".format(int(n or 0)).replace(",", " ")
def hhmm(t): return time.strftime("%H:%M", time.localtime(t or 0))
def fp_short(fp): return ":".join(fp[i:i + 2] for i in range(0, 8, 2)).upper() + ":…:" + ":".join(fp[i:i + 2] for i in range(len(fp) - 8, len(fp), 2)).upper() if fp else ""


def tick():
    old = jload(os.path.join(C, "state.json"), {})
    st = {"at": now(), "state": "ok", "why": ""}
    try:
        st["summary"] = api("GET", "/api/stats/summary")
        st["blocking"] = api("GET", "/api/dns/blocking")
        st["queries"] = api("GET", "/api/queries?length=100").get("queries", [])
        st["clients"] = api("GET", "/api/stats/top_clients?count=5").get("clients", [])
        st["messages"] = api("GET", "/api/info/messages").get("messages", [])
        if now() - old.get("slow_at", 0) > 600 or not old.get("lists"):   # the slow-changing ones every 10 minutes
            st["lists"] = api("GET", "/api/lists").get("lists", [])
            st["domains"] = api("GET", "/api/domains").get("domains", [])
            v = api("GET", "/api/info/version").get("version", {})
            st["version"] = {k: ((v.get(k) or {}).get("local") or {}).get("version", "") for k in ("core", "web", "ftl")}
            st["slow_at"] = now()
        else:
            for k in ("lists", "domains", "version", "slow_at"): st[k] = old.get(k)
        st["fails"] = 0
    except Refused as e: st.update(state="refused", why=str(e))
    except CertChanged as e: st.update(state="certchanged", why="its certificate changed", fp=e.fp)
    except Down as e: st.update(state="down", why=str(e), fails=old.get("fails", 0) + 1)
    st["down_since"] = (old.get("down_since") or now()) if st["state"] == "down" else 0
    b = (st.get("blocking") or {}).get("blocking")
    if b == "disabled" and (old.get("blocking") or {}).get("blocking") != "disabled":
        st["off_at"], st["off_total"] = now(), ((st.get("summary") or {}).get("queries") or {}).get("total", 0)
    elif b == "disabled": st["off_at"], st["off_total"] = old.get("off_at", now()), old.get("off_total", 0)
    if st["state"] != "ok":   # keep the last good picture to show, marked old
        for k in ("summary", "blocking", "queries", "clients", "messages", "lists", "domains", "version"): st.setdefault(k, old.get(k))
    if now() - old.get("unbound_at", 0) >= UNBOUND_EVERY or "unbound" not in old:
        st["unbound"], st["unbound_at"] = unbound(), now()
    else: st["unbound"], st["unbound_at"] = old.get("unbound"), old.get("unbound_at")
    # the messages there already the first time are not news
    st["seen_msgs"] = old.get("seen_msgs") if old else ["%s:%s" % (m.get("id"), m.get("timestamp")) for m in st.get("messages") or []]
    jsave(os.path.join(C, "state.json"), st)
    alerts(old, st)


def alerts(old, st):
    """A card per change, once (the PiholeNotify board)."""
    if not old: return
    host = conf()["host"]
    b, ob = (st.get("blocking") or {}).get("blocking"), (old.get("blocking") or {}).get("blocking")
    if st["state"] == "ok" and old.get("state") == "ok" and b != ob:
        if b == "disabled":
            t = (st.get("blocking") or {}).get("timer")
            post("Ad blocking is off · back on in %d min" % round(t / 60) if t else "Ad blocking is off · until you resume it",
                 "Paused at %s · every device on the network sees ads%s" % (hhmm(st.get("off_at")), " until %s" % hhmm(now() + t) if t else ""), "warn", "resume:Resume,open:Open", tag="OFF", stays=True)
        elif b == "enabled" and ob == "disabled":
            off = max(0, now() - old.get("off_at", now()))
            passed = max(0, ((st.get("summary") or {}).get("queries") or {}).get("total", 0) - old.get("off_total", 0))
            post("Ad blocking is back on", "Off for %d min · %s queries passed unfiltered meanwhile" % (round(off / 60), fmt_n(passed)), "done", tag="ON")
    if st["state"] == "down" and st.get("fails") == 2:
        post("Pi-hole isn’t answering", "%s · no answer since %s · lookups on the network fail until it’s back" % (host, hhmm(st.get("down_since"))), "warn", tag="DOWN", stays=True)
    if st["state"] == "ok" and old.get("state") == "down" and old.get("fails", 0) >= 2:
        since = old.get("down_since") or now()
        post("Pi-hole answers again", "%s · was down for %d min (%s–%s)" % (host, round((now() - since) / 60), hhmm(since), hhmm(now())), "done", tag="BACK")
    if st["state"] == "certchanged" and old.get("state") != "certchanged":
        post("Pi-hole’s certificate changed", "k4 stopped talking to %s until you check the new fingerprint" % host, "warn", tag="CERT", stays=True, quote="SHA-256  " + fp_short(st.get("fp", "")))
    u, ou = st.get("unbound") or {}, old.get("unbound") or {}
    if not u.get("nossh") and not ou.get("nossh") and "ok" in ou and u.get("ok") != ou.get("ok"):
        if u.get("ok"): post("unbound: back", "Resolves and validates again · %d ms" % u.get("ms", 0), "done", app="unbound", tag="OK")
        elif u.get("resolves"): post("unbound: DNSSEC validation failing", "Lookups still resolve, but answers aren’t verified · a broken-signature test domain resolved", "warn", app="unbound", tag="DNSSEC", stays=True)
        else: post("unbound: not resolving", "Pi-hole has no resolver behind it · lookups fail · Restart in the Pi-hole popup", "warn", app="unbound", tag="DOWN", stays=True)
    g = ((st.get("summary") or {}).get("gravity") or {}).get("last_update") or 0
    if g and now() - g > 14 * 86400 and now() - old.get("gravity_warned", 0) > 86400:
        post("Pi-hole’s adlists are %d days old" % ((now() - g) // 86400), "Gravity last ran %s · new ad domains aren’t blocked yet" % time.strftime("%a %-d %b", time.localtime(g)), "warn"); st["gravity_warned"] = now()
    else: st["gravity_warned"] = old.get("gravity_warned", 0)
    seen = set(old.get("seen_msgs", []))
    for m in st.get("messages") or []:
        k = "%s:%s" % (m.get("id"), m.get("timestamp"))
        if k in seen: continue
        seen.add(k)
        if old.get("seen_msgs") is not None: post("Pi-hole: %s" % (m.get("type") or "message").replace("_", " ").lower(), (m.get("plain") or "") + " · from Pi-hole’s own messages", "warn")
    st["seen_msgs"] = sorted(seen)[-200:]
    jsave(os.path.join(C, "state.json"), st)


# ---------- what the page, the bar and the launcher show ----------

def state(): return jload(os.path.join(C, "state.json"), {})


def mmss(s): s = int(s or 0); return "%d:%02d" % (s // 60, s % 60)


def ago(t):
    s = int(now() - (t or 0))
    return "just now" if s < 60 else "%d min ago" % (s // 60) if s < 3600 else "%d h ago" % (s // 3600) if s < 86400 else "%d d ago" % (s // 86400)


def blocking(st):
    """(on, seconds left while paused) as of now: the timer counts down from the tick."""
    b = st.get("blocking") or {}
    left = b.get("timer")
    if left: left = max(0, int(left - (now() - st.get("at", now()))))
    return b.get("blocking") != "disabled" or (b.get("timer") and left == 0), left


def setup_status():
    c = conf()
    if not password(): return "nopassword"
    st = state()
    if st.get("state") == "refused": return "refused"
    if st.get("state") == "certchanged": return "certchanged"
    return "ok"


FLASH = os.path.join(C, "flash.json")   # a right click's feedback: {"kind": "off|on|no", "until": t}


def bar_json():
    """The bar item (the KPiholeBar board): quiet when fine, yellow OFF and a countdown while paused,
    a red block only for DNS down, red text for DNSSEC and a changed certificate; hidden until set up."""
    st = state()
    if not st or setup_status() == "nopassword": return {}
    f = jload(FLASH, {})
    if f.get("until", 0) > time.time():
        return {"shape": "shield-off", "text": "paused 5 min", "icon_tone": "yellow", "text_tone": "yellow", "wash": "yellow"} if f["kind"] == "off" else \
               {"shape": "shield-on", "text": "blocking on", "icon_tone": "green", "text_tone": "green", "wash": "green"} if f["kind"] == "on" else \
               {"shape": "shield-broken", "text": "can’t reach it", "class": "critical"}
    on, left = blocking(st)
    q = (st.get("summary") or {}).get("queries") or {}
    pc = q.get("percent_blocked") or 0
    u = st.get("unbound") or {}
    uok = "ok" if u.get("ok") else ("not watched" if u.get("nossh") or not u else ("DNSSEC failing" if u.get("resolves") else "not resolving"))
    if st.get("state") == "certchanged":
        return {"shape": "shield-broken", "text": "cert", "icon_tone": "red", "text_tone": "red", "tooltip": "Pi-hole’s certificate changed · click to check it"}
    if (st.get("state") == "down" and st.get("fails", 0) >= 2) or (u and not u.get("nossh") and u.get("resolves") is False):
        tip = "Pi-hole not answering since %s · unbound %s" % (hhmm(st.get("down_since")), uok) if st.get("state") == "down" else "unbound isn’t resolving · Pi-hole has no resolver"
        return {"shape": "shield-broken", "text": "DNS down", "class": "critical", "tooltip": tip}
    if u and not u.get("nossh") and u.get("resolves") and not u.get("dnssec"):
        return {"shape": "shield-unsafe", "text": "DNSSEC", "icon_tone": "red", "text_tone": "red", "tooltip": "%s queries · %.1f %% blocked · unbound: DNSSEC failing" % (fmt_n(q.get("total")), pc)}
    if not on:
        if left: return {"shape": "shield-off", "text": "OFF %s" % mmss(left), "icon_tone": "yellow", "text_tone": "yellow", "minw": 86, "tooltip": "Blocking off · back on at %s · right click resumes" % hhmm(time.time() + left)}
        return {"shape": "shield-off", "text": "OFF", "icon_tone": "yellow", "text_tone": "yellow", "tooltip": "Blocking off until you resume · right click resumes"}
    return {"shape": "shield-on", "text": "%d%%" % round(pc), "tooltip": "%s queries today · %.1f %% blocked · unbound %s" % (fmt_n(q.get("total")), pc, uok)}


def bar(follow=False):
    """One line, or (follow) a line whenever it changes: every second while paused, quickly during a flash."""
    if not follow: print(json.dumps(bar_json(), ensure_ascii=False)); return
    last = None
    while True:
        line = json.dumps(bar_json(), ensure_ascii=False)
        if line != last: print(line, flush=True); last = line
        st = state()
        f = jload(FLASH, {})
        time.sleep(0.2 if f.get("until", 0) > time.time() - 1 else (1 if not blocking(st)[0] else 3))


def toggle():
    """The bar's right click: pause 5 min, or resume while paused; says so on the item for 1.5 s."""
    st = state()
    on, _ = blocking(st)
    kind = "no"
    try:
        if st.get("state") in ("down", "certchanged") or setup_status() != "ok": raise Down("not answering")
        if on: api("POST", "/api/dns/blocking", {"blocking": False, "timer": 300}); kind = "off"
        else: api("POST", "/api/dns/blocking", {"blocking": True, "timer": None}); kind = "on"
    except (Down, Refused, CertChanged): kind = "no"
    jsave(FLASH, {"kind": kind, "until": time.time() + 1.5})
    if kind != "no":
        try: tick()
        except Exception: pass


def page():
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    rid = lambda act: b64("k4-pihole run " + b64(act))
    me = shlex.quote(FRONT)
    out = []
    def row(label, act, meta="", flags="", stay=True):
        out.append("A\t%s\t%s\t%s\t\t%s" % (rid(act), field(label), field(meta), ("stay;" + flags if stay else flags).strip(";")))
    c = conf()
    sst = setup_status()
    st = state()
    if sst == "nopassword" or sst == "refused":
        out.append("D\tPi-hole on %s · ads blocked for the whole network\tnot connected\tSearch Pi-hole…" % field(c["host"]))
        out.append("Y\t↑↓\tStep\t↵\tDo it\t⌃V\tPaste\t⌫\tBack")
        out.append("N\t%s\tPi-hole’s web page › Settings › Web interface / API › Configure app password: copy it and paste it here. It stays in the keyring; your login password stays yours.\t%s\t"
                   % ("Pi-hole refused the app password" if sst == "refused" else "Connect your Pi-hole", "yellow" if sst == "refused" else "accent"))
        row("Open Pi-hole’s settings", "bg xdg-open https://%s/admin/settings/api" % c["host"], "the web page", "mark=1;markc=accent")
        row("Paste the app password", "%s setup-password" % me, "kept in the keyring", "mark=2;markc=accent;input=Pi-hole app password|Settings › Web interface / API › app password|password")
        print("\n".join(out)); return
    if sst == "certchanged":
        out.append("D\tPi-hole on %s\tcertificate changed\tSearch Pi-hole…" % field(c["host"]))
        out.append("N\tPi-hole’s certificate changed\tk4 stopped talking to it. If you renewed Pi-hole (it renews its own certificate once a year), trust the new one. If you didn’t, something else may be answering as %s.\tyellow\t" % field(c["host"]))
        row("Trust the new certificate", "%s trust" % me, "SHA-256 %s…" % (st.get("fp") or "")[:16], "mark=!;markc=yellow")
        print("\n".join(out)); return
    on, left = blocking(st)
    s = st.get("summary") or {}
    q = s.get("queries") or {}
    g = s.get("gravity") or {}
    u = st.get("unbound") or {}
    down = st.get("state") == "down"
    count = "DOWN" if down else ("on" if on else "off · %s" % (mmss(left) if left else "until resumed"))
    out.append("D\tPi-hole on %s · %s queries today · %d%% blocked · %d clients\t%s\tFilter queries…" % (field(c["host"]), q.get("total", "?"), round(q.get("percent_blocked") or 0), (s.get("clients") or {}).get("active", 0), count))
    out.append("Y\t↑↓\tMove\t↵\tRun · allow\t⌃B\tBlock\tDel\tRemove\ttype\tFilter\t⌫\tBack")
    if down: out.append("N\tPi-hole isn’t answering\t%s · showing what it said %s\tyellow\t" % (field(st.get("why")), ago(st.get("at"))))
    out.append("H\tBlocking\t")
    if on:
        for mins in (5, 30): row("Pause for %d minutes" % mins, "%s pause %d" % (me, mins * 60), "the whole network", "mark=‖;markc=accent")
        row("Pause until resumed", "%s pause 0" % me, "", "mark=‖;markc=dim")
    else:
        row("Resume blocking", "%s resume" % me, "back on %s" % ("in " + mmss(left) if left else "only when resumed"), "mark=▶;markc=yellow;chip=OFF;chipc=yellow")
    out.append("H\tunbound\t%s" % ("ok" if u.get("ok") else ""))
    if u.get("nossh"):
        row("Let k4 into %s with your key" % c["host"], ":", "ssh-copy-id kr4nk@%s · then k4-pihole setup-host" % c["host"], "mark=?;markc=yellow;dim", stay=False)
    elif u:
        if u.get("nostats"): row("Allow k4 to read unbound’s stats", ":", "run k4-pihole setup-host once (sudo asks there)", "mark=?;markc=yellow;dim", stay=False)
        row("unbound %s" % ("resolves · DNSSEC validates" if u.get("ok") else u.get("why") or "?"), ":", "%d ms%s" % (u.get("ms", 0), " · checked %s" % ago(st.get("unbound_at"))),
            "mark=%s;markc=%s;l2=%s;l2c=dim" % ("✓" if u.get("ok") else "!", "green" if u.get("ok") else "red",
            flag("cache hits %d%% · recursion %d ms · %d SERVFAIL · up %s" % (u.get("hit", 0), u.get("rec_ms", 0), u.get("servfail", 0), "%dd" % (u.get("uptime", 0) // 86400)))), stay=False)
        row("Restart unbound", "%s restart-unbound" % me, "sudo systemctl restart unbound", "mark=↻;markc=%s" % ("accent" if not u.get("ok") else "dim"))
    qs = st.get("queries") or []
    out.append("H\tRecent queries\t%d" % len(qs))
    for x in qs:
        d = x.get("domain") or ""
        blocked = x.get("status") in BLOCKED
        cl = (x.get("client") or {})
        who = cl.get("name") or cl.get("ip") or ""
        when = time.strftime("%H:%M:%S", time.localtime(x.get("time") or 0))
        f = "mark=%s;markc=%s;l2=%s;l2c=dim;find=%s" % ("⊘" if blocked else "·", "red" if blocked else "dim", flag("%s · %s%s" % (who, when, " · %s" % WHY.get(x.get("status"), x.get("status", "").lower()) if blocked else "")), flag("%s %s" % (d, who)))
        if blocked: row(d, "%s allow %s" % (me, shlex.quote(d)), "↵ allows", f + ";metac=red")
        else: row(d, ":", x.get("type") or "", f + ";k^b=" + rid("%s block %s" % (me, shlex.quote(d))) + ";dim", stay=False)
    cs = st.get("clients") or []
    if cs:
        out.append("H\tTop clients today\t")
        for x in cs: row(x.get("name") or x.get("ip") or "?", ":", "%d queries" % x.get("count", 0), "mark=◦;markc=dim;l2=%s;l2c=dim" % flag(x.get("ip") if x.get("name") else ""), stay=False)
    ls = [l for l in (st.get("lists") or []) if l.get("type", "block") == "block"]
    out.append("H\tAdlists\t%d" % len(ls))
    row("Update gravity", "%s gravity" % me, "%s domains · updated %s" % ("{:,}".format(g.get("domains_being_blocked") or 0).replace(",", " "), ago(g.get("last_update")) if g.get("last_update") else "never"), "mark=↻;markc=accent")
    for l in ls:
        row(re.sub(r"^https?://", "", l.get("address", "")), "%s list-toggle %s" % (me, shlex.quote(l.get("address", ""))), "{:,}".format(l.get("number") or 0).replace(",", " ") + " domains",
            "toggle=%s;l2=%s;l2c=dim" % ("on" if l.get("enabled") else "off", flag(l.get("comment") or "")))
    ds = st.get("domains") or []
    if ds:
        out.append("H\tYour allow and deny entries\t%d" % len(ds))
        for d in ds:
            allow = d.get("type") == "allow"
            row(d.get("domain"), ":", "%s%s" % ("allowed" if allow else "blocked", " · regex" if d.get("kind") == "regex" else ""),
                "mark=%s;markc=%s;del=%s" % ("✓" if allow else "⊘", "green" if allow else "red", rid("%s unlist %s %s %s" % (me, d.get("type"), d.get("kind", "exact"), shlex.quote(d.get("domain", ""))))), stay=False)
    v = st.get("version") or {}
    out.append("H\tMore\t")
    row("Open Pi-hole’s web page", "bg xdg-open https://%s/admin/" % c["host"], "Pi-hole %s · FTL %s" % (v.get("core", "?"), v.get("ftl", "?")), "mark=↗;markc=dim", stay=False)
    row("Look now", "%s tick" % me, "checked %s · every minute" % ago(st.get("at")), "mark=↻;markc=dim")
    print("\n".join(out))


def window_data():
    """The KPihole window's lines (k4 --pihole, src/pihole.odin):
      S state left host sub     state ok|down|setup|cert; left: blocking's seconds left (-1 off until
                                resumed, 0 on); sub: the versions, or since when it's down
      N total blocked percent active clients     today's numbers
      U kind ms hit rec_ms servfail uptime        unbound: ok, dnssec, noresolve, nossh, nostats
      Q domain blocked tag device time type      the last 100 queries, newest first (tag: ADLIST, REGEX,
                                                 YOUR DENY, YOUR ALLOW, CACHED or -)
      C name count · L address name count on · G domains ago lists_on · E type kind domain note
      F label when fingerprint                   (the certificate setup: TRUSTED and NEW)
      R / L                                      the runner and the loader"""
    c = conf()
    st = state()
    sst = setup_status()
    host = c["host"]
    if sst in ("nopassword", "refused"):
        print("S\tsetup\t0\t%s\t%s" % (host, "Pi-hole refused the app password · paste a new one" if sst == "refused" else "%s · found on the network" % host))
    elif sst == "certchanged":
        print("S\tcert\t0\t%s\t%s · k4 stopped talking to it at %s" % (host, host, hhmm(st.get("cert_at") or st.get("at"))))
        print("F\tTRUSTED\tsince %s\tSHA-256  %s" % (c.get("pinned_on", "setup"), ":".join(c.get("pin", "")[i:i + 2] for i in range(0, 64, 2)).upper()[:95]))
        print("F\tNEW\tseen %s\tSHA-256  %s" % (hhmm(st.get("at")), ":".join(st.get("fp", "")[i:i + 2] for i in range(0, 64, 2)).upper()[:95]))
    else:
        on, left = blocking(st)
        v = st.get("version") or {}
        down = st.get("state") == "down" and st.get("fails", 0) >= 1
        sub = "no answer since %s · retrying every minute" % hhmm(st.get("down_since")) if down else "Pi-hole %s · FTL %s · Web %s" % (v.get("core", "?"), v.get("ftl", "?"), v.get("web", "?"))
        print("S\t%s\t%d\t%s\t%s" % ("down" if down else "ok", 0 if on else (left or -1), host, sub))
    s_ = st.get("summary") or {}
    q = s_.get("queries") or {}
    cl = s_.get("clients") or {}
    print("N\t%d\t%d\t%.1f\t%d\t%d" % (q.get("total") or 0, q.get("blocked") or 0, q.get("percent_blocked") or 0, cl.get("active") or 0, cl.get("total") or 0))
    u = st.get("unbound") or {}
    kind = "nossh" if (not u or u.get("nossh")) else "noresolve" if not u.get("resolves") else "dnssec" if not u.get("dnssec") else "nostats" if u.get("nostats") else "ok"
    print("U\t%s\t%d\t%d\t%d\t%d\t%d" % (kind, u.get("ms", 0), u.get("hit", 0), u.get("rec_ms", 0), u.get("servfail", 0), u.get("uptime", 0)))
    ds = st.get("domains") or []
    allowed = {d.get("domain") for d in ds if d.get("type") == "allow" and d.get("kind") == "exact"}
    for x in st.get("queries") or []:
        d = x.get("domain") or ""
        blocked = x.get("status") in BLOCKED
        tag = {"GRAVITY": "ADLIST", "GRAVITY_CNAME": "ADLIST", "REGEX": "REGEX", "REGEX_CNAME": "REGEX", "DENYLIST": "YOUR DENY", "DENYLIST_CNAME": "YOUR DENY"}.get(x.get("status"), "BLOCKED") if blocked \
              else ("YOUR ALLOW" if d in allowed else "CACHED" if str(x.get("status", "")).startswith("CACHE") else "-")
        cl_ = x.get("client") or {}
        print("Q\t%s\t%d\t%s\t%s\t%s\t%s" % (field(d), 1 if blocked else 0, tag, field((cl_.get("name") or cl_.get("ip") or "?").split(".")[0] if cl_.get("name") else cl_.get("ip") or "?"),
                                          time.strftime("%H:%M:%S", time.localtime(x.get("time") or 0)), field(x.get("type") or "")))
    for x in st.get("clients") or []:
        print("C\t%s\t%d" % (field((x.get("name") or "").split(".")[0] or x.get("ip") or "?"), x.get("count") or 0))
    ls = [l for l in (st.get("lists") or []) if l.get("type", "block") == "block"]
    for l in ls:
        print("L\t%s\t%s\t%d\t%d" % (field(l.get("address")), field(l.get("comment") or re.sub(r"^https?://", "", l.get("address", ""))), l.get("number") or 0, 1 if l.get("enabled") else 0))
    g = s_.get("gravity") or {}
    print("G\t%d\t%s\t%d" % (g.get("domains_being_blocked") or 0, ago(g.get("last_update")) if g.get("last_update") else "never", sum(1 for l in ls if l.get("enabled"))))
    for d in ds:
        print("E\t%s\t%s\t%s\t%s" % (d.get("type"), d.get("kind", "exact"), field(d.get("domain")), field(d.get("comment") or "-")))
    print("R\t%s\nL\t%s window-data" % (FRONT, FRONT))


def find_rows():
    """The launcher's Pi-hole rows (the Main board): pause 5/30 min (or resume), the status, update gravity."""
    if setup_status() != "ok": return
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    st = state()
    on, left = blocking(st)
    q = (st.get("summary") or {}).get("queries") or {}
    g = (st.get("summary") or {}).get("gravity") or {}
    u = st.get("unbound") or {}
    rows = []
    if on:
        for mins in (5, 30): rows.append(("Pause ad blocking · %d min" % mins, "%s pause %d" % (me, mins * 60), "Pi-hole · back on %s" % hhmm(time.time() + mins * 60), "pause ads adblock blocking %d min" % mins))
    else: rows.append(("Resume ad blocking", "%s resume" % me, "Pi-hole · off%s" % (" · back on " + hhmm(time.time() + left) if left else ""), "resume ads adblock blocking"))
    rows.append(("Pi-hole · %s · %.1f%% today" % ("blocking on" if on else "blocking off", q.get("percent_blocked") or 0), "bg %s window" % me, "unbound %s · open" % ("ok" if u.get("ok") else "not watched" if u.get("nossh") else "failing"), "status kr4nkenhole dns unbound"))
    rows.append(("Update gravity", "bg %s gravity" % me, "Pi-hole · %s domains · %s" % (fmt_n(g.get("domains_being_blocked")), ago(g.get("last_update")) if g.get("last_update") else "never"), "update gravity adlists"))
    for label, act, meta, words in rows:
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=70;tag=Pi-hole;icon=󰒃;find=pihole pi-hole %s" % (b64("k4-pihole run " + b64(act)), label, meta, words))


# ---------- changes ----------

def changed(msg):
    say(msg)
    try: tick()
    except Exception: pass


def main(argv):
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    try:
        if cmd == "tick": tick()
        elif cmd == "page": page()
        elif cmd == "bar": bar("--follow" in rest)
        elif cmd == "toggle": toggle()
        elif cmd == "window-data": window_data()
        elif cmd == "restart-ftl":
            if FAKE: open(os.path.join(FAKE, "log"), "a").write("ssh restart pihole-FTL\n"); return say("Pi-hole’s FTL restarted")
            r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", conf()["host"], "sudo -n systemctl restart pihole-FTL"], capture_output=True, text=True, timeout=60)
            changed("Pi-hole’s FTL restarted" if r.returncode == 0 else "Couldn’t restart FTL · k4-pihole setup-host allows it")
        elif cmd == "keep-cert": say("Kept the old certificate · still not talking to %s" % conf()["host"])
        elif cmd == "set-host":
            h = (os.environ.get("K4_INPUT") or (rest[0] if rest else "")).strip()
            if not h: return say("Type the host first")
            c = conf(); c["host"] = h; c.pop("pin", None); jsave(CONF, c); say("Pi-hole on %s · paste its app password" % h)
        elif cmd == "find": find_rows()
        elif cmd == "status": say(setup_status())
        elif cmd == "pause":
            secs = int(rest[0]) if rest else 300
            api("POST", "/api/dns/blocking", {"blocking": False, "timer": secs or None})
            changed("Ad blocking paused%s" % (" for %d min" % (secs // 60) if secs else " until you resume it"))
        elif cmd == "resume": api("POST", "/api/dns/blocking", {"blocking": True, "timer": None}); changed("Ad blocking is back on")
        elif cmd in ("allow", "block") and rest:
            d = rest[0].strip().lower().rstrip(".")
            if not re.fullmatch(r"[a-z0-9_.-]+\.[a-z0-9-]+", d): return say("That isn’t a domain")
            api("POST", "/api/domains/%s/exact" % ("allow" if cmd == "allow" else "deny"), {"domain": d, "comment": "k4", "enabled": True})
            changed("%s %s" % ("Allowed" if cmd == "allow" else "Blocked", d))
        elif cmd == "unlist" and len(rest) >= 3:
            api("DELETE", "/api/domains/%s/%s/%s" % (rest[0], rest[1], urllib.parse.quote(rest[2], safe="")))
            changed("Removed %s" % rest[2])
        elif cmd == "list-toggle" and rest:
            l = next((x for x in state().get("lists") or [] if x.get("address") == rest[0]), None)
            if not l: return say("No such adlist")
            api("PUT", "/api/lists/%s?type=block" % urllib.parse.quote(rest[0], safe=""), {"enabled": not l.get("enabled"), "comment": l.get("comment"), "groups": l.get("groups") or [0]})
            st = state(); st["slow_at"] = 0; jsave(os.path.join(C, "state.json"), st)
            changed("%s · update gravity to apply it" % ("Turned off" if l.get("enabled") else "Turned on"))
        elif cmd == "gravity":
            last = [""]
            def line(s):
                s = re.sub(r"\x1b\[[0-9;]*[A-Za-z]|\[[✓✗i]\]\s*", "", s).strip()
                if s: last[0] = s; say(s)
            api("POST", "/api/action/gravity", stream=line)
            st = state(); st["slow_at"] = 0; jsave(os.path.join(C, "state.json"), st)
            post("Gravity updated", last[0] or "the adlists are fresh", "done")
            changed("Gravity updated")
        elif cmd == "restart-dns": api("POST", "/api/action/restartdns"); changed("Pi-hole’s DNS restarted")
        elif cmd == "restart-unbound":
            if FAKE: open(os.path.join(FAKE, "log"), "a").write("ssh restart unbound\n"); return say("unbound restarted")
            r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", conf()["host"], "sudo -n systemctl restart unbound"], capture_output=True, text=True, timeout=40)
            st = state(); st["unbound_at"] = 0; jsave(os.path.join(C, "state.json"), st)
            changed("unbound restarted" if r.returncode == 0 else "Couldn’t restart unbound · k4-pihole setup-host allows it")
        elif cmd == "setup-password":
            pw = (os.environ.get("K4_INPUT") or "").strip()
            if not pw: return say("Paste the app password first")
            c = conf()
            if not FAKE and not c.get("pin"): c["pin"], c["pinned_on"] = fingerprint(c["host"]), time.strftime("%-d %b"); jsave(CONF, c)   # the first time: this certificate is Pi-hole's
            r = raw("POST", "/api/auth", {"password": pw}).get("session", {})
            if not r.get("valid"): say("Pi-hole refused it"); say("k4:tone red"); return
            if not FAKE: subprocess.run(["k4-secret", "store", "token", "pihole"], input=pw, text=True, capture_output=True, timeout=20)
            jsave(SESSION, {"sid": r["sid"], "until": time.time() + (r.get("validity") or 300)}, private=True)
            changed("Connected to Pi-hole on %s" % c["host"])
        elif cmd == "trust":
            c = conf(); st = state()
            if not st.get("fp"): return say("Nothing to trust")
            c["pin"], c["pinned_on"] = st["fp"], time.strftime("%-d %b"); jsave(CONF, c); changed("Trusted · talking to %s again" % c["host"])
        elif cmd == "card" and rest:   # a card's button: KEY ID
            if rest[0] == "resume": main([argv[0], "resume"])
            elif not FAKE: subprocess.Popen([FRONT, "window"], start_new_session=True)   # Open, or the card itself: the popup
        else: say(__doc__.strip()); return 2
    except Refused as e: say("Pi-hole: %s · Apps › Pi-hole" % e); say("k4:tone yellow")
    except CertChanged: say("Pi-hole’s certificate changed · Apps › Pi-hole"); say("k4:tone yellow")
    except Down as e: say("Pi-hole isn’t answering · %s" % e); say("k4:tone yellow")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
