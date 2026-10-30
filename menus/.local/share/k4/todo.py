#!/usr/bin/env python3
"""k4's todos (k4-todo is its front): Google Tasks, on the Apps page, the bar beside the clock and the
launcher. The lists and tasks are cached (~/.cache/k4/todo, K4_TODO_DIR) so nothing waits for the
network; changes go out at once, or wait in a queue while offline. k4-todo.timer syncs every 5 min.

Todos k4 adds itself (the event finder, k4-events: from your messages, GitHub, the calendar) are
remembered in ~/.local/state/k4/todo/k4.json with where they came from; only those are ever ticked
off by k4, never ones you made. Ticked ones list on the page for a week (↵ reopens).

  todo.py sync [--quiet] | signin | signout
  todo.py add TEXT ("Buy milk · fri": a day or a date after · is the due date) | add-input ($K4_INPUT)
  todo.py done|undone|delete|open ID | edit ID ($K4_INPUT "Title · 2026-11-05") | edit-ask ID
  todo.py page | bar | find | done-next | card ID BUTTON NOTE

Signed in with google.py (scope tasks), the same OAuth client as Calendar and Gmail; the Google
Tasks API must be enabled on that Cloud project once.

Tests: K4_TODO_FAKE=DIR: the API is DIR/server.json (lists, tasks per list), calls go to DIR/log,
cards to DIR/posts.log; DIR/offline makes every call fail as if offline, DIR/nosignin as if signed
out. K4_TODO_NOW pins the clock.
"""
import base64, datetime as dt, json, os, re, secrets, shlex, shutil, subprocess, sys, time, urllib.error

HOME = os.path.expanduser("~")
SHARE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.environ.get("K4_TODO_FAKE")
DIR = os.environ.get("K4_TODO_DIR") or (os.path.join(FAKE, "cache") if FAKE else os.path.join(HOME, ".cache/k4/todo"))
STATE = os.environ.get("K4_TODO_STATE") or (os.path.join(FAKE, "state") if FAKE else os.path.join(HOME, ".local/state/k4/todo"))
FRONT = os.environ.get("K4_TODO_FRONT") or shutil.which("k4-todo") or "k4-todo"
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
API = "https://tasks.googleapis.com/tasks/v1"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SV_DAYS = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"]
SOURCES = {"mail": "Mail", "messenger": "Messenger", "discord": "Discord", "github": "GitHub", "calendar": "Calendar", "parcels": "Parcels"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def flag(s): return field(s).replace(";", ",")
def now(): return float(os.environ.get("K4_TODO_NOW") or time.time())
def today(): return dt.datetime.fromtimestamp(now()).date()


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


def log(line):
    if FAKE:
        with open(os.path.join(FAKE, "log"), "a") as f: f.write(line + "\n")


# ---------- the API (Google's, or the test's server.json) ----------

class Offline(Exception): pass


class Google:
    def __init__(self):
        sys.path.insert(0, SHARE)
        import google
        self.g = google
        self.acct = google.Account("Google Tasks", "https://www.googleapis.com/auth/tasks", ["service", "k4-google-tasks"],
                                   os.path.join(RUN, "k4-todo-token.json"), API)

    def connected(self): return bool(self.acct.refresh_token())

    def call(self, method, path, body=None, query=None):
        try: return self.acct.request(method, path, body, query)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:400]
            if e.code == 403 and ("accessNotConfigured" in msg or "has not been used" in msg or "disabled" in msg): raise PermissionError("noapi")
            if e.code == 401: raise PermissionError("signin")
            raise
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if isinstance(e, PermissionError): raise
            raise Offline(str(e))


class Fake:
    """server.json: {"lists": [{id, title}], "tasks": {LIST: [task, …]}}"""
    def __init__(self): self.p = os.path.join(FAKE, "server.json")
    def connected(self): return not os.path.exists(os.path.join(FAKE, "nosignin"))

    def call(self, method, path, body=None, query=None):
        if os.path.exists(os.path.join(FAKE, "offline")): raise Offline("offline")
        if not self.connected(): raise PermissionError("signin")
        s = jload(self.p, {"lists": [], "tasks": {}})
        parts = path.strip("/").split("/")
        if path == "/users/@me/lists": return {"items": s["lists"]}
        lst = parts[1]
        ts = s["tasks"].setdefault(lst, [])
        if method == "GET": return {"items": ts}
        log("%s %s %s" % (method, path, json.dumps(body, ensure_ascii=False, sort_keys=True) if body else ""))
        if method == "POST":
            t = dict(body, id="t%d" % (sum(len(v) for v in s["tasks"].values()) + 1), status=body.get("status", "needsAction"), updated="2026-01-01T00:00:00Z")
            ts.insert(0, t); jsave(self.p, s); return t
        t = next((x for x in ts if x["id"] == parts[3]), None)
        if not t:
            raise urllib.error.HTTPError(path, 404, "not found", {}, None)
        if method == "DELETE": ts.remove(t)
        else:
            t.update(body)
            if body.get("status") == "completed": t["completed"] = dt.datetime.fromtimestamp(now(), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            if "completed" in body and body["completed"] is None: t.pop("completed", None)
        jsave(self.p, s)
        return {} if method == "DELETE" else t


_api = None
def api():
    global _api
    if _api is None: _api = Fake() if FAKE else Google()
    return _api


# ---------- the cache, the queue, k4's own ----------

def cache(): return jload(os.path.join(DIR, "tasks.json"), {"at": 0, "lists": [], "tasks": [], "err": ""})
def save_cache(c): jsave(os.path.join(DIR, "tasks.json"), c)
def queue(): return jload(os.path.join(STATE, "queue.json"), [])
def save_queue(q): jsave(os.path.join(STATE, "queue.json"), q)
MINE = os.environ.get("K4_TODO_MINE") or os.path.join(STATE, "k4.json")   # (the desktop with a Pi: the Pi's copy, pulled)
def mine(): return jload(MINE, {})
def save_mine(m): jsave(MINE, m)


def norm(t): return " ".join(sorted(set(re.findall(r"[a-zåäö0-9]{3,}", str(t).lower()))))


def task_of(g, lst):
    due = (g.get("due") or "")[:10]
    comp = 0
    if g.get("completed"):
        try: comp = dt.datetime.fromisoformat(g["completed"].replace("Z", "+00:00")).timestamp()
        except ValueError: comp = now()
    return {"id": g["id"], "list": lst, "title": g.get("title") or "", "notes": g.get("notes") or "", "status": g.get("status") or "needsAction",
            "due": due, "completed": comp, "parent": g.get("parent") or "", "pos": g.get("position") or "", "link": g.get("webViewLink") or ""}


def default_list(c=None):
    c = c or cache()
    return c["lists"][0]["id"] if c["lists"] else "@default"


def fetch():
    """Lists and tasks from Google into the cache (completed ones of the last two weeks too)."""
    a = api()
    lists = [{"id": l["id"], "title": l.get("title") or "Tasks"} for l in a.call("GET", "/users/@me/lists").get("items", [])]
    since = dt.datetime.fromtimestamp(now() - 14 * 86400, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    tasks = []
    for l in lists:
        tok = None
        while True:
            q = {"showCompleted": "true", "showHidden": "true", "maxResults": 100, "completedMin": since}
            if FAKE: q.pop("completedMin")
            if tok: q["pageToken"] = tok
            j = a.call("GET", "/lists/%s/tasks" % l["id"], query=q)
            tasks += [task_of(g, l["id"]) for g in j.get("items", []) if not g.get("deleted")]
            tok = j.get("nextPageToken")
            if not tok: break
    c = cache()
    pending = {op.get("id") for op in queue()}
    keep = [t for t in c["tasks"] if t["id"].startswith("local-") or t["id"] in pending]   # not sent yet: kept as they are
    keep_ids = {t["id"] for t in keep}
    c.update(at=now(), lists=lists, tasks=keep + [t for t in tasks if t["id"] not in keep_ids], err="")
    save_cache(c)


def send(op):
    """One queued change to Google; the new task's id for an add."""
    a = api()
    if op["op"] == "add":
        body = {"title": op["title"]}
        if op.get("notes"): body["notes"] = op["notes"]
        if op.get("due"): body["due"] = op["due"] + "T00:00:00.000Z"
        return a.call("POST", "/lists/%s/tasks" % op["list"], body).get("id")
    path = "/lists/%s/tasks/%s" % (op["list"], op["id"])
    if op["op"] == "delete": a.call("DELETE", path)
    elif op["op"] == "done": a.call("PATCH", path, {"status": "completed"})
    elif op["op"] == "undone": a.call("PATCH", path, {"status": "needsAction", "completed": None})
    elif op["op"] == "edit": a.call("PATCH", path, {"title": op["title"], "due": (op["due"] + "T00:00:00.000Z") if op.get("due") else None})


def rename(old, new):
    c = cache()
    for t in c["tasks"]:
        if t["id"] == old: t["id"] = new
    save_cache(c)
    m = mine()
    if old in m: m[new] = m.pop(old); save_mine(m)
    save_queue([dict(o, id=new) if o.get("id") == old else o for o in queue()])


def flush():
    """Sends what waits; False when it stopped (offline, signed out)."""
    while True:
        q = queue()
        if not q: return True
        op = q[0]
        if op.get("id", "").startswith("local-") and op["op"] != "add":   # its add was refused: nothing to change
            save_queue(q[1:]); continue
        try: new = send(op)
        except (Offline, PermissionError): return False
        except urllib.error.HTTPError as e:
            if e.code >= 500: return False
            new = None   # gone or refused: dropped
        save_queue(queue()[1:])
        if op["op"] == "add" and new: rename(op["tmp"], new)


def change(op):
    """Queues one change and tries to send it now."""
    save_queue(queue() + [op])
    flush()


def sync(quiet=False):
    try:
        flush()
        fetch()
        msg = "Synced · %d open" % sum(1 for t in cache()["tasks"] if t["status"] != "completed")
    except PermissionError as e:
        c = cache(); c["err"] = str(e); save_cache(c)
        msg = "Enable the Google Tasks API, then sync again" if str(e) == "noapi" else "Sign in to Google Tasks first"
    except (Offline, urllib.error.HTTPError) as e:
        msg = "Offline · showing what was synced %s" % ago(cache()["at"])
    if not quiet: say(msg)


def status():
    c = cache()
    if c.get("at") and not c.get("err"): return "ok"   # synced fine last time: no keyring lookup on every open (a revoked sign-in shows at the next sync)
    if not FAKE:
        sys.path.insert(0, SHARE)
        import google
        if not google.have_client(): return "noclient"
    if not api().connected(): return "signin"
    err = cache().get("err")
    return err if err in ("noapi", "signin") else "ok"


# ---------- changes ----------

def parse_due(s):
    """"fri", "fredag", "tomorrow", "imorgon", "2026-11-05", "5 nov", "11-05" → YYYY-MM-DD, or None."""
    s = s.strip().lower().rstrip(".")
    t = today()
    if s in ("today", "idag"): return t.isoformat()
    if s in ("tomorrow", "imorgon", "i morgon"): return (t + dt.timedelta(days=1)).isoformat()
    for names in (WEEKDAYS, SV_DAYS):
        for i, n in enumerate(names):
            if s.startswith(n) and len(s) <= 9:
                return (t + dt.timedelta(days=(i - t.weekday() - 1) % 7 + 1)).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s) or re.fullmatch(r"()(\d{1,2})[-/](\d{1,2})", s)
    if m:
        y = int(m.group(1)) if m.group(1) else t.year
        try:
            d = dt.date(y, int(m.group(2)), int(m.group(3)))
            if not m.group(1) and d < t: d = d.replace(year=y + 1)
            return d.isoformat()
        except ValueError: return None
    m = re.fullmatch(r"(\d{1,2})\s*([a-zå]{3})[a-zå]*", s)
    if m and m.group(2)[:3].replace("maj", "may").replace("okt", "oct") in MONTHS:
        try:
            d = dt.date(t.year, MONTHS.index(m.group(2)[:3].replace("maj", "may").replace("okt", "oct")) + 1, int(m.group(1)))
            return (d if d >= t else d.replace(year=t.year + 1)).isoformat()
        except ValueError: return None
    return None


def split_text(text):
    """"Buy milk · fri" → ("Buy milk", "2026-11-06"); without a due part the whole text is the title."""
    title, sep, rest = text.rpartition("·")
    if sep and title.strip():
        d = parse_due(rest)
        if d: return title.strip(), d
    return text.strip(), None


def add(title, due=None, notes="", meta=None, lst=None):
    """A new task (the default list); meta marks it as k4's own. Returns its id."""
    c = cache()
    lst = lst or default_list(c)
    tmp = "local-" + secrets.token_hex(4)
    c["tasks"].insert(0, {"id": tmp, "list": lst, "title": title, "notes": notes, "status": "needsAction", "due": due or "", "completed": 0, "parent": "", "pos": "", "link": ""})
    save_cache(c)
    if meta is not None:
        m = mine(); m[tmp] = dict(meta, title=title, added=now()); save_mine(m)
    change({"op": "add", "tmp": tmp, "list": lst, "title": title, "due": due, "notes": notes})
    return next((t["id"] for t in cache()["tasks"] if t["id"] == tmp), None) or newest_id(title)


def newest_id(title):
    return next((t["id"] for t in cache()["tasks"] if t["title"] == title), "")


def find(ident):
    return next((t for t in cache()["tasks"] if t["id"] == ident), None)


def set_status(ident, done, why=None):
    """Ticks off (or reopens) a task; why: k4 ticked it (only ever on k4's own)."""
    c = cache()
    t = next((x for x in c["tasks"] if x["id"] == ident), None)
    if not t: return False
    t["status"], t["completed"] = ("completed", now()) if done else ("needsAction", 0)
    save_cache(c)
    m = mine()
    if ident in m:
        if done and why: m[ident].update(ticked=now(), tick_why=why)
        elif not done: m[ident].pop("ticked", None); m[ident].pop("tick_why", None)
        save_mine(m)
    change({"op": "done" if done else "undone", "list": t["list"], "id": ident})
    return True


def delete(ident):
    c = cache()
    t = next((x for x in c["tasks"] if x["id"] == ident), None)
    if not t: return False
    c["tasks"].remove(t); save_cache(c)
    m = mine()
    if ident in m: m[ident]["gone"] = now(); save_mine(m)
    change({"op": "delete", "list": t["list"], "id": ident})
    return True


def edit(ident, text):
    t = find(ident)
    if not t: return say("No such todo")
    title, due = split_text(text)
    if "·" in text and not due: say("Write it as: Title · fri (or · 2026-11-05)"); say("k4:tone yellow"); return
    c = cache()
    for x in c["tasks"]:
        if x["id"] == ident: x["title"], x["due"] = title, due or ""
    save_cache(c)
    change({"op": "edit", "list": t["list"], "id": ident, "title": title, "due": due})
    say("Saved · %s%s" % (title, " · " + when(due) if due else ""))


# ---------- k4's own (for the event finder) ----------

def k4_open():
    """k4's open todos (the finder may tick these off), oldest first: [(id, task, meta)]."""
    m = mine()
    out = [(t["id"], t, m[t["id"]]) for t in cache()["tasks"] if t["id"] in m and t["status"] != "completed"]
    return sorted(out, key=lambda x: x[2].get("added", 0))


def known(key=None, title=None):
    """Was this added by k4 before (any state, even deleted since): by key, or an open task by title."""
    m = mine()
    if key and any(v.get("key") == key for v in m.values()): return True
    if title:
        n = norm(title)
        if any(norm(t["title"]) == n for t in cache()["tasks"] if t["status"] != "completed"): return True
        if any(norm(v.get("title", "")) == n and v.get("added", 0) > now() - 30 * 86400 for v in m.values()): return True
    return False


# ---------- what the page, the bar and the launcher show ----------

def ago(t):
    if not t: return "never"
    s = int(now() - t)
    return "just now" if s < 60 else "%d min ago" % (s // 60) if s < 3600 else "%d h ago" % (s // 3600) if s < 86400 else "%d d ago" % (s // 86400)


def when(due):
    if not due: return ""
    d = dt.date.fromisoformat(due)
    t = today()
    if d == t: return "today"
    if d == t + dt.timedelta(days=1): return "tomorrow"
    if d < t: return "overdue · %s %d %s" % (d.strftime("%a"), d.day, d.strftime("%b"))
    return "%s %d %s" % (d.strftime("%a"), d.day, d.strftime("%b"))


def order(ts):
    """Overdue and today first, then by due date, then undated (Google's own order), subtasks under their parent."""
    t = today().isoformat()
    top = sorted((x for x in ts if not x["parent"]), key=lambda x: (0 if x["due"] and x["due"] <= t else 1 if x["due"] else 2, x["due"] or "9", x["pos"]))
    kids = {}
    for x in ts:
        if x["parent"]: kids.setdefault(x["parent"], []).append(x)
    out = []
    for x in top:
        out.append(x)
        out += sorted(kids.pop(x["id"], []), key=lambda k: k["pos"])
    for rest in kids.values(): out += rest   # a parent that is done or gone
    return out


def due_now(c=None):
    c = c or cache()
    t = today().isoformat()
    return order([x for x in c["tasks"] if x["status"] != "completed" and x["due"] and x["due"] <= t])


def page():
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    rid = lambda act: b64("k4-todo run " + b64(act))
    me = shlex.quote(FRONT)
    out = []
    def row(label, act, meta="", flags="", stay=True):
        out.append("A\t%s\t%s\t%s\t\t%s" % (rid(act), field(label), field(meta), ("stay;" + flags if stay else flags).strip(";")))
    st = status()
    if st != "ok":
        out.append("D\tGoogle Tasks · your todo lists\tnot connected\tSearch todos…")
        out.append("Y\t↑↓\tStep\t↵\tDo it\t⌫\tBack")
        if st == "noclient":
            out.append("N\tConnect Google first\tTodos use the same Google sign-in as Calendar and Mail. Set up Calendar (Apps › Calendar) or Mail once, then come back here.\taccent\t")
            row("Set up Google Calendar", "bg k4-cal connect", "the OAuth client, once", "mark=1;markc=accent")
        else:
            out.append("N\t%s\tk4 shows your Google Tasks lists here and on the bar beside the clock. It uses the Google sign-in Calendar and Mail use, with its own permission for tasks.\t%s\t"
                       % ("The Google Tasks API isn’t on yet" if st == "noapi" else "Connect Google Tasks", "yellow" if st == "noapi" else "accent"))
            row("Enable the Google Tasks API", "bg xdg-open https://console.cloud.google.com/apis/library/tasks.googleapis.com", "Cloud Console › your k4 project › Enable", "mark=1;markc=accent")
            row("Sign in" if st != "noapi" else "Sync again", "bg %s signin" % me if st != "noapi" else "%s sync" % me, "Google asks once" if st != "noapi" else "after enabling it", "mark=2;markc=accent")
        print("\n".join(out)); return
    c = cache()
    m = mine()
    t = today().isoformat()
    open_ = [x for x in c["tasks"] if x["status"] != "completed"]
    over = sum(1 for x in open_ if x["due"] and x["due"] < t)
    dn = sum(1 for x in open_ if x["due"] == t)
    count = " · ".join(p for p in ("%d overdue" % over if over else "", "%d today" % dn if dn else "") if p) or "%d open" % len(open_)
    out.append("D\tGoogle Tasks · type to add (“Buy milk · fri”)\t%s\tAdd a todo… (· fri for a due date)" % count)
    out.append("Q\t" + rid("%s add-input" % me))
    out.append("Y\t↑↓\tMove\t↵\tDone\t⌃E\tEdit\tDel\tDelete\ttype\tAdd\t⌫\tBack")
    for l in c["lists"] or [{"id": default_list(c), "title": "My Tasks"}]:
        ts = order([x for x in open_ if x["list"] == l["id"]])
        out.append("H\t%s\t%s" % (field(l["title"]), len(ts) or ""))
        for x in ts:
            k = m.get(x["id"])
            late = x["due"] and x["due"] < t
            flags = ["mark=%s" % ("!" if late else "○"), "markc=%s" % ("red" if late else "accent" if x["due"] == t else "dim"),
                     "metac=%s" % ("red" if late else "accent" if x["due"] == t else "dim"), "del=" + rid("%s delete %s" % (me, x["id"])), "k^e=" + rid("%s edit-ask %s" % (me, x["id"]))]
            sub = ("from %s · %s%s" % (k.get("who") or k.get("source"), SOURCES.get(k.get("source", ""), k.get("source", "").title()), " · “%s”" % k["why"] if k.get("why") else "")) if k else x["notes"].split("\n")[0]
            if sub: flags += ["l2=" + flag(sub), "l2c=dim"]
            if k: flags += ["chip=K4", "chipc=accent", "k^o=" + rid("%s open %s" % (me, x["id"]))]
            row(("   ↳ " if x["parent"] else "") + x["title"], "%s done %s" % (me, x["id"]), when(x["due"]), ";".join(flags))
        if not ts: out.append("E\tNothing to do")
    ticked = sorted(((x, m[x["id"]]) for x in c["tasks"] if x["status"] == "completed" and x["id"] in m and m[x["id"]].get("ticked", 0) > now() - 7 * 86400), key=lambda p: -p[1]["ticked"])
    if ticked:
        out.append("H\tTicked off by k4 · this week · ↵ reopens\t%d" % len(ticked))
        for x, k in ticked:
            row(x["title"], "%s undone %s" % (me, x["id"]), ago(k["ticked"]), "mark=✓;markc=green;dim;l2=%s;l2c=dim;k^o=%s" % (flag("“%s”" % k.get("tick_why", "")), rid("%s open %s" % (me, x["id"]))))
    done = sorted((x for x in c["tasks"] if x["status"] == "completed" and not (x["id"] in m and m[x["id"]].get("ticked"))), key=lambda x: -x["completed"])[:5]
    if done:
        out.append("H\tDone\t")
        for x in done: row(x["title"], "%s undone %s" % (me, x["id"]), ago(x["completed"]) if x["completed"] else "", "mark=✓;markc=green;dim")
    out.append("H\tMore\t")
    if os.environ.get("K4_PI_SEEN"):   # the Pi adds and ticks off k4's todos: say when it hasn't been heard from
        try: seen = float(open(os.environ["K4_PI_SEEN"]).read().strip() or 0)
        except (OSError, ValueError): seen = 0
        if now() - seen > 900: row("The Pi (%s) isn’t answering" % os.environ.get("K4_PI", "pi"), ":", "last heard %s · k4’s own todos catch up when it does" % ago(seen), "mark=!;markc=yellow;dim", stay=False)
    q = len(queue())
    row("Sync now", "%s sync" % me, "synced %s%s · every 5 min" % (ago(c["at"]), " · %d waiting to send" % q if q else ""), "mark=↻;markc=accent")
    print("\n".join(out))


def bar():
    """The bar module beside the clock: the next todo due (today or overdue) and how many; red when
    one is overdue; hidden when nothing is due."""
    if status() != "ok": print("{}"); return
    ds = due_now()
    if not ds: print("{}"); return
    late = [x for x in ds if x["due"] < today().isoformat()]
    o = {"icon": "󰄱", "text": ds[0]["title"][:40], "tooltip": "Todo · " + " · ".join("%s (%s)" % (x["title"], when(x["due"])) for x in ds[:6]) + (" …" if len(ds) > 6 else "")}
    if len(ds) > 1: o["pill"] = str(len(ds))
    if late: o.update(icon_tone="red", badge_tone="red")
    print(json.dumps(o, ensure_ascii=False))


def find_rows():
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    for x in order([t for t in cache()["tasks"] if t["status"] != "completed"]):
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=60;tag=Todo;icon=󰄱;find=%s" % (b64("k4-todo run " + b64("%s done %s" % (me, x["id"]))), field(x["title"]),
              field(("%s · " % when(x["due"]) if x["due"] else "") + "↵ ticks it off"), flag("todo " + x["title"])))


def post(title, body, acts, ident):
    if FAKE:
        with open(os.path.join(FAKE, "posts.log"), "a") as f: f.write("%s | %s | %s\n" % (title, body, acts))
        return
    line = "\t".join(["post", "0", "Todo", field(title), field(body), "done", "-1", "-1", "", "", "", acts, "%s card %s" % (FRONT, ident)])
    sys.path.insert(0, SHARE)
    import k4host
    k4host.post(line)


def open_source(ident):
    k = mine().get(ident)
    t = find(ident)
    cmd = (k or {}).get("open_cmd") or (["xdg-open", t["link"]] if t and t.get("link") else ["xdg-open", "https://tasks.google.com"])
    if FAKE: log("open " + " ".join(cmd)); return
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv):
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if cmd == "sync": sync("--quiet" in rest)
    elif cmd == "signin":
        ok, msg = api().acct.sign_in() if not FAKE else (True, "")
        if ok: c = cache(); c["err"] = ""; save_cache(c); sync(True)
        say("Google Tasks connected" if ok else "Not connected · " + msg)
    elif cmd == "signout": api().acct.sign_out() if not FAKE else None; say("Signed out")
    elif cmd in ("add", "add-input"):
        text = " ".join(rest) if cmd == "add" else os.environ.get("K4_INPUT", "")
        if not text.strip(): return say("Type the todo first")
        title, due = split_text(text)
        add(title, due)
        q = len(queue())
        say("Added · %s%s%s" % (title, " · " + when(due) if due else "", " · sends when online" if q else ""))
    elif cmd in ("done", "undone") and rest:
        t = find(rest[0])
        if not t: return say("No such todo")
        flip = cmd == "done" and t["status"] == "completed"   # ↵ on a done one (from search) reopens it
        set_status(rest[0], cmd == "done" and not flip)
        say(("Done · %s" if cmd == "done" and not flip else "Reopened · %s") % t["title"])
    elif cmd == "done-next":
        ds = due_now()
        if not ds: return say("Nothing due")
        set_status(ds[0]["id"], True)
        post("Done · %s" % ds[0]["title"], "%d more due" % (len(ds) - 1) if len(ds) > 1 else "nothing else due today", "undo:Undo", ds[0]["id"])
    elif cmd == "delete" and rest:
        t = find(rest[0])
        if delete(rest[0]): say("Deleted · %s" % t["title"])
    elif cmd == "edit" and rest: edit(rest[0], os.environ.get("K4_INPUT") or " ".join(rest[1:]))
    elif cmd == "edit-ask" and rest:
        t = find(rest[0]) or {}
        b64 = lambda x: base64.b64encode(x.encode()).decode()
        say("k4:input\t%s\t%s\t%s" % (b64("k4-todo run " + b64("%s edit %s" % (shlex.quote(FRONT), rest[0]))), "Title · due day or date",
                                      "now: %s%s" % (t.get("title", "?"), " · " + t["due"] if t.get("due") else "")))
    elif cmd == "open" and rest: open_source(rest[0])
    elif cmd == "card" and len(rest) > 1:   # card ID BUTTON NOTE (a card's button)
        if rest[1] == "undo": set_status(rest[0], False)
        elif rest[1] == "default": subprocess.Popen([FRONT], start_new_session=True) if not FAKE else log("open page")
    elif cmd == "page": page()
    elif cmd == "bar": bar()
    elif cmd == "find": find_rows()
    elif cmd == "status": say(status())
    else: say(__doc__.strip()); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
