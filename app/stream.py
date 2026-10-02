"""The stream as a digest.

Two halves. The garden half is Niwa's own and always there: planted, unpublished, stage changes and suggestions
(Niwa's garden events), links that died (its link table) and notes tended (its clone's git log). The board half
(the now-list, per-project moves and Log rows, machine change logs) comes from Konbini's /api/digest when
NIWA_KONBINI_URL is set and Konbini answers; without it the stream shows the garden alone.

A "now" block (WIP and Blocked cards with their next step), then the
last 30 days grouped by project: one entry per project per day for the
current week, one per project per week before that. Each entry shows the
column moves, the one or two most significant Log rows (release, then
milestone, then status), a count of everything else, the current next
step and links back to the card and the garden note. Machine change
logs collapse to one line per host per day, garden events (planted,
tended, unpublished) appear, vault housekeeping commits are hidden and
agent chatter folds into the counts. Nothing appears twice."""
import datetime

from zoneinfo import ZoneInfo
import os

TZ = ZoneInfo(os.environ.get("TZ") or "UTC")      # the day boundaries of the stream and the "this week" counts
# Commit authors that are not people tending a note: Niwa's own writes (NIWA_GIT_NAME) plus any bots that commit to the
# vault (NIWA_IGNORE_AUTHORS, comma-separated).
IGNORED_AUTHORS = frozenset({os.environ.get("NIWA_GIT_NAME", "garden")} |
                            {a.strip() for a in os.environ.get("NIWA_IGNORE_AUTHORS", "").split(",") if a.strip()})


def today():
    return datetime.datetime.now(TZ).date()


def local_date(ts):
    """'2026-01-15T09:30:00Z' -> the local date (events are stored in UTC)."""
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TZ).date()
    except (ValueError, AttributeError):
        return None

def _top(rows, n=2):
    seen, out = set(), []
    for rank, text in sorted(rows, key=lambda r: r[0]):
        if text not in seen:
            seen.add(text)
            out.append(text)
        if len(out) >= n:
            break
    return out


def window(days):
    end = today() + datetime.timedelta(days=1)
    return end - datetime.timedelta(days=days + 1), end


def build(garden, days=30, links=None, reading=None, public=False):
    """reading: optional callable(start, end) -> {"total", "top", "search"} (Hister,
    owner-only). Pass it only for the owner's web stream, never for gemini or
    gopher.

    public=True is the stream for gemini and gopher: garden events about notes that are published now,
    and nothing from the board (no cards, no `next:` steps, no blocked-by text), so nothing about an unpublished
    note, its title or its text, can reach it."""
    store = garden.store
    start, end = window(days)
    garden.index()
    published = {n.rel: n for n in garden.published()}
    now, board_entries = (garden.konbini.digest(days) if garden.konbini and garden.konbini.enabled() and not public
                          else (None, []))
    slug_path = {c["slug"]: path for path, c in (garden.konbini.cards_by_path() if now else {}).items()}
    for x in board_entries:                      # link a project to its garden note, by the card's note path
        note = published.get(x.get("path") or "")
        x["note_slug"] = note.slug if note else ""
    for c in (now or {}).get("wip", []) + (now or {}).get("blocked", []):
        note = published.get(slug_path.get(c.get("slug"), ""))
        c["note_slug"] = note.slug if note else ""
    now = now or {"wip": [], "blocked": []}

    since = datetime.datetime.combine(start - datetime.timedelta(days=1), datetime.time()).isoformat()
    until = datetime.datetime.combine(end + datetime.timedelta(days=1), datetime.time()).isoformat()
    garden_events = []
    for ev in store.events(since=since, until=until, limit=100000):
        d = local_date(ev.get("ts", ""))
        if not d or not start <= d < end:
            continue
        kind = ev.get("type")
        if kind == "garden" and "growth" in (ev.get("changes") or {}):
            rel = ev.get("path") or ""
            n = garden.notes.get(rel)
            old, new = ev["changes"]["growth"]
            order = {"seedling": 0, "budding": 1, "evergreen": 2}
            verb = "promoted to %s" % new if order.get(new, 1) > order.get(old or "budding", 1) else "stage set to %s" % (new or "default")
            garden_events.append({"kind": "garden", "date": d, "event": verb, "title": n.title if n else rel,
                                  "note_slug": n.slug if n and n.published else "", "rel": rel})
        elif kind == "suggest":
            rel = ev.get("path") or ""
            n = garden.notes.get(rel)
            who = ev.get("agent") if ev.get("agent") not in (None, "web", "api") else (ev.get("actor") or "")
            garden_events.append({"kind": "garden", "date": d, "event": "suggested" + ((" by " + who) if who else ""),
                                  "title": n.title if n else rel, "note_slug": n.slug if n and n.published else "", "rel": rel})
        elif kind in ("publish", "unpublish"):
            rel = ev.get("path") or ""
            n = garden.notes.get(rel)
            garden_events.append({"kind": "garden", "date": d, "event": "planted" if kind == "publish" else "unpublished",
                                  "title": n.title if n else rel, "note_slug": n.slug if n and n.published else "",
                                  "rel": rel})
    planted = {(g["rel"], g["date"]) for g in garden_events}
    if links:
        for d, r in links.died_between(start, end):
            rels = [x for x in (r.get("notes") or "").split("\n") if x]
            n = next((garden.notes.get(x) for x in rels if garden.notes.get(x) and garden.notes[x].published), None)
            short = r["url"].split("//", 1)[-1]
            garden_events.append({"kind": "garden", "date": d, "event": "link died" + (", archived" if r.get("archive_url") else ""),
                                  "title": short if len(short) <= 60 else short[:57] + "\u2026", "note_slug": n.slug if n else "", "rel": ""})

    # tended: commits by people (not NIWA_IGNORE_AUTHORS bots or the garden's own writes) that touched a published note
    out = garden.git("log", "--since=%s 00:00" % start.isoformat(), "--format=@%as|%an", "--name-only", "--",
                     garden.subdir or ".")
    tended, current, author = set(), None, ""
    prefix = garden.subdir + "/" if garden.subdir else ""
    for line in out.splitlines():
        if line.startswith("@"):
            current, _, author = line[1:].partition("|")
        elif line and line.startswith(prefix) and current and author not in IGNORED_AUTHORS:
            rel = line[len(prefix):]
            if rel in published:
                tended.add((rel, current))
    for rel, ds in sorted(tended):
        d = datetime.date.fromisoformat(ds)
        if start <= d < end and (rel, d) not in planted:
            n = published[rel]
            garden_events.append({"kind": "garden", "date": d, "event": "tended", "title": n.title,
                                  "note_slug": n.slug, "rel": rel})

    if public:      # only what concerns a note that is published now (the others' titles stay private)
        garden_events = [x for x in garden_events if x.get("note_slug")]
    entries = board_entries + garden_events

    # -- weeks -----------------------------------------------------------------------
    this_monday = today() - datetime.timedelta(days=today().weekday())
    weeks = {}
    for x in entries:
        monday = x["date"] - datetime.timedelta(days=x["date"].weekday())
        weeks.setdefault(monday, []).append(x)

    def order(xs):
        kind_rank = {"project": 0, "garden": 1, "systems": 2}
        return sorted(xs, key=lambda x: (kind_rank[x["kind"]], 0 if x.get("moves") or x.get("done") else 1,
                                         (x.get("title") or x.get("host") or "").lower()))

    def merge_week(xs):
        """Older weeks: one entry per project (and per host) for the whole week."""
        proj, hosts, others = {}, {}, []
        for x in xs:
            if x["kind"] == "project":
                m = proj.get(x["slug"])
                if not m:
                    proj[x["slug"]] = dict(x, rows=[], top=[], moves=list(x["moves"]), more=0, rows_n=0)
                    m = proj[x["slug"]]
                    m["_rows"] = []
                else:
                    m["moves"] += x["moves"]
                    m["date"] = max(m["date"], x["date"])
                    m["done"] = m["done"] or x["done"]
                    m["started"] = m["started"] or x["started"]
                m["_rows"] += [(0, t) for t in x["top"]]
                m["more"] += x["more"]
                m["rows_n"] += x["rows_n"]
            elif x["kind"] == "systems":
                h = hosts.setdefault(x["host"], {"kind": "systems", "date": x["date"], "host": x["host"], "count": 0})
                h["count"] += x["count"]
                h["date"] = max(h["date"], x["date"])
            else:
                others.append(x)
        out = []
        for m in proj.values():
            top = _top(m.pop("_rows"))
            m["top"] = top
            m["more"] = max(0, m["rows_n"] - len(top)) + m["more"]
            out.append(m)
        return order(out + others + list(hosts.values()))

    result = []
    for monday in sorted(weeks, reverse=True):
        xs = weeks[monday]
        week = {"start": monday, "end": monday + datetime.timedelta(days=7), "current": monday == this_monday,
                "label": "This week" if monday == this_monday else "Week of %s" % monday.strftime("%b %d")}
        projects = [x for x in xs if x["kind"] == "project"]
        week["summary"] = {
            "done": sorted({x["title"] for x in projects if x["done"]}),
            "started": sorted({x["title"] for x in projects if x["started"]}),
            "projects": len({x["slug"] for x in projects}),
            "milestones": sum(x["rows_n"] for x in projects),
            "updates": sum(x["more"] for x in projects),
            "systems": sum(x["count"] for x in xs if x["kind"] == "systems"),
            "hosts": len({x["host"] for x in xs if x["kind"] == "systems"}),
            "garden": sum(1 for x in xs if x["kind"] == "garden"),
        }
        week["reading"] = None
        if reading:
            try:
                r = reading(monday, min(week["end"], today() + datetime.timedelta(days=1)))
                week["reading"] = r if r and r.get("total") else None
            except Exception:
                pass
        if week["current"]:
            by_day = {}
            for x in xs:
                by_day.setdefault(x["date"], []).append(x)
            week["days"] = [{"date": d, "entries": order(by_day[d])} for d in sorted(by_day, reverse=True)]
            week["entries"] = []
        else:
            week["days"] = []
            week["entries"] = merge_week(xs)
        result.append(week)

    total = sum(len(d["entries"]) for w in result for d in w["days"]) + sum(len(w["entries"]) for w in result)
    return {"now": now, "weeks": result, "days": days, "entries": total,
            "start": start + datetime.timedelta(days=1), "end": end}


def summary_text(s):
    """One line for an older week: '2 done (A, B), 3 started, 12 milestones across 5 projects, 40 system changes on 3 hosts, 1 garden change'."""
    parts = []
    if s["done"]:
        parts.append("%d done (%s)" % (len(s["done"]), ", ".join(s["done"][:4]) + (", …" if len(s["done"]) > 4 else "")))
    if s["started"]:
        parts.append("%d started (%s)" % (len(s["started"]), ", ".join(s["started"][:4]) + (", …" if len(s["started"]) > 4 else "")))
    if s["milestones"] or s["updates"]:
        parts.append("%d milestones and %d updates across %d projects" % (s["milestones"], s["updates"], s["projects"]))
    if s["systems"]:
        parts.append("%d system changes on %d host%s" % (s["systems"], s["hosts"], "" if s["hosts"] == 1 else "s"))
    if s["garden"]:
        parts.append("%d garden change%s" % (s["garden"], "" if s["garden"] == 1 else "s"))
    return "; ".join(parts) or "a quiet week"
