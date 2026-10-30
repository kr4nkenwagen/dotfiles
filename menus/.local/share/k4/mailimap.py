"""mailimap.py: k4's IMAP accounts (k4-mail, beside Gmail): the ones aerc has in
~/.config/aerc/accounts.conf, their passwords in the keyring (k4-secret, kind mail, named by the
login), the mail cached in ~/.cache/k4/mail/imap/<account>/ in the shape gmail.py keeps Gmail's.

  accounts()           the accounts: name, login, IMAP and SMTP host and port, From, the inbox
  migrate()            accounts.conf's passwords into the keyring, the file made to ask for them
                       (source-cred-cmd, outgoing-cred-cmd); a copy of the old file is kept, 0600
  Account(a)           one account's IMAP and SMTP: folders, the newest 50 of a folder, new mail
                       since the last look, flags, moves, sending (and a copy in Sent), drafts

Ids the window sees: a folder is "<account>:<folder>", a message "<account>:<folder>:<uid>";
gmail.py sends what has such an id here.
"""
import email, email.policy, email.utils, html, imaplib, json, os, re, smtplib, subprocess, time

HOME = os.path.expanduser("~")
AERC = os.environ.get("K4_AERC_ACCOUNTS") or os.path.join(HOME, ".config/aerc/accounts.conf")
SECRET = os.environ.get("K4_SECRET") or os.path.join(HOME, ".local/bin/k4-secret")
PAGE = 50


# ---------- accounts.conf ----------

def _sections(text):
    """[(name, [(key, value, line)])] in the file's order."""
    out, cur = [], None
    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = (s[1:-1], []); out.append(cur)
        elif cur is not None and "=" in s and not s.startswith("#"):
            k, _, v = s.partition("=")
            cur[1].append((k.strip(), v.strip(), ln))
    return out


def _url(u):
    """scheme, login, password, host, port of imaps://login:password@host:port (the login may hold @)."""
    scheme, _, rest = u.partition("://")
    userinfo, _, hostport = rest.rpartition("@")
    login, _, pw = userinfo.partition(":")
    host, _, port = hostport.partition(":")
    return scheme, login, pw, host, int(port or (993 if scheme.startswith("imap") else 465))


def slug(name): return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def accounts():
    """The IMAP accounts in aerc's file (not Gmail ones: k4 reads Gmail through its API)."""
    if os.environ.get("K4_MAIL_FAKE") and not os.environ.get("K4_AERC_ACCOUNTS"): return []   # (tests: never the real accounts)
    try:
        with open(AERC) as f: text = f.read()
    except OSError:
        return []
    out = []
    for name, kv in _sections(text):
        d = {k: v for k, v, _ in kv}
        src = d.get("source", "")
        if not src.startswith(("imaps://", "imap://")) or "gmail.com" in src: continue
        scheme, login, _, host, port = _url(src)
        out_ = d.get("outgoing", "")
        oscheme, ologin, _, ohost, oport = _url(out_) if out_ else ("", login, "", host, 465)
        out.append({"id": slug(name), "name": name, "login": login, "host": host, "port": port, "ssl": scheme == "imaps",
                    "smtp": ohost, "sport": oport, "sssl": oscheme != "smtp+starttls", "slogin": ologin or login,
                    "from": d.get("from", login), "inbox": d.get("default", "INBOX")})
    return out


def password(login):
    """The login's password from the keyring (k4-secret; a locked keyring: none)."""
    try:
        r = subprocess.run([SECRET, "lookup", "mail", login], capture_output=True, text=True, timeout=20)
        return r.stdout if r.returncode == 0 and r.stdout else None
    except (OSError, subprocess.SubprocessError):
        return None


def migrate():
    """accounts.conf's passwords into the keyring; the file asks k4-secret for them instead.
    Returns (moved, message). Nothing secret is printed."""
    try:
        with open(AERC) as f: text = f.read()
    except OSError:
        return 0, "No aerc accounts.conf"
    if subprocess.run([SECRET, "locked"], capture_output=True).returncode == 0:
        return 0, "The keyring is locked · unlock it and run this again"
    lines, moved, cur_login, done = text.split("\n"), 0, {}, set()
    out = []
    for name, kv in _sections(text):
        for k, v, _ in kv:
            if k == "source" and "://" in v: cur_login[name] = _url(v)[1]
    section = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"): section = s[1:-1]
        k, sep, v = s.partition("=")
        k, v = k.strip(), v.strip()
        if sep and k in ("source", "outgoing") and "://" in v and section in cur_login:
            scheme, login, pw, host, port = _url(v)
            cmd = "%s-cred-cmd" % k
            if pw and login not in done:   # stored once per login (IMAP and SMTP share it)
                r = subprocess.run([SECRET, "store", "mail", login], input=pw, text=True, capture_output=True, timeout=20)
                if r.returncode != 0: return moved, "Could not store the password for %s" % login
                done.add(login); moved += 1
            if pw or "%s:@" % login in v:   # (an empty password: the account's own)
                out.append("%s = %s://%s@%s:%d" % (k.ljust(13), scheme, login, host, port))
                out.append("%s = %s lookup mail %s" % (cmd.ljust(13), SECRET, login))
                continue
        out.append(ln)
    if moved == 0: return 0, "No passwords in accounts.conf · nothing to move"
    keep = os.path.join(HOME, ".local/state/k4/aerc-accounts.conf.bak")   # (not beside it: accounts.conf may live in a git repo)
    os.makedirs(os.path.dirname(keep), exist_ok=True)
    fd = os.open(keep, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: f.write(text)
    tmp = AERC + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: f.write("\n".join(out))
    os.replace(tmp, AERC)
    return moved, "Moved %d password%s into the keyring · aerc asks k4-secret now · the old file is %s (delete it once aerc works)" % (moved, "" if moved == 1 else "s", keep)


# ---------- the mail ----------

G = None   # gmail.py, set by it: the parsing it shares (html_text, split_quote, who, field)
DIR = None  # its cache root; an account's is DIR/imap/<id>


def adir(a, *p): return os.path.join(DIR, "imap", a["id"], *p)


def load(a, name, default):
    try:
        with open(adir(a, name)) as f: return json.load(f)
    except (OSError, ValueError): return default


def save(a, name, data):
    path = adir(a, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(data, f)
    os.replace(path + ".tmp", path)


def fkey(folder): return re.sub(r"[^A-Za-z0-9_-]+", "_", folder)[:100]


def mid(a, folder, uid): return "%s:%s:%s" % (a["id"], folder, uid)


def split_id(x):
    """account id, folder, uid of an id this module made (None when it is Gmail's)."""
    acct, sep, rest = x.partition(":")
    if not sep: return None
    folder, _, uid = rest.rpartition(":")
    return (acct, folder, uid) if folder and uid.isdigit() else (acct, rest, "")


def by_id(acct):
    return next((a for a in accounts() if a["id"] == acct), None)


SPECIAL = {"\\Sent": "Sent", "\\Drafts": "Drafts", "\\Trash": "Trash", "\\Junk": "Junk", "\\Archive": "Archive"}


def connect(a):
    pw = password(a["login"])
    if not pw: raise PermissionError("no password in the keyring for %s" % a["login"])
    c = imaplib.IMAP4_SSL(a["host"], a["port"], timeout=30) if a["ssl"] else imaplib.IMAP4(a["host"], a["port"], timeout=30)
    try: c.login(a["login"], pw)
    except imaplib.IMAP4.error: raise PermissionError("%s refused the password for %s" % (a["host"], a["login"]))
    return c


def q(folder): return '"%s"' % folder.replace("\\", "\\\\").replace('"', '\\"')


def folders(c):
    """[(name, role)]: role Inbox, Sent, Drafts, Trash, Junk, Archive or ""."""
    out = []
    for raw in c.list()[1] or []:
        m = re.match(rb'\((?P<flags>[^)]*)\) "(?P<d>[^"]*)" (?P<name>.+)', raw or b"")
        if not m: continue
        name = m.group("name").decode("utf-8", "replace").strip().strip('"')
        flags = m.group("flags").decode()
        if "\\Noselect" in flags: continue
        role = "Inbox" if name.upper() == "INBOX" else next((r for f, r in SPECIAL.items() if f in flags), "")
        out.append((name, role))
    order = ["Inbox", "Sent", "Drafts", "Archive", "Junk", "Trash"]
    out.sort(key=lambda x: (order.index(x[1]) if x[1] in order else 9, x[0].lower()))
    return out


def role_of(a, role):
    return next((f["id"] for f in load(a, "state.json", {}).get("folders", []) if f["role"] == role), "")


def parse_raw(a, folder, uid, raw, flags, ts):
    """One message (its bytes) in gmail.py's shape: who, the text, the quote, the files."""
    m = email.message_from_bytes(raw, policy=email.policy.default)
    plain, rich, att = [], [], []
    for i, part in enumerate(m.walk()):
        if part.is_multipart(): continue
        ctype, fn = part.get_content_type(), part.get_filename()
        disp = str(part.get("Content-Disposition", "")).lower()
        if fn or disp.startswith("attachment"):
            size = len(part.get_payload(decode=True) or b"")
            att.append({"id": str(i), "name": fn or "file-%d" % i, "size": size, "mime": ctype, "inline": disp.startswith("inline") and ctype.startswith("image/")})
            continue
        try: text = part.get_content()
        except (LookupError, KeyError, ValueError): text = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        if ctype == "text/plain": plain.append(text)
        elif ctype == "text/html": rich.append(text)
    body = "\n".join(plain) if plain else (G.html_text("\n".join(rich)) if rich else "")
    body = body.replace("\r\n", "\n").strip()
    new, quoted, qhead = G.split_quote(body)
    labels = ([] if "\\Seen" in flags else ["UNREAD"]) + (["STARRED"] if "\\Flagged" in flags else []) + (["INBOX"] if folder.upper() == "INBOX" else [])
    frm = str(m.get("From", ""))
    snippet = re.sub(r"\s+", " ", new or body)[:160]
    return {"id": mid(a, folder, uid), "thread": mid(a, folder, uid), "from": frm, "to": str(m.get("To", "")), "cc": str(m.get("Cc", "")),
            "addr": (email.utils.getaddresses([frm]) or [("", "")])[0][1], "subject": str(m.get("Subject", "")), "ts": ts,
            "labels": labels, "snippet": snippet, "body": new, "quoted": quoted, "qhead": qhead, "att": att,
            "msgid": str(m.get("Message-ID", "")), "refs": str(m.get("References", "")), "reply_to": str(m.get("Reply-To", "")),
            "mine": a["login"].lower() in frm.lower() or email.utils.parseaddr(a["from"])[1].lower() in frm.lower()}


def row_of(msg, me):
    """A message as the list's row (one message, one row)."""
    return {"id": msg["id"], "hist": "", "from": ", ".join(G.who(msg["from"], me)) or "(nobody)", "addr": msg["addr"],
            "subject": msg["subject"] or "(no subject)", "snippet": msg["snippet"], "ts": msg["ts"],
            "unread": "UNREAD" in msg["labels"], "starred": "STARRED" in msg["labels"], "count": 1,
            "attach": any(not x.get("inline") for x in msg["att"]), "labels": []}


def _fetch(c, a, folder, uids):
    """Whole messages (their flags and date) by UID, parsed and kept: threads/ and raw/."""
    out = {}
    me = email.utils.parseaddr(a["from"])[1]
    for i in range(0, len(uids), 10):
        chunk = ",".join(uids[i:i + 10])
        typ, data = c.uid("FETCH", chunk, "(UID FLAGS INTERNALDATE BODY.PEEK[])")
        for item in data or []:
            if not isinstance(item, tuple): continue
            head, raw = item[0].decode("utf-8", "replace"), item[1]
            uid = re.search(r"UID (\d+)", head).group(1)
            flags = (re.search(r"FLAGS \(([^)]*)\)", head) or [None, ""])[1]
            when = imaplib.Internaldate2tuple(item[0])
            ts = int(time.mktime(when)) if when else int(time.time())
            msg = parse_raw(a, folder, uid, raw, flags, ts)
            save(a, "threads/%s.json" % fkey(msg["id"]), {"id": msg["id"], "messages": [msg]})
            os.makedirs(adir(a, "raw"), exist_ok=True)
            fd = os.open(adir(a, "raw", fkey(msg["id"]) + ".eml"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f: f.write(raw)
            out[uid] = row_of(msg, me)
    return out


def sync_folder(c, a, folder, search=None):
    """The newest PAGE of a folder (or of a search in it): new ones fetched whole, the rest's
    flags refreshed. Returns the UIDs of unread mail that is new since the last look."""
    c.select(q(folder), readonly=True)
    validity = (c.response("UIDVALIDITY")[1] or [b"0"])[0]
    key = "lists/%s.json" % fkey(folder if search is None else "q-" + folder + "-" + search)
    old = load(a, key, {})
    if old.get("validity") != (validity.decode() if isinstance(validity, bytes) else str(validity)): old = {}
    typ, data = c.uid("SEARCH", None, *(search_terms(search) if search else ["ALL"]))
    uids = (data[0] or b"").decode().split()[-PAGE:]
    have = {r["id"].rpartition(":")[2]: r for r in old.get("threads", [])}
    fresh = [u for u in uids if u not in have]
    got = _fetch(c, a, folder, fresh) if fresh else {}
    keep = [u for u in uids if u in have]
    if keep:   # the flags of the ones kept (read elsewhere, starred, …)
        typ, data = c.uid("FETCH", ",".join(keep), "(UID FLAGS)")
        for item in data or []:
            line = item.decode() if isinstance(item, bytes) else ""
            m_ = re.search(r"UID (\d+) FLAGS \(([^)]*)\)", line) or re.search(r"FLAGS \(([^)]*)\) UID (\d+)", line)
            if not m_: continue
            uid, flags = (m_.group(1), m_.group(2)) if m_.re.pattern.startswith("UID") else (m_.group(2), m_.group(1))
            r = have[uid]; r["unread"] = "\\Seen" not in flags; r["starred"] = "\\Flagged" in flags
    rows = [got.get(u) or have.get(u) for u in uids]
    rows = [r for r in rows if r]
    rows.sort(key=lambda r: -r["ts"])
    save(a, key, {"threads": rows, "validity": validity.decode() if isinstance(validity, bytes) else str(validity), "more": len(data[0].split()) > PAGE if search is None else False})
    first = not old
    return [u for u in fresh if u in got and got[u]["unread"]] if not first else []


def search_terms(qry):
    """Gmail's words as IMAP's: from:x FROM, is:unread UNSEEN, is:starred FLAGGED, words TEXT."""
    out = []
    for w in qry.split():
        lw = w.lower()
        if lw.startswith("from:"): out += ["FROM", '"%s"' % w[5:].replace('"', "")]
        elif lw.startswith("to:"): out += ["TO", '"%s"' % w[3:].replace('"', "")]
        elif lw.startswith("subject:"): out += ["SUBJECT", '"%s"' % w[8:].replace('"', "")]
        elif lw == "is:unread": out.append("UNSEEN")
        elif lw == "is:starred": out.append("FLAGGED")
        elif lw.startswith(("has:", "in:", "label:")): continue
        else: out += ["TEXT", '"%s"' % w.replace('"', "")]
    return out or ["ALL"]


def sync(a, view_folder=None, search=None):
    """An account: its folders and their counts, the Inbox (and the folder shown), new mail."""
    c = connect(a)
    try:
        fs = folders(c)
        st = load(a, "state.json", {})
        counts = []
        for name, role in fs:
            try:
                typ, d = c.status(q(name), "(MESSAGES UNSEEN)")
                m_ = re.search(rb"MESSAGES (\d+).*UNSEEN (\d+)", d[0] or b"")
                total, unread = (int(m_.group(1)), int(m_.group(2))) if m_ else (0, 0)
            except imaplib.IMAP4.error:
                total, unread = 0, 0
            counts.append({"id": name, "name": "Inbox" if role == "Inbox" else name.replace("INBOX.", ""), "role": role,
                           "unread": unread if role not in ("Sent", "Drafts", "Trash", "Junk") else 0, "total": total})
        st.update(folders=counts, status="ok", note="", synced=int(time.time()))
        save(a, "state.json", st)
        new = sync_folder(c, a, "INBOX")
        if view_folder and view_folder != "INBOX": sync_folder(c, a, view_folder)
        if search is not None and view_folder: sync_folder(c, a, view_folder, search)
        return new
    finally:
        try: c.logout()
        except (imaplib.IMAP4.error, OSError): pass


def state(a): return load(a, "state.json", {})


def rows(a, folder, search=None):
    return load(a, "lists/%s.json" % fkey(folder if not search else "q-" + folder + "-" + search), {}).get("threads", [])


def thread(a, x):
    return load(a, "threads/%s.json" % fkey(x), None)


def raw_of(a, x):
    try:
        with open(adir(a, "raw", fkey(x) + ".eml"), "rb") as f: return f.read()
    except OSError: return None


# ---------- what you do ----------

def _with(a, folder, fn):
    c = connect(a)
    try:
        c.select(q(folder))
        return fn(c)
    finally:
        try: c.logout()
        except (imaplib.IMAP4.error, OSError): pass


def flag(a, x, add, name):
    """\\Seen or \\Flagged on, or off, in the cache at once and then on the server."""
    _, folder, uid = split_id(x)
    for key in [f for f in os.listdir(adir(a, "lists"))] if os.path.isdir(adir(a, "lists")) else []:
        lst = load(a, "lists/" + key, {})
        for r in lst.get("threads", []):
            if r["id"] == x:
                if name == "\\Seen": r["unread"] = not add
                if name == "\\Flagged": r["starred"] = add
        save(a, "lists/" + key, lst)
    th = thread(a, x)
    if th:
        lab = {"\\Seen": "UNREAD", "\\Flagged": "STARRED"}[name]
        for m in th["messages"]:
            want = (not add) if lab == "UNREAD" else add
            m["labels"] = [l for l in m["labels"] if l != lab] + ([lab] if want else [])
        save(a, "threads/%s.json" % fkey(x), th)
    _with(a, folder, lambda c: c.uid("STORE", uid, "+FLAGS" if add else "-FLAGS", "(%s)" % name))
    if name == "\\Seen":   # the folder's count follows
        st = state(a)
        for f in st.get("folders", []):
            if f["id"] == folder: f["unread"] = max(0, f["unread"] + (-1 if add else 1))
        save(a, "state.json", st)


def move(a, x, role_or_name):
    """To a folder (by its role, Archive made when it is missing); gone from the list at once."""
    _, folder, uid = split_id(x)
    dest = role_of(a, role_or_name) or role_or_name
    for key in [f for f in os.listdir(adir(a, "lists"))] if os.path.isdir(adir(a, "lists")) else []:
        lst = load(a, "lists/" + key, {})
        was = any(r["id"] == x and r["unread"] for r in lst.get("threads", []))
        lst["threads"] = [r for r in lst.get("threads", []) if r["id"] != x]
        save(a, "lists/" + key, lst)
    def go(c):
        if role_or_name == "Archive" and not role_of(a, "Archive"): c.create(q("Archive"))
        if b"MOVE" in b" ".join(x.encode() if isinstance(x, str) else x for x in c.capabilities):
            c.uid("MOVE", uid, q(dest))
        else:
            c.uid("COPY", uid, q(dest)); c.uid("STORE", uid, "+FLAGS", "(\\Deleted)"); c.expunge()
    _with(a, folder, go)
    return dest


def send(a, msg, folder_for_copy=True):
    """SMTP, then a copy in Sent (the server keeps none on its own)."""
    pw = password(a["login"])
    if not pw: raise PermissionError("no password in the keyring for %s" % a["login"])
    s = smtplib.SMTP_SSL(a["smtp"], a["sport"], timeout=30) if a["sssl"] else smtplib.SMTP(a["smtp"], a["sport"], timeout=30)
    try:
        if not a["sssl"]: s.starttls()
        s.login(a["slogin"], pw)
        s.send_message(msg)
    finally:
        try: s.quit()
        except (smtplib.SMTPException, OSError): pass
    if folder_for_copy:
        sent = role_of(a, "Sent") or "Sent"
        c = connect(a)
        try: c.append(q(sent), "(\\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        finally:
            try: c.logout()
            except (imaplib.IMAP4.error, OSError): pass


def draft(a, msg):
    c = connect(a)
    try: c.append(q(role_of(a, "Drafts") or "Drafts"), "(\\Draft \\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    finally:
        try: c.logout()
        except (imaplib.IMAP4.error, OSError): pass


def attachment(a, x, part):
    """A file of a message: its name and bytes (the message as it was fetched)."""
    raw = raw_of(a, x)
    if raw is None: return None, None
    m = email.message_from_bytes(raw, policy=email.policy.default)
    for i, p in enumerate(m.walk()):
        if str(i) == str(part): return p.get_filename() or "file-%s" % part, p.get_payload(decode=True) or b""
    return None, None


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["migrate"]: print(migrate()[1])
    elif sys.argv[1:] == ["accounts"]:
        for a in accounts(): print("%s\t%s\t%s:%d\t%s:%d" % (a["id"], a["login"], a["host"], a["port"], a["smtp"], a["sport"]))
