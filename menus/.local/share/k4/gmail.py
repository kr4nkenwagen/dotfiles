#!/usr/bin/env python3
"""gmail.py: k4's Gmail (k4-mail runs it): the sync, the cache, the window's data and its actions.

  gmail.py data                 the window's lines (src/mail.odin): S V G T O M A
  gmail.py sync [--quiet]       what changed since the last sync (history), the open label again;
                                new Inbox mail posts a card (k4 --notify-ctl)
  gmail.py act VERB [ARG…]      open T, close, label G, more, search Q, clear, archive T, trash T,
                                star T, unread T, read T, move T G, send reply|replyall T ($K4_INPUT),
                                compose [reply|replyall|forward T] (a draft in the editor), attachment
                                MSG AID NAME, browser [T], connect, disconnect, sync
  gmail.py note KEY CARD        a card's button (default, read, archive, inline-reply: $K4_INPUT)
  gmail.py bar | count | find   the bar (JSON), the Inbox's unread count, the launcher's rows (TSV)

Signed in with google.py (scope gmail.modify: read, label, archive, trash, send; never a
permanent delete); the cache is ~/.cache/k4/mail (K4_MAIL_DIR in tests, where K4_MAIL_FAKE
names a folder of API answers and the calls made are logged to its calls.log).
"""
import base64, concurrent.futures, email.message, email.utils, html, html.parser, json, os, re
import shlex, subprocess, sys, tempfile, time, urllib.error, urllib.parse

HOME = os.path.expanduser("~")
DIR = os.environ.get("K4_MAIL_DIR") or os.path.join(HOME, ".cache/k4/mail")
FAKE = os.environ.get("K4_MAIL_FAKE")
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
SELF = os.path.realpath(__file__)
FRONT = os.environ.get("K4_MAIL_FRONT") or "k4-mail"
sys.path.insert(0, os.path.dirname(SELF))
import google  # noqa: E402
import mailimap  # noqa: E402  (the IMAP accounts aerc has: All inboxes, a section each)

API = "https://gmail.googleapis.com/gmail/v1/users/me"
GOOGLE = google.Account("Gmail", "https://www.googleapis.com/auth/gmail.modify", ["service", "k4-google-mail"],
                        os.path.join(RUN, "k4-mail-token.json"), API,
                        test_token=(lambda: "test") if FAKE else None)
PAGE = 50
mailimap.DIR = DIR
NL = " "   # a line break inside a field (the panel's lines are one per record)
SYSTEM = [("INBOX", "Inbox"), ("STARRED", "Starred"), ("SNOOZED", "Snoozed"), ("IMPORTANT", "Important"),
          ("SENT", "Sent"), ("DRAFT", "Drafts"), ("SPAM", "Spam"), ("TRASH", "Trash")]


# ---------- files ----------

def path(*p): return os.path.join(DIR, *p)


def load(name, default):
    try:
        with open(path(name)) as f: return json.load(f)
    except (OSError, ValueError): return default


def save(name, data):
    os.makedirs(os.path.dirname(path(name)), exist_ok=True)
    tmp = path(name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(data, f)
    os.replace(tmp, path(name))


def field(s): return re.sub(r"[\t\r\n]+", " ", str(s or "")).strip()


def multi(s): return str(s or "").replace(NL, " ").replace("\t", "    ").replace("\r", "").replace("\n", NL)


def say(*lines):
    for ln in lines: print(ln, flush=True)


# ---------- the API ----------

def api(method, url, body=None, query=None, raw=None, ctype=None):
    if FAKE:  # tests: answers from files named after the call, and a log of the calls
        with open(os.path.join(FAKE, "calls.log"), "a") as f:
            f.write("%s %s%s%s\n" % (method, url, ("?" + urllib.parse.urlencode(query, doseq=True)) if query else "",
                                     (" " + json.dumps(body, sort_keys=True)) if body is not None else ""))
        name = re.sub(r"[^A-Za-z0-9]+", "_", "%s %s" % (method, url)).strip("_") + ".json"
        try:
            with open(os.path.join(FAKE, name)) as f: return json.load(f)
        except OSError:
            return {}
    return GOOGLE.request(method, url, body, query, raw, ctype)


def open_url(url):
    if FAKE:  # tests: never a browser
        with open(os.path.join(FAKE, "calls.log"), "a") as f: f.write("OPEN %s\n" % url)
        return
    google.open_url(url)


def connected(): return bool(FAKE) or bool(GOOGLE.refresh_token())


def state():
    """ok, noclient (no OAuth client file), connect (never signed in), signin (expired), offline, error"""
    st = load("state.json", {})
    if not FAKE and not google.have_client(): return "noclient", st
    if not connected(): return "connect", st
    return st.get("status", "ok"), st


def set_status(status, note=""):
    st = load("state.json", {})
    st.update(status=status, note=note)
    save("state.json", st)


def guarded(fn):
    """The API's failures as the window's state: signin, offline, error."""
    def run(*a, **k):
        try:
            r = fn(*a, **k)
            st = load("state.json", {})
            if r and st.get("status") not in (None, "ok"): set_status("ok")   # (a step that failed inside keeps its why)
            return r
        except PermissionError:
            set_status("signin", "Google wants you to sign in again")
            if not quiet_cards(): signin_card()
        except urllib.error.HTTPError as e:
            set_status("error", google_says(e))
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            set_status("offline", field(getattr(e, "reason", e)))
        return None
    return run


# ---------- messages ----------

def google_says(e):
    """An HTTP error as Google words it: its message's first sentence (a disabled API, a quota)."""
    try:
        msg = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")
    except (ValueError, OSError, AttributeError):
        msg = ""
    if "has not been used" in msg or "is disabled" in msg:
        return "The Gmail API is off in your Google Cloud project · turn it on (↵ opens the page), wait a minute"
    return field(msg.split(". ")[0]) or "Gmail answered %d" % e.code


def b64(data): return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)) if data else b""


def headers(payload): return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def who(addr, me=""):
    """A From/To header as short names: 'Maja Lind' (or the mailbox's local part), 'me' for you."""
    out = []
    for name, mail in email.utils.getaddresses([addr or ""]):
        if me and mail.lower() == me.lower(): out.append("me"); continue
        out.append(name.strip('"') or mail.split("@")[0])
    return out


class Text(html.parser.HTMLParser):
    """HTML mail as plain text: blocks as lines, links kept as 'text <url>', quotes as '> '."""
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.href, self.skip, self.quote = [], None, 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("style", "script", "head", "title"): self.skip += 1
        elif tag == "a": self.href = a.get("href")
        elif tag == "blockquote": self.quote += 1; self.out.append("\n")
        elif tag == "li": self.out.append("\n• ")
        elif tag in self.BLOCK: self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head", "title"): self.skip = max(0, self.skip - 1)
        elif tag == "a": self.href = None
        elif tag == "blockquote": self.quote = max(0, self.quote - 1); self.out.append("\n")
        elif tag in self.BLOCK: self.out.append("\n")

    def handle_data(self, d):
        if self.skip: return
        d = re.sub(r"\s+", " ", d)
        if self.href and self.href.startswith("http") and self.href not in d and d.strip():
            d = "%s <%s>" % (d.strip(), self.href)
        if self.quote and self.out and self.out[-1].endswith("\n"): d = "> " * self.quote + d.lstrip()
        self.out.append(d)

    def text(self):
        t = "".join(self.out)
        t = "\n".join(ln.strip() for ln in t.split("\n"))
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def html_text(s):
    p = Text()
    try: p.feed(s); p.close()
    except Exception: return re.sub(r"<[^>]+>", " ", s)
    return p.text()


def part_text(p):
    raw = b64(p.get("body", {}).get("data", ""))
    cs = "utf-8"
    for h in p.get("headers", []):
        if h["name"].lower() == "content-type":
            m = re.search(r'charset="?([\w.-]+)', h["value"], re.I)
            if m: cs = m.group(1)
    try: return raw.decode(cs, "replace")
    except LookupError: return raw.decode("utf-8", "replace")


def walk(p):
    yield p
    for c in p.get("parts", []) or []: yield from walk(c)


def body_of(payload):
    """(text, attachments): text/plain preferred, else HTML made text; Gmail has already undone
    base64 and quoted-printable into body.data (base64url)."""
    plain, rich, att = [], [], []
    for p in walk(payload):
        mt, b = p.get("mimeType", ""), p.get("body", {})
        if p.get("filename") and (b.get("attachmentId") or b.get("data")):
            att.append({"id": b.get("attachmentId", ""), "name": p["filename"], "size": b.get("size", 0), "mime": mt,
                        "inline": "inline" in str(headers(p).get("content-disposition", "")).lower()})
        elif mt == "text/plain" and b.get("data"): plain.append(part_text(p))
        elif mt == "text/html" and b.get("data"): rich.append(part_text(p))
    if plain: text = "\n".join(plain)
    elif rich: text = html_text("\n".join(rich))
    else: text = ""
    return text.replace("\r\n", "\n").strip(), att


QUOTE_HEAD = re.compile(r"^(On .{4,200} wrote:|Den .{4,200} skrev:|-{2,} ?Original Message ?-{2,}|-{2,} ?Forwarded message ?-{2,}|From: .+)$", re.I)


def split_quote(text):
    """(new, quoted, head): the part written in this mail, the quoted rest, and the line that starts it."""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if QUOTE_HEAD.match(s) and (i + 1 >= len(lines) or lines[i + 1].startswith(">") or s.startswith("-") or s.lower().startswith("from:")):
            return "\n".join(lines[:i]).rstrip(), "\n".join(lines[i + 1:]).strip(), s
        if s.startswith(">") and all(not x.strip() or x.startswith(">") for x in lines[i:]):
            return "\n".join(lines[:i]).rstrip(), "\n".join(lines[i:]).strip(), ""
    return text, "", ""


def parse_message(m, me):
    h = headers(m.get("payload", {}))
    text, att = body_of(m.get("payload", {}))
    new, quoted, qhead = split_quote(text)
    return {"id": m["id"], "thread": m.get("threadId", ""), "from": h.get("from", ""), "to": h.get("to", ""),
            "addr": (email.utils.getaddresses([h.get("from", "")]) or [("", "")])[0][1],
            "cc": h.get("cc", ""), "subject": h.get("subject", ""), "ts": int(m.get("internalDate", "0")) // 1000,
            "labels": m.get("labelIds", []), "snippet": html.unescape(m.get("snippet", "")),
            "body": new, "quoted": quoted, "qhead": qhead, "att": att,
            "msgid": h.get("message-id", ""), "refs": h.get("references", ""), "reply_to": h.get("reply-to", ""),
            "mine": h.get("from", "").lower().find((me or "\0").lower()) >= 0}


def summary(t, me, labelnames):
    """One thread as the list's row."""
    msgs = t.get("messages", [])
    if not msgs: return None
    names, addr = [], ""
    for m in msgs:
        h = headers(m.get("payload", {}))
        for n in who(h.get("from", ""), me):
            if n not in names: names.append(n)
        for name, mail in email.utils.getaddresses([h.get("from", "")]):
            if mail and (not me or mail.lower() != me.lower()):
                addr = mail
                if name: CONTACTS[name.strip('"')] = mail
    first, last = headers(msgs[0].get("payload", {})), msgs[-1]
    labels = set(l for m in msgs for l in m.get("labelIds", []))
    attach = any("multipart/mixed" in headers(m.get("payload", {})).get("content-type", "") for m in msgs)
    return {"id": t["id"], "hist": t.get("historyId", ""), "from": ", ".join(names[-3:]), "addr": addr,
            "subject": first.get("subject", "") or "(no subject)", "snippet": html.unescape(last.get("snippet", "")),
            "ts": int(last.get("internalDate", "0")) // 1000, "unread": "UNREAD" in labels, "starred": "STARRED" in labels,
            "count": len(msgs), "attach": attach,
            "labels": [labelnames[l] for l in labels if l in labelnames and not l.isupper()]}


# ---------- sync ----------

CONTACTS = {}   # name → address, from the mail seen (the compose card's To finds people by name)


def save_contacts():
    if not CONTACTS: return
    c = load("contacts.json", {})
    c.update(CONTACTS)
    save("contacts.json", c)

def label_names():
    return {l["id"]: l["name"] for l in load("state.json", {}).get("labels", [])}


def fetch_labels():
    ls = api("GET", "/labels").get("labels", [])
    want = [l for l in ls if l["id"] in dict(SYSTEM) or l.get("type") == "user"]

    def one(l):
        try: g = api("GET", "/labels/" + urllib.parse.quote(l["id"]))
        except Exception: g = l
        return {"id": l["id"], "name": dict(SYSTEM).get(l["id"], l.get("name", l["id"])),
                "kind": "system" if l["id"] in dict(SYSTEM) else "user",
                "unread": g.get("threadsUnread", 0) if l["id"] not in ("SENT", "DRAFT", "TRASH") else 0,
                "total": g.get("threadsTotal", 0)}
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        got = list(ex.map(one, want))
    order = {k: i for i, (k, _) in enumerate(SYSTEM)}
    got.sort(key=lambda l: (l["kind"] != "system", order.get(l["id"], 99), l["name"].lower()))
    return got


def view():
    return load("view.json", {"label": "INBOX", "query": "", "open": ""})


def list_key(v): return "lists/%s.json" % re.sub(r"[^A-Za-z0-9_-]+", "_", "q-" + v["query"] if v["query"] else v["label"])[:120]


def fetch_list(v, page=None):
    """The view's threads (the label's, or the search's), PAGE at a time; summaries reused while
    a thread's historyId is the same."""
    me = load("state.json", {}).get("account", "")
    q = {"maxResults": PAGE}
    if v["query"]: q["q"] = v["query"]
    else: q["labelIds"] = v["label"]
    if page: q["pageToken"] = page
    r = api("GET", "/threads", query=q)
    old = {t["id"]: t for t in load(list_key(v), {}).get("threads", [])}
    names = label_names()

    def one(t):
        o = old.get(t["id"])
        if o and o.get("hist") == t.get("historyId"): return o
        full = api("GET", "/threads/" + t["id"], query={"format": "metadata",
                                                         "metadataHeaders": ["From", "Subject", "Date", "Content-Type"]})
        return summary(full, me, names)
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        rows = [x for x in ex.map(one, r.get("threads", [])) if x]
    prev = load(list_key(v), {}).get("threads", []) if page else []
    seen = {t["id"] for t in rows}
    rows = [t for t in prev if t["id"] not in seen] + rows if page else rows
    save(list_key(v), {"threads": rows, "next": r.get("nextPageToken", "")})
    save_contacts()
    return rows


def fetch_thread(tid):
    me = load("state.json", {}).get("account", "")
    t = api("GET", "/threads/" + tid, query={"format": "full"})
    msgs = [parse_message(m, me) for m in t.get("messages", [])]
    save("threads/%s.json" % re.sub(r"\W", "", tid), {"id": tid, "messages": msgs})
    return msgs


def run_queue():
    """What waited offline, sent now (stops at the first failure: the rest stay)."""
    q = load("queue.json", [])
    while q:
        op = q[0]
        api(op["method"], op["url"], op.get("body"), raw=op["raw"].encode() if op.get("raw") else None,
            ctype=op.get("ctype"))
        q.pop(0)
        save("queue.json", q)


@guarded
def full_sync():
    prof = api("GET", "/profile")
    st = load("state.json", {})
    st.update(account=prof.get("emailAddress", st.get("account", "")), history=prof.get("historyId", st.get("history")))
    st["labels"] = fetch_labels()
    save("state.json", st)
    fetch_list(view())
    if view()["label"] != "INBOX" or view()["query"]:
        fetch_list({"label": "INBOX", "query": ""})
    st = load("state.json", {})
    st.update(synced=int(time.time()), status="ok", note="")
    save("state.json", st)
    return True


@guarded
def sync(quiet=False):
    run_queue()
    st = load("state.json", {})
    if not st.get("history"): return full_sync()
    try:
        h = api("GET", "/history", query={"startHistoryId": st["history"], "historyTypes": ["messageAdded", "labelAdded", "labelRemoved", "messageDeleted"]})
    except urllib.error.HTTPError as e:
        if e.code == 404: st.pop("history", None); save("state.json", st); return full_sync()
        raise
    recs = h.get("history", [])
    st["history"] = h.get("historyId", st["history"])
    st["synced"] = int(time.time())
    save("state.json", st)
    if recs:
        new = [a["message"] for r in recs for a in r.get("messagesAdded", [])
               if "INBOX" in a["message"].get("labelIds", []) and "UNREAD" in a["message"].get("labelIds", [])]
        st["labels"] = fetch_labels()
        save("state.json", st)
        fetch_list(view())
        if view()["label"] != "INBOX" or view()["query"]:
            fetch_list({"label": "INBOX", "query": ""})
        v = view()
        if v.get("open"): fetch_thread(v["open"])
        if new and not quiet_cards(): post_cards(new)
    return True


def quiet_cards(): return os.environ.get("K4_MAIL_NO_CARDS") == "1"


# ---------- cards (k4's notifications) ----------

def post_line(old, title, body, acts, persistent=False):
    line = "\t".join(["post", str(old), "Mail", field(title), field(body)[:300], "1", "-1" if not persistent else "0", "-1", "", "󰊫", "",
                      acts, "%s note" % shlex.quote(FRONT)])
    try:
        out = subprocess.run(["k4", "--notify-ctl", line], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out if out.isdigit() else ""


def post_cards(new):
    """A card per new mail (its thread's card replaced), or one "N new mails" when several come at once."""
    if len([m for m in new if m["id"] not in set(load("seen.json", []))]) > 1: return post_many(new)

    me = load("state.json", {}).get("account", "")
    cards = load("cards.json", {})
    seen = set(load("seen.json", []))
    v = view()
    for m in new:
        if m["id"] in seen: continue
        seen.add(m["id"])
        if v.get("open") == m.get("threadId") and window_open(): continue   # the window shows it
        full = api("GET", "/messages/" + m["id"], query={"format": "metadata", "metadataHeaders": ["From", "Subject"]})
        h = headers(full.get("payload", {}))
        if me and me.lower() in h.get("from", "").lower(): continue
        title = ", ".join(who(h.get("from", ""))) or "New mail"
        body = (h.get("subject", "") or "(no subject)") + " — " + html.unescape(full.get("snippet", ""))
        tid = m.get("threadId", "")
        old = next((int(c) for c, t in cards.items() if t == tid), 0)
        out = post_line(old, title, body, "inline-reply:Reply,archive:Archive,read:Mark read,default:")
        if out:
            cards = {c: t for c, t in cards.items() if t != tid}
            cards[out] = tid
    save("cards.json", cards)
    save("seen.json", list(seen)[-500:])


def post_many(new):
    me = load("state.json", {}).get("account", "")
    seen = set(load("seen.json", []))
    fresh = [m for m in new if m["id"] not in seen]
    people, newest = [], ""
    for m in fresh:
        full = api("GET", "/messages/" + m["id"], query={"format": "metadata", "metadataHeaders": ["From", "Subject"]})
        h = headers(full.get("payload", {}))
        if me and me.lower() in h.get("from", "").lower(): continue
        for n in who(h.get("from", "")):
            if n not in people: people.append(n)
        newest = newest or h.get("subject", "")
    seen.update(m["id"] for m in fresh)
    save("seen.json", list(seen)[-500:])
    if not people: return
    cards = load("cards.json", {})
    old = next((int(c) for c, t in cards.items() if t == "*"), 0)
    names = ", ".join(people[:-1]) + " and " + people[-1] if len(people) > 1 else people[0]
    out = post_line(old, "%d new mails" % len(fresh), "From %s · newest: %s" % (names, newest), "read-all:Mark all read,default:Open Inbox")
    if out: cards = {c: t for c, t in cards.items() if t != "*"}; cards[out] = "*"; save("cards.json", cards)


def signin_card():
    """Google ended the sign-in: one card that stays until it is handled."""
    cards = load("cards.json", {})
    if "signin" in cards.values(): return
    acct = load("state.json", {}).get("account", "")
    out = post_line(0, "Sign in to Gmail again", "Google ended the sign-in%s. New mail waits until you sign in." % (" for " + acct if acct else ""),
                    "signin:Sign in,default:", persistent=True)
    if out: cards[out] = "signin"; save("cards.json", cards)


def drop_cards(tid):
    cards = load("cards.json", {})
    for c, t in list(cards.items()):
        if t == tid:
            subprocess.run(["k4", "--notify-ctl", "close %s" % c], capture_output=True, timeout=5)
            cards.pop(c)
    save("cards.json", cards)


def syncing():
    """A sync runs now (it holds the lock)."""
    import fcntl
    try:
        fd = os.open(os.path.join(RUN, "k4-mail-sync.lock"), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
        return False
    except OSError:
        return True


def window_open():
    return subprocess.run(["pgrep", "-f", "^k4 --mail"], capture_output=True).returncode == 0


# ---------- the accounts ----------
# Gmail (the API, its labels) and each IMAP account (mailimap.py, its folders). Ids with a colon
# are IMAP's: <account>:<folder> a folder, <account>:<folder>:<uid> a message. ALL: every inbox.

def imap_of(x):
    """The IMAP account an id is of (None: Gmail's)."""
    sp = mailimap.split_id(x or "")
    return mailimap.by_id(sp[0]) if sp else None


def gmail_on():
    status, _ = state()
    return status not in ("noclient", "connect")


def all_rows(query=""):
    """Every account's inbox (or a search in them), newest first: (row, account id)."""
    out = []
    if gmail_on():
        v = {"label": "INBOX", "query": query}
        out += [(t, "gmail") for t in load(list_key(v), {}).get("threads", [])]
    for a in mailimap.accounts():
        out += [(t, a["id"]) for t in mailimap.rows(a, "INBOX", query or None)]
    out.sort(key=lambda x: -x[0]["ts"])
    return out


def view_rows(v):
    if v["label"] == "ALL": return all_rows(v["query"])
    a = imap_of(v["label"])
    if a:
        folder = mailimap.split_id(v["label"])[1]
        return [(t, a["id"]) for t in mailimap.rows(a, folder, v["query"] or None)]
    return [(t, "gmail") for t in load(list_key(v), {}).get("threads", [])]


def imap_unread():
    return sum(next((f["unread"] for f in mailimap.state(a).get("folders", []) if f["role"] == "Inbox"), 0) for a in mailimap.accounts())


def imap_sync(force=False, view_folder=None, search=None, cards=True):
    """The IMAP accounts once a minute (force: now); new Inbox mail posts cards."""
    for a in mailimap.accounts():
        st = mailimap.state(a)
        if not force and time.time() - st.get("synced", 0) < 55 and view_folder is None: continue
        mine = view_folder if view_folder and imap_of(view_folder) is a else None
        try:
            new = mailimap.sync(a, mailimap.split_id(mine)[1] if mine else None, search if mine else None)
        except PermissionError as e:
            st.update(status="signin", note=field(e)); mailimap.save(a, "state.json", st); continue
        except (OSError, mailimap.imaplib.IMAP4.error) as e:
            st.update(status="offline", note=field(e)); mailimap.save(a, "state.json", st); continue
        if new and cards and not quiet_cards(): imap_cards(a, new)


def imap_cards(a, uids):
    rows = {t["id"].rpartition(":")[2]: t for t in mailimap.rows(a, "INBOX")}
    got = [rows[u] for u in uids if u in rows]
    if not got: return
    cards = load("cards.json", {})
    if len(got) > 1:
        names = []
        for t in got:
            if t["from"] not in names: names.append(t["from"])
        out = post_line(0, "%d new mails · %s" % (len(got), a["name"]), "From %s · newest: %s" % (", ".join(names[:3]), got[0]["subject"]), "default:Open Inbox")
        if out: cards[out] = "*"
    else:
        t = got[0]
        out = post_line(0, "%s · %s" % (t["from"], t["subject"]), "%s · %s" % (a["name"], t["snippet"]), "inline-reply:Reply,archive:Archive,read:Mark read,default:")
        if out: cards[out] = t["id"]
    save("cards.json", cards)


def froms():
    """Who you can write as: (account id, address, name)."""
    out = []
    st = load("state.json", {})
    if gmail_on() and st.get("account"): out.append(("gmail", st["account"], "Gmail"))
    for a in mailimap.accounts(): out.append((a["id"], a["from"], a["name"]))
    return out


# ---------- the window's data ----------

def data():
    status, st = state()
    imaps = mailimap.accounts()
    v = view()
    if imaps and v["label"] == "INBOX" and not st.get("labels"): v["label"] = "ALL"   # (Gmail not there yet: every inbox)
    inbox = (next((l["unread"] for l in st.get("labels", []) if l["id"] == "INBOX"), 0) if gmail_on() else 0) + imap_unread()
    note = st.get("note", "")
    if imaps and status in ("noclient", "connect", "signin"):   # the IMAP accounts work without Gmail
        note = "Gmail is not connected · Apps › Mail connects it" if status != "signin" else "Gmail wants you to sign in again · Apps › Mail"
        status = "ok"
    if status == "ok" and not st.get("labels") and not imaps and syncing(): status = "syncing"   # the first sync: nothing to show yet
    bad = [a["name"] for a in imaps if mailimap.state(a).get("status") in ("signin", "offline")]
    if bad and status == "ok": note = (note + " · " if note else "") + "%s not answering" % ", ".join(bad)
    say("S\t%s\t%d\t%s\t%s\t%d\t%d" % (status, inbox, field(st.get("account", "") or (imaps[0]["login"] if imaps else "")), field(note),
                                       len(load("queue.json", [])), st.get("synced", 0) or max([mailimap.state(a).get("synced", 0) for a in imaps] or [0])))
    more = load(list_key(v), {}).get("next") if not imap_of(v["label"]) and v["label"] != "ALL" else ""
    say("V\t%s\t%s\t%s" % (v["label"], field(v["query"]), "1" if more else "0"))
    for acct, addr, name in froms(): say("Y\t%s\t%s\t%s" % (acct, field(addr), field(name)))
    if imaps: say("G\tALL\tAll inboxes\t%d\tsystem\t0\tall" % inbox)
    if gmail_on():
        for l in st.get("labels", []):
            say("G\t%s\t%s\t%d\t%s\t%d\tgmail" % (l["id"], field(l["name"]), l.get("unread", 0), l["kind"], l.get("total", 0)))
    for a in imaps:
        for f in mailimap.state(a).get("folders", []):
            say("G\t%s:%s\t%s\t%d\t%s\t%d\t%s" % (a["id"], f["id"], field(f["name"]), f["unread"], "system" if f["role"] else "folder", f["total"], a["id"]))
    for t, acct in view_rows(v):
        say("T\t%s\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%s\t%s" % (t["id"], field(t["from"]), field(t["subject"]), field(t["snippet"]),
            t["ts"], t["unread"], t["starred"], t["count"], t["attach"], field("|".join(t.get("labels", []))), acct))
    if v.get("open"):
        a = imap_of(v["open"])
        th = mailimap.thread(a, v["open"]) if a else load("threads/%s.json" % re.sub(r"\W", "", v["open"]), None)
        if a: st = dict(st, account=a["login"])
        if th and th.get("messages"):
            msgs = th["messages"]
            labels = set(l for m in msgs for l in m["labels"])
            names = label_names()
            say("O\t%s\t%s\t%s\t%d" % (v["open"], field(msgs[0]["subject"] or "(no subject)"),
                                      field("|".join(names[l] for l in labels if l in names and not l.isupper())), "STARRED" in labels))
            me = st.get("account", "")
            for m in msgs:
                say("M\t%s\t%s\t%s\t%s\t%s\t%d\t%d\t%s\t%s\t%s" % (m["id"], field(", ".join(who(m["from"], me))), field(m.get("addr", "")), field(", ".join(who(m["to"], me))),
                    field(", ".join(who(m["cc"], me))), m["ts"], "UNREAD" in m["labels"], multi(m["body"]), multi(m["quoted"]), field(m["qhead"])))
                for a in m["att"]:
                    if not a.get("inline"):
                        say("A\t%s\t%s\t%s\t%d\t%s" % (m["id"], a["id"], field(a["name"]), a["size"], a["mime"]))
    say("R\t%s act" % FRONT, "L\t%s data" % FRONT)


# ---------- actions ----------

def modify(tid, add=(), remove=()):
    """Labels on a whole thread, at once in the cache (the window shows it), then Gmail (queued offline)."""
    body = {"addLabelIds": list(add), "removeLabelIds": list(remove)}
    inbox_unread_delta(tid, add, remove)
    for name in os.listdir(path("lists")) if os.path.isdir(path("lists")) else []:
        lst = load("lists/" + name, {})
        changed = False
        for t in lst.get("threads", []):
            if t["id"] == tid:
                if "UNREAD" in add: t["unread"] = True
                if "UNREAD" in remove: t["unread"] = False
                if "STARRED" in add: t["starred"] = True
                if "STARRED" in remove: t["starred"] = False
                changed = True
        v = name[:-5]
        if (v in remove) or ("TRASH" in add and v != "TRASH"):
            lst["threads"] = [t for t in lst.get("threads", []) if t["id"] != tid]; changed = True
        if changed: save("lists/" + name, lst)
    th = load("threads/%s.json" % re.sub(r"\W", "", tid), None)
    if th:
        for m in th["messages"]:
            m["labels"] = [l for l in m["labels"] if l not in remove] + [l for l in add if l not in m["labels"]]
        save("threads/%s.json" % re.sub(r"\W", "", tid), th)
    send_op("POST", "/threads/%s/modify" % tid, body)


def inbox_unread_delta(tid, add, remove):
    """The Inbox's unread count follows a change at once (the next sync has Gmail's own)."""
    th = load("threads/%s.json" % re.sub(r"\W", "", tid), None)
    row = next((t for t in load("lists/INBOX.json", {}).get("threads", []) if t["id"] == tid), None)
    labels = set(l for m in (th or {}).get("messages", []) for l in m["labels"])
    was = ("UNREAD" in labels) if th else bool(row and row["unread"])
    inbox = ("INBOX" in labels) if th else row is not None
    before = was and inbox
    after = (was or "UNREAD" in add) and "UNREAD" not in remove and inbox and "INBOX" not in remove and "TRASH" not in add
    if before == after: return
    st = load("state.json", {})
    for l in st.get("labels", []):
        if l["id"] == "INBOX": l["unread"] = max(0, l.get("unread", 0) + (1 if after else -1))
    save("state.json", st)


def send_op(method, url, body=None, raw=None, ctype=None):
    try:
        api(method, url, body, raw=raw.encode() if raw else None, ctype=ctype)
        return True
    except PermissionError:
        set_status("signin", "Google wants you to sign in again")
    except urllib.error.HTTPError as e:
        set_status("error", google_says(e)); return False
    except (urllib.error.URLError, OSError, TimeoutError):
        set_status("offline", "no connection")
    q = load("queue.json", [])
    q.append({"method": method, "url": url, "body": body, "raw": raw, "ctype": ctype})
    save("queue.json", q)
    return None


def thread_msgs(tid):
    a = imap_of(tid)
    if a: return (mailimap.thread(a, tid) or {}).get("messages", [])
    th = load("threads/%s.json" % re.sub(r"\W", "", tid), None)
    return th["messages"] if th else (fetch_thread(tid) or [])


def me_of(tid):
    a = imap_of(tid)
    return (email.utils.parseaddr(a["from"])[1] or a["login"]) if a else load("state.json", {}).get("account", "")


def recipients(msgs, kind, me=None):
    """To and Cc for a reply: the last message not yours (its Reply-To first); reply all adds
    everyone else on it, never you."""
    me = (me if me is not None else load("state.json", {}).get("account", "")).lower()
    base = next((m for m in reversed(msgs) if not m["mine"]), msgs[-1])
    to = [a for a in email.utils.getaddresses([base["reply_to"] or base["from"]]) if a[1].lower() != me]
    if base["mine"]: to = [a for a in email.utils.getaddresses([base["to"]]) if a[1].lower() != me]
    cc = []
    if kind == "replyall":
        taken = {a[1].lower() for a in to} | {me}
        for a in email.utils.getaddresses([base["to"], base["cc"]]):
            if a[1] and a[1].lower() not in taken: cc.append(a); taken.add(a[1].lower())
    fmt = lambda xs: ", ".join(email.utils.formataddr(a) for a in xs)
    return fmt(to), fmt(cc), base


def build(to, cc, subject, text, reply_of=None, attach=(), sender=None):
    return base64.urlsafe_b64encode(build_msg(to, cc, subject, text, reply_of, attach, sender).as_bytes()).decode()


def build_msg(to, cc, subject, text, reply_of=None, attach=(), sender=None):
    m = email.message.EmailMessage()
    st = load("state.json", {})
    if sender or st.get("account"): m["From"] = sender or st["account"]
    m["Date"] = email.utils.formatdate(localtime=True)
    m["Message-ID"] = email.utils.make_msgid(domain=(email.utils.parseaddr(sender or st.get("account", ""))[1].rpartition("@")[2] or None))
    m["To"] = to
    if cc: m["Cc"] = cc
    m["Subject"] = subject
    if reply_of:
        if reply_of.get("msgid"):
            m["In-Reply-To"] = reply_of["msgid"]
            m["References"] = (reply_of.get("refs", "") + " " + reply_of["msgid"]).strip()
    m.set_content(text)
    for name, mime, blob in attach:
        main, _, sub = (mime or "application/octet-stream").partition("/")
        m.add_attachment(blob, maintype=main, subtype=sub or "octet-stream", filename=name)
    return m


def re_subject(s, pre="Re: "):
    return s if s.lower().startswith(pre.strip().lower()) else pre + s


def send_imap(a, msg):
    """True sent, False refused (said why)."""
    try:
        mailimap.send(a, msg); return True
    except PermissionError as e: say("Not sent · %s" % e); say("k4:tone red")
    except (OSError, mailimap.smtplib.SMTPException, mailimap.imaplib.IMAP4.error) as e: say("Not sent · %s" % field(e)[:120]); say("k4:tone red")
    return False


def send_reply(kind, tid, text):
    msgs = thread_msgs(tid)
    if not msgs: say("Could not open the thread"); return
    a = imap_of(tid)
    to, cc, base = recipients(msgs, kind, me_of(tid))
    if a:
        if not send_imap(a, build_msg(to, cc, re_subject(msgs[0]["subject"]), text, base, sender=a["from"])): return
        names = [n.split()[0] if n else m for n, m in email.utils.getaddresses([to, cc])]
        say("Sent to %s · from %s" % (names[0] if names else "them", a["name"])); say("k4:tone green"); drop_cards(tid)
        if any("UNREAD" in m["labels"] for m in msgs): mailimap.flag(a, tid, True, "\\Seen")
        return
    raw = build(to, cc, re_subject(msgs[0]["subject"]), text, base)
    ok = send_op("POST", "/messages/send", {"raw": raw, "threadId": tid})
    names = [n.split()[0] if n else m for n, m in email.utils.getaddresses([to, cc])]
    if ok: say("Sent to %s" % (names[0] if len(names) == 1 else "%s and %d more" % (names[0], len(names) - 1) if names else "them")); say("k4:tone green"); drop_cards(tid)
    elif ok is None: say("Queued · sends when online"); say("k4:tone yellow")
    else: say("Could not send"); say("k4:tone red")


# A draft as the window sends it ($K4_INPUT) and gets it back (k4:draft, line breaks as U+2028):
#   To: Maja Lind <maja@example.com>, erik@example.com
#   Cc: …
#   Subject: …
#   Attach: /path/to/file          (one line each)
#   <a blank line, then the body>
def parse_draft(text):
    head, _, body = text.replace("\r", "").partition("\n\n")
    d = {"from": "", "to": "", "cc": "", "subject": "", "attach": [], "body": body}
    for ln in head.split("\n"):
        k, sep, v = ln.partition(":")
        k = k.strip().lower()
        if not sep: continue
        if k == "attach": d["attach"].append(v.strip())
        elif k in ("from", "to", "cc", "subject"): d[k] = v.strip()
    return d


def draft_text(d):
    head = ("From: %s\n" % d["from"] if d.get("from") else "") + "To: %s\nCc: %s\nSubject: %s\n" % (d["to"], d["cc"], d["subject"])
    head += "".join("Attach: %s\n" % a for a in d["attach"])
    return head + "\n" + d["body"]


def prefill(kind, tid):
    """What a new card starts with: a reply's people and quote, a forward's message."""
    d = {"from": (imap_of(tid) or {}).get("id", "gmail" if tid else ""), "to": "", "cc": "", "subject": "", "attach": [], "body": ""}
    msgs = thread_msgs(tid) if tid else []
    if kind in ("reply", "replyall") and msgs:
        d["to"], d["cc"], base = recipients(msgs, kind, me_of(tid))
        d["subject"] = re_subject(msgs[0]["subject"])
        d["body"] = "\n\nOn %s, %s wrote:\n" % (time.strftime("%a %d %b %Y %H:%M", time.localtime(base["ts"])), base["from"]) + \
            "\n".join("> " + ln for ln in base["body"].split("\n"))
    elif kind == "forward" and msgs:
        base = msgs[-1]
        d["subject"] = re_subject(msgs[0]["subject"], "Fwd: ")
        d["body"] = "\n\n---------- Forwarded message ---------\nFrom: %s\nDate: %s\nSubject: %s\nTo: %s\n\n%s" % (
            base["from"], time.strftime("%a %d %b %Y %H:%M", time.localtime(base["ts"])), base["subject"], base["to"], base["body"])
    return d


def say_draft(d): say("k4:draft\t" + multi(draft_text(d)))


def mime_of(path_):
    import mimetypes
    return mimetypes.guess_type(path_)[0] or "application/octet-stream"


def sender_of(kind, tid, d):
    """The account a mail goes from: the one it answers, else the card's From, else Gmail (or the first)."""
    if tid and kind in ("reply", "replyall") and imap_of(tid): return imap_of(tid)
    f = d.get("from", "")
    if f and f != "gmail": return mailimap.by_id(f)
    if f == "gmail" or gmail_on(): return None
    return (mailimap.accounts() or [None])[0]


def message_of(kind, tid, d, msg_too=False):
    """(raw, threadId): the mail to send or keep as a draft; a forward takes the original's attachments along."""
    msgs = thread_msgs(tid) if tid else []
    acct = sender_of(kind, tid, d)
    base = None
    if kind in ("reply", "replyall") and msgs: base = next((m for m in reversed(msgs) if not m["mine"]), msgs[-1])
    attach = []
    for f in d["attach"]:
        f = os.path.expanduser(f)
        with open(f, "rb") as fh: attach.append((os.path.basename(f), mime_of(f), fh.read()))
    if kind == "forward" and msgs:
        src = imap_of(tid)
        for a in msgs[-1]["att"]:
            if not a.get("id"): continue
            if src:
                name, blob = mailimap.attachment(src, msgs[-1]["id"], a["id"])
                if blob is not None: attach.append((a["name"], a["mime"], blob))
            else:
                got = api("GET", "/messages/%s/attachments/%s" % (msgs[-1]["id"], a["id"]))
                attach.append((a["name"], a["mime"], b64(got.get("data", ""))))
    m = build_msg(d["to"], d["cc"], d["subject"], d["body"], base, attach, sender=acct["from"] if acct else None)
    if msg_too: return m, acct
    return base64.urlsafe_b64encode(m.as_bytes()).decode(), (tid if base and not imap_of(tid) else "")


def send_compose(kind, tid, text):
    d = parse_draft(text)
    if not d["to"].strip(): say("Add someone in To first"); say("k4:tone yellow"); return
    try:
        m, acct = message_of(kind, tid, d, msg_too=True)
        if acct:
            if send_imap(acct, m): say("Sent · “%s” · from %s" % (d["subject"] or "(no subject)", acct["name"])); say("k4:tone green"); say("k4:sent")
            return
        raw, th = message_of(kind, tid, d)
    except OSError as e: say("Could not attach %s" % os.path.basename(getattr(e, "filename", "") or "a file")); say("k4:tone red"); return
    req = {"raw": raw}
    if th: req["threadId"] = th
    ok = send_op("POST", "/messages/send", req)
    if ok: say("Sent · “%s”" % (d["subject"] or "(no subject)")); say("k4:tone green"); say("k4:sent")
    elif ok is None: say("Queued · sends when online"); say("k4:tone yellow"); say("k4:sent")
    else: say("Could not send"); say("k4:tone red")


def save_draft(kind, tid, text):
    d = parse_draft(text)
    if not (d["to"] or d["subject"] or d["body"].strip()): say("k4:noreload"); return
    acct = sender_of(kind, tid, d)
    if acct:
        try:
            m, _ = message_of(kind, tid, d, msg_too=True)
            mailimap.draft(acct, m); say("Saved as a draft · %s" % acct["name"])
        except (OSError, PermissionError, mailimap.imaplib.IMAP4.error): say("Could not save the draft"); say("k4:tone yellow")
        return
    try: raw, th = message_of(kind, tid, d)
    except OSError: raw, th = build(d["to"], d["cc"], d["subject"], d["body"]), ""
    msg = {"raw": raw}
    if th: msg["threadId"] = th
    ok = send_op("POST", "/drafts", {"message": msg})
    say("Saved as a draft" if ok else "Draft kept · saves when online" if ok is None else "Could not save the draft")


def edit(text):
    """The draft in the editor (a floating terminal), the card's fields and body back from it.
    :cq (an editor's error) throws the edit away."""
    fd, f = tempfile.mkstemp(prefix="k4-mail-", suffix=".eml", dir=RUN)
    with os.fdopen(fd, "w") as fh: fh.write(text)
    editor = os.environ.get("EDITOR") or "nvim"
    term = ["ghostty", "--class=TUI.float", "-e"] if subprocess.run(["sh", "-c", "command -v ghostty"], capture_output=True).returncode == 0 \
        else ["xdg-terminal-exec", "--app-id=TUI.float"]
    line = text.count("\n", 0, text.find("\n\n") + 2) + 2 if "\n\n" in text else 1
    r = 1 if FAKE else subprocess.run(term + ["sh", "-c", '"$0" "+$1" "$2"', editor, str(line), f]).returncode
    with open(f) as fh: out = fh.read()
    os.remove(f)
    if r != 0 or out == text: say("k4:noreload"); say("Back from the editor · unchanged"); return
    say_draft(parse_draft(out)); say("k4:noreload"); say("Back from the editor · body updated"); say("k4:tone green")


def zenity(*a):
    if FAKE: return ""
    try: return subprocess.run(["zenity", "--file-selection", *a], capture_output=True, text=True, timeout=600).stdout.strip()
    except (OSError, subprocess.SubprocessError): return ""


def pick():
    got = [f for f in zenity("--multiple", "--separator=\n", "--title", "Attach files").split("\n") if f]
    for f in got: say("k4:attach\t%s\t%d" % (f, os.path.getsize(f) if os.path.exists(f) else 0))
    say("k4:noreload")
    say("Attached %s" % (os.path.basename(got[0]) if len(got) == 1 else "%d files" % len(got)) if got else "Nothing attached")


def pick_client():
    f = zenity("--title", "Your Google OAuth client (client_secret_….json)", "--file-filter", "*.json")
    if not f: say("No file picked"); return
    try:
        with open(f) as fh: c = json.load(fh)
        if "client_id" not in (c.get("installed") or c.get("web") or c): raise ValueError
    except (OSError, ValueError):
        say("That file is not a Google OAuth client"); say("k4:tone red"); return
    os.makedirs(os.path.dirname(google.CLIENT), exist_ok=True)
    fd = os.open(google.CLIENT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out: json.dump(c, out)
    say("Google client saved · Calendar uses it too"); say("k4:tone green")


def who_is(q):
    """People seen in your mail whose name or address starts with what was typed (the To field's ↵)."""
    q = q.strip().lower()
    c = load("contacts.json", {})
    hits = [(n, a) for n, a in c.items() if any(w.startswith(q) for w in n.lower().split()) or a.lower().startswith(q)]
    hits.sort(key=lambda x: (not x[0].lower().startswith(q), x[0]))
    for n, a in hits[:5]: say("k4:who\t%s\t%s" % (field(n), a))
    say("k4:noreload")
    if not hits: say("Nobody called “%s” in your mail · type the address" % q); say("k4:tone yellow")


def attachment(mid, aid, name):
    name = os.path.basename(name) or "attachment"
    d = api("GET", "/messages/%s/attachments/%s" % (mid, aid))
    dl = os.path.join(HOME, "Downloads")
    os.makedirs(dl, exist_ok=True)
    out, n = os.path.join(dl, name), 1
    stem, ext = os.path.splitext(name)
    while os.path.exists(out): out = os.path.join(dl, "%s (%d)%s" % (stem, n, ext)); n += 1
    with open(out, "wb") as f: f.write(b64(d.get("data", "")))
    if not FAKE:
        subprocess.Popen(["xdg-open", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    say("Saved %s in Downloads" % os.path.basename(out))


def set_view(**k):
    v = view(); v.update(k); save("view.json", v); return v


def imap_act(verb, a):
    """What an IMAP id (or All inboxes) asks; True when it was one of theirs."""
    acct = imap_of(a[0])
    if verb in ("label", "search", "clear", "more"):
        v = view()
        label = a[0] if verb == "label" else v["label"]
        if label != "ALL" and not imap_of(label): return False
        if verb == "label": v = set_view(label=label, query="", open="")
        elif verb == "search": v = set_view(query=" ".join(x for x in a if x), open="")
        elif verb == "clear": v = set_view(query="", open="")
        else: say("The newest 50 are all k4 keeps of this folder · ^O opens webmail"); return True
        try:
            if label == "ALL":
                if gmail_on() and v["query"]: guarded(fetch_list)({"label": "INBOX", "query": v["query"]})
                for x in mailimap.accounts():
                    mailimap.sync(x, "INBOX" if v["query"] else None, v["query"] or None) if v["query"] else None
            else:
                x = imap_of(label)
                mailimap.sync(x, mailimap.split_id(label)[1], v["query"] or None)
        except (OSError, PermissionError, mailimap.imaplib.IMAP4.error) as e:
            say("Showing what was saved · %s" % field(e)[:100]); say("k4:tone yellow"); return True
        if verb == "search": say("%d for “%s”" % (len(view_rows(v)), v["query"]))
        return True
    if not acct: return False
    try:
        if verb == "open":
            set_view(open=a[0])
            th = mailimap.thread(acct, a[0])
            if th and any("UNREAD" in m["labels"] for m in th["messages"]): mailimap.flag(acct, a[0], True, "\\Seen"); drop_cards(a[0])
        elif verb in ("read", "unread"):
            mailimap.flag(acct, a[0], verb == "read", "\\Seen")
            if verb == "unread": set_view(open="")
            else: drop_cards(a[0])
            say("Marked %s" % verb)
        elif verb == "star":
            row = next((t for t, _ in view_rows(view()) if t["id"] == a[0]), None) or next(iter(mailimap.rows(acct, "INBOX")), None)
            th = mailimap.thread(acct, a[0])
            on = bool(th and any("STARRED" in m["labels"] for m in th["messages"]))
            mailimap.flag(acct, a[0], not on, "\\Flagged")
            say("Unstarred" if on else "Starred"); say("k4:tone green")
        elif verb in ("archive", "trash"):
            dest = mailimap.move(acct, a[0], "Archive" if verb == "archive" else "Trash")
            drop_cards(a[0]); set_view(open="")
            say("%s · %s" % ("Archived" if verb == "archive" else "Moved to Trash", acct["name"])); say("k4:tone green")
        elif verb in ("unarchive", "untrash"):
            say("It is in %s on %s · move it back there (^O webmail)" % ("Archive" if verb == "unarchive" else "Trash", acct["name"])); say("k4:tone yellow")
        elif verb == "attachment":
            name, blob = mailimap.attachment(acct, a[0], a[1])
            if blob is None: say("That file is not in the cache · open the mail again"); say("k4:tone yellow"); return True
            save_download(a[2] or name, blob)
        elif verb == "browser": say("k4:noreload"); say("%s has no web link here · it is %s" % (acct["name"], acct["host"]))
        elif verb == "move":
            mailimap.move(acct, a[0], mailimap.split_id(a[1])[1] if imap_of(a[1]) else a[1]); set_view(open=""); say("Moved")
        else:
            return False
    except PermissionError as e: say(str(e)); say("k4:tone red")
    except (OSError, mailimap.imaplib.IMAP4.error) as e: say("%s did not answer · %s" % (acct["name"], field(e)[:80])); say("k4:tone yellow")
    return True


def save_download(name, blob):
    name = os.path.basename(name) or "attachment"
    dl = os.path.join(HOME, "Downloads")
    os.makedirs(dl, exist_ok=True)
    out, n = os.path.join(dl, name), 1
    stem, ext = os.path.splitext(name)
    while os.path.exists(out): out = os.path.join(dl, "%s (%d)%s" % (stem, n, ext)); n += 1
    with open(out, "wb") as f: f.write(blob)
    if not FAKE:
        subprocess.Popen(["xdg-open", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    say("Saved %s in Downloads" % os.path.basename(out))


def act(verb, args):
    a = args + [""] * 3
    inp = os.environ.get("K4_INPUT", "")
    if verb in ("label", "search", "clear", "more", "open", "read", "unread", "star", "archive", "trash", "unarchive",
                "untrash", "attachment", "browser", "move") and imap_act(verb, a if verb != "attachment" else [a[0], a[1], " ".join(args[2:])]):
        return
    if verb == "connect":
        if not google.have_client():
            for url in ("https://console.cloud.google.com/apis/library/gmail.googleapis.com",
                        "https://console.cloud.google.com/apis/credentials"):
                open_url(url)
            say("Google Cloud · enable the Gmail API, create an OAuth client (Desktop app), download its JSON, then ↵ again"); return
        ok, why = GOOGLE.sign_in()
        if not ok: say("Not connected · " + why); say("k4:tone yellow"); return
        set_status("ok")
        drop_cards("signin")
        if full_sync(): say("Connected · %s" % load("state.json", {}).get("account", "Gmail")); say("k4:tone green")
        else: say("Signed in, but Gmail did not answer · %s" % load("state.json", {}).get("note", "")); say("k4:tone yellow")
    elif verb == "disconnect":
        GOOGLE.sign_out()
        import shutil; shutil.rmtree(DIR, ignore_errors=True)
        say("Signed out of Gmail · the cache is gone")
    elif verb == "sync":
        r = sync() if gmail_on() else True
        imap_sync(force=True)
        say("Up to date" if r else "Could not sync · %s" % load("state.json", {}).get("note", ""))
    elif verb == "open":
        set_view(open=a[0])
        msgs = guarded(fetch_thread)(a[0])
        if msgs and any("UNREAD" in m["labels"] for m in msgs): modify(a[0], remove=["UNREAD"]); drop_cards(a[0])
        if msgs is None and not thread_msgs_cached(a[0]): say("Could not open it · offline"); say("k4:tone yellow")
    elif verb == "close": set_view(open=""); say("k4:noreload")
    elif verb == "home": set_view(label="ALL" if mailimap.accounts() else "INBOX", query="", open=""); say("k4:noreload")
    elif verb == "label":
        v = set_view(label=a[0], query="", open="")
        if guarded(fetch_list)(v) is None: say("Showing what was saved · %s" % load("state.json", {}).get("note", "offline"))
    elif verb == "search":
        v = set_view(query=" ".join(args), open="")
        r = guarded(fetch_list)(v)
        say("%d threads for “%s”" % (len(r), v["query"]) if r is not None else "Search needs a connection")
    elif verb == "clear": v = set_view(query="", open=""); guarded(fetch_list)(v)
    elif verb == "more":
        v = view(); nxt = load(list_key(v), {}).get("next")
        if not nxt: say("That is all"); return
        r = guarded(fetch_list)(v, nxt)
        say("%d threads" % len(r) if r is not None else "Could not load more")
    elif verb == "archive":
        modify(a[0], remove=["INBOX"]); drop_cards(a[0]); set_view(open="")
        say("Archived%s · ^Z undo" % (" · waits to sync" if load("queue.json", []) else "")); say("k4:tone green")
    elif verb == "trash": modify(a[0], add=["TRASH"], remove=["INBOX"]); drop_cards(a[0]); set_view(open=""); say("Moved to Trash · ^Z undo")
    elif verb == "unarchive": modify(a[0], add=["INBOX"]); say("Back in the Inbox")
    elif verb == "untrash": modify(a[0], add=["INBOX"], remove=["TRASH"]); say("Back from the Trash")
    elif verb == "star":
        th = load("threads/%s.json" % re.sub(r"\W", "", a[0]), None)
        starred = any(t["id"] == a[0] and t["starred"] for t in load(list_key(view()), {}).get("threads", [])) or \
            bool(th and any("STARRED" in m["labels"] for m in th["messages"]))
        if starred: modify(a[0], remove=["STARRED"]); say("Unstarred")
        else: modify(a[0], add=["STARRED"]); say("Starred"); say("k4:tone green")
    elif verb == "unread": modify(a[0], add=["UNREAD"]); set_view(open=""); say("Marked unread")
    elif verb == "read": modify(a[0], remove=["UNREAD"]); drop_cards(a[0]); say("Marked read")
    elif verb == "move":
        modify(a[0], add=[a[1]], remove=["INBOX"]); set_view(open="")
        say("Moved to %s" % label_names().get(a[1], a[1]))
    elif verb == "send":   # send reply|replyall T (the reply line), send compose KIND [T] (the card)
        if not inp.strip(): say("Write something first"); say("k4:tone yellow"); return
        if a[0] == "compose": send_compose(a[1] or "new", a[2], inp)
        else: send_reply(a[0] or "reply", a[1], inp)
    elif verb == "draft": save_draft(a[0] or "new", a[1], inp)
    elif verb == "prefill": say_draft(prefill(a[0], a[1])); say("k4:noreload")
    elif verb == "edit": edit(inp)
    elif verb == "pick": pick()
    elif verb == "pickclient": pick_client()
    elif verb == "who": who_is(" ".join(args))
    elif verb == "enableapi":
        open_url("https://console.cloud.google.com/apis/library/gmail.googleapis.com"); say("k4:noreload")
        say("Opened the Gmail API page · Enable, then wait a minute")
    elif verb == "howto":
        open_url("https://console.cloud.google.com/apis/credentials/consent"); say("k4:noreload")
        say("Opened the consent screen · Publishing status › In production")
    elif verb == "attachment": attachment(a[0], a[1], " ".join(args[2:]))
    elif verb == "url":
        if a[0].startswith(("http://", "https://")): open_url(a[0]); say("k4:noreload"); say("Opened in the browser")
        else: say("Not a link")
    elif verb == "browser":
        open_url("https://mail.google.com/mail/u/0/#%s" % ("all/" + a[0] if a[0] else "inbox"))
        say("k4:noreload"); say("Opened in the browser")
    else:
        say("unknown: " + verb)


def thread_msgs_cached(tid): return os.path.exists(path("threads/%s.json" % re.sub(r"\W", "", tid)))


def note(key, card):
    tid = load("cards.json", {}).get(card, "")
    if not tid: return
    if key == "default":
        set_view(open="" if tid in ("*", "signin") else tid, query="", label="INBOX")
        if not FAKE: subprocess.Popen(["setsid", "-f", FRONT, "window"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif key == "signin":
        drop_cards("signin")
        if not FAKE: subprocess.Popen(["setsid", "-f", FRONT, "window"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif key == "read-all" and tid == "*":
        for t in load("lists/INBOX.json", {}).get("threads", []):
            if t["unread"]: modify(t["id"], remove=["UNREAD"])
        drop_cards("*")
    elif key == "read": act("read", [tid])
    elif key == "archive": act("archive", [tid])
    elif key == "inline-reply" and os.environ.get("K4_INPUT", "").strip(): send_reply("reply", tid, os.environ["K4_INPUT"]); modify(tid, remove=["UNREAD"])


# ---------- bar, launcher ----------

def total_unread():
    st = load("state.json", {})
    return (next((l["unread"] for l in st.get("labels", []) if l["id"] == "INBOX"), 0) if gmail_on() else 0) + imap_unread()


def bar():
    status, st = state()
    imaps = mailimap.accounts()
    if status in ("noclient", "connect") and not imaps: print("{}"); return
    n = total_unread()
    acct = ", ".join(([st["account"]] if gmail_on() and st.get("account") else []) + [a["name"] for a in imaps]) or "Mail"
    if imaps and status in ("noclient", "connect"): status = "ok"
    if status == "signin": print(json.dumps({"icon": "󰊫", "icon_tone": "yellow", "text": "!", "text_tone": "yellow", "tooltip": "Gmail · sign in again"}, ensure_ascii=False)); return
    if status == "offline": print(json.dumps({"icon": "󰊫", "icon_tone": "dim", **({"badge": n, "badge_tone": "dnd"} if n > 0 else {}), "tooltip": "Gmail · offline · %d unread when last synced" % n}, ensure_ascii=False)); return
    if n <= 0: print(json.dumps({"icon": "󰊫", "tooltip": "Mail · %s · nothing unread · Super+Alt+E" % acct}, ensure_ascii=False)); return
    print(json.dumps({"icon": "󰊫", "badge": n, "tooltip": "Mail · %s · %d unread · Super+Alt+E" % (acct, n)}, ensure_ascii=False))


def find():
    """The newest 100 threads cached (any list), newest first: id, from, subject, ts, unread, count, address."""
    rows = {}
    if os.path.isdir(path("lists")):
        for name in os.listdir(path("lists")):
            for t in load("lists/" + name, {}).get("threads", []): rows[t["id"]] = t
    for a in mailimap.accounts():
        for t in mailimap.rows(a, "INBOX"): rows[t["id"]] = t
    for t in sorted(rows.values(), key=lambda t: -t["ts"])[:150]:
        print("\t".join([t["id"], field(t["from"]), field(t["subject"]), str(t["ts"]), "1" if t["unread"] else "0",
                         str(t.get("count", 1)), t.get("addr", "")]))


def info():
    """The Apps page's lines: S state unread account synced; I the Inbox's unread threads; G the labels."""
    status, st = state()
    imaps = mailimap.accounts()
    if imaps and status in ("noclient", "connect"): status = "ok"
    synced = max([st.get("synced", 0)] + [mailimap.state(a).get("synced", 0) for a in imaps])
    print("S\t%s\t%d\t%s\t%d" % (status, total_unread(), field(st.get("account", "") or (imaps[0]["login"] if imaps else "")), synced))
    for t, _ in all_rows() if imaps else [(t, "gmail") for t in load("lists/INBOX.json", {}).get("threads", [])]:
        if t["unread"]: print("I\t%s\t%s\t%s\t%d\t%s" % (t["id"], field(t["from"]), field(t["subject"]), t["ts"], field(t["snippet"])))
    if imaps: print("G\tALL\tAll inboxes\t%d\tsystem" % total_unread())
    if gmail_on():
        for l in st.get("labels", []):
            if l["id"] in ("SPAM", "TRASH", "IMPORTANT"): continue
            print("G\t%s\t%s\t%d\t%s" % (l["id"], field(l["name"]) if not imaps else "Gmail · " + field(l["name"]) if l["id"] == "INBOX" else field(l["name"]), l.get("unread", 0), l["kind"]))
    for a in imaps:
        f = next((f for f in mailimap.state(a).get("folders", []) if f["role"] == "Inbox"), None)
        if f: print("G\t%s:%s\t%s · Inbox\t%d\tuser" % (a["id"], f["id"], field(a["name"]), f["unread"]))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "data"
    if cmd == "data": data()
    elif cmd == "sync":
        lock = os.path.join(RUN, "k4-mail-sync.lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
            import fcntl; fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: return 0   # one at a time
        r = sync("--quiet" in argv) if connected() and gmail_on() else True
        imap_sync()
        if "--quiet" not in argv: say("Up to date" if r else "Could not sync")
    elif cmd == "act": act(argv[2] if len(argv) > 2 else "", argv[3:])
    elif cmd == "note": note(argv[2], argv[3])
    elif cmd == "bar": bar()
    elif cmd == "count": print(total_unread())
    elif cmd == "find": find()
    elif cmd == "info": info()
    elif cmd == "state": st = state()[0]; print("ok" if mailimap.accounts() and st in ("noclient", "connect") else st)
    else: print(__doc__, file=sys.stderr); return 2
    return 0


mailimap.G = sys.modules[__name__]   # (the parsing mailimap shares)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
