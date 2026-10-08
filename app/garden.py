"""The private digital garden: published notes rendered from the vault.

A note is in the garden when its frontmatter has `publish: true`; only the
owner sets that, from the web UI (writer.set_publish). Everything here is
derived from Niwa's own clone of the vault and cached per git revision:

  - rendering: python-markdown (tables, fenced code, Obsidian-style soft line
    breaks) after rewriting [[wikilinks]] (published target -> garden link,
    anything else -> plain text) and ![[embeds]] (images from the vault)
  - growth stage: `growth:` or, by default, from type/status tags
  - last tended: the note's latest commit date
  - backlinks and "nearby" notes (shared topics/area/machines, direct links)
  - check(): what a pre-publish scan would warn about (addresses, keys,
    tokens, links to private (NIWA_PRIVATE_FOLDERS) or unpublished notes, missing summary)
"""
import datetime
import hashlib
import os
import re
import threading

from vaultkit import _str
# The shared vault core (vendored from machiya-kobo/machiya vaultkit/; don't edit app/vaultkit/ here). Re-exported for
# gmodern and smallweb, which import these names from garden.
from vaultkit.front import FRONT_RE                                                  # noqa: F401
from vaultkit.notes import (CONFIDENCE, LINK_RE, STAGE_MARK, STAGES, TYPES, Note, e,  # noqa: F401
                            first_paragraph, relative, stage_of, type_of)
from vaultkit.vault import CALLOUT_RE, EMBED_RE, IMAGE_EXT, MDIMG_RE, Vault         # noqa: F401

# The landing page's intro while no Garden.md is published, on the web, gemini and gopher: NIWA_INTRO (plain text,
# HTML-escaped when shown), else this.
DEFAULT_INTRO = "Notes from the vault, shared as they grow."
INTRO = os.environ.get("NIWA_INTRO", "").strip() or DEFAULT_INTRO

# Pre-publish scan
CHECKS = [
    ("error", "LAN or tailnet address", re.compile(
        r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3})\b"
        r"|\bfd7a:115c:[0-9a-f:]+", re.I)),
    ("error", "MAC address", re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.I)),
    ("error", "key fingerprint or key ID", re.compile(r"\b[0-9A-F]{40}\b|\b[0-9A-F]{16}\b")),
    ("error", "token or private key", re.compile(
        r"tskey-\w|ghp_\w{10}|github_pat_|sk-[A-Za-z0-9]{20}|xox[bp]-|-----BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}")),
    ("warn", "password or secret mentioned", re.compile(r"(?i)\b(password|passwd|secret|api[_ ]?key)\s*[:=]")),
    ("warn", "tailnet name", re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net\b", re.I)),
    ("warn", "email address", re.compile(r"\b[\w.+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b", re.I)),
]
DENY_LABEL = "denied word (NIWA_SCAN_DENY)"

# A long note is a warning, not an error: NIWA_LONG_WORDS (default 800, 0 turns it off).
try:
    LONG_WORDS = int(os.environ.get("NIWA_LONG_WORDS", "").strip() or 800)
except ValueError:
    LONG_WORDS = 800

# A note can publish just a part of itself: the section under a heading called Garden (and its sub-sections), plus a
# section called Updates when there is one. The rest never reaches the garden, its scan, links, search or feeds. A note
# with no Garden heading publishes whole.
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
UPDATES_HEAD = re.compile(r"^(#{1,6})\s+updates\s*$", re.I | re.M)
UPDATE_LINE = re.compile(r"^\s*[-*]\s+(\d{4}-\d{2}-\d{2})\s*(?:[:\u2014\u2013-]\s*)?(.+?)\s*$", re.M)


def excerpt(text):
    """The part of a note the garden publishes: its frontmatter, the section under a Garden heading (to the next
    heading of the same level or above) and an Updates section; None when the note has no Garden heading, so it
    publishes whole. Headings inside a code fence don't count."""
    m = FRONT_RE.match(text)
    head = m.group(0) if m else ""
    lines = text[len(head):].split("\n")
    marks, fence = [], False                      # (line, level, name) of every heading outside a code fence
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence:
            h = HEADING.match(line)
            if h:
                marks.append((i, len(h.group(1)), h.group(2).strip().lower()))
    if not any(name == "garden" for _, _, name in marks):
        return None
    parts, covered = [], 0
    for k, (i, level, name) in enumerate(marks):
        if name not in ("garden", "updates") or i < covered:
            continue                              # not ours, or already inside a section we took
        end = next((j for j, lv, _ in marks[k + 1:] if lv <= level), len(lines))
        parts.append("\n".join(lines[i + 1 if name == "garden" else i:end]).strip())
        covered = end
    return head + "\n\n".join(p for p in parts if p) + "\n"


def count_words(text):
    return len(FRONT_RE.sub("", text, count=1).split())


def deny_re(words):
    """NIWA_SCAN_DENY: words or names (hostnames, people, places) that must never be published, matched whole and
    ignoring case; None when there are none."""
    words = sorted({w.strip() for w in words if w and w.strip()}, key=len, reverse=True)
    if not words:
        return None
    return re.compile(r"(?<![\w.-])(?:%s)(?![\w-])" % "|".join(re.escape(w) for w in words), re.I)


class Garden(Vault):
    """The garden's view of the vault: vaultkit.Vault (index, wikilinks, rendering) over Niwa's own clone,
    re-indexed when `revision` (the synced commit, set by niwa.py) changes. `store` is Niwa's state (garden events,
    link records); `konbini` the optional board client."""

    def __init__(self, repo, subdir, state, git=None, private=()):
        super().__init__(repo, subdir, git=git)
        self.store = state
        self.deny = None     # deny_re(NIWA_SCAN_DENY), set by niwa.py
        self.queue_folders = ()      # NIWA_QUEUE_FOLDERS, set by niwa.py: the only folders the Queue lists (and suggestions)
        self.full_words = {}         # rel -> words in the whole note, for a note that publishes an excerpt
        self.held = {}       # rel -> the error findings that hold a `publish: true` note back (see _apply_private)
        self._errors = {}    # rel -> (hash of text and deny list, [(label, hit)]): the scan's errors, once per text
        self._hits = {}      # rel -> (the same hash, scan_hits): the full scan, once per text (the Queue scans every note)
        self._index_lock = threading.RLock()     # one re-index at a time: requests that arrive during it wait for it
        self._applied = None     # the revision whose index and holds are both done
        self.private = private    # folder prefixes ("Private/") whose notes are never queued or published (see the setter)
        self.links = None    # set by niwa.py (links.Links)
        self.hister = None
        self.konbini = None
        self._public_assets, self._public_assets_key = set(), None

    def public_asset_path(self, rel):
        """asset_path() for gemini and gopher: only an image a published note shows (an ![[embed]] or a Markdown image,
        resolved the way rendering resolves them), never one that only private or unpublished notes use."""
        self.index()
        key = (self.key(), tuple(sorted(self.held)))      # an acknowledgement changes what is published, not the key
        if self._public_assets_key != key:
            shown = set()
            for n in self.notes.values():
                if not n.published:
                    continue
                for m in EMBED_RE.finditer(n.text):
                    if m.group(1).strip().lower().endswith(IMAGE_EXT):
                        shown.add(self.assets.get(os.path.basename(m.group(1).strip())))
                for m in MDIMG_RE.finditer(n.text):
                    if not re.match(r"https?://", m.group(2)):
                        shown.add(self.assets.get(os.path.basename(m.group(2).replace("%20", " "))))
            self._public_assets, self._public_assets_key = shown - {None}, key
        return self.asset_path(rel) if rel in self._public_assets else None

    @property
    def private(self):
        return self._private

    @private.setter
    def private(self, folders):
        self._private = tuple(folders)
        self._apply_private()

    def _apply_private(self):
        """`publish: true` in a private folder (NIWA_PRIVATE_FOLDERS) counts for nothing: such a note is never published
        on the web, gemini, gopher or the feed, whatever its frontmatter says (so one edit can't leak it).
        A `publish: true` note whose scan finds errors (addresses, keys, tokens, NIWA_SCAN_DENY words) is held back
        too, everywhere, until the owner acknowledges exactly those findings on its page ("Publish anyway"; the
        digest is kept in Niwa's own SQLite, never in the vault). A new finding, or a `publish: true` written outside
        Niwa, holds it again."""
        acks = self.store.acks() if self.store is not None and hasattr(self.store, "acks") else {}
        held = {}
        for n in getattr(self, "notes", {}).values():
            n.published = n.fm.get("publish") is True and not self.is_private(n.rel)
            if n.published:
                found = self.errors(n)
                if found and digest(found) not in acks.get(n.rel, ()):
                    n.published = False
                    held[n.rel] = found
        self.held = held

    def refresh_holds(self):
        """After an acknowledgement: work the holds out again now (the notes haven't changed)."""
        self.index()
        self._apply_private()

    def scan_key(self, note):
        return hashlib.sha256(("%s\0%s" % (self.deny.pattern if self.deny else "", note.text)).encode("utf-8")).digest()

    def errors(self, note):
        """The scan's error findings in a note's body, in full: [(label, hit)], sorted. Cached per text."""
        body_key = self.scan_key(note)
        cached = self._errors.get(note.rel)
        if cached and cached[0] == body_key:
            return cached[1]
        body = FRONT_RE.sub("", note.text, count=1)
        found = {(label, m.group(0)) for severity, label, rx in CHECKS if severity == "error" for m in rx.finditer(body)}
        if self.deny:
            found |= {(DENY_LABEL, m.group(0)) for m in self.deny.finditer(body)}
        found = sorted(found)
        self._errors[note.rel] = (body_key, found)
        return found

    def hold_digest(self, note):
        """The digest "Publish anyway" acknowledges: of the note's error findings now; "" when it has none."""
        found = self.errors(note)
        return digest(found) if found else ""

    def index(self):
        """Index the vault for the current revision, once: the first caller after a pull does the work (the sync thread,
        niwa.py's on_pull) and the others wait for it. `_applied` is set only after the holds are worked out, so nobody
        sees the new notes before they know what is published."""
        if self.key() == self._applied:
            return
        with self._index_lock:
            key = self.key()
            if key != self._applied:
                super().index()
                self._apply_private()
                self._applied = key

    def source(self):
        """The vault's notes, a note with garden markers cut down to its excerpt: everything downstream (the render,
        the scan, links, search, the feeds, the word count) then sees only what the garden publishes."""
        self.full_words = {}
        for rel, fm, text in super().source():
            part = excerpt(text)
            if part is not None:
                self.full_words[rel] = count_words(text)
                text = part
            yield rel, fm, text

    def word_count(self, note):
        """Words in the part of the note the garden shows."""
        return count_words(note.text)

    def updates(self, note):
        """The note's short dated updates, newest first: [(date, text)]. They are the "- 2026-10-07: text" bullets under
        a heading called Updates, up to the next heading of the same level or above."""
        m = UPDATES_HEAD.search(note.text)
        if not m:
            return []
        rest = note.text[m.end():]
        end = re.search(r"^#{1,%d}\s" % len(m.group(1)), rest, re.M)
        out = []
        for d, text in UPDATE_LINE.findall(rest[:end.start()] if end else rest):
            try:
                out.append((datetime.date.fromisoformat(d), text))
            except ValueError:
                pass
        return sorted(out, key=lambda t: t[0], reverse=True)

    def is_private(self, rel):
        return rel.startswith(self._private)

    def published(self):
        """Published notes, without the landing intro (Garden.md), which is rendered above them."""
        self.index()
        return [n for n in self.notes.values() if n.published and n.rel != "Garden.md"]

    # -- relations -----------------------------------------------------

    def linked_from(self, note):
        return sorted((self.notes[r] for r in self.backlinks.get(note.rel, ()) if self.notes[r].published),
                      key=lambda n: n.title.lower())

    def nearby(self, note, limit=6):
        def facets(n):
            return ({t for t in n.tags if t.startswith(("topic/", "machine/"))},
                    {t for t in n.tags if t.startswith("area/") and t != "area/projects"})
        mine, my_area = facets(note)
        scored = []
        for other in self.published():
            if other.rel == note.rel:
                continue
            theirs, their_area = facets(other)
            score = 2 * len(mine & theirs) + len(my_area & their_area)
            if other.rel in note.links or note.rel in other.links:
                score += 3
            if score:
                scored.append((score, other.title.lower(), other))
        return [n for _, _, n in sorted(scored, key=lambda t: (-t[0], t[1]))[:limit]]

    def tags(self):
        counts = {}
        for n in self.published():
            for t in n.tags:
                if t.startswith(("topic/", "area/")) and t != "area/projects":
                    counts[t] = counts.get(t, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    # -- pre-publish scan ----------------------------------------------

    def scan_hits(self, note):
        """What the pattern scan found in a note's body, in full: [(severity, label, [text, ...])]. The owner's page
        shows and highlights each one."""
        key = self.scan_key(note)
        cached = self._hits.get(note.rel)
        if cached and cached[0] == key:
            return cached[1]
        body = FRONT_RE.sub("", note.text, count=1)
        out = []
        for severity, label, rx in list(CHECKS) + ([("error", DENY_LABEL, self.deny)] if self.deny else []):
            hits = sorted({m.group(0) for m in rx.finditer(body)})
            if hits:
                out.append((severity, label, hits))
        self._hits[note.rel] = (key, out)
        return out

    def check(self, note):
        self.index()
        found = []
        for severity, label, hits in self.scan_hits(note):
            shown = ", ".join(h if severity == "warn" else h[:6] + "…" for h in hits[:4])
            found.append((severity, "%s (%d): %s" % (label, len(hits), shown)))
        words = self.word_count(note)
        if LONG_WORDS and words > LONG_WORDS:
            whole = self.full_words.get(note.rel)
            found.append(("warn", "long: %s words, over %s. A focused post is shorter: shorten it, or publish an excerpt "
                                  "(put it under a Garden heading)" % (format(words, ","), format(LONG_WORDS, ","))
                          + ((" (the whole note is %s)" % format(whole, ",")) if whole else "")))
        private = sorted({self.notes[r].title for r in note.links if self.is_private(r)})
        if private:
            found.append(("warn", "links to private notes: " + ", ".join(private)))
        unpublished = sorted({self.notes[r].title for r in note.links
                              if not self.notes[r].published and not self.is_private(r)})
        if unpublished:
            found.append(("info", "%d link(s) to unpublished notes show as plain text: %s"
                          % (len(unpublished), ", ".join(unpublished[:6]))))
        if not _str(note.fm.get("summary")):
            found.append(("info", "no summary: the garden lists it without a description"))
        if self.links:
            dead = self.links.dead_for_note(note.rel)
            if dead:
                found.append(("warn", "%d dead link(s)%s: %s" % (
                    len(dead), "" if all(r.get("archive_url") for r in dead) else " without an archived copy",
                    ", ".join(r["url"][:60] for r in dead[:3]))))
        if self.is_private(note.rel):
            found.insert(0, ("error", "%s/ notes are private and shouldn't be published" % note.rel.split("/")[0]))
        return found

    # -- landing page -------------------------------------------------------

    def maps(self):
        """Published topic maps (MOCs) with the number of published notes they link to."""
        out = []
        for n in self.published():
            if n.ntype == "map":
                count = sum(1 for r in n.links if r in self.notes and self.notes[r].published)
                out.append((n, count))
        return sorted(out, key=lambda t: (-t[1], t[0].title.lower()))

    def random_note(self):
        import random
        notes = self.published()
        return random.choice(notes) if notes else None

    def stats(self):
        notes = self.published()
        return {"total": len(notes), **{k: sum(1 for n in notes if n.stage == k) for k, _, _ in STAGES},
                "types": {k: sum(1 for n in notes if n.ntype == k) for k, _ in TYPES}}

    def intro(self, base):
        """The landing intro: the body of a published Garden.md, else None."""
        self.index()
        n = self.notes.get("Garden.md")
        if n and n.published:
            return self.render(n, base)
        return None

    # -- queue ---------------------------------------------------------------

    def suggestions(self, days=60):
        """rel -> {"who", "reason", "date"} for open suggestions: the latest
        suggest event per note not followed by unsuggest or publish."""
        self.index()
        since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        state = {}
        events = [ev for t in ("suggest", "unsuggest", "publish")
                  for ev in reversed(self.store.events(since=since, limit=5000, etype=t))]     # oldest first, so a tie keeps the later write
        for ev in sorted(events, key=lambda ev: ev.get("ts", "")):
            rel = ev.get("path") or ""
            if ev.get("type") == "suggest":
                who = ev.get("agent") if ev.get("agent") not in (None, "web", "api") else (ev.get("actor") or "")
                state[rel] = {"who": who, "reason": ev.get("body") or "", "date": ev.get("ts", "")[:10]}
            else:
                state.pop(rel, None)
        return {rel: s for rel, s in state.items() if rel in self.notes and not self.notes[rel].published}

    def well_linked(self, minimum=3, limit=8):
        """The most linked-to unpublished notes: rel -> backlink count (top `limit`)."""
        self.index()
        out = {}
        for rel, srcs in self.backlinks.items():
            n = self.notes.get(rel)
            if n and not n.published and not self.is_private(rel) and len(srcs) >= minimum:
                out[rel] = len(srcs)
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))[:limit])

    def check_summary(self, note):
        """(errors, warnings) from the pre-publish scan."""
        found = self.check(note)
        return sum(1 for s, _ in found if s == "error"), sum(1 for s, _ in found if s == "warn")

    def preview(self, note):
        return {"title": note.title, "description": note.description, "stage": note.stage,
                "stage_name": dict((k, n) for k, n, _ in STAGES).get(note.stage, note.stage),
                "confidence": note.confidence, "planted": note.planted, "tended": self.tended.get(note.rel, ""),
                "type": note.ntype}


def digest(found):
    """A stable digest of a note's error findings ([(label, hit)]), for its acknowledgement."""
    return hashlib.sha256("\n".join("%s\t%s" % f for f in sorted(found)).encode("utf-8")).hexdigest()


def today_iso():
    return datetime.date.today().isoformat()
