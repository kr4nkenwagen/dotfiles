#!/usr/bin/env python3
"""k4's event finder (k4-events is its front): a local model (Ollama) reads what is new in your mail,
Messenger and Discord for plans that belong in the calendar; Parcels' pickups and delivery windows
come without it. What it finds goes straight into the calendar (k4-cal add) with a card saying so; Apps ›
Events lists them, and Del takes one out again (k4-cal delete). One that could not be added waits
there for ↵. When a later message calls off one k4 added ("cancelled", "can't make it Saturday"), it
comes out of the calendar again with a card; ↵ on it in Apps › Events puts it back. Only k4's own
events are ever removed, never ones you made.

Todos too (Google Tasks, through k4-todo/todo.py): things to do in a message ("pay the invoice by
Friday") are added, and k4's own todos are ticked off when a message shows they are done ("paid").
GitHub (gh, your login): PRs waiting for your review and issues assigned to you become todos without
the model and are ticked off once merged, closed or reviewed; mentions go to the model like mail.
Upcoming calendar events go to it as well, for prep todos ("buy a gift", "bring the passport").

The model runs in Ollama on this machine ($K4_EVENTS_MODEL, default gemma4; $OLLAMA_HOST), so nothing
leaves it; only items not looked at before are read, and the model is unloaded right after (the GPU
is free for games again). While a game is running the GPU stays the game's: Claude Haiku reads them
instead, through your own Claude Code login (claude -p, tools off), unless its usage is over 90 %. State: ~/.local/state/k4/events (K4_EVENTS_STATE).

  events.py scan [--quiet] [--dry] [--again WORD]   look at what is new (--dry: counts only, nothing sent or
                                     saved; --again: the last week's mail and messages with WORD, read again)
  events.py add ID | add-all | remove ID | edit ID ($K4_INPUT: "Title · 2026-11-05 14:30") | open ID
  events.py info | find | count (added in the last day)

Tests: K4_EVENTS_FAKE=DIR: items from DIR/mail/*.eml, DIR/messenger.txt, DIR/discord.json,
DIR/parcels.json, DIR/gh.json (prs, issues, notifications); todos go to the fake Tasks API in
DIR/todo (todo.py's K4_TODO_FAKE); the model is DIR/llm (prompt on stdin, the answer's JSON out; argv[1] "haiku" when
it stands in for Claude); K4_EVENTS_GAMING=1 pretends a game is running.; k4-cal and cards go to DIR/log.
K4_EVENTS_NOW pins the clock.
"""
import datetime as dt, email, email.policy, email.utils, glob, hashlib, json, os, re, shlex, shutil, subprocess, sys, time

HOME = os.path.expanduser("~")
SHARE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SHARE)
import k4host   # where this runs: the desktop, or the Pi (cards to the outbox, no Discord, no game to yield to)
STATE = os.environ.get("K4_EVENTS_STATE") or os.path.join(HOME, ".local/state/k4/events")
FAKE = os.environ.get("K4_EVENTS_FAKE")
FRONT = os.environ.get("K4_EVENTS_FRONT") or shutil.which("k4-events") or "k4-events"
CAL = os.environ.get("K4_CAL_DIR") or os.path.join(HOME, ".cache/k4/cal")
FIRST_DAYS = 3
MAX_ITEMS, MAX_CHARS, ITEM_CHARS = 40, 60000, 3000
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def now(): return float(os.environ.get("K4_EVENTS_NOW") or time.time())


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w") as f: json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(p + ".tmp", p)


def log(line):
    with open(os.path.join(FAKE, "log"), "a") as f: f.write(line + "\n")


def sid(*parts): return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


# ---------- what is new ----------

def mail_items(seen, since):
    """New mail (Gmail and the IMAP accounts) since SINCE: no ads (Gmail's Promotions), read-only."""
    if FAKE:
        out = []
        for p in sorted(glob.glob(os.path.join(FAKE, "mail", "*.eml"))):
            k = "mail:" + os.path.basename(p)
            if k in seen: continue
            with open(p, "rb") as f: m = email.message_from_bytes(f.read(), policy=email.policy.default)
            part = m.get_body(preferencelist=("plain", "html"))
            out.append({"id": k, "source": "mail", "who": str(m["From"]), "subject": str(m["Subject"]), "at": email.utils.parsedate_to_datetime(m["Date"]).timestamp(),
                        "text": part.get_content() if part else "", "open": ""})
        return out
    sys.path.insert(0, SHARE)
    import parcels as P
    days = max(1, int((now() - since) // 86400) + 1)
    found = P.gmail_mails(seen, query="newer_than:%dd in:inbox -category:promotions -category:social" % days, limit=40) + P.imap_mails(seen, words=[], days=days, limit=40)
    return [{"id": k, "source": "mail", "who": se, "subject": su, "at": at, "text": te, "open": k} for k, se, su, te, at in found if at >= since - 3600]


def messenger_items(seen, since):
    """New Messenger messages (k4-messengerd ctl recent), a conversation an item with what came before."""
    if FAKE:
        try: text = open(os.path.join(FAKE, "messenger.txt")).read()
        except OSError: return []
    else:
        try: text = subprocess.run(["k4-messengerd", "ctl", "recent", str(int(since))], capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired): return []
    rooms = {}
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) < 7 or f[0] != "T": continue
        rooms.setdefault(f[1], {"name": f[2], "msgs": []})["msgs"].append((float(f[3] or 0), "me" if f[5] == "1" else f[4], f[6]))
    out = []
    for rid, r in rooms.items():
        new = [m for m in r["msgs"] if m[0] > since]
        if not new: continue
        k = "messenger:%s:%d" % (rid, max(m[0] for m in new))
        if k in seen: continue
        ctx = r["msgs"][-(len(new) + 10):]
        out.append({"id": k, "source": "messenger", "who": r["name"], "subject": "", "at": max(m[0] for m in new), "open": rid,
                    "text": "\n".join("[%s] %s: %s" % (dt.datetime.fromtimestamp(t).strftime("%a %Y-%m-%d %H:%M"), w, x) for t, w, x in ctx)})
    return out


def discord_items(seen, since):
    if k4host.pi_mode(): return []   # Discord is read from the desktop's running app: not on the Pi
    p = os.path.join(FAKE, "discord.json") if FAKE else os.path.join(HOME, ".local/state/k4/discord/state.json")
    out = []
    for n in jload(p, {}).get("log", []):
        k = "discord:%s:%d" % (n.get("open", ""), n.get("at", 0))
        if n.get("at", 0) <= since or k in seen: continue
        out.append({"id": k, "source": "discord", "who": n.get("title", ""), "subject": "", "at": n["at"], "text": n.get("body", ""), "open": n.get("open", "")})
    return out


def calendar_items(seen, s):
    """Upcoming calendar events (the next 14 days) the model hasn't seen, for prep todos; not k4's own."""
    t = dt.datetime.fromtimestamp(now()).date()
    mine = {(g["date"], norm(g["title"])) for g in s["items"]}
    out = []
    for e in jload(os.path.join(CAL, "events.json"), []):
        try: d = dt.date.fromisoformat(e.get("date", ""))
        except ValueError: continue
        k = "calendar:%s:%s" % (e.get("id", ""), e.get("date", ""))
        if not (t <= d <= t + dt.timedelta(days=14)) or k in seen or (e["date"], norm(e.get("title", ""))) in mine: continue
        text = "Calendar event: %s · %s %s%s%s%s" % (e.get("title", ""), d.strftime("%A %Y-%m-%d"), e.get("s") or "all day", (" · at " + e["loc"]) if e.get("loc") else "",
                                                 (" · organised by " + e["org"]) if e.get("org") and not e.get("own") else "", ("\n" + str(e["notes"])[:600]) if e.get("notes") else "")
        out.append({"id": k, "source": "calendar", "who": e.get("org") or "your calendar", "subject": e.get("title", ""), "at": now(), "text": text, "open": e.get("link", "")})
    return out[:15]


def gh(*args):
    """gh's JSON answer, or None when it can't be had (not installed, signed out, offline)."""
    try: r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired): return None
    if r.returncode != 0: return None
    try: return json.loads(r.stdout or "null")
    except ValueError: return None


def gh_web(api_url):
    """https://api.github.com/repos/o/r/pulls/12 → https://github.com/o/r/pull/12"""
    m = re.match(r"https://api\.github\.com/repos/([^/]+/[^/]+)/(issues|pulls)/(\d+)", api_url or "")
    return "https://github.com/%s/%s/%s" % (m.group(1), "pull" if m.group(2) == "pulls" else "issues", m.group(3)) if m else "https://github.com/notifications"


def github_items(seen, since):
    """GitHub mentions since SINCE (notifications you take part in), with the comment that mentioned you."""
    if FAKE: ns = jload(os.path.join(FAKE, "gh.json"), {}).get("notifications", [])
    else:
        ns = gh("api", "notifications?participating=true&since=%s" % dt.datetime.fromtimestamp(since, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")) or []
    out = []
    for n in ns[:10]:
        if n.get("reason") not in ("mention", "team_mention", "comment", "author"): continue
        sub = n.get("subject") or {}
        k = "github:%s:%s" % (n.get("id"), n.get("updated_at"))
        if k in seen: continue
        body = n.get("body", "")
        if not FAKE and sub.get("latest_comment_url"):
            body = (gh("api", sub["latest_comment_url"]) or {}).get("body") or ""
        try: at = dt.datetime.fromisoformat(n["updated_at"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError): at = now()
        repo = (n.get("repository") or {}).get("full_name", "")
        out.append({"id": k, "source": "github", "who": repo, "subject": sub.get("title", ""), "at": at, "open": gh_web(sub.get("url")),
                    "text": "GitHub %s on %s: %s\n%s" % (sub.get("type", "").lower() or "thread", repo, sub.get("title", ""), body[:ITEM_CHARS])})
    return out


def github_work():
    """PRs waiting for your review and issues assigned to you: {key: (title, due, url, why)}, or None
    when GitHub can't be asked (then nothing is ticked off)."""
    if FAKE:
        g = jload(os.path.join(FAKE, "gh.json"), None)
        if g is None: return None
        prs, issues = g.get("prs", []), g.get("issues", [])
    else:
        fields = "number,title,repository,url,createdAt"
        prs = gh("search", "prs", "--review-requested=@me", "--state=open", "--json", fields, "--limit", "30")
        issues = gh("search", "issues", "--assignee=@me", "--state=open", "--json", fields, "--limit", "30")
        if prs is None or issues is None: return None
    t = dt.datetime.fromtimestamp(now()).date().isoformat()
    out = {}
    for p in prs:
        repo = (p.get("repository") or {}).get("name", "")
        out["gh:" + p["url"]] = ("Review PR #%s · %s (%s)" % (p["number"], p["title"], repo), t, p["url"], "review requested on GitHub")
    for i in issues:
        repo = (i.get("repository") or {}).get("name", "")
        out["gh:" + i["url"]] = ("Issue #%s · %s (%s)" % (i["number"], i["title"], repo), None, i["url"], "assigned to you on GitHub")
    return out


def parcel_suggestions():
    """Parcels' own dates, no model: a pickup's last day (all day), today's delivery window."""
    p = os.path.join(FAKE, "parcels.json") if FAKE else os.path.join(HOME, ".local/state/k4/parcels.json")
    out = []
    for k, x in jload(p, {}).get("parcels", {}).items():
        if x.get("archived"): continue
        shop = x.get("shop") or x.get("carrier", "").title()
        if x.get("status") == "ready" and x.get("last"):
            d = dt.datetime.fromtimestamp(x["last"]).date()
            title = "Pick up the %s parcel%s%s" % (shop, " · " + x["point"] if x.get("point") else "", " · code " + x["code"] if x.get("code") else "")
            out.append(sug("parcels", k, title, d.isoformat(), None, None, "", "last day to pick it up", "high", "Parcels", k))
        if x.get("status") == "out" and x.get("window"):
            m = re.match(r"(\d{1,2})\D+(\d{1,2})", x["window"])
            if m:
                d = dt.datetime.fromtimestamp(x.get("at") or now()).date()
                out.append(sug("parcels", k, "%s delivery (%s)" % (shop, x["window"]), d.isoformat(), "%02d:00" % int(m.group(1)), "%02d:00" % int(m.group(2)), "", "out for delivery", "high", "Parcels", k))
    return out


def sug(source, ref, title, date, start, end, place, why, conf, who, open_):
    return {"id": sid(source, date, norm(title)), "source": source, "ref": ref, "title": title.strip(), "date": date, "start": start, "end": end,
            "place": place or "", "why": why or "", "conf": conf, "who": who, "open": open_, "state": "new", "found": now()}


# ---------- asking the local model ----------

MODEL = os.environ.get("K4_EVENTS_MODEL") or "gemma4"
OLLAMA = (os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
if "://" not in OLLAMA: OLLAMA = "http://" + OLLAMA
NUM_CTX = 32768   # the prompt is up to MAX_CHARS (~20k tokens) plus the answer
TIMEOUT = int(os.environ.get("K4_EVENTS_TIMEOUT") or (2700 if k4host.pi_mode() else 600))   # a Pi's CPU thinks slowly: up to 45 min a run there
THINK = os.environ.get("K4_EVENTS_THINK", "1") != "0"   # think first: slower, but the 8B model resolves dates far better


def calendar_next(days=14):
    t = dt.datetime.fromtimestamp(now()).date()
    out = []
    for e in jload(os.path.join(CAL, "events.json"), []):
        try: d = dt.date.fromisoformat(e.get("date", ""))
        except ValueError: continue
        if t <= d <= t + dt.timedelta(days=days): out.append("%s %s %s" % (d.isoformat(), e.get("s") or "all day", e.get("title", "")))
    return sorted(out)


def cancellable(s):
    """k4's own upcoming events a message may call off, as the prompt names them (K1, K2, …)."""
    today = dt.datetime.fromtimestamp(now()).date().isoformat()
    gs = sorted((g for g in s["items"] if g["state"] == "added" and g["date"] >= today and not g.get("cancel_why")), key=lambda g: (g["date"], g.get("start") or ""))
    return gs[:40]


def prompt(items, mine=(), todos=()):
    n = dt.datetime.fromtimestamp(now()).astimezone()
    head = ("You read someone's recent messages, mails, GitHub mentions and upcoming calendar events, and find what belongs in their calendar and their todo list. "
            "Today is %s %s, %s (time zone %s).\n"
            "Return ONLY a JSON object {\"events\": [...], \"cancelled\": [...], \"todos\": [...], \"done\": [...]} (no prose).\n"
            "events: {\"item\": N, \"title\": short, \"date\": \"YYYY-MM-DD\", \"start\": \"HH:MM\" or null, \"end\": \"HH:MM\" or null, \"place\": text or \"\", "
            "\"why\": a short quote from the text, \"confidence\": \"high\"|\"medium\"|\"low\"}; an end time only when the text gives one. "
            "Only real plans with a date you can work out: appointments, bookings, reservations, tickets, invitations, meetups agreed in a chat, deadlines. "
            "Resolve relative dates (\"Saturday at 10\", \"tomorrow\") against the item's own date. Skip newsletters, ads, receipts without a date to attend, "
            "past dates, calendar items (they are already in the calendar) and anything already in the calendar below.\n"
            "todos: {\"item\": N, \"title\": short and doable, \"due\": \"YYYY-MM-DD\" or null, \"why\": a short quote}. Things the person themself has to do: "
            "pay an invoice, reply to or send something someone asked for, renew, return, book, buy. Not appointments (those are events), not things others will do, "
            "not marketing. For a calendar item, only a preparation that is clearly needed (bring tickets, buy a gift for a birthday, prepare a presentation), "
            "due the day before; most calendar items need none.\n"
            "If nothing qualifies, return {\"events\": [], \"cancelled\": [], \"todos\": [], \"done\": []}.\n\n" % (WEEKDAYS[n.weekday()], n.strftime("%Y-%m-%d"), n.strftime("%H:%M"), n.tzname()))
    head += "Days ahead (look weekdays up here, don't count): " + ", ".join(
        "%s %s" % (WEEKDAYS[(n + dt.timedelta(days=k)).weekday()], (n + dt.timedelta(days=k)).strftime("%Y-%m-%d")) for k in range(15)) + ".\n"
    head += "Write titles as a calendar or todo list would: short, capitalised, in the message's own language (a Swedish message gets a Swedish title).\n\n"
    if mine:
        head += ("Events k4 added earlier from messages, each with its number (K1, K2, …):\n" + "\n".join("K%d · %s %s · %s · from %s" % (k, g["date"], g.get("start") or "all day", g["title"], g["who"])
                 for k, g in enumerate(mine, 1)) + "\nIf an item clearly calls one of these off (cancelled, won't happen, can't make it and nobody else is going, "
                 "moved to another day), put it in \"cancelled\": {\"event\": its number as listed above (for example \"K1\"), \"item\": the item's number, \"why\": a short quote}. A move also goes in \"events\" with "
                 "the new date. Only when the item is plainly about that same plan; never guess.\n\n")
    if todos:
        head += ("Open todos k4 added earlier, each with its number (T1, T2, …):\n" + "\n".join("T%d · %s%s · from %s" % (k, t["title"], " · due " + t["due"] if t["due"] else "", m.get("who") or m.get("source", ""))
                 for k, (_, t, m) in enumerate(todos, 1)) + "\nIf an item plainly shows one of these is done (paid, sent, booked, returned, \"done\", \"fixed\"), put it in \"done\": "
                 "{\"todo\": its number as listed above (for example \"T1\"), \"item\": the item's number, \"why\": a short quote}. Never guess. Don't add a todo that is already listed here.\n\n")
    cal = calendar_next()
    head += "Already in the calendar (next 14 days):\n" + ("\n".join(cal) if cal else "(nothing)") + "\n\n"
    body = []
    for i, it in enumerate(items, 1):
        when = dt.datetime.fromtimestamp(it["at"]).strftime("%a %Y-%m-%d %H:%M")
        body.append("### Item %d · %s · %s · from %s%s\n%s" % (i, it["source"], when, field(it["who"]), (" · subject: " + field(it["subject"])) if it["subject"] else "",
                                                              it["text"][:ITEM_CHARS]))
    return head + "\n\n".join(body)


SCHEMA = {"type": "object", "required": ["events"], "properties": {"events": {"type": "array", "items": {"type": "object",
          "required": ["item", "title", "date"], "properties": {"item": {"type": "integer"}, "title": {"type": "string"}, "date": {"type": "string"},
          "start": {"type": ["string", "null"]}, "end": {"type": ["string", "null"]}, "place": {"type": "string"}, "why": {"type": "string"},
          "confidence": {"type": "string", "enum": ["high", "medium", "low"]}}}},
          "cancelled": {"type": "array", "items": {"type": "object", "required": ["event", "item", "why"],
          "properties": {"event": {"type": "string"}, "item": {"type": "integer"}, "why": {"type": "string"}}}},
          "todos": {"type": "array", "items": {"type": "object", "required": ["item", "title"],
          "properties": {"item": {"type": "integer"}, "title": {"type": "string"}, "due": {"type": ["string", "null"]}, "why": {"type": "string"}}}},
          "done": {"type": "array", "items": {"type": "object", "required": ["todo", "item", "why"],
          "properties": {"todo": {"type": "string"}, "item": {"type": "integer"}, "why": {"type": "string"}}}}}}


def claude_bin():
    p = os.path.join(HOME, ".local/share/mise/installs/claude/latest/claude")
    if os.access(p, os.X_OK): return p
    try:
        r = subprocess.run(["mise", "which", "claude"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip(): return r.stdout.strip()
    except OSError: pass
    return shutil.which("claude") or ""


def ask(text, haiku=False):
    """The model's answer, {"events": [...], "cancelled": [...]}, or None when it can't be had (Ollama down, no such model, Claude
    signed out, no JSON). haiku: Claude Haiku instead of the local model (a game has the GPU)."""
    if FAKE:
        try: res = subprocess.run([os.path.join(FAKE, "llm")] + (["haiku"] if haiku else []), input=text, capture_output=True, text=True, timeout=60).stdout
        except OSError: return None
    elif haiku:
        cb = claude_bin()
        if not cb: return None
        try:
            r = subprocess.run([cb, "-p", text, "--model", "haiku", "--tools", "", "--output-format", "json", "--no-session-persistence"],
                               capture_output=True, text=True, timeout=300, cwd=HOME)
        except (OSError, subprocess.TimeoutExpired): return None
        try: res = json.loads(r.stdout).get("result", "")
        except ValueError: res = r.stdout
    else:
        import urllib.request, urllib.error
        body = {"model": MODEL, "stream": False, "think": THINK, "format": SCHEMA, "keep_alive": 0,
                "options": {"temperature": 0, "num_ctx": NUM_CTX}, "messages": [{"role": "user", "content": text}]}
        req = urllib.request.Request(OLLAMA + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r: res = json.load(r).get("message", {}).get("content", "")
        except (OSError, ValueError, urllib.error.URLError): return None
    m = re.search(r"[\[{].*[\]}]", res, re.S)
    if not m: return None
    try: v = json.loads(m.group(0))
    except ValueError: return None
    if isinstance(v, list): v = {"events": v}
    return {k: v.get(k) or [] for k in ("events", "cancelled", "todos", "done")} if isinstance(v, dict) else None


def ollama_up():
    if FAKE: return True
    import urllib.request
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r: return any(m.get("name", "").split(":")[0] == MODEL.split(":")[0] for m in json.load(r).get("models", []))
    except (OSError, ValueError): return False


def norm(t): return " ".join(sorted(set(re.findall(r"[a-zåäö0-9]{3,}", t.lower()))))


def _flat(t): return " ".join(re.sub(r"[“”\"'«»*_>]+", " ", str(t).lower()).split())


def locate(x, items):
    """Which item the model's answer really comes from, by its quote ("why"), not its number: small models
    number items loosely. The quote's pieces (split at …) must be in the item; the item it named wins when
    they are, else the first that holds them, else the closest by words (most of the quote's words). 0: the
    quote is in no item (made up): the answer is dropped."""
    why = _flat(x.get("why") or "")
    parts = [p.strip(" .,:;!?-") for p in re.split(r"…|\.\.\.", why)]
    parts = [p for p in parts if len(p) >= 6]
    if not parts: return 0
    texts = [_flat("%s %s %s" % (it["who"], it["subject"], it["text"])) for it in items]
    try: hint = int(x.get("item", 0))
    except (TypeError, ValueError): hint = 0
    order = ([hint] if 1 <= hint <= len(items) else []) + [i for i in range(1, len(items) + 1) if i != hint]
    for i in order:
        if all(p in texts[i - 1] for p in parts): return i
    words = set(w for w in re.findall(r"[a-zåäö0-9]{4,}", why))
    if len(words) < 3: return 0
    best = max(order, key=lambda i: len(words & set(re.findall(r"[a-zåäö0-9]{4,}", texts[i - 1]))))
    return best if len(words & set(re.findall(r"[a-zåäö0-9]{4,}", texts[best - 1]))) >= 0.8 * len(words) else 0


def checked(answer, items):
    """The model's suggestions that hold: a real item, a valid date within a year, a title; no duplicates."""
    out = []
    today = dt.datetime.fromtimestamp(now()).date()
    for x in answer if isinstance(answer, list) else []:
        if not isinstance(x, dict): continue
        try: d = dt.date.fromisoformat(str(x.get("date", "")))
        except (TypeError, ValueError): continue
        i = locate(x, items)
        if not i or not (today <= d <= today + dt.timedelta(days=366)): continue
        title = field(x.get("title"))[:80]
        if not title: continue
        st, en = (x.get("start") or None), (x.get("end") or None)
        if st and not re.fullmatch(r"\d{2}:\d{2}", str(st)): st = None
        if en and not re.fullmatch(r"\d{2}:\d{2}", str(en)) or not st: en = None
        it = items[i - 1]
        if it["source"] == "calendar": continue   # already in the calendar: only prep todos come from these
        who = re.sub(r"\s*<[^>]+>", "", field(it["who"])) or it["source"]
        out.append(sug(it["source"], it["id"], title, d.isoformat(), st, en, field(x.get("place")), field(x.get("why"))[:140],
                       x.get("confidence") if x.get("confidence") in ("high", "medium", "low") else "medium", who, it["open"]))
    return out


# ---------- the run ----------

def load(): return jload(os.path.join(STATE, "suggestions.json"), {"items": [], "seen": {}, "runs": []})
def save(s): jsave(os.path.join(STATE, "suggestions.json"), s)


def in_calendar(sg):
    t = norm(sg["title"])
    for e in jload(os.path.join(CAL, "events.json"), []):
        if e.get("date") == sg["date"] and (norm(e.get("title", "")) == t or set(t.split()) & set(norm(e.get("title", "")).split())): return True
    return False


def usage_high():
    l = jload(os.path.join(HOME, ".cache/k4/claude-limits.json"), {})
    return (l.get("five_hour") or {}).get("used", 0) > 0.9


def gaming():
    """WoW (or another game under Wine/Proton) is running: the local model would take the GPU from it."""
    if FAKE: return os.environ.get("K4_EVENTS_GAMING") == "1"
    if k4host.pi_mode(): return False   # the Pi has its own processor
    try: return subprocess.run(["pgrep", "-if", r"wow(classic|-64)?\.exe|steamapps/common/.*\.exe"], capture_output=True).returncode == 0
    except OSError: return False


def scan(quiet=False, dry=False, again=None):
    """again WORD: read once more the last week's mail and messages that mention WORD, even ones read
    before (to try a change, or a todo that was missed); the hourly schedule is left as it was."""
    s = load()
    t = now()
    since = max(r["at"] for r in s["runs"]) if s["runs"] else t - FIRST_DAYS * 86400
    seen = s["seen"]
    if again:
        w, wk = again.lower(), t - 7 * 86400
        items = [it for it in mail_items({}, wk) + messenger_items({}, wk) + github_items({}, wk) if w in (it["subject"] + " " + it["text"]).lower()]
        items.sort(key=lambda x: x["at"])
    else:
        items = mail_items(seen, since) + messenger_items(seen, since) + discord_items(seen, since) + github_items(seen, since)
        items.sort(key=lambda x: x["at"])
        items += calendar_items(seen, s)   # last: after what people wrote
    batch, size = [], 0
    for it in items:
        if len(batch) >= MAX_ITEMS or size + min(len(it["text"]), ITEM_CHARS) > MAX_CHARS: break
        batch.append(it); size += min(len(it["text"]), ITEM_CHARS)
    found = parcel_suggestions()
    if dry:
        by = {}
        for it in items: by[it["source"]] = by.get(it["source"], 0) + 1
        say("New since %s: %s · %d would go to %s · %d from Parcels" % (dt.datetime.fromtimestamp(since).strftime("%a %H:%M"),
            ", ".join("%s %d" % kv for kv in sorted(by.items())) or "nothing", len(batch), MODEL, len(found)))
        return
    asked = ""
    todos_new, ticked = [], []
    gw = github_work()
    if gw is not None: todos_new, ticked = github_todos(gw)
    wait = ""   # the model couldn't read this batch: it waits for the next run (GitHub's todos still go in)
    haiku = gaming()   # the game keeps the GPU: Claude Haiku reads this batch
    if batch and haiku and usage_high(): wait = "Waiting · a game is running and your Claude usage is over 90 % · trying again next hour"
    elif batch and not haiku and not ollama_up(): wait = "Ollama isn’t running (or has no %s) · trying again next hour" % MODEL
    if batch and not wait:
        mine = cancellable(s)
        tmine = T().k4_open() if todo_ok() else []
        ans = ask(prompt(batch, mine, tmine), haiku)
        if ans is None: wait = "%s did not answer · trying again next hour" % ("Claude Haiku" if haiku else MODEL)
    if wait:
        batch = []
        if not quiet: say(wait)
        if todos_new or ticked: card([], [], todos_new, ticked)
        return
    if batch:
        asked = "haiku" if haiku else "local"
        found += checked(ans["events"], batch)
        called_off(ans["cancelled"], batch, mine, t)
        todos_new += todos_from(ans["todos"], batch)
        ticked += ticked_from(ans["done"], batch, tmine)
    for it in batch: seen[it["id"]] = t
    known = {x["id"] for x in s["items"]}
    new = []
    for g in found:
        if g["id"] in known or in_calendar(g): continue
        known.add(g["id"]); new.append(g)
    s["items"] = (s["items"] + new)[-300:]
    s["seen"] = {k: v for k, v in seen.items() if v > t - 30 * 86400}
    if not again: s["runs"] = (s["runs"] + [{"at": t, "items": len(batch), "asked": asked, "found": len(new)}])[-50:]
    save(s)
    added = [g for g in new if put(g, t)]
    gone = [g for g in s["items"] if g["state"] == "added" and g.get("cancel_why") and uncal(g)]   # this run's, and ones the calendar hadn't synced yet
    for g in gone: g["state"], g["cancelled"] = "cancelled", t
    save(s)
    if new or todos_new or ticked: card(added, [g for g in new if g not in added], todos_new, ticked)
    if gone: card_gone(gone)
    if not quiet: say("Looked at %d new item%s · %d event%s added%s%s%s" % (len(batch), "" if len(batch) == 1 else "s", len(added), "" if len(added) == 1 else "s",
                      " · %d cancelled one%s removed" % (len(gone), "" if len(gone) == 1 else "s") if gone else "",
                      " · %d todo%s added" % (len(todos_new), "" if len(todos_new) == 1 else "s") if todos_new else "", " · %d ticked off" % len(ticked) if ticked else ""))


def T():
    """todo.py (k4-todo): Google Tasks; in tests its fake API lives in DIR/todo."""
    if FAKE: os.environ.setdefault("K4_TODO_FAKE", os.path.join(FAKE, "todo")); os.makedirs(os.environ["K4_TODO_FAKE"], exist_ok=True)
    os.environ.setdefault("K4_TODO_NOW", str(now()))
    sys.path.insert(0, SHARE)
    import todo
    return todo


def todo_ok():
    try: return T().status() == "ok"
    except Exception: return False


def todos_from(answer, items):
    """The model's new todos that hold, added to Google Tasks (k4's own): [title]."""
    if not todo_ok(): return []
    td = T()
    today = dt.datetime.fromtimestamp(now()).date()
    out = []
    for x in answer if isinstance(answer, list) else []:
        if not isinstance(x, dict): continue
        i = locate(x, items)
        title = field(x.get("title"))[:90]
        if not i or not title: continue
        due = None
        try:
            d = dt.date.fromisoformat(str(x.get("due") or ""))
            if today <= d <= today + dt.timedelta(days=366): due = d.isoformat()
        except ValueError: pass
        it = items[i - 1]
        key = "item:%s:%s" % (it["id"], norm(title))
        if td.known(key=key, title=title): continue
        who = re.sub(r"\s*<[^>]+>", "", field(it["who"])) or it["source"]
        td.add(title, due, "from %s · %s%s" % (who, {"github": "GitHub"}.get(it["source"], it["source"].title()), " · “%s”" % field(x.get("why"))[:140] if x.get("why") else ""),
               {"key": key, "source": it["source"], "who": who, "why": field(x.get("why"))[:140], "open_cmd": open_cmd(it["source"], it["open"])})
        out.append(title)
    return out


def ticked_from(answer, items, tmine):
    """Ticks off k4's own todos a message shows are done: [title]."""
    out = []
    for x in answer if isinstance(answer, list) else []:
        if not isinstance(x, dict): continue
        m = re.fullmatch(r"T?(\d+)", str(x.get("todo", "")).strip(), re.I)
        i = locate(x, items)
        why = field(x.get("why"))[:140]
        if not m or not (1 <= int(m.group(1)) <= len(tmine)) or not i or not why: continue
        ident, t, _ = tmine[int(m.group(1)) - 1]
        if T().set_status(ident, True, why): out.append(t["title"])
    return out


def github_todos(work):
    """GitHub's own todos, no model: new review requests and assigned issues added, k4's GitHub todos
    that no longer wait (merged, closed, reviewed) ticked off. ([added titles], [ticked titles])"""
    if not todo_ok(): return [], []
    td = T()
    added, ticked = [], []
    for key, (title, due, url, why) in work.items():
        if td.known(key=key): continue
        td.add(title, due, "%s · %s" % (why, url), {"key": key, "source": "github", "who": "GitHub", "why": why, "open_cmd": ["xdg-open", url]})
        added.append(title)
    for ident, t, m in td.k4_open():
        if m.get("key", "").startswith("gh:") and m["key"] not in work and td.set_status(ident, True, "merged, closed or reviewed on GitHub"): ticked.append(t["title"])
    return added, ticked


def called_off(answer, items, mine, t):
    """Marks k4's events a message calls off (cancel_why); scan takes them out of the calendar."""
    for x in answer if isinstance(answer, list) else []:
        if not isinstance(x, dict): continue
        m = re.fullmatch(r"K?(\d+)", str(x.get("event", "")).strip(), re.I)
        i = locate(x, items)
        why = field(x.get("why"))[:140]
        if not m or not (1 <= int(m.group(1)) <= len(mine)) or not i or not why: continue
        g, it = mine[int(m.group(1)) - 1], items[i - 1]
        g["cancel_why"], g["cancel_who"], g["cancel_open"] = why, re.sub(r"\s*<[^>]+>", "", field(it["who"])) or it["source"], it["open"]


def when(g):
    d = dt.date.fromisoformat(g["date"])
    return "%s %d %s%s" % (d.strftime("%a"), d.day, d.strftime("%b"), (" " + g["start"] + ("–" + g["end"] if g.get("end") else "")) if g.get("start") else "")


def card(added, failed, todos=(), ticked=()):
    """One card per run: what went into the calendar and the todo list (and what could not)."""
    pl = lambda n, w: "%d %s%s" % (n, w, "" if n == 1 else "s")
    parts = ([pl(len(added), "event")] if added else []) + ([pl(len(todos), "todo")] if todos else [])
    title = ("Added " + " and ".join(parts) if parts else "") + (" · ticked off %d" % len(ticked) if ticked and parts else "Ticked off " + pl(len(ticked), "todo") if ticked else "")
    if not title: title = "Couldn’t add " + pl(len(failed), "event")
    things = ["%s %s" % (g["title"], when(g)) for g in (added or failed)] + list(todos) + ["✓ " + x for x in ticked]
    body = " · ".join(things[:3]) + (" …" if len(things) > 3 else "")
    if added and failed: body += " · %d waiting: Apps › Events" % len(failed)
    if FAKE: log("card %s | %s" % (title, body)); return
    review = "%s card" % FRONT if (added or failed) else "k4-todo"
    line = "\t".join(["post", "0", "Calendar" if (added or failed) else "Todo", field(title), field(body), "1" if (added or todos or ticked) else "warn", "-1", "-1", "", "", "", "review:Review", review])
    k4host.post(line)


def card_gone(gs):
    title = "Removed %d cancelled event%s" % (len(gs), "" if len(gs) == 1 else "s")
    body = " · ".join("%s %s (“%s”)" % (g["title"], when(g), g["cancel_why"]) for g in gs[:2]) + (" …" if len(gs) > 2 else "")
    if FAKE: log("card %s | %s" % (title, body)); return
    line = "\t".join(["post", "0", "Calendar", field(title), field(body), "1", "-1", "-1", "", "", "", "review:Review", "%s card" % FRONT])
    k4host.post(line)


def find(s, ident):
    for g in s["items"]:
        if g["id"] == ident: return g
    return None


def cal_add(g):
    title = g["title"] + (" · " + g["place"] if g.get("place") and g["place"].lower() not in g["title"].lower() else "")
    args = ["k4-cal", "add", "primary", g["date"]] + ([g["start"]] if g.get("start") else []) + [title]
    if FAKE: log("add " + " ".join(args[3:])); return "Created  %s" % title
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return (r.stdout.strip().splitlines() or ["Added"])[-1]


def put(g, t=None):
    """Into the calendar; True when k4-cal created it (or queued it while offline)."""
    msg = cal_add(g)
    ok = msg.startswith(("Created", "Added")) or "queue" in msg.lower() or "online" in msg.lower()
    if ok: g["state"], g["added"] = "added", t or now()
    else: g["error"] = msg[:120]
    return ok


def add(ident):
    s = load()
    g = find(s, ident)
    if not g: return say("No such event")
    back = g["state"] == "cancelled"
    if put(g):
        for k in ("cancel_why", "cancel_who", "cancel_open", "cancelled"): g.pop(k, None)
        save(s); say(("Put back · %s" if back else "Added · %s") % when(g))
    else: save(s); say(g.get("error") or "Not added"); say("k4:tone yellow")


def add_all():
    s = load()
    n = sum(1 for g in pending(s) if put(g))
    save(s)
    say("Added %d event%s" % (n, "" if n == 1 else "s"))


def cal_event(g):
    """The calendar's own copy of an added event (k4-cal's cache): its id, or ""."""
    t = norm(g["title"])
    for e in jload(os.path.join(CAL, "events.json"), []):
        if e.get("date") == g["date"] and (e.get("s") or "") == (g.get("start") or "") and set(t.split()) <= set(norm(e.get("title", "")).split()): return e.get("id", "")
    return ""


def uncal(g):
    """Out of the calendar (k4-cal delete); False when the calendar has no copy yet (it syncs every 5 min)."""
    ev = cal_event(g)
    if FAKE: log("delete %s %s" % (ev or "?", g["title"])); return True
    if not ev: return False
    subprocess.run(["k4-cal", "delete", ev, g["title"]], capture_output=True, text=True, timeout=60)
    return True


def remove(ident):
    """Del on an added one: out of the calendar again (k4-cal delete), and never added again."""
    s = load()
    g = find(s, ident)
    if not g: return say("No such event")
    if g["state"] == "added":
        if not uncal(g):
            say("Not found in the calendar yet · it syncs within 5 minutes, try again then"); say("k4:tone yellow"); return
    g["state"] = "dismissed"; save(s)
    say("Removed · %s won’t be added again" % g["title"])


def edit(ident, text):
    """"Title · 2026-11-05 14:30[-15:30]" (or "· 2026-11-05" all day)."""
    s = load()
    g = find(s, ident)
    if not g: return say("No such suggestion")
    title, _, rest = text.rpartition("·")
    m = re.search(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2})(?:\s*[-–]\s*(\d{1,2}:\d{2}))?)?", rest)
    if not title.strip() or not m: say("Write it as: Title · 2026-11-05 14:30"); say("k4:tone yellow"); return
    try: dt.date.fromisoformat(m.group(1))
    except ValueError: say("That date doesn’t exist"); say("k4:tone yellow"); return
    g.update(title=title.strip(), date=m.group(1), start=m.group(2) and m.group(2).zfill(5), end=m.group(3) and m.group(3).zfill(5))
    save(s)
    say("Changed · %s %s · ↵ adds it" % (g["title"], when(g)))


def open_cmd(source, ref):
    """The command that shows an item where it came from."""
    if source == "mail": return ["k4-mail", "window"]
    if source == "messenger": return ["k4-messenger", "window", ref]
    if source == "parcels": return ["k4-parcels", "open", ref]
    if source == "discord" and "/" in ref:
        gid, cid = ref.split("/", 1)
        return ["k4-discord", "open", "" if gid == "@me" else gid, cid]
    if source in ("github", "calendar") and ref.startswith("http"): return ["xdg-open", ref]
    return []


def open_source(ident):
    g = find(load(), ident)
    if not g: return say("No such suggestion")
    cmd = open_cmd(g["source"], g["open"])
    if not cmd: return
    if FAKE: log("open " + " ".join(cmd)); return
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def pending(s=None):
    s = s or load()
    today = dt.datetime.fromtimestamp(now()).date().isoformat()
    return sorted((g for g in s["items"] if g["state"] == "new" and g["date"] >= today), key=lambda g: (g["date"], g.get("start") or ""))


def recent(s=None, days=7):
    s = s or load()
    t = now()
    return sorted((g for g in s["items"] if g["state"] == "added" and g.get("added", 0) > t - days * 86400), key=lambda g: -g.get("added", 0))


def cancelled(s=None, days=7):
    s = s or load()
    t = now()
    return sorted((g for g in s["items"] if g["state"] == "cancelled" and g.get("cancelled", 0) > t - days * 86400), key=lambda g: -g["cancelled"])


def info():
    """The page: R last-run items asked found at · G state id title when date start source who why conf place
    (state waiting: not added yet; added: in the calendar, newest first; cancelled: taken out again, a message called it off)."""
    s = load()
    r = s["runs"][-1] if s["runs"] else {}
    by = r.get("asked") or ""
    print("R\t%d\t%d\t%s\t%d" % (r.get("at", 0), r.get("items", 0), "local" if by is True else (by or "-"), r.get("found", 0)))
    for st, gs in (("waiting", pending(s)), ("added", recent(s)), ("cancelled", cancelled(s))):
        for g in gs:
            who, why = (g["cancel_who"], g["cancel_why"]) if st == "cancelled" else (g["who"], g["why"])
            print("G\t" + "\t".join(field(x) or "-" for x in (st, g["id"], g["title"], when(g), g["date"], g.get("start") or "", g["source"], who, why, g["conf"], g.get("place", ""))))


def find_rows():
    import base64
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    for g in pending():
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=60;tag=Events;icon=󰃭;find=%s" % (b64("k4-events run " + b64("%s add %s" % (me, g["id"]))), field("Add %s · %s" % (g["title"], when(g))),
              field("from %s · %s · ↵ adds it" % (g["who"], g["source"])), field("event calendar " + g["who"]).replace(";", ",")))


def main(argv):
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if cmd == "scan": scan("--quiet" in rest, "--dry" in rest, rest[rest.index("--again") + 1] if "--again" in rest[:-1] else None)
    elif cmd == "add" and rest: add(rest[0])
    elif cmd == "add-all": add_all()
    elif cmd in ("remove", "dismiss") and rest: remove(rest[0])
    elif cmd == "edit" and rest: edit(rest[0], os.environ.get("K4_INPUT", " ".join(rest[1:])))
    elif cmd == "open" and rest: open_source(rest[0])
    elif cmd == "info": info()
    elif cmd == "find": find_rows()
    elif cmd == "count": say(len(recent(days=1)))
    else: say(__doc__.strip()); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
