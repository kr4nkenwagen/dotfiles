#!/usr/bin/env python3
"""k4's Releases (k4-releases is its front): what is coming in movies and TV (TMDB, Swedish dates),
games (Steam's store, no key) and books (Hardcover); trailers through k4's corner player; dates into the calendar;
titles you follow get a card when their date nears or moves (and their calendar event moves too).

Keys of your own, kept in the keyring (k4-secret token tmdb | hardcover); Steam needs none. Lists
are cached 6 h in ~/.cache/k4/releases.

  releases.py data                     the window's lines (k4 --releases, see src/releases.odin)
  releases.py act VERB …               play KIND ID [N] | cal KIND ID | follow KIND ID | open KIND ID
                                       search KIND QUERY | clear | refresh | key tmdb|hardcover ($K4_INPUT)
  releases.py refresh [--force]       the lists (stale ones) and their posters, in the background
  releases.py tick | info | find

Tests: K4_RELEASES_FAKE=DIR: API answers from DIR (files named after the request), no network,
cards and k4-cal/k4-youtube to DIR/log; K4_RELEASES_NOW pins the clock.
"""
import datetime as dt, hashlib, json, os, re, shlex, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
FAKE = os.environ.get("K4_RELEASES_FAKE")
STATE = os.environ.get("K4_RELEASES_STATE") or os.path.join(HOME, ".local/state/k4/releases")
CACHE = os.environ.get("K4_RELEASES_CACHE") or os.path.join(HOME, ".cache/k4/releases")
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
FRONT = os.environ.get("K4_RELEASES_FRONT") or shutil.which("k4-releases") or "k4-releases"
CAL = os.environ.get("K4_CAL_DIR") or os.path.join(HOME, ".cache/k4/cal")
TTL = 6 * 3600
KINDS = ("movies", "tv", "games", "books")
GLYPH = {"movies": "🎬", "tv": "📺", "games": "🎮", "books": "📖"}
UA = "k4-releases"


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def now(): return float(os.environ.get("K4_RELEASES_NOW") or time.time())
def today(): return dt.datetime.fromtimestamp(now()).date()


def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError): return d


def jsave(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w") as f: json.dump(data, f, ensure_ascii=False)
    os.replace(p + ".tmp", p)


def log(line):
    with open(os.path.join(FAKE, "log"), "a") as f: f.write(line + "\n")


# ---------- keys ----------

def key(name):
    if FAKE: return "" if name in os.environ.get("K4_RELEASES_NOKEYS", "").split(",") else "test"
    r = subprocess.run(["k4-secret", "lookup", "token", name], capture_output=True, text=True, timeout=15)
    return r.stdout.strip() if r.returncode == 0 else ""


def keep(name, value):
    if FAKE: log("keep %s" % name); return
    subprocess.run(["k4-secret", "store", "token", name], input=value, text=True, capture_output=True, timeout=20)


# ---------- HTTP ----------

def fake_name(url, body=None):
    return re.sub(r"[^A-Za-z0-9]+", "_", re.sub(r"https?://", "", url) + ("_" + hashlib.sha1(body.encode()).hexdigest()[:8] if body else ""))[:140] + ".json"


def get(url, headers=None, body=None):
    if FAKE:
        p = os.path.join(FAKE, fake_name(url, body))
        if not os.path.exists(p):
            with open(os.path.join(FAKE, "missing.log"), "a") as f: f.write(os.path.basename(p) + "\n")
            raise urllib.error.URLError("no fixture")
        return jload(p, {})
    req = urllib.request.Request(url, data=body.encode() if body else None, headers=dict({"User-Agent": UA, "Accept": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)


def image(url, fetch=False):
    """A poster or cover's file once it is downloaded ("" until then); FETCH downloads it (the
    background refresh does: the window never waits), and a miss is remembered for a day."""
    if not url: return ""
    p = os.path.join(CACHE, "img", hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
    if os.path.exists(p): return p
    if FAKE or not fetch: return ""
    miss = p + ".miss"
    if os.path.exists(miss) and time.time() - os.path.getmtime(miss) < 86400: return ""
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r, open(p + ".tmp", "wb") as f: f.write(r.read())
        os.replace(p + ".tmp", p)
        return p
    except Exception:
        try: open(miss, "w").close()
        except OSError: pass
        return ""


# ---------- TMDB: movies and TV (Swedish dates) ----------

TMDB = "https://api.themoviedb.org/3"


def tmdb(path, **q):
    k = key("tmdb")
    if not k: raise PermissionError("tmdb")
    headers = {}
    if len(k) > 40: headers["Authorization"] = "Bearer " + k   # a v4 read access token
    else: q["api_key"] = k                                      # a v3 key
    try: return get(TMDB + path + "?" + urllib.parse.urlencode(sorted(q.items())), headers)
    except urllib.error.HTTPError as e:
        if e.code == 401: raise PermissionError("tmdb")   # (a wrong key: the tab asks for it again)
        raise


def poster(p): return "https://image.tmdb.org/t/p/w342" + p if p else ""


def trailers_of(videos):
    vs = [v for v in (videos or {}).get("results", []) if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")]
    vs.sort(key=lambda v: (v.get("type") != "Trailer", not v.get("official"), v.get("published_at", "")))
    return [{"id": v["key"], "name": v.get("name", "Trailer")} for v in vs[:4]]


def providers_se(d):
    se = ((d.get("watch/providers") or {}).get("results") or {}).get("SE") or {}
    return [p["provider_name"] for p in (se.get("flatrate") or [])][:2]


def movie(mid):
    d = tmdb("/movie/%s" % mid, append_to_response="videos,credits,release_dates,watch/providers", language="en-US")
    dates = []
    for c in (d.get("release_dates") or {}).get("results", []):
        if c.get("iso_3166_1") != "SE": continue
        for r in c.get("release_dates", []):
            t = {2: "in cinemas (limited)", 3: "in cinemas", 4: "digital", 5: "on disc", 6: "on TV"}.get(r.get("type"))
            if t and r.get("release_date"): dates.append((r["release_date"][:10], t))
    if not dates and d.get("release_date"): dates.append((d["release_date"], "release"))
    dates.sort()
    prov = providers_se(d)
    upcoming = [x for x in dates if x[0] >= today().isoformat()] or dates[-1:]
    date, label = upcoming[0] if upcoming else ("", "")
    if label == "digital" and prov: label = "on " + prov[0]
    crew = [c["name"] for c in (d.get("credits") or {}).get("crew", []) if c.get("job") == "Director"][:1]
    cast = [c["name"] for c in (d.get("credits") or {}).get("cast", [])[:3]]
    return {"kind": "movies", "id": str(mid), "title": d.get("title", ""), "date": date, "when": label, "genres": [g["name"] for g in d.get("genres", [])],
            "line": ", ".join(g["name"] for g in d.get("genres", [])[:3]), "poster": poster(d.get("poster_path")),
            "facts": " · ".join(x for x in (date[:4], ("%d h %d m" % divmod(d["runtime"], 60)) if d.get("runtime") else "", ", ".join(prov)) if x),
            "overview": d.get("overview", ""), "people": " · ".join(x for x in (("Director " + crew[0]) if crew else "", ", ".join(cast)) if x),
            "rating": ("%.1f/10" % d["vote_average"]) if d.get("vote_count", 0) >= 20 else "",
            "dates": [{"date": a, "label": b} for a, b in dates if a >= (today() - dt.timedelta(days=60)).isoformat()][:5],
            "trailers": trailers_of(d.get("videos")), "url": "https://www.themoviedb.org/movie/%s" % mid}


def show(tid):
    d = tmdb("/tv/%s" % tid, append_to_response="videos,credits,watch/providers", language="en-US")
    nxt = d.get("next_episode_to_air") or {}
    new = (d.get("first_air_date") or "") >= today().isoformat()
    if new: date, label = d.get("first_air_date", ""), "new series"
    elif nxt.get("air_date"): date, label = nxt["air_date"], ("season %d" % nxt.get("season_number", 0)) if nxt.get("episode_number") == 1 else "S%02dE%02d" % (nxt.get("season_number", 0), nxt.get("episode_number", 0))
    else: date, label = "", ""
    prov = providers_se(d) or [n["name"] for n in d.get("networks", [])[:1]]
    if prov: label += " · " + prov[0]
    return {"kind": "tv", "id": str(tid), "title": d.get("name", ""), "date": date, "when": label, "genres": [g["name"].replace("Sci-Fi & Fantasy", "Sci-Fi").replace("Action & Adventure", "Action") for g in d.get("genres", [])],
            "line": ", ".join(g["name"] for g in d.get("genres", [])[:3]), "poster": poster(d.get("poster_path")),
            "facts": " · ".join(x for x in ((d.get("first_air_date") or "")[:4], "%d season%s" % (d.get("number_of_seasons", 0), "" if d.get("number_of_seasons") == 1 else "s") if d.get("number_of_seasons") else "", ", ".join(prov)) if x),
            "overview": d.get("overview", ""), "people": ", ".join(c["name"] for c in (d.get("credits") or {}).get("cast", [])[:3]),
            "rating": ("%.1f/10" % d["vote_average"]) if d.get("vote_count", 0) >= 20 else "",
            "dates": [{"date": date, "label": label}] if date else [], "season_premiere": new or nxt.get("episode_number") == 1,
            "trailers": trailers_of(d.get("videos")), "url": "https://www.themoviedb.org/tv/%s" % tid}


def list_movies():
    t = today()
    ids = []
    for page in (1, 2):
        r = tmdb("/discover/movie", region="SE", **{"release_date.gte": t.isoformat(), "release_date.lte": (t + dt.timedelta(days=240)).isoformat(),
                 "with_release_type": "2|3|4", "sort_by": "popularity.desc", "include_adult": "false", "language": "en-US", "page": page})
        ids += [m["id"] for m in r.get("results", [])]
    out = []
    for i in ids[:30]:
        try:
            m = cached("movie-%s" % i, lambda: movie(i), 24 * 3600)
            if m["date"] >= t.isoformat(): out.append(m)
        except (urllib.error.URLError, OSError, ValueError): continue
    return out


def list_tv():
    t = today()
    r = tmdb("/discover/tv", **{"air_date.gte": t.isoformat(), "air_date.lte": (t + dt.timedelta(days=150)).isoformat(), "sort_by": "popularity.desc",
             "watch_region": "SE", "include_null_first_air_dates": "false", "language": "en-US", "page": 1})
    out = []
    for s in r.get("results", [])[:30]:
        try:
            x = cached("tv-%s" % s["id"], lambda: show(s["id"]), 24 * 3600)
            if x["date"] >= t.isoformat() and x.get("season_premiere"): out.append(x)
        except (urllib.error.URLError, OSError, ValueError): continue
    return out


# ---------- Steam: games (no key) ----------

STEAM = "https://store.steampowered.com"
STEAM_IMG = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/%s/library_600x900.jpg"


def steam_date(text):
    """Steam's release date text → (YYYY-MM-DD or "", the text when it is vague: "Q1 2027", "2027")."""
    t = (text or "").strip()
    for f in ("%d %b, %Y", "%b %d, %Y", "%d %B, %Y", "%B %d, %Y", "%d %b %Y"):
        try: return dt.datetime.strptime(t, f).date().isoformat(), ""
        except ValueError: pass
    return "", t if t and t.lower() not in ("coming soon", "to be announced", "tba") else (t or "")


def game(app, d):
    date, vague = steam_date((d.get("release_date") or {}).get("date", ""))
    plats = [p for p, on in (("Windows", (d.get("platforms") or {}).get("windows")), ("Linux", (d.get("platforms") or {}).get("linux")), ("macOS", (d.get("platforms") or {}).get("mac"))) if on]
    movies = []
    for mv in d.get("movies", [])[:4]:
        url = mv.get("hls_h264") or (mv.get("mp4") or {}).get("max") or (mv.get("webm") or {}).get("max") or mv.get("dash_h264")
        if url: movies.append({"id": url, "name": mv.get("name", "Trailer")})
    poster = STEAM_IMG % app
    return {"kind": "games", "id": str(app), "title": d.get("name", ""), "date": date, "when": vague or "Steam", "genres": [g["description"] for g in d.get("genres", [])],
            "line": ", ".join(g["description"] for g in d.get("genres", [])[:2]), "poster": poster, "poster2": d.get("header_image", ""),
            "facts": " · ".join(x for x in (", ".join(plats), ", ".join(d.get("developers", [])[:1])) if x), "overview": re.sub(r"<[^>]+>", " ", d.get("short_description", "")),
            "people": ", ".join(d.get("developers", [])[:2] + [p for p in d.get("publishers", [])[:1] if p not in d.get("developers", [])]),
            "rating": ("%d want it" % (d.get("recommendations") or {}).get("total")) if (d.get("recommendations") or {}).get("total") else "",
            "dates": [{"date": date, "label": "Steam"}] if date else [], "trailers": movies, "url": "%s/app/%s" % (STEAM, app)}


def steam_app(app):
    r = get("%s/api/appdetails?appids=%s&cc=se&l=english" % (STEAM, app))
    d = ((r or {}).get(str(app)) or {}).get("data")
    return game(app, d) if d and d.get("type") == "game" else None


def list_games():
    ids = []
    r = get("%s/search/results/?filter=popularcomingsoon&json=1&count=40&cc=se&l=english" % STEAM)
    for it in (r or {}).get("items", []):
        m = re.search(r"/apps/(\d+)/", it.get("logo", ""))
        if m and m.group(1) not in ids: ids.append(m.group(1))
    for it in (get("%s/api/featuredcategories?cc=se&l=english" % STEAM) or {}).get("coming_soon", {}).get("items", []):
        if str(it.get("id")) not in ids: ids.append(str(it["id"]))
    out = []
    for app in ids[:40]:
        try: g = cached("steam-%s" % app, lambda: steam_app(app), 24 * 3600)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError): continue
        if g and (not g["date"] or g["date"] >= today().isoformat()): out.append(g)
    return out


# ---------- Hardcover: books ----------

HC_FIELDS = "id title slug release_date description pages users_count rating cached_tags image { url } contributions { author { name } } book_series { position series { name } }"


def hardcover(query):
    k = key("hardcover")
    if not k: raise PermissionError("hardcover")
    k = k[7:] if k.lower().startswith("bearer ") else k
    try: r = get("https://api.hardcover.app/v1/graphql", {"Authorization": "Bearer " + k, "Content-Type": "application/json"}, json.dumps({"query": query}))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): raise PermissionError("hardcover")
        raise
    return (r or {}).get("data", {})


def book(b):
    authors = [c["author"]["name"] for c in b.get("contributions", []) if c.get("author")][:2]
    ser = (b.get("book_series") or [{}])[0] if b.get("book_series") else {}
    series = ("%s, book %s" % (ser["series"]["name"], ("%g" % ser["position"]) if ser.get("position") else "?")) if ser.get("series") else ""
    tags = b.get("cached_tags") or {}
    if isinstance(tags, str):
        try: tags = json.loads(tags)
        except ValueError: tags = {}
    genres = [t.get("tag", "") for t in (tags.get("Genre") or [])[:4] if isinstance(t, dict) and t.get("tag")]
    return {"kind": "books", "id": str(b["id"]), "title": b.get("title", ""), "date": b.get("release_date") or "", "when": "", "genres": genres,
            "line": " · ".join(x for x in (", ".join(authors), series) if x), "poster": (b.get("image") or {}).get("url", ""),
            "facts": " · ".join(x for x in ((b.get("release_date") or "")[:4], ("%d pages" % b["pages"]) if b.get("pages") else "") if x),
            "overview": re.sub(r"<[^>]+>", " ", b.get("description") or ""), "people": ", ".join(authors),
            "rating": ("%d want it" % b["users_count"]) if b.get("users_count") else "", "dates": [{"date": b["release_date"], "label": "release"}] if b.get("release_date") else [],
            "trailers": [], "url": "https://hardcover.app/books/%s" % b.get("slug", "")}


def list_books():
    q = '{ books(where: {release_date: {_gt: "%s"}}, order_by: {users_count: desc}, limit: 40) { %s } }' % (today().isoformat(), HC_FIELDS)
    return [book(b) for b in hardcover(q).get("books", [])]


# ---------- the lists, cached ----------

def cached(name, fn, ttl=TTL):
    p = os.path.join(CACHE, name + ".json")
    c = jload(p, None)
    if c is not None and (FAKE or time.time() - os.path.getmtime(p) < ttl): return c
    v = fn()
    jsave(p, v)
    return v


LISTS = {"movies": list_movies, "tv": list_tv, "games": list_games, "books": list_books}


def status(): return jload(os.path.join(CACHE, "status.json"), {})


def cached_listing(kind):
    """For the window, never waiting: (state, items, fetched). The cached list, stale or not; a
    stale or missing one is fetched again in the background (state "refreshing" meanwhile)."""
    c = jload(os.path.join(CACHE, "list-%s.json" % kind), None)
    st = status().get(kind, "")
    if c is not None and (FAKE or time.time() - c.get("at", 0) < TTL): return st if st in ("nokey",) else "ok", c["items"], c["at"]
    if st == "nokey" and c is None: return "nokey", [], 0
    return "refreshing", (c or {}).get("items", []), (c or {}).get("at", 0)


def refresh_bg():
    """The background refresh, once at a time (releases.py refresh holds the lock)."""
    if FAKE: return
    subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "refresh"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)


def refresh(force=False):
    """The lists that are stale (FORCE: all), then their posters; nokey and offline noted for the window."""
    import fcntl
    os.makedirs(CACHE, exist_ok=True)
    lock = open(os.path.join(CACHE, "refresh.lock"), "w")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: return
    st = status()
    for kind in KINDS:
        c = jload(os.path.join(CACHE, "list-%s.json" % kind), None)
        if not force and c is not None and time.time() - c.get("at", 0) < TTL: continue
        s_, items, _ = listing(kind, fresh=True)
        st[kind] = s_
        jsave(os.path.join(CACHE, "status.json"), st)
    for kind in KINDS:
        for it in jload(os.path.join(CACHE, "list-%s.json" % kind), {}).get("items", []):
            image(it["poster"], fetch=True) or image(it.get("poster2", ""), fetch=True)
    for f in follows().values():
        it = f.get("item") or {}
        if it: image(it.get("poster", ""), fetch=True) or image(it.get("poster2", ""), fetch=True)


def listing(kind, fresh=False):
    """(state, items, fetched): ok, nokey or offline (then the cached list, if any)."""
    p = os.path.join(CACHE, "list-%s.json" % kind)
    c = jload(p, None)
    if c is not None and not fresh and (FAKE or time.time() - c.get("at", 0) < TTL): return "ok", c["items"], c["at"]
    try:
        items = sorted(LISTS[kind](), key=lambda x: x["date"] or "9999")
        jsave(p, {"at": now(), "items": items})
        return "ok", items, now()
    except PermissionError: return "nokey", [], 0
    except (urllib.error.URLError, OSError, ValueError, KeyError, TimeoutError):
        return ("offline", c["items"], c.get("at", 0)) if c else ("offline", [], 0)


def follows(): return jload(os.path.join(STATE, "follow.json"), {})
def save_follows(f): jsave(os.path.join(STATE, "follow.json"), f)


def find_item(kind, ident):
    for it in jload(os.path.join(CACHE, "list-%s.json" % kind), {}).get("items", []) + jload(os.path.join(CACHE, "search.json"), {}).get("items", []):
        if it["kind"] == kind and it["id"] == ident: return it
    f = follows().get("%s:%s" % (kind, ident))
    return f.get("item") if f else None


def detail(kind, ident):
    """A title fetched again (a followed one's date), or None."""
    try:
        if kind == "movies": return movie(ident)
        if kind == "tv": return show(ident)
        if kind == "games": return steam_app(ident)
        if kind == "books":
            r = hardcover("{ books(where: {id: {_eq: %d}}) { %s } }" % (int(ident), HC_FIELDS)).get("books", [])
            return book(r[0]) if r else None
    except (PermissionError, urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TimeoutError): return None


# ---------- what the window reads ----------

def data():
    """K kind state fetched · I tab kind id title date when line poster followed incal trailers olddate ·
    O/P/F/G kind id text (overview, people, facts, rating) · E kind id date label · V kind id video name ·
    C kind id genre|genre (the categories to filter by) · Q kind query."""
    fol = follows()
    out_items = {}

    def emit(tab, it):
        k = "%s:%s" % (it["kind"], it["id"])
        f = fol.get(k, {})
        moved = f.get("cal_date") if f.get("cal_date") and f.get("cal_date") != it["date"] else ""
        pic = image(it["poster"]) or image(it.get("poster2", ""))
        say("I\t" + "\t".join(field(x) or "-" for x in (tab, it["kind"], it["id"], it["title"], it["date"], it["when"], it["line"], pic,
                                                         "1" if k in fol else "0", "1" if f.get("cal_date") else "0", str(len(it["trailers"])), moved)))
        if k not in out_items:
            out_items[k] = it
            for tag, v in (("O", it["overview"]), ("P", it["people"]), ("F", it["facts"]), ("G", it["rating"]), ("U", it["url"])):
                if v: say("%s\t%s\t%s\t%s" % (tag, it["kind"], it["id"], field(v)[:900]))
            for d in it["dates"]: say("E\t%s\t%s\t%s\t%s" % (it["kind"], it["id"], d["date"], field(d["label"]) or "-"))
            if it.get("genres"): say("C\t%s\t%s\t%s" % (it["kind"], it["id"], "|".join(field(g).replace("|", "/") for g in it["genres"])))
            for v in it["trailers"]: say("V\t%s\t%s\t%s\t%s" % (it["kind"], it["id"], v["id"], field(v["name"])))

    stale = False
    for kind in KINDS:
        st, items, at = listing(kind) if FAKE else cached_listing(kind)
        stale |= st == "refreshing"
        say("K\t%s\t%s\t%d" % (kind, st, at))
        for it in items: emit(kind, it)
    s = jload(os.path.join(CACHE, "search.json"), {})
    if s.get("q"):
        say("Q\t%s\t%s" % (s["kind"], field(s["q"])))
        for it in s.get("items", []): emit("search", it)
    for k, f in sorted(fol.items(), key=lambda kv: kv[1].get("item", {}).get("date") or "9999"):
        if f.get("item"): emit("following", f["item"])
    say("R\t%s act" % FRONT)
    say("L\t%s data" % FRONT)
    if stale: refresh_bg()


# ---------- what you do ----------

def search(kind, q):
    q = q.strip()
    if not q: return clear()
    try:
        if kind == "movies":
            r = tmdb("/search/movie", query=q, region="SE", language="en-US")
            items = [movie(m["id"]) for m in r.get("results", [])[:10]]
        elif kind == "tv":
            r = tmdb("/search/tv", query=q, language="en-US")
            items = [show(s["id"]) for s in r.get("results", [])[:10]]
        elif kind == "games":
            r = get("%s/api/storesearch/?term=%s&cc=se&l=english" % (STEAM, urllib.parse.quote(q)))
            items = [x for x in (steam_app(i["id"]) for i in (r or {}).get("items", [])[:10]) if x]
        else:
            items = [book(b) for b in hardcover('{ books(where: {title: {_ilike: "%%%s%%"}}, order_by: {users_count: desc}, limit: 10) { %s } }' % (q.replace('"', ""), HC_FIELDS)).get("books", [])]
    except PermissionError: return say("%s needs its key first" % {"movies": "TMDB", "tv": "TMDB", "books": "Hardcover"}[kind])
    except (urllib.error.URLError, OSError, ValueError, TimeoutError): return say("Couldn’t search · offline?")
    jsave(os.path.join(CACHE, "search.json"), {"kind": kind, "q": q, "items": items})
    for it in items: image(it["poster"], fetch=True) or image(it.get("poster2", ""), fetch=True)
    say("%d found for “%s”" % (len(items), q))


def clear():
    try: os.remove(os.path.join(CACHE, "search.json"))
    except OSError: pass


def cal_title(it):
    return "%s %s%s" % (GLYPH[it["kind"]], it["title"], (" · " + it["when"]) if it.get("when") else "")


def cal_add(it, date=None):
    args = ["k4-cal", "add", "primary", date or it["date"], cal_title(it)]
    if FAKE: log("cal " + " ".join(args[3:])); return True
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return r.returncode == 0 and "Not created" not in r.stdout


def cal_remove(it, date):
    """The calendar's copy of a release (k4-cal's cache) deleted, e.g. before moving it."""
    t = cal_title(it)
    for e in jload(os.path.join(CAL, "events.json"), []):
        if e.get("date") == date and e.get("title") == t:
            if FAKE: log("cal-delete %s %s" % (date, t)); return
            subprocess.run(["k4-cal", "delete", e["id"], t], capture_output=True, timeout=60)
            return
    if FAKE: log("cal-delete %s %s (not found)" % (date, t))


def post(title, body, acts, ident, kind="1"):
    if FAKE: log("card %s | %s | %s" % (title, body, acts)); return
    line = "\t".join(["post", "0", "Releases", field(title), field(body), kind, "-1", "-1", "", "", "", acts, "%s card %s" % (FRONT, ident)])
    subprocess.run(["k4", "--notify-ctl", line], capture_output=True, timeout=5)


def day(d):
    x = dt.date.fromisoformat(d)
    return "%s %d %s" % (x.strftime("%a"), x.day, x.strftime("%b"))


def act(argv):
    v, a = (argv[0] if argv else ""), argv[1:] + ["", "", ""]
    kind, ident = a[0], a[1]
    if v in ("play", "cal", "follow", "open"):
        it = find_item(kind, ident)
        if not it: return say("That title isn’t loaded any more · refresh")
        if v == "play":
            vs = it["trailers"]
            if not vs:
                act(["open", kind, ident]); return say("No trailer · opened its page")
            n = int(a[2] or 0) % len(vs)
            if FAKE: log("play %s" % vs[n]["id"])
            else: subprocess.Popen(["k4-youtube", "play", vs[n]["id"]], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return say("Playing “%s”%s" % (vs[n]["name"], " · t for the next" if len(vs) > 1 else ""))
        if v == "open":
            if FAKE: log("open %s" % it["url"])
            else: subprocess.Popen(["xdg-open", it["url"]], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        fol = follows()
        k = "%s:%s" % (kind, ident)
        if v == "follow":
            if k in fol and not fol[k].get("cal_date"):
                del fol[k]; save_follows(fol); return say("Not following %s" % it["title"])
            fol.setdefault(k, {})["item"] = it
            save_follows(fol)
            return say("Following %s · a card when it nears or moves" % it["title"])
        if v == "cal":
            if not it["date"]: return say("No date yet · follow it (f) and k4 adds it when there is one")
            if fol.get(k, {}).get("cal_date") == it["date"]: return say("Already in your calendar · %s" % day(it["date"]))
            if not cal_add(it): say("Couldn’t add it · is Calendar connected?"); return say("k4:tone yellow")
            fol.setdefault(k, {}).update(item=it, cal_date=it["date"])   # (in the calendar: followed, so a moved date moves the event)
            save_follows(fol)
            return say("Added to your calendar · %s %s" % (day(it["date"]), GLYPH[kind]))
    if v == "search": return search(kind or "movies", " ".join(argv[2:]) or os.environ.get("K4_INPUT", ""))
    if v == "clear": return clear()
    if v == "refresh":
        refresh(force=True)
        return say("Fetched again")
    if v == "key":
        val = os.environ.get("K4_INPUT", "").strip()
        if not val: return say("Nothing pasted")
        if a[0] == "tmdb" and len(val) < 30: say("That’s too short for a TMDB key · copy the whole API Read Access Token (or the 32-character API Key)"); return say("k4:tone yellow")
        keep(a[0], val)
        st = status()
        for kd in KINDS:
            if st.get(kd) == "nokey": st.pop(kd)
            try: os.remove(os.path.join(CACHE, "list-%s.json" % kd))
            except OSError: pass
        jsave(os.path.join(CACHE, "status.json"), st)
        return say("Saved the %s key" % {"tmdb": "TMDB", "hardcover": "Hardcover", "igdb": "IGDB"}.get(a[0], a[0]))
    say("k4-releases act: unknown %s" % v)


def tick():
    """Daily: followed titles fetched again; a moved date gives a card (and moves its calendar event);
    a week before and on the day, a card."""
    fol = follows()
    said = jload(os.path.join(STATE, "said.json"), {})
    t = today()
    for k, f in fol.items():
        it = f.get("item") or {}
        kind, ident = k.split(":", 1)
        new = detail(kind, ident)
        if new and new.get("date") and new["date"] != it.get("date"):
            old = it.get("date") or ""
            f["item"] = new
            if f.get("cal_date"):
                cal_remove(new, f["cal_date"])
                if cal_add(new): f["cal_date"] = new["date"]
            post("%s · %s" % (new["title"], "now " + day(new["date"]) if old else "dated " + day(new["date"])),
                 ("was %s" % day(old) if old else "a date at last") + (" · moved in your calendar" if f.get("cal_date") else ""), "open:Open", k)
            it = new
        if not it.get("date"): continue
        d = dt.date.fromisoformat(it["date"])
        for when_, label in ((d - dt.timedelta(days=7), "in a week"), (d, "today")):
            sk = "%s:%s:%s" % (k, it["date"], label)
            if when_ == t and sk not in said:
                post("%s %s · %s" % (GLYPH[kind], it["title"], label), it.get("when") or day(it["date"]), ("trailer:Watch trailer," if it.get("trailers") else "") + "open:Open", k, "wait" if label == "today" else "1")
                said[sk] = now()
    save_follows(fol)
    jsave(os.path.join(STATE, "said.json"), said)


def card(btn, k):
    kind, _, ident = k.partition(":")
    if btn == "trailer": act(["play", kind, ident])
    elif btn in ("open", "default"): act(["open", kind, ident])


def info():
    """The Apps page: K kind state count · N followed soonest first (kind title date when)."""
    for kind in KINDS:
        p = jload(os.path.join(CACHE, "list-%s.json" % kind), None)
        st = "ok" if p else ("nokey" if kind != "games" and not key({"movies": "tmdb", "tv": "tmdb", "books": "hardcover"}[kind]) else "notyet")
        say("K\t%s\t%s\t%d" % (kind, st, len(p["items"]) if p else 0))
    for k, f in sorted(follows().items(), key=lambda kv: kv[1].get("item", {}).get("date") or "9999")[:8]:
        it = f.get("item") or {}
        say("N\t%s\t%s\t%s\t%s" % (it.get("kind", ""), field(it.get("title")), it.get("date") or "-", field(it.get("when")) or "-"))


def find_rows():
    import base64
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    me = shlex.quote(FRONT)
    rows, seen = [], set()
    fol = follows()
    for k, f in fol.items():
        if f.get("item"): rows.append((f["item"], 75))
    for kind in KINDS:
        for it in jload(os.path.join(CACHE, "list-%s.json" % kind), {}).get("items", [])[:15]: rows.append((it, 50))
    for it, rank in rows:
        k = "%s:%s" % (it["kind"], it["id"])
        if k in seen or not it.get("date"): continue
        seen.add(k)
        label = "%s · %s%s" % (it["title"], (it["when"] + " ") if it.get("when") else "", day(it["date"]))
        print("A\t%s\t%s\t%s\t\tsearch;words;min=3;rank=%d;tag=Releases;icon=%s;find=%s" % (b64("k4-releases run " + b64("bg %s window %s %s" % (me, it["kind"], it["id"]))),
              field(label), "★ followed" if k in fol else it["kind"], rank, GLYPH[it["kind"]], field(it.get("line", "")).replace(";", ",")))


def main(argv):
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if cmd == "data": data()
    elif cmd == "act": act(rest)
    elif cmd == "tick": tick(); refresh()
    elif cmd == "refresh": refresh("--force" in rest)
    elif cmd == "card" and len(rest) >= 2: card(rest[1], rest[0])
    elif cmd == "info": info()
    elif cmd == "find": find_rows()
    else: say(__doc__.strip()); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
