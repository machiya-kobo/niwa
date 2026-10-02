"""Konbini, optionally: the board's cards (column badges, "in bloom", the stream's now-list) and the board half of
the stream (/api/digest). Niwa works without it (NIWA_KONBINI_URL unset, or Konbini down): the badges and board
activity just don't appear. Answers are cached for a minute, and a failure is cached too, so a down Konbini never
slows a page by more than one timeout a minute.
"""
import datetime
import json
import threading
import time
import urllib.error
import urllib.request


class Konbini:
    def __init__(self, url, ttl=60, timeout=4, login=""):
        self.url = (url or "").rstrip("/")
        # Behind Tailscale, serve adds Tailscale-User-Login itself (Niwa's calls leave the server as the owner's machine);
        # `login` is only for running Niwa and Konbini side by side without Tailscale (tests).
        self.login = login
        self.ttl, self.timeout = ttl, timeout
        self.cache, self.lock = {}, threading.Lock()
        self.error = ""

    def enabled(self):
        return bool(self.url)

    def get(self, path):
        if not self.url:
            return None
        with self.lock:
            hit = self.cache.get(path)
            if hit and time.time() - hit[0] < self.ttl:
                return hit[1]
        try:
            headers = {"Accept": "application/json", "X-Agent": "niwa"}
            if self.login:
                headers["Tailscale-User-Login"] = self.login
            req = urllib.request.Request(self.url + path, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
            self.error = ""
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.error = "konbini unreachable: %s" % e
            data = None
        with self.lock:
            self.cache[path] = (time.time(), data)
        return data

    def cards_by_path(self):
        """{note path: card} ({} without Konbini)."""
        d = self.get("/api/cards") or {}
        return {c["path"]: c for c in d.get("cards") or [] if c.get("path")}

    def digest(self, days):
        """(now, entries) of the board half of the stream, dates as datetime.date; (None, []) without Konbini."""
        d = self.get("/api/digest?days=%d" % days)
        if not d:
            return None, []
        entries = []
        for x in d.get("entries") or []:
            try:
                x["date"] = datetime.date.fromisoformat(str(x.get("date"))[:10])
            except ValueError:
                continue
            entries.append(x)
        return d.get("now"), entries

    def status(self):
        return {"url": self.url or None, "error": self.error or None}
