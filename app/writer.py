"""The garden's writes: publish/unpublish, stage/confidence/pin, suggestions. Owner only, except suggest (agents may
suggest a note; they never publish). Who is the owner: with Machiya's identity file, the caller's `niwa` `publish`
grant (the handler passes it as `power`); without one, a write labelled "web" (the owner's form posts). Each write edits frontmatter lines only (vaultkit's
edit_front, the same code Konbini uses), records a garden event in `.garden/events/`, and joins the next batch
commit by `garden`, which vaultkit.GitSync pulls, replays onto upstream if needed, and pushes.
"""
import itertools
import os
import threading

from vaultkit import EditError, edit_front, note_front, safe_path

GROWTH = ("seedling", "budding", "evergreen")
CONFIDENCE = ("certain", "likely", "possible", "speculative")


class WriteError(EditError):
    pass


def owner_only(agent, power, message):
    """power: the identity file's answer (True/False), or None without one, when the "web" label decides as before.
    `agent` is then only a label for the events."""
    if not (agent == "web" if power is None else power is True):
        raise WriteError(403, message)


class Writer:
    def __init__(self, sync, garden, state):
        self.sync, self.garden, self.state = sync, garden, state
        # The git sync's own lock: a write can't land in the middle of its commit, pull or conflict replay (which would
        # reset it away together with its event line).
        self.lock = getattr(sync, "lock", None) or threading.RLock()
        self.counter = itertools.count(1)

    def full(self, rel):
        return os.path.join(self.garden.root, rel)

    def checked(self, rel):
        """The path of an existing note to edit: relative, inside the vault, with no symlink anywhere in it
        (vaultkit.safe_path), so a write never lands on a file a link points at."""
        try:
            path = safe_path(self.garden.root, rel)
        except ValueError:
            raise WriteError(404, "no such note")
        if not os.path.exists(path):
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

    def set_publish(self, rel, value, actor, agent, power=None):
        owner_only(agent, power, "only the owner publishes to the garden, from the web UI")
        with self.lock:
            self.checked(rel)
            if value and self.garden.is_private(rel):       # no "publish anyway": a private folder is never published
                raise WriteError(422, "notes in a private folder are never published")
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

    def dismiss(self, rel, actor, agent, power=None):
        owner_only(agent, power, "only the owner dismisses suggestions, from the web UI")
        with self.lock:
            self.state.add_event("unsuggest", actor, agent, path=rel)
            self.changed("dismiss " + os.path.splitext(os.path.basename(rel))[0])

    def set_garden_meta(self, rel, fields, actor, agent, power=None):
        """Stage, confidence and pin: owner only. Empty values remove the line (stage goes back to the default
        rule)."""
        owner_only(agent, power, "only the owner tends the garden, from the web UI")
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
