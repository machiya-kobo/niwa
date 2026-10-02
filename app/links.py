"""Link rot: an archived copy next to every external link.

The garden collects the external links of published notes, checks each one
on a slow schedule, and (with NIWA_ARCHIVE=wayback) saves a copy at the
Wayback Machine. Results are kept in NIWA_DB. Garden notes swap a dead link
for its archived copy and list their links with status, the stream reports
links that died, and the pre-publish check warns about links already known
dead. Nothing is written into the notes.

Two kinds of copy, kept apart on purpose:
- archive_url: the public copy (Wayback Machine). Backends implement
  lookup(url) / save(url) -> (archive_url, when) or None.
- private_url: the owner-only copy. A cold-archive snapshot when there is one
  (NIWA_COLD_MAP, a static map of snapshots), else Hister's copy; with
  NIWA_HISTER_SAVE on, a live link Hister doesn't have yet is indexed into it.
Gemini and gopher read only archive_url; private_url is for the owner's web
pages."""
import datetime
import ipaddress
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html import escape, unescape


URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]`]+")
ARCHIVE_HOSTS = ("web.archive.org", "archive.org")
# Only links some published note still has are checked and archived (collect() clears `notes` for the others).
IN_USE = "COALESCE(notes, '') != ''"
# Never external: this machine and tailnet names (*.ts.net is never public), plus NIWA_SKIP_HOSTS (comma-separated host
# names, each matching itself and its subdomains). Private, loopback and link-local IP literals are skipped too (is_internal).
SKIP_HOSTS = ("localhost", "ts.net") + tuple(h.strip().lower().strip(".") for h in os.environ.get("NIWA_SKIP_HOSTS", "").split(",")
                                              if h.strip().strip("."))
UA = os.environ.get("NIWA_LINKS_USER_AGENT", "").strip() or "niwa-links/1"     # add a contact URL for the sites it checks
CHECK_DAYS = 7          # re-check a link this often
BATCH_CHECK = 25        # per hourly run
BATCH_SAVE = 8          # archive saves per hourly run (Wayback rate limits)
BATCH_PRIVATE = 40      # private copies per hourly run (local, no rate limit)
COLD_REFRESH = 86400    # re-read the cold archive's urlmap.json daily
DEAD_CODES = (404, 410, 451)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_url(u):
    return u.rstrip(".,;:!?…")


def is_internal(host):
    """A name that isn't on the public internet: SKIP_HOSTS or a non-global IP literal (10/8, 192.168/16, 100.64/10, ...).
    Only IP literals are matched as addresses, so a real host like 100.example.com is not internal."""
    host = host.lower().strip(".")
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return any(host == h or host.endswith("." + h) for h in SKIP_HOSTS)


def is_external(url):
    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    if not host or "." not in host:  # tailnet short names and localhost
        return False
    return not (is_internal(host) or any(host == h or host.endswith("." + h) for h in ARCHIVE_HOSTS))


def extract(text):
    out, seen = [], set()
    for m in URL_RE.finditer(text):
        u = clean_url(m.group(0))
        if u not in seen and is_external(u):
            seen.add(u)
            out.append(u)
    return out


# -- backends ----------------------------------------------------------------

class WaybackBackend:
    name = "wayback"

    def lookup(self, url):
        # the availability API wants the URL without its scheme
        q = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url.split("://", 1)[-1], safe="/")
        req = urllib.request.Request(q, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        snap = (data.get("archived_snapshots") or {}).get("closest") or {}
        if snap.get("available") and snap.get("url"):
            ts = snap.get("timestamp", "")
            when = "%s-%s-%s" % (ts[:4], ts[4:6], ts[6:8]) if len(ts) >= 8 else ""
            return snap["url"].replace("http://web.archive.org", "https://web.archive.org"), when
        return None

    def save(self, url):
        req = urllib.request.Request("https://web.archive.org/save/" + url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            loc = r.headers.get("Content-Location") or ""
            final = r.geturl()
        if loc.startswith("/web/"):
            return "https://web.archive.org" + loc, now_iso()[:10]
        if "/web/" in final:
            return final, now_iso()[:10]
        return None


class ColdArchive:
    """A cold archive of static page snapshots, served read-only: a JSON map at NIWA_COLD_MAP,
    {"urls": {norm(url): {"snapshot", "date", "raw"}}}, keyed by urlnorm.norm(url)."""
    name = "cold"

    def __init__(self, map_url):
        self.map_url = map_url
        self.urls, self.loaded, self.error = {}, 0.0, ""

    def refresh(self):
        if time.time() - self.loaded < COLD_REFRESH and self.urls:
            return
        try:
            with urllib.request.urlopen(urllib.request.Request(self.map_url, headers={"User-Agent": UA}), timeout=30) as r:
                self.urls = json.loads(r.read().decode("utf-8")).get("urls") or {}
            self.loaded, self.error = time.time(), ""
        except Exception as exc:  # keep the old map
            self.error = "urlmap: %s" % str(exc)[:100]
            self.loaded = time.time() - COLD_REFRESH + 600  # retry in 10 minutes

    def lookup(self, url):
        from urlnorm import norm
        self.refresh()
        hit = self.urls.get(norm(url))
        return (hit["snapshot"], hit.get("date") or "") if hit and hit.get("snapshot") else None


class HisterBackend:
    """Hister's copy of a page (hister.Hister). save() indexes only URLs that
    Hister doesn't hold yet: re-indexing an existing document would replace
    its metadata."""
    name = "hister"

    def __init__(self, hister):
        self.h = hister

    def lookup(self, url):
        from hister import ts_date
        d = self.h.find(url)
        return (self.h.preview_url(d["url"]), ts_date(d.get("updated") or d.get("added"))) if d else None

    def final_url(self, url):
        """Where a URL redirects to: Hister stores the page under its final address."""
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.geturl()
        except Exception:
            return url

    def save(self, url):
        found = self.lookup(url)
        if found:
            return found
        final = self.final_url(url)
        if final != url:
            found = self.lookup(final)
            if found:
                return found
        if not self.h.index(url):
            return None
        for _ in range(4):  # Hister indexes in the background
            time.sleep(2)
            found = self.lookup(url) or (self.lookup(final) if final != url else None)
            if found:
                return found
        return None


class Links:
    def __init__(self, store, garden, backends=(), enabled=True, cold=None, hister=None, hister_save=False):
        self.store, self.garden = store, garden
        self.backends = list(backends)
        self.cold, self.hister = cold, hister  # private copies (owner-only)
        self.enabled = enabled
        self.hister_save = hister_save   # off: Hister is looked up, never indexed into (Shiori saves pages)
        self.lock = threading.Lock()
        self.last_run = ""
        self._index, self._index_version = ({}, {}), None

    # -- collect ---------------------------------------------------------------

    def collect(self):
        """Register the external links of published notes; a link no published note has any more keeps its record
        (and its copies) with no notes, and is no longer checked or archived."""
        self.garden.index()
        refs = {}
        for n in self.garden.notes.values():
            if not n.published:
                continue
            for u in extract(n.text):
                refs.setdefault(u, set()).add(n.rel)
        added = 0
        for u, rels in refs.items():
            rec = self.store.link(u)
            notes = "\n".join(sorted(rels))
            if rec:
                if rec.get("notes") != notes:
                    self.store.link_set(u, notes=notes)
            else:
                self.store.link_set(u, first_seen=now_iso(), status="unknown", fails=0, notes=notes)
                added += 1
        for rec in self.store.links(IN_USE):
            if rec["url"] not in refs:
                self.store.link_set(rec["url"], notes="")
        return added

    # -- check -----------------------------------------------------------------

    def probe(self, url):
        """HTTP status of a link, or None when it can't be reached."""
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                if method == "HEAD" and e.code in (405, 403, 501):
                    continue
                return e.code
            except Exception:
                if method == "HEAD":
                    continue
                return None
        return None

    def check(self, rec):
        code = self.probe(rec["url"])
        fields = {"last_checked": now_iso(), "http": code}
        if code is not None and code < 400:
            fields.update(status="live", fails=0)
        elif code in DEAD_CODES:
            fields.update(status="dead", fails=(rec.get("fails") or 0) + 1)
        else:
            fails = (rec.get("fails") or 0) + 1
            fields.update(fails=fails, status="dead" if fails >= 3 else (rec.get("status") if rec.get("status") == "live" else "unknown"))
        if fields.get("status") == "dead" and rec.get("status") != "dead":
            fields["died_at"] = now_iso()
        if fields.get("status") == "live":
            fields["died_at"] = None
        self.store.link_set(rec["url"], **fields)
        return fields["status"]

    # -- archive ---------------------------------------------------------------

    def archive(self, rec):
        for b in self.backends:
            try:
                found = b.lookup(rec["url"])
                if found and found[1] and (datetime.date.today() - datetime.date.fromisoformat(found[1][:10])).days <= 365:
                    self.store.link_set(rec["url"], archive_url=found[0], archived_at=found[1], backend=b.name)
                    return found[0]
                saved = b.save(rec["url"])
                if saved:
                    self.store.link_set(rec["url"], archive_url=saved[0], archived_at=saved[1], backend=b.name)
                    return saved[0]
                if found:  # older than a year but better than nothing
                    self.store.link_set(rec["url"], archive_url=found[0], archived_at=found[1], backend=b.name)
                    return found[0]
            except Exception as exc:  # one backend failing must not stop the others
                print("links: %s %s: %s" % (b.name, rec["url"][:80], str(exc)[:80]), flush=True)
        return None

    def private_copy(self, rec):
        """Fill private_url: the cold snapshot if there is one, else Hister's
        copy. With NIWA_HISTER_SAVE on, a live link Hister lacks is indexed when
        there's no snapshot or the snapshot is over a year old (the old snapshot
        stays the answer); otherwise Hister is only looked up."""
        url, fields = rec["url"], {"private_checked": now_iso()}
        cold = hist = None
        try:
            cold = self.cold.lookup(url) if self.cold else None
            if self.hister:
                hist = self.hister.lookup(url)
                stale = not cold or not cold[1] or (datetime.date.today() - datetime.date.fromisoformat(cold[1][:10])).days > 365
                if not hist and stale and rec.get("status") == "live" and self.hister_save:
                    hist = self.hister.save(url)
        except Exception as exc:
            print("links: private %s: %s" % (url[:80], str(exc)[:80]), flush=True)
        best, name = (cold, "cold") if cold else ((hist, "hister") if hist else (None, None))
        if best:
            fields.update(private_url=best[0], private_at=best[1], private_backend=name)
        self.store.link_set(url, **fields)
        return best[0] if best else None

    # -- the hourly worker -------------------------------------------------------

    def run_once(self):
        added = self.collect()
        due = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=CHECK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        checked = 0
        for rec in self.store.links("(last_checked IS NULL OR last_checked < ?) AND " + IN_USE, (due,), BATCH_CHECK):
            self.check(rec)
            checked += 1
            time.sleep(1)
        saved = 0
        if self.enabled and self.backends:
            for rec in self.store.links("archive_url IS NULL AND status != 'unknown' AND " + IN_USE, (), BATCH_SAVE):
                if self.archive(rec):
                    saved += 1
                time.sleep(3)
        if self.cold or self.hister:
            week = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=CHECK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for rec in self.store.links("private_url IS NULL AND status != 'unknown' AND "
                                        "(private_checked IS NULL OR private_checked < ?) AND " + IN_USE, (week,),
                                        BATCH_PRIVATE):
                if self.private_copy(rec):
                    saved += 1
        self.last_run = now_iso()
        return added, checked, saved

    def worker(self, first_delay=60, every=3600):
        time.sleep(first_delay)
        while True:
            try:
                added, checked, saved = self.run_once()
                print("links: +%d new, %d checked, %d archived" % (added, checked, saved), flush=True)
            except Exception as exc:
                print("links: run failed: %s" % exc, flush=True)
            time.sleep(every)

    # -- for pages -------------------------------------------------------------

    def index(self):
        """({url: record}, {note rel: [records]}), read once per change to the link table (pages ask per note and
        per link)."""
        version = self.store.links_version
        if self._index_version != version:
            by_url, by_note = {}, {}
            for r in self.store.links():
                by_url[r["url"]] = r
                for rel in filter(None, (r.get("notes") or "").split("\n")):
                    by_note.setdefault(rel, []).append(r)
            self._index, self._index_version = (by_url, by_note), version
        return self._index

    def for_note(self, rel):
        return list(self.index()[1].get(rel, ()))

    def dead_for_note(self, rel):
        return [r for r in self.for_note(rel) if r.get("status") == "dead"]

    def annotate(self, html, private=False):
        """Point dead links at their archived copy and mark them. private=True
        (the owner's modern pages) prefers the private copy; everything else
        only ever gets the public Wayback copy."""
        by_url = self.index()[0]
        def swap(m):
            url = unescape(m.group(1))      # the href is HTML (&amp;); the table holds the URL as written
            rec = by_url.get(url)
            if not rec or rec.get("status") != "dead":
                return m.group(0)
            if private and rec.get("private_url"):
                return '<a class="dead" title="dead link, private copy from %s" href="%s"' % (
                    escape(rec.get("private_at") or "?"), escape(rec["private_url"]))
            if rec.get("archive_url"):
                return '<a class="dead" title="dead link, archived copy from %s" href="%s"' % (
                    escape(rec.get("archived_at") or "?"), escape(rec["archive_url"]))
            return '<a class="dead" title="dead link, no archived copy" href="%s"' % escape(url)
        return re.sub(r'<a href="(https?://[^"]+)"', swap, html)

    def died_between(self, start, end):
        out = []
        for r in self.store.links("died_at IS NOT NULL", ()):
            try:
                d = datetime.date.fromisoformat((r.get("died_at") or "")[:10])
            except ValueError:
                continue
            if start <= d < end:
                out.append((d, r))
        return out

    def stats(self):
        rows = self.store.links()
        return {"total": len(rows), "live": sum(1 for r in rows if r["status"] == "live"),
                "dead": sum(1 for r in rows if r["status"] == "dead"),
                "archived": sum(1 for r in rows if r.get("archive_url")),
                "private": sum(1 for r in rows if r.get("private_url")), "last_run": self.last_run,
                "cold": (self.cold.error or "%d snapshots" % len(self.cold.urls)) if self.cold else "off",
                "hister": (self.hister.h.error or "ok") if self.hister else "off"}
