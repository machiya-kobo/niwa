"""Niwa's state: the link-rot table and the scan acknowledgements (SQLite, NIWA_DB), and the garden's events.

Garden events (publish, unpublish, garden = growth/confidence/pin changes, suggest, unsuggest) are Niwa's own. New ones are appended to `.garden/events/YYYY-MM.jsonl` in the vault repo (committed with
the garden's batch, union-merged, so they survive a lost /data). Older events from a shared board are read from
`.board/events/*.jsonl` (the same event shapes). The link table is rebuildable: a fresh one re-checks every link.
"""
import datetime
import glob
import json
import os
import sqlite3
import threading

GARDEN_TYPES = ("publish", "unpublish", "garden", "suggest", "unsuggest")
EVENTS_DIR = ".garden/events"
SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    url TEXT PRIMARY KEY, first_seen TEXT, last_checked TEXT, status TEXT, http INTEGER, fails INTEGER,
    archive_url TEXT, archived_at TEXT, backend TEXT, died_at TEXT, notes TEXT,
    private_url TEXT, private_at TEXT, private_backend TEXT, private_checked TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS acks (rel TEXT, digest TEXT, at TEXT, actor TEXT, PRIMARY KEY (rel, digest));
"""


class State:
    def __init__(self, db_path, repo):
        self.repo = repo
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.commit()
        self._events, self._events_key = [], None
        self.links_version = 0      # bumped by every link_set, so readers can cache the table

    # -- links (used by links.py) -------------------------------------------------------------------------------

    def link(self, url):
        rows = self.links("url = ?", (url,), 1)
        return rows[0] if rows else None

    def links(self, where="", args=(), limit=100000):
        with self.lock:
            cur = self.db.execute("SELECT * FROM links %s ORDER BY first_seen LIMIT ?" % (("WHERE " + where) if where else ""),
                                  (*args, limit))
            keys = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(keys, r)) for r in rows]

    def link_set(self, url, **fields):
        with self.lock, self.db:
            self.links_version += 1
            cur = self.db.execute("SELECT url FROM links WHERE url = ?", (url,)).fetchone()
            if cur:
                if fields:
                    self.db.execute("UPDATE links SET %s WHERE url = ?" % ", ".join("%s = ?" % k for k in fields),
                                    (*fields.values(), url))
            else:
                cols = ["url"] + list(fields)
                self.db.execute("INSERT INTO links (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" * len(cols))),
                                (url, *fields.values()))

    # -- acknowledgements: the scan findings the owner published anyway (garden.py's hold) ----------------------

    def ack(self, rel, digest, actor):
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO acks (rel, digest, at, actor) VALUES (?, ?, ?, ?)",
                            (rel, digest, now, actor))

    def acks(self):
        """{rel: {digest, …}}"""
        with self.lock:
            rows = self.db.execute("SELECT rel, digest FROM acks").fetchall()
        out = {}
        for rel, d in rows:
            out.setdefault(rel, set()).add(d)
        return out

    # -- garden events --------------------------------------------------------------------------------------------

    def _files(self):
        return sorted(glob.glob(os.path.join(self.repo, ".board", "events", "*.jsonl"))) + \
            sorted(glob.glob(os.path.join(self.repo, EVENTS_DIR, "*.jsonl")))

    def load_events(self):
        """Every garden event (history from .board/events + Niwa's .garden/events), oldest first; cached until the
        files change."""
        files = self._files()
        key = tuple((f, os.path.getmtime(f), os.path.getsize(f)) for f in files)
        if key == self._events_key:
            return self._events
        out, seen = [], set()
        for f in files:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line in seen:
                        continue
                    seen.add(line)
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("type") in GARDEN_TYPES:
                        out.append(ev)
        out.sort(key=lambda ev: ev.get("ts", ""))
        self._events, self._events_key = out, key
        return out

    def events(self, card=None, limit=50, since=None, until=None, etype=None):
        """Konbini's store.events signature: newest first."""
        out = []
        for ev in reversed(self.load_events()):
            ts = ev.get("ts", "")
            if (card and ev.get("card") != card) or (etype and ev.get("type") != etype) or \
                    (since and ts < since) or (until and ts >= until):
                continue
            out.append(ev)
            if len(out) >= limit:
                break
        return out

    def add_event(self, etype, actor, agent, **data):
        now = datetime.datetime.now(datetime.timezone.utc)
        ev = {"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "card": data.get("path", ""), "type": etype,
              "actor": actor, "agent": agent}
        ev.update({k: v for k, v in data.items() if v not in (None, "", [], {})})
        d = os.path.join(self.repo, EVENTS_DIR)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, now.strftime("%Y-%m") + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev
