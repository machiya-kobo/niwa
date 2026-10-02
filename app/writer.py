"""The garden's writes: publish/unpublish, stage/confidence/pin, suggestions. Owner only from the web UI, except
suggest (agents may suggest a note; they never publish). Each write edits frontmatter lines only (vaultkit's
edit_front, the same code Konbini uses), records a garden event in `.garden/events/`, and joins the next batch
commit by `garden`, which vaultkit.GitSync pulls, replays onto upstream if needed, and pushes.
"""
import itertools
import os
import threading

from vaultkit import EditError, edit_front, note_front

GROWTH = ("seedling", "budding", "evergreen")
CONFIDENCE = ("certain", "likely", "possible", "speculative")


class WriteError(EditError):
    pass


class Writer:
    def __init__(self, sync, garden, state):
        self.sync, self.garden, self.state = sync, garden, state
        self.lock = threading.RLock()
        self.counter = itertools.count(1)

    def full(self, rel):
        return os.path.join(self.garden.root, rel)

    def checked(self, rel):
        path = os.path.realpath(self.full(rel))
        if not path.startswith(os.path.realpath(self.garden.root) + os.sep) or not os.path.exists(path):
            raise WriteError(404, "no such note")
        return path

    def read(self, rel):
        with open(self.full(rel), encoding="utf-8") as f:
            return f.read()

    def write_file(self, rel, text):
        path = self.full(rel)
        tmp = path + ".niwa-tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    def changed(self, summary):
        """Queue the batch commit and make the garden re-read the notes now (the commit comes later)."""
        self.sync.touch(summary)
        self.garden.revision = "%s+w%d" % (self.garden.revision.split("+w")[0], next(self.counter))

    def set_publish(self, rel, value, actor, agent):
        if agent != "web":
            raise WriteError(403, "only the owner publishes to the garden, from the web UI")
        with self.lock:
            self.checked(rel)
            self.write_file(rel, edit_front(self.read(rel), {"publish": bool(value)}))
            self.state.add_event("publish" if value else "unpublish", actor, agent, path=rel)
            self.changed(("publish " if value else "unpublish ") + os.path.splitext(os.path.basename(rel))[0])

    def suggest(self, rel, reason, actor, agent):
        """An agent (or the owner) suggests a note for the garden: an event and a badge in the queue, never a
        publish."""
        with self.lock:
            self.checked(rel)
            ev = self.state.add_event("suggest", actor, agent, path=rel, body=str(reason or "").strip()[:300])
            self.changed("suggest " + os.path.splitext(os.path.basename(rel))[0])
            return ev

    def dismiss(self, rel, actor, agent):
        if agent != "web":
            raise WriteError(403, "only the owner dismisses suggestions, from the web UI")
        with self.lock:
            self.state.add_event("unsuggest", actor, agent, path=rel)
            self.changed("dismiss " + os.path.splitext(os.path.basename(rel))[0])

    def set_garden_meta(self, rel, fields, actor, agent):
        """Stage, confidence and pin: owner only. Empty values remove the line (stage goes back to the default
        rule)."""
        if agent != "web":
            raise WriteError(403, "only the owner tends the garden, from the web UI")
        scalars = {}
        if "growth" in fields:
            g = str(fields["growth"] or "").strip().lower()
            if g and g not in GROWTH:
                raise WriteError(422, "growth must be one of " + ", ".join(GROWTH))
            scalars["growth"] = g or None
        if "confidence" in fields:
            c = str(fields["confidence"] or "").strip().lower()
            if c and c not in CONFIDENCE:
                raise WriteError(422, "confidence must be one of " + ", ".join(CONFIDENCE))
            scalars["confidence"] = c or None
        if "garden_pin" in fields:
            scalars["garden_pin"] = True if str(fields["garden_pin"]).lower() in ("1", "true", "on", "yes") else None
        if not scalars:
            raise WriteError(422, "nothing to change")
        with self.lock:
            self.checked(rel)
            text = self.read(rel)
            fm = note_front(text) or {}
            changes = {}
            for k, v in scalars.items():
                old = fm.get(k)
                old = (str(old).lower() if old not in (None, "", False) else None) if k != "garden_pin" else (old is True or None)
                if old != v:
                    changes[k] = [old, v]
            if not changes:
                return {"changed": {}}
            self.write_file(rel, edit_front(text, scalars))
            self.state.add_event("garden", actor, agent, path=rel, changes=changes)
            self.changed("garden " + os.path.splitext(os.path.basename(rel))[0])
            return {"changed": changes}
