#!/usr/bin/env python3
"""k4's Parcels (k4-parcels is its front): shipments found in your mail, and numbers added by hand.

Every 15 minutes (k4-parcels.timer) it searches the last 30 days of Gmail (k4-mail's sign-in) and
the IMAP accounts k4 mail reads (aerc's, read-only: nothing is marked read) for carrier mails:
PostNord, DHL, Budbee, Instabox, Bring, Schenker, Airmee, Early Bird. Each mail gives a number, a
status, maybe a pickup point, its code and last day, a delivery window and the shop. With a key,
PostNord and DHL are also asked directly (k4-secret store token postnord|dhl). A status change
gives a card. State: ~/.local/state/k4/parcels.json (K4_PARCELS_STATE in tests).

  parcels.py sync [--quiet]          look again (mail, then the carriers)
  parcels.py add NUMBER [NAME] | archive KEY | copy KEY | open KEY
  parcels.py info | bar | find | guess NUMBER | scan   (scan: counts only, nothing saved or posted)

Tests: K4_PARCELS_FAKE=DIR: mails are DIR/*.eml, live answers DIR/<carrier>-<number>.json, cards go to
DIR/posts.log; K4_PARCELS_NOW pins the clock.
"""
import datetime as dt, email, email.policy, email.utils, glob, json, os, re, shlex, shutil, subprocess, sys, time, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
SHARE = os.path.dirname(os.path.abspath(__file__))
STATE = os.environ.get("K4_PARCELS_STATE") or os.path.join(HOME, ".local/state/k4")
FAKE = os.environ.get("K4_PARCELS_FAKE")
FRONT = os.environ.get("K4_PARCELS_FRONT") or shutil.which("k4-parcels") or "k4-parcels"
DAYS = 30
KEEP_DELIVERED = 3 * 86400
STALE = 14 * 86400

CARRIERS = {   # key: (name, sender words, tracking link)
    "postnord": ("PostNord", ["postnord"], "https://tracking.postnord.com/se/?id={n}"),
    "dhl": ("DHL", ["dhl"], "https://www.dhl.com/se-sv/home/tracking.html?tracking-id={n}"),
    "budbee": ("Budbee", ["budbee"], "https://tracking.budbee.com/{n}"),
    "instabox": ("Instabox", ["instabox"], "https://track.instabox.io/{n}"),
    "bring": ("Bring", ["bring"], "https://tracking.bring.se/tracking/{n}"),
    "schenker": ("Schenker", ["schenker", "dbschenker"], "https://www.dbschenker.com/app/tracking-public/?refNumber={n}"),
    "airmee": ("Airmee", ["airmee"], "https://track.airmee.com/{n}"),
    "earlybird": ("Early Bird", ["earlybird"], "https://earlybird.se/tracking/{n}"),
}
ORDER = {"problem": 0, "ready": 1, "out": 2, "transit": 3, "registered": 4, "delivered": 5}

# (status, phrases) in the order they win: a mail saying "delivered" and "on its way" is delivered
STATUS = [
    ("delivered", r"har levererats|är levererat|levererad till|levererades|has been delivered|was delivered|\bdelivered\b|har hämtats|has been collected|picked up"),
    ("problem", r"försenat|förseningar|kunde inte levereras|kunde inte delas ut|returneras|skickas tillbaka|could not be delivered|delayed|returned to sender|delivery failed|adressproblem"),
    ("ready", r"kan hämtas|redo att hämtas|finns att hämta|väntar på dig|har kommit fram till|ready for (?:pick-?up|collection)|ready to be (?:picked up|collected)|in (?:your|the) (?:parcel )?locker|i ditt paketskåp|hämta ditt paket"),
    ("out", r"ute för leverans|ute på utkörning|levereras idag|kommer idag|på väg till dig idag|out for delivery|delivered today|arriving today"),
    ("transit", r"är på väg|har skickats|är skickat|har avsänts|har lämnat|in transit|has (?:been )?shipped|on (?:its|the) way|has left|har tagits emot"),
    ("registered", r"har registrerats|vi har fått information|we have received information|has been registered|förbereds"),
]
NUMBER_LABELS = r"(?:spårningsnummer|spårnings-?id|kollinummer|kolli-?id|försändelse-?id|sändnings-?id|sändningsnummer|tracking (?:number|id|code)|shipment (?:number|id)|waybill)"


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def now(): return float(os.environ.get("K4_PARCELS_NOW") or time.time())


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w") as f: json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(p + ".tmp", p)


def load(): return jload(os.path.join(STATE, "parcels.json"), {"parcels": {}, "mails": {}})
def save(s): jsave(os.path.join(STATE, "parcels.json"), s)


# ---------- numbers ----------

def guess(number):
    """The carrier a number's shape says ("" when it could be anyone's)."""
    n = re.sub(r"\s+", "", number).upper()
    if re.fullmatch(r"[A-Z]{2}\d{9}SE", n) or re.fullmatch(r"00\d{16,18}", n) or re.fullmatch(r"\d{9}SE", n): return "postnord"
    if re.fullmatch(r"IB[A-Z0-9]{6,}", n): return "instabox"
    if re.fullmatch(r"EB\d{6,}", n): return "earlybird"
    if re.fullmatch(r"BB[A-Z0-9]{8,}", n): return "budbee"
    if re.fullmatch(r"JJD\d{8,}|JVGL\d{8,}|GM\d{16,}|\d{10}|[A-Z]{3}\d{7}", n): return "dhl"
    if re.fullmatch(r"(?:CRAY|TESTP)\w+|370\d{14}|70\d{15}", n): return "bring"
    if re.fullmatch(r"[A-Z0-9]{8}", n) and re.search(r"[A-Z]", n) and re.search(r"\d", n): return "budbee"
    return ""


def link_of(carrier, number):
    c = CARRIERS.get(carrier)
    return c[2].format(n=urllib.parse.quote(number)) if c and number else ""


# ---------- reading a mail ----------

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dec": 12}


def date_in(text, sent):
    """"2026-11-06", "6 november", "6/11" → unix (the end of that day), else 0."""
    y = dt.datetime.fromtimestamp(sent).year
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    try:
        if m: d = dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            m = re.search(r"(\d{1,2})\s+([a-zåäö]{3})[a-zåäö]*\.?(?:\s+(\d{4}))?", text, re.I)
            if m and m.group(2).lower()[:3] in MONTHS: d = dt.datetime(int(m.group(3) or y), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
            else:
                m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", text)
                if not m: return 0
                d = dt.datetime(y, int(m.group(2)), int(m.group(1)))
    except ValueError: return 0
    return int((d + dt.timedelta(hours=23, minutes=59)).timestamp())


def unwrap(url):
    """A click-tracking redirect (Postmark's track.pstmrk.it/3s/<the url, encoded>/…) → the url it leads to."""
    if "pstmrk.it" in url or "%2F" in url[:80]:
        for seg in urllib.parse.urlparse(url).path.split("/"):
            t = urllib.parse.unquote(seg)
            if "." in t and "/" in t: return t if t.startswith("http") else "https://" + t
    return url


def carrier_of(sender, text):
    s = sender.lower()
    for k, (_, words, _) in CARRIERS.items():
        if any(w in s for w in words): return k
    t = text.lower()
    for k, (_, words, _) in CARRIERS.items():
        if any(w + "." in t or w + " " in t for w in words): return k
    return ""


def parse_mail(sender, subject, text, sent):
    """One carrier mail → {carrier, number, status, code, point, last, window, shop, link} (whatever it says), or None."""
    full = "%s\n%s" % (subject, text)
    carrier = carrier_of(sender, full)
    num = ""
    m = re.search(NUMBER_LABELS + r"\s*(?:är|is|:|#|nr\.?)?\s*:?\s*([A-Z0-9][A-Z0-9 -]{6,30}[A-Z0-9])", full, re.I)
    if m: num = re.sub(r"[\s-]", "", m.group(1)).upper()
    if not num:
        for pat in (r"\b[A-Z]{2}\d{9}SE\b", r"\b00370\d{13,15}\b", r"\bJJD\d{8,}\b", r"\bJVGL\d{8,}\b"):
            m = re.search(pat, full)
            if m: num = m.group(0); break
    link = ""
    for l in (unwrap(x) for x in re.findall(r"https?://[^\s\"'<>)\]]+", full)):
        u = urllib.parse.urlparse(l)
        if re.search(r"track|spar|spår|sparning|tracking", u.netloc + u.path, re.I) and not re.search(r"pstmrk|sendgrid|mailchimp|list-manage|click\.", u.netloc, re.I):
            link = l.rstrip(".,"); break
    if not num and link:   # the id in the tracking link: ?a= / ?id= / …, else its last part (Budbee, Instabox)
        u = urllib.parse.urlparse(link)
        qs = urllib.parse.parse_qs(u.query)
        for k in ("a", "id", "trackingNumber", "tracking-id", "trackingId", "parcel", "shipment", "q", "ref", "refNumber"):
            if qs.get(k) and re.fullmatch(r"[A-Za-z0-9]{6,40}", qs[k][0]): num = qs[k][0].upper(); break
        if not num:
            m = re.search(r"/([A-Za-z0-9]{6,40})/?$", u.path)
            if m and re.search(r"\d", m.group(1)): num = m.group(1).upper()
    if not carrier and num: carrier = guess(num)
    if not carrier or not num: return None
    status = ""
    low = full.lower()
    for st, pat in STATUS:
        if re.search(pat, low): status = st; break
    out = {"carrier": carrier, "number": num, "status": status or "registered", "at": sent, "link": link or link_of(carrier, num)}
    m = re.search(r"(?:hämtkod|upphämtningskod|utlämningskod|pick-?up code|collection code|\bpin(?:-?kod)?|\bkod)\s*(?:är|is)?\s*:?\s*([A-Z0-9]{4,8})\b", full, re.I)
    if m: out["code"] = m.group(1).upper()
    m = re.search(r"(?:utlämningsställe|ombud|hämtställe|paketskåp|pick-?up point|service point|collect (?:it )?at)\s*:?\s*([^\n]{3,80})", full, re.I)
    if m: out["point"] = re.split(r"\s{2,}|, *\d{3} ?\d{2}", m.group(1).strip(" :."))[0][:60]
    m = re.search(r"(?:hämtas senast|senast|last day|collect (?:it )?(?:by|before)|until|t\.?o\.?m\.?)\s*:?\s*([^\n]{3,40})", full, re.I)
    if m and status in ("ready", ""):
        d = date_in(m.group(1), sent)
        if d: out["last"] = d
    m = re.search(r"(?:mellan|between|kl\.?|klockan)?\s*\b([01]?\d|2[0-3])[:.]?([0-5]\d)?\s*[-–]\s*([01]?\d|2[0-3])[:.]?([0-5]\d)?\b", full)
    if m and status == "out": out["window"] = "%s–%s" % (m.group(1), m.group(3))
    m = re.search(r"(?:paket|order|beställning|försändelse|package|parcel|shipment)\s+(?:från|from)\s+([A-ZÅÄÖ][\w&.' -]{1,40}?)(?:\s+(?:är|has|is|har|kan|will)\b|[.,!\n])", full)
    if m: out["shop"] = m.group(1).strip()
    else:
        name = email.utils.parseaddr(sender)[0]
        if name and carrier not in name.lower(): out["shop"] = name
    return out


# ---------- the mailboxes ----------

QUERY_WORDS = sorted({w for _, words, _ in CARRIERS.values() for w in words})


def gmail_mails(known, query=None, limit=60):
    """(id, sender, subject, text, sent) of carrier mails in Gmail (or QUERY's), new ones fetched."""
    if FAKE: return []
    sys.path.insert(0, SHARE)
    try:
        import gmail as G
        if not G.connected(): return []
        q = query or "newer_than:%dd (%s OR subject:(spårningsnummer OR kollinummer OR \"tracking number\" OR hämtas OR paket))" % (DAYS, " OR ".join("from:" + w for w in QUERY_WORDS))
        ids = [m["id"] for m in G.api("GET", "/messages", query={"q": q, "maxResults": limit}).get("messages", [])]
    except Exception: return []
    out = []
    for i in ids:
        k = "gmail:" + i
        if k in known: continue
        try:
            m = G.api("GET", "/messages/" + i, query={"format": "full"})
            h = G.headers(m.get("payload", {}))
            text, _ = G.body_of(m.get("payload", {}))
            out.append((k, h.get("from", ""), h.get("subject", ""), text, int(m.get("internalDate", "0")) / 1000))
        except Exception: continue
    return out


def imap_mails(known, words=None, days=None, limit=60):
    """The same from the IMAP accounts (INBOX, read-only: BODY.PEEK keeps them unread); WORDS=[] all mail."""
    if FAKE: return []
    sys.path.insert(0, SHARE)
    try:
        import mailimap as M
        if getattr(M, "G", None) is None:   # (mailimap reads HTML through gmail.py's helpers)
            import gmail
            M.G = gmail
    except Exception: return []
    out = []
    since = (dt.date.today() - dt.timedelta(days=days or DAYS)).strftime("%d-%b-%Y")
    words = QUERY_WORDS if words is None else words
    for a in M.accounts():
        try:
            c = M.connect(a)
            c.select(M.q(a.get("inbox") or "INBOX"), readonly=True)
            uids = set()
            for w in words or [None]:
                typ, data = c.uid("SEARCH", None, "SINCE", since, *(("FROM", w) if w else ()))
                if typ == "OK" and data and data[0]: uids |= set(data[0].split())
            for u in sorted(uids, key=int)[-limit:]:
                k = "imap:%s:%s" % (a["id"], u.decode())
                if k in known: continue
                typ, data = c.uid("FETCH", u, "(BODY.PEEK[] INTERNALDATE)")
                raw = next((x[1] for x in data if isinstance(x, tuple)), b"")
                msg = M.parse_raw(a, "INBOX", u.decode(), raw, "", 0)
                sent = email.utils.parsedate_to_datetime(email.message_from_bytes(raw).get("Date")).timestamp() if raw else now()
                out.append((k, msg["from"], msg["subject"], msg["body"] + "\n" + msg.get("quoted", ""), sent))
            c.logout()
        except Exception: continue
    return out


def fake_mails(known):
    out = []
    for p in sorted(glob.glob(os.path.join(FAKE, "*.eml"))):
        k = "fake:" + os.path.basename(p)
        if k in known: continue
        with open(p, "rb") as f: m = email.message_from_bytes(f.read(), policy=email.policy.default)
        part = m.get_body(preferencelist=("plain", "html"))
        text = part.get_content() if part else ""
        if part and part.get_content_type() == "text/html": text = re.sub(r"<[^>]+>", " ", text)
        sent = email.utils.parsedate_to_datetime(m["Date"]).timestamp() if m["Date"] else now()
        out.append((k, str(m["From"]), str(m["Subject"]), text, sent))
    return out


# ---------- live status (PostNord, DHL with a key) ----------

def key_of(name):
    if FAKE: return "test"
    r = subprocess.run(["k4-secret", "lookup", "token", name], capture_output=True, text=True, timeout=15)
    return r.stdout.strip() if r.returncode == 0 else ""


def get_json(url, headers=None, fake=""):
    if FAKE:
        p = os.path.join(FAKE, fake + ".json")
        return jload(p, None)
    req = urllib.request.Request(url, headers=dict({"User-Agent": "k4", "Accept": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)


def live(p):
    """A carrier's own answer for a parcel ({} when there is no key or no answer)."""
    try:
        if p["carrier"] == "postnord":
            k = key_of("postnord")
            if not k: return {}
            j = get_json("https://api2.postnord.com/rest/shipment/v5/trackandtrace/findByIdentifier.json?" + urllib.parse.urlencode({"apikey": k, "id": p["number"], "locale": "sv"}),
                         fake="postnord-" + p["number"])
            sh = ((j or {}).get("TrackingInformationResponse", {}).get("shipments") or [{}])[0]
            code = (sh.get("status") or "").upper()
            st = {"DELIVERED": "delivered", "AVAILABLE_FOR_DELIVERY": "ready", "DELAYED": "problem", "STOPPED": "problem", "RETURNED": "problem",
                  "EN_ROUTE": "transit", "INFORMED": "registered", "OTHER": ""}.get(code, "")
            out = {"status": st} if st else {}
            dp = sh.get("deliveryPoint") or {}
            if dp.get("displayName"): out["point"] = dp["displayName"]
            eta = sh.get("estimatedTimeOfArrival") or ""
            if eta: out["eta"] = int(dt.datetime.fromisoformat(eta.replace("Z", "+00:00")).timestamp())
            return out
        if p["carrier"] == "dhl":
            k = key_of("dhl")
            if not k: return {}
            j = get_json("https://api-eu.dhl.com/track/shipments?" + urllib.parse.urlencode({"trackingNumber": p["number"]}), {"DHL-API-Key": k}, fake="dhl-" + p["number"])
            sh = ((j or {}).get("shipments") or [{}])[0]
            code = (sh.get("status") or {}).get("statusCode", "")
            st = {"delivered": "delivered", "transit": "transit", "failure": "problem", "pre-transit": "registered"}.get(code, "")
            out = {"status": st} if st else {}
            desc = ((sh.get("status") or {}).get("description") or "").lower()
            if st == "transit" and re.search(STATUS[3][1], desc): out["status"] = "out"
            if st == "transit" and re.search(STATUS[2][1], desc): out["status"] = "ready"
            eta = sh.get("estimatedTimeOfDelivery") or ""
            if eta: out["eta"] = int(dt.datetime.fromisoformat(eta.replace("Z", "+00:00")).timestamp())
            return out
    except Exception: return {}
    return {}


# ---------- cards ----------

def post(title, body, acts, kind="1", tag="", ident="", code="", stays=False):
    """A card (ParcelNotify): kind 1, warn, wait or done; a pickup code shown large (CODE|carrier)."""
    if FAKE:
        with open(os.path.join(FAKE, "posts.log"), "a") as f: f.write("%s | %s | %s | %s %s%s\n" % (title, body, acts, kind, tag, (" | code " + code) if code else ""))
        return
    line = "\t".join(["post", "0", "Parcels", field(title), field(body), kind, "-1", "0" if stays else "-1", tag, "", "",
                      acts, "%s card %s" % (FRONT, ident), "", code])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import k4host
    k4host.post(line)


def day_name(t):
    d = dt.datetime.fromtimestamp(t)
    today = dt.datetime.fromtimestamp(now()).date()
    if d.date() == today: return "today"
    if d.date() == today + dt.timedelta(days=1): return "tomorrow"
    return d.strftime("%a %-d %b")


def card(k, p):
    """The ParcelNotify cards: out for delivery, ready (the code large, stays), its last day (warn),
    delivered (done), a problem (warn, stays)."""
    shop = p.get("shop") or CARRIERS[p["carrier"]][0]
    car = CARRIERS[p["carrier"]][0]
    st = p["status"]
    code = ("%s|%s" % (p["code"], car)) if p.get("code") else ""
    if st == "ready":
        lastday = p.get("last") and dt.datetime.fromtimestamp(p["last"]).date() == dt.datetime.fromtimestamp(now()).date()
        acts = ("copy:Copy code," if p.get("code") else "") + "open:Open"
        if lastday: post("Last day · %s%s" % (shop, " at " + p["point"] if p.get("point") else ""), "After today it goes back to the shop", acts, "warn", "", k, code, stays=True)
        else: post("%s · ready to pick up" % shop, " · ".join(x for x in (p.get("point"), ("by " + day_name(p["last"])) if p.get("last") else "") if x) or car,
                   acts, "1", "", k, code, stays=True)
    elif st == "out": post("Out for delivery%s" % (" · %s" % p["window"] if p.get("window") else ""), "%s · %s" % (shop, car), "open:Open", "1", "", k)
    elif st == "delivered": post("%s · delivered" % shop, p.get("point") or car, "open:Open", "done", "DELIVERED", k)
    elif st == "problem": post("%s · a problem with the delivery" % shop, "%s · %s" % (car, p.get("note") or "see the carrier’s page"), "open:Fix it,later:Later", "warn", "", k, stays=True)


# ---------- sync ----------

def merge(s, ev):
    k = "%s:%s" % (ev["carrier"], ev["number"])
    p = s["parcels"].get(k) or {"carrier": ev["carrier"], "number": ev["number"], "status": "", "at": 0, "added": now()}
    if p.get("archived"): return
    for f in ("code", "point", "last", "window", "shop", "link"):
        if ev.get(f) and (not p.get(f) or ev["at"] >= p.get("at", 0)): p[f] = ev[f]
    if ev["at"] >= p.get("at", 0) and ev.get("status"): p["status"], p["at"] = ev["status"], ev["at"]
    s["parcels"][k] = p


def sync(quiet=False):
    s = load()
    known = s["mails"]
    mails = fake_mails(known) if FAKE else gmail_mails(known) + imap_mails(known)
    for k, sender, subject, text, sent in mails:
        ev = parse_mail(sender, subject, text, sent)
        known[k] = 1 if ev else 0
        if ev: merge(s, ev)
    t = now()
    for k, p in list(s["parcels"].items()):
        if p.get("archived"): continue
        if p["status"] != "delivered":
            lv = live(p)
            if lv.get("status") and lv["status"] != p["status"]: p["status"], p["at"] = lv["status"], t
            for f in ("point", "eta"):
                if lv.get(f): p[f] = lv[f]
        if p["status"] == "delivered" and t - p.get("at", t) > KEEP_DELIVERED: p["archived"] = True
        if p["status"] != "delivered" and t - max(p.get("at", t), p.get("added", 0)) > STALE: p["archived"] = True   # (no news for two weeks)
        if p["status"] != p.get("said") and p["status"] in ("ready", "out", "delivered", "problem") and t - p.get("at", t) < 2 * 86400:
            card(k, p)
            p["said"] = p["status"]
        if p["status"] == "ready" and p.get("last") and dt.datetime.fromtimestamp(p["last"]).date() == dt.datetime.fromtimestamp(t).date() and p.get("said_last") != p["last"]:
            card(k, p); p["said_last"] = p["last"]
    s["synced"] = t
    save(s)
    if not quiet:
        act = [p for p in s["parcels"].values() if not p.get("archived")]
        say("%d parcel%s · %d ready for pickup" % (len(act), "" if len(act) == 1 else "s", sum(1 for p in act if p["status"] == "ready")))


def scan():
    """What a sync would find in the real mailboxes: counts and carriers only (nothing saved or posted)."""
    mails = fake_mails({}) if FAKE else gmail_mails({}) + imap_mails({})
    evs = [parse_mail(se, su, te, at) for _, se, su, te, at in mails]
    found = [e for e in evs if e]
    by = {}
    for e in found: by[e["carrier"]] = by.get(e["carrier"], 0) + 1
    say("%d carrier mails, %d with a parcel: %s" % (len(mails), len(found), ", ".join("%s %d" % (CARRIERS[k][0], n) for k, n in sorted(by.items())) or "none"))


def add(number, name=""):
    n = re.sub(r"\s+", "", number).upper()
    if len(n) < 6: return say("That doesn't look like a tracking number")
    c = guess(n)
    if not c: c = "postnord" if n.endswith("SE") else "dhl"
    s = load()
    k = "%s:%s" % (c, n)
    s["parcels"][k] = dict(s["parcels"].get(k) or {}, carrier=c, number=n, status=(s["parcels"].get(k) or {}).get("status") or "registered",
                           at=now(), added=now(), link=link_of(c, n), **({"shop": name} if name else {}))
    s["parcels"][k].pop("archived", None)
    save(s)
    say("Tracking %s · %s" % (n, CARRIERS[c][0]))


def find_key(s, k):
    if k in s["parcels"]: return k
    for x, p in s["parcels"].items():
        if p["number"] == k.upper(): return x
    return ""


def act_on(verb, k):
    s = load()
    k = find_key(s, k)
    if not k: return say("No such parcel")
    p = s["parcels"][k]
    if verb == "archive":
        p["archived"] = True; save(s); say("Archived")
    elif verb == "copy":
        if not p.get("code"): return say("No code for this one")
        if FAKE: say("(copy %s)" % p["code"])
        else: subprocess.run(["wl-copy"], input=p["code"], text=True)
        say("Copied the code %s" % p["code"])
    elif verb == "open":
        url = p.get("link") or link_of(p["carrier"], p["number"])
        if FAKE: say("(open %s)" % url); return
        subprocess.Popen(["xdg-open", url], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- what the page, the bar and the launcher read ----------

def active():
    s = load()
    return sorted(((k, p) for k, p in s["parcels"].items() if not p.get("archived")), key=lambda kp: (ORDER.get(kp[1]["status"], 9), -kp[1].get("at", 0)))


def info():
    """The page: Y synced · P key status carrier number shop code point last window eta at link."""
    s = load()
    print("Y\t%d\t%d" % (s.get("synced", 0), 1 if key_of("postnord") or key_of("dhl") else 0))
    for k, p in active():
        print("P\t" + "\t".join(field(x) or "-" for x in (k, p["status"], CARRIERS[p["carrier"]][0], p["number"], p.get("shop", ""), p.get("code", ""), p.get("point", ""),
                                                    day_name(p["last"]) if p.get("last") else "", p.get("window", ""), day_name(p["eta"]) if p.get("eta") else "", int(p.get("at", 0)))))


def bar():
    """The bar module (BarModParcels): a pill for parcels to pick up, today's window; yellow on a last
    pickup day; a problem beats both ("delayed"). Hidden when nothing is active."""
    ps = [p for _, p in active()]
    ready = [p for p in ps if p["status"] == "ready"]
    out_ = [p for p in ps if p["status"] == "out"]
    prob = [p for p in ps if p["status"] == "problem"]
    if not (ready or out_ or prob): print("{}"); return
    today = dt.datetime.fromtimestamp(now()).date()
    lastday = [p for p in ready if p.get("last") and dt.datetime.fromtimestamp(p["last"]).date() == today]
    tip = ["%s · %s%s" % (p.get("shop") or CARRIERS[p["carrier"]][0], p.get("point") or "pickup point", " · code " + p["code"] if p.get("code") else "") for p in ready]
    tip += ["%s · out for delivery%s" % (p.get("shop") or CARRIERS[p["carrier"]][0], " " + p["window"] if p.get("window") else "") for p in out_]
    o = {"icon": "󰏗", "tooltip": "Parcels · " + " · ".join(tip or ["%d with a problem" % len(prob)])}
    if prob: o.update(icon_tone="yellow", text="delayed", text_tone="yellow")
    else:
        if ready: o["pill"] = str(len(ready))
        if lastday: o.update(icon_tone="yellow", badge_tone="yellow", text="last day", text_tone="yellow")
        elif out_: o["text"] = out_[0].get("window") or "today"
    print(json.dumps(o, ensure_ascii=False))


def find_rows():
    """The launcher (SearchParcel): "Trailshop · ready at ICA Nära · code 4821" / "PostNord · by Fri 6 Nov",
    found by shop, carrier, place, number or code; ↵ copies a pickup's code, else opens its page."""
    import base64
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    for k, p in active():
        car = CARRIERS[p["carrier"]][0]
        shop = p.get("shop") or car
        st = p["status"]
        if st == "ready": label, meta = "%s · ready%s%s" % (shop, " at " + p["point"] if p.get("point") else "", " · code " + p["code"] if p.get("code") else ""), car + (" · by " + day_name(p["last"]) if p.get("last") else "")
        elif st == "out": label, meta = "%s · out for delivery%s" % (shop, " · " + p["window"] if p.get("window") else ""), car + " · today"
        elif st == "delivered": label, meta = "%s · delivered" % shop, "%s · %s" % (car, day_name(p.get("at", now())))
        elif st == "problem": label, meta = "%s · a problem" % shop, car + " · see the page"
        else: label, meta = "%s · %s" % (shop, "in transit" if st == "transit" else "registered"), car + (" · " + day_name(p["eta"]) if p.get("eta") else "")
        action = "%s %s %s" % (me, "copy" if st == "ready" and p.get("code") else "open", shlex.quote(k))
        words = " ".join(x for x in (car, p["number"], p.get("point", ""), p.get("code", ""), "parcel paket") if x)
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=65;tag=Parcels;icon=󰏗;find=%s" % (b64("k4-parcels run " + b64(action)), field(label), field(meta), field(words).replace(";", ",")))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    rest = argv[2:]
    if cmd == "sync": sync("--quiet" in rest)
    elif cmd == "scan": scan()
    elif cmd == "add" and rest: add(rest[0], " ".join(rest[1:]))
    elif cmd in ("archive", "copy", "open") and rest: act_on(cmd, rest[0])
    elif cmd == "card":   # card KEY BUTTON ID (a card's button)
        if len(rest) > 1 and rest[1] in ("copy", "open", "default"): act_on("open" if rest[1] == "default" else rest[1], rest[0])
    elif cmd == "info": info()
    elif cmd == "bar": bar()
    elif cmd == "find": find_rows()
    elif cmd == "guess" and rest: say(CARRIERS.get(guess(rest[0]), ("",))[0])
    else: say(__doc__.strip()); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
