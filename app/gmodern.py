"""The garden's HTML5 pages, in Machiya's shared shell (shell.py). `base` is the path prefix the pages are mounted
under ("" when Niwa serves them at its root).
Links to garden notes wear the garden's colour (.thing.is-garden), links into Kura the notes' (.thing.is-note)."""
import datetime
from urllib.parse import quote

import shell as modern
import re

from links import web_url
from garden import CONFIDENCE, FRONT_RE, STAGES, TYPES, relative, stage_of
from vaultkit import _str
from shell import COLUMN_TITLES, e

STAGE_NAME = {k: n for k, n, _ in STAGES}


def top(ctx, base, current, title="", search=True, q=""):
    return modern.header(current, title, search, ctx, q)


def gpage(ctx, base, title, body, current, head=""):
    return modern.page(ctx, title, body, current, head)


def glink(base, n):
    """A link to a note in the garden, in the garden's colour."""
    return '<a class="thing is-garden" href="%s/n/%s">%s</a>' % (base, quote(n.slug), e(n.title))


def stage_badge(stage, confidence=""):
    out = '<span class="stage stage-%s">%s</span>' % (stage, STAGE_NAME[stage])
    if confidence:
        out += ' <span class="conf conf-%s" title="confidence">%s</span>' % (confidence, e(confidence))
    return out


def note_row(ctx, base, g, n, cards, when=""):
    card = cards.get(n.rel)
    col = ('<span class="col-badge col-%s">%s</span>' % (card["board"], e(COLUMN_TITLES.get(card["board"], "")))
           if card and card["board"] else "")
    tended = g.tended.get(n.rel, "")
    label = when or (("tended " + relative(tended)) if tended else "")
    return ('<li><a class="ntl" href="%s/n/%s">%s</a> %s%s%s%s</li>'
            % (base, quote(n.slug), e(n.title), col, stage_badge(n.stage, n.confidence),
               (' <span class="tended">%s</span>' % e(label)) if label else "",
               ('<p class="summary">%s</p>' % e(n.description)) if n.description else ""))


def empty(title, line):
    """An empty state in Shiori's style: a Title Case heading and one line."""
    return '<div class="empty"><h2>%s</h2><p>%s</p></div>' % (title, line)


def section(title, cls, inner):
    return '<section class="gsec"><h3 class="sechead %s">%s</h3>%s</section>' % (cls, title, inner)


def stage_groups(ctx, base, g, notes, cards):
    parts = []
    for key, name, color in STAGES:
        group = sorted((n for n in notes if n.stage == key), key=lambda n: n.title.lower())
        if group:
            parts.append(section('%s <span class="colcount">%d</span>' % (name, len(group)), "stage-" + key,
                                 '<ul class="garden-list">%s</ul>' % "".join(note_row(ctx, base, g, n, cards) for n in group)))
    return "".join(parts)


from garden import DEFAULT_INTRO, INTRO  # noqa: E402,F401  (the landing intro; gemini and gopher use the same)


def home(ctx, base, g, cards, ntype=""):
    notes = g.published()
    parts = [top(ctx, base, "garden"), '<main class="garden landing">']
    intro = g.intro(base)
    if intro:
        parts.append('<div class="intro nbody is-garden">%s</div>' % intro)
    else:
        hint = "" if modern.public(ctx) else ' <span class="hint">(Publish <code>Garden.md</code> to write your own intro.)</span>'
        parts.append('<p class="intro none">%s%s</p>' % (e(INTRO), hint))
    if not notes:
        parts.append(empty("Nothing Published Yet", "Nothing is in the garden yet." if modern.public(ctx) else
                           'Pick notes to publish from the <a href="%s/queue">Queue</a>.' % base))
        parts.append("</main>")
        return gpage(ctx, base, "", "\n".join(parts), "garden")
    st = g.stats()
    chips = ['<a href="%s/"%s>all</a>' % (base, ' class="here"' if not ntype else "")]
    chips += ['<a href="%s/?type=%s"%s>%s <span class="n">%d</span></a>' % (base, k, ' class="here"' if ntype == k else "", label.lower(), st["types"][k])
              for k, label in TYPES if st["types"].get(k)]
    parts.append('<p class="gstats"><b>%d notes</b> &middot; <span class="stage-evergreen">%d evergreen</span> &middot; '
                 '<span class="stage-budding">%d budding</span> &middot; <span class="stage-seedling">%d seedlings</span> &middot; '
                 '<a href="%s/random">random note</a></p><p class="typechips">%s</p>'
                 % (st["total"], st["evergreen"], st["budding"], st["seedling"], base, "".join(chips)))
    if ntype:
        shown = [n for n in notes if n.ntype == ntype]
        label = dict(TYPES).get(ntype, ntype)
        parts.append(stage_groups(ctx, base, g, shown, cards) or empty(
            "No Published %s" % e(label), 'Nothing of this type is in the garden yet. <a href="%s/">Show All</a>' % base))
        parts.append("</main>")
        return gpage(ctx, base, label, "\n".join(parts), "garden")
    maps = g.maps()
    if maps:
        tiles = "".join('<a class="maptile" href="%s/n/%s"><b>%s</b><span class="count">%d note%s</span>%s</a>'
                        % (base, quote(n.slug), e(n.title), c, "" if c == 1 else "s",
                           ('<p>%s</p>' % e(n.description)) if n.description else "") for n, c in maps)
        parts.append(section("Topic maps", "", '<div class="maps">%s</div>' % tiles))
    pinned = g.pinned()
    if pinned:
        parts.append(section("Start here", "", '<ul class="garden-list">%s</ul>' % "".join(note_row(ctx, base, g, n, cards) for n in pinned)))
    recent = g.recent(8)
    if recent:
        parts.append(section("Recently tended", "", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s %s <span class="tended">%s</span></li>'
            % (glink(base, n), stage_badge(n.stage), e(relative(g.tended.get(n.rel, "")))) for n in recent)))
    bloom = [n for n in notes if n.ntype == "project" and cards.get(n.rel) and cards[n.rel]["board"]]
    if bloom:
        rows = []
        for n in sorted(bloom, key=lambda n: n.title.lower()):
            c = cards[n.rel]
            rows.append('<li><a class="ntl" href="%s/n/%s">%s</a> <span class="col-badge col-%s">%s</span>%s</li>'
                        % (base, quote(n.slug), e(n.title), c["board"], e(COLUMN_TITLES.get(c["board"], "")),
                           ('<p class="next">next: %s</p>' % e(c["next"])) if c.get("next") else ""))
        parts.append(section("Projects in bloom", "", '<ul class="garden-list">%s</ul>' % "".join(rows)))
    seedlings = sorted((n for n in notes if n.stage == "seedling"), key=lambda n: n.title.lower())
    if seedlings:
        parts.append(section("Seedlings", "stage-seedling", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s%s</li>' % (glink(base, n), (' <span class="tended">%s</span>' % e(n.description)) if n.description else "")
            for n in seedlings)))
    needs = [] if modern.public(ctx) else g.needs_tending()       # the owner's to-do list
    if needs:
        parts.append(section("Needs tending", "", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s %s <span class="tended">%s</span></li>' % (glink(base, n), stage_badge(n.stage), e(why))
            for n, why in needs)))
    parts.append(section("Everything", "", stage_groups(ctx, base, g, notes, cards)))
    parts.append("</main>")
    return gpage(ctx, base, "", "\n".join(parts), "garden")


def meta_form(base, n, g):
    growth = _str(n.fm.get("growth")).lower()
    opts = '<option value=""%s>auto (%s)</option>' % ("" if growth else " selected", stage_of({k: v for k, v in n.fm.items() if k != "growth"}))
    opts += "".join('<option value="%s"%s>%s</option>' % (k, " selected" if growth == k else "", name) for k, name, _ in STAGES[::-1])
    conf = '<option value="">none</option>' + "".join('<option value="%s"%s>%s</option>' % (c, " selected" if n.confidence == c else "", c) for c in CONFIDENCE)
    return ('<form class="metaform" method="post" action="%s/meta"><input type="hidden" name="rel" value="%s">'
            '<label>Stage <select name="growth">%s</select></label><label>Confidence <select name="confidence">%s</select></label>'
            '<label class="check"><input type="checkbox" name="garden_pin" value="1"%s> start here</label>'
            '<button type="submit" class="quiet">Save</button></form>'
            % (base, e(n.rel), opts, conf, " checked" if n.pinned else ""))


def note(ctx, base, g, n, cards, checks=None):
    card = cards.get(n.rel)
    tags = " ".join('<a class="tag" href="%s/t/%s">%s</a>' % (base, quote(t), e(t)) for t in n.tags
                    if t.startswith(("topic/", "area/")) and t != "area/projects")
    meta = [stage_badge(n.stage, n.confidence), '<span class="ntype">%s</span>' % e(dict(TYPES).get(n.ntype, n.ntype).lower().rstrip("s"))]
    dates = []
    if n.planted:
        dates.append('planted <span title="%s">%s</span>' % (e(n.planted), e(relative(n.planted))))
    if g.tended.get(n.rel):
        dates.append('tended <span title="%s">%s</span>' % (e(g.tended[n.rel]), e(relative(g.tended[n.rel]))))
    if dates:
        meta.append('<span class="tended">%s</span>' % " &middot; ".join(dates))
    if card and card["board"]:
        meta.append('<a class="col-badge col-%s" href="%s">board: %s</a>' % (
            card["board"], ("/p/" if base else modern.BOARD_URL + "/p/") + quote(card["slug"]),
            e(COLUMN_TITLES.get(card["board"], ""))))
    if card and card.get("post_url"):
        meta.append('<a class="postlink" href="%s">blog post</a>' % e(card["post_url"]))
    public = modern.public(ctx)
    if modern.KURA_URL and not public:
        meta.append('<a class="thing is-note" href="%s/n/%s">View in Kura</a>' % (e(modern.KURA_URL), quote(n.slug)))
    if modern.GARDEN_URL and n.published and not public:
        meta.append('<a class="postlink" href="%s/n/%s">public page</a>' % (e(modern.GARDEN_URL), quote(n.slug)))
    held = g.held.get(n.rel)
    if held and checks is None:         # publish: true, held back by the scan: its findings and "Publish anyway"
        checks = [c for c in g.check(n) if c[0] in ("error", "warn")]
    banner = "" if n.published else (
        '<p class="preview"><b>Held back</b>: the scan found errors, so it is not in the garden. Only you can see this page.</p>'
        if held else '<p class="preview"><b>Preview</b>: not published. Only you can see this page.</p>')
    sug = g.suggestions().get(n.rel) if not n.published and not public else None
    if sug:
        banner += '<p class="preview sugg-banner">Suggested%s%s</p>' % (
            (" by <b>%s</b>" % e(sug["who"])) if sug["who"] else "", (": " + e(sug["reason"])) if sug["reason"] else "")
    rel_links = []
    linked = g.linked_from(n)
    if linked:
        rel_links.append(section("Linked from", "", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s</li>' % glink(base, x) for x in linked)))
    near = g.nearby(n)
    if near:
        rel_links.append(section("Nearby", "", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s %s</li>' % (glink(base, x), stage_badge(x.stage)) for x in near)))
    body = g.render(n, base, False).lstrip()
    if g.links:
        body = g.links.annotate(body, private=not public)  # the owner's pages: private copies are fine; never public
    if body.startswith("<h1") and "</h1>" in body:
        cut = body.index("</h1>") + 5
        heading, body = body[:cut], body[cut:]
    else:
        heading = '<h1>%s</h1>' % e(n.title)
    if g.links:
        recs = g.links.for_note(n.rel)
        if recs:
            rows = "".join(
                '<li><span class="chk chk-%s">%s</span> <a href="%s">%s</a>%s</li>' % (
                    {"live": "ok", "dead": "err"}.get(r["status"], "warn"), e(r["status"] or "unchecked"), e(r["url"]),
                    e(r["url"] if len(r["url"]) <= 70 else r["url"][:67] + "\u2026"),
                    ((' <a class="nlink" href="%s" title="archived %s">archived copy</a>' % (e(r["archive_url"]), e(r.get("archived_at") or "")))
                     if web_url(r.get("archive_url")) else "")
                    + ((' <a class="nlink" href="%s" title="%s %s">private copy</a>' % (
                        e(r["private_url"]), "Archived snapshot" if r.get("private_backend") == "cold" else "Hister copy",
                        e(r.get("private_at") or ""))) if web_url(r.get("private_url")) and not public else ""))
                for r in recs if web_url(r["url"]))
            rel_links.append(section("Links", "", '<ul class="garden-list plain linklist">%s</ul>' % rows))
    tend = "" if public else ('<section class="gsec owner"><h3 class="sechead">Tend</h3>%s%s</section>'
                              % (meta_form(base, n, g), publish_form(ctx, base, n, checks, g.hold_digest(n))))
    main = ('<main class="garden"><article class="note">%s<header class="nhead">%s'
            '<p class="nmeta">%s<br>%s</p></header><div class="nbody is-garden">%s</div></article>%s%s</main>'
            % ("" if public else banner, heading, " &middot; ".join(meta), tags, body, "".join(rel_links), tend))
    pin = modern.house.OFFLINE_PIN if n.fm.get("offline") is True else ""       # offline: true -> kept for good
    return gpage(ctx, base, n.title, top(ctx, base, "", n.title) + main, "", pin)


def publish_form(ctx, base, n, checks=None, ack=""):
    """ack: the digest of the scan's errors shown here (garden.hold_digest): "Publish anyway" acknowledges exactly
    those, so a finding added since holds the note back again."""
    warn = ""
    if checks:
        warn = '<ul class="checks">%s</ul>' % "".join('<li class="chk-%s">%s: %s</li>' % (s, s, e(msg)) for s, msg in checks)
    if n.published:
        return ('<form class="pubform" method="post" action="%s/publish"><input type="hidden" name="rel" value="%s">'
                '<input type="hidden" name="on" value="0"><span>In the garden.</span> '
                '<button type="submit" class="quiet">Unpublish</button></form>' % (base, e(n.rel)))
    return ('<form class="pubform" method="post" action="%s/publish"><input type="hidden" name="rel" value="%s">'
            '<input type="hidden" name="on" value="1"><input type="hidden" name="confirm" value="%s">%s%s'
            '<button type="submit">%s</button></form>'
            % (base, e(n.rel), "1" if checks else "",
               ('<input type="hidden" name="ack" value="%s">' % e(ack)) if checks and ack else "", warn,
               "Publish anyway" if checks else "Publish to garden"))


def tag_page(ctx, base, g, tag, cards):
    notes = [n for n in g.published() if tag in n.tags]
    parts = [top(ctx, base, "tags", tag), '<main class="garden">']
    for key, name, color in STAGES:
        group = sorted((n for n in notes if n.stage == key), key=lambda n: n.title.lower())
        if group:
            parts.append(section(name, "stage-" + key, '<ul class="garden-list">%s</ul>'
                                 % "".join(note_row(ctx, base, g, n, cards) for n in group)))
    co = {}
    for n in notes:
        for t in n.tags:
            if t != tag and t.startswith(("topic/", "area/")) and t != "area/projects":
                co[t] = co.get(t, 0) + 1
    if co:
        parts.append('<p class="related">Related tags: %s</p>' % " ".join(
            '<a class="tag" href="%s/t/%s">%s</a>' % (base, quote(t), e(t)) for t, _ in sorted(co.items(), key=lambda kv: -kv[1])[:12]))
    if not notes:
        parts.append(empty("No Published Notes", "Nothing in the garden is tagged <code>%s</code> yet." % e(tag)))
    parts.append("</main>")
    return gpage(ctx, base, tag, "\n".join(parts), "tags")


def tags_page(ctx, base, g):
    items = "".join('<a class="tag" href="%s/t/%s">%s <span class="n">%d</span></a>' % (base, quote(t), e(t), c)
                    for t, c in g.tags())
    return gpage(ctx, base, "Tags", top(ctx, base, "tags") +
                 '<main class="garden">%s</main>' % (('<p class="tagcloud">%s</p>' % items) if items else empty(
                     "No Tags Yet", "Topic and area tags appear here once their notes are published.")), "tags")


def stream(ctx, base, g, d):
    from stream import summary_text
    from shell import ago
    card_url = lambda slug: ("/p/" if base else modern.BOARD_URL + "/p/") + quote(slug)
    roundup_url = lambda date: ("" if base else modern.BOARD_URL) + "/roundup?period=day&date=" + date.isoformat()

    def note_link(x):
        return (' <a class="nlink thing is-garden" href="%s/n/%s">garden</a>' % (base, quote(x["note_slug"]))) if x.get("note_slug") else ""

    def entry(x):
        if x["kind"] == "systems":
            if modern.public(ctx):          # the roundup is on the board: the owner's
                return ""
            n = x["count"]
            return ('<li class="dentry systems"><span class="kind ev-systems">system</span> <b>%s</b>: '
                    '<a href="%s">%d change%s</a></li>' % (e(x["host"]), roundup_url(x["date"]), n, "" if n == 1 else "s"))
        if x["kind"] == "garden":
            title = ('<a class="thing is-garden" href="%s/n/%s">%s</a>' % (base, quote(x["note_slug"]), e(x["title"]))) if x.get("note_slug") else e(x["title"])
            return '<li class="dentry garden"><span class="kind ev-garden">%s</span> %s</li>' % (e(x["event"]), title)
        moves = "".join('<span class="move">%s</span>' % e(m) for m in x["moves"])
        top = "".join("<li>%s</li>" % e(t if len(t) <= 170 else t[:167].rstrip() + "…") for t in x["top"])
        more = (' <span class="more">+%d update%s</span>' % (x["more"], "" if x["more"] == 1 else "s")) if x["more"] else ""
        nxt = ('<p class="next">next: %s</p>' % e(x["next"] if len(x["next"]) <= 140 else x["next"][:137] + "…")) \
            if x["next"] and x["board"] in ("ready", "wip", "blocked") else ""
        title = ('<a class="ntl thing is-card" href="%s">%s</a>' % (card_url(x["slug"]), e(x["title"]))) if x["has_card"] else '<b class="ntl">%s</b>' % e(x["title"])
        return ('<li class="dentry project%s"><div class="dhead">%s %s%s%s</div>%s%s</li>'
                % (" done" if x["done"] else "", title, moves, more, note_link(x),
                   ('<ul class="top">%s</ul>' % top) if top else "", nxt))

    parts = [top(ctx, base, "stream"), '<main class="garden stream">',
             '<p class="none">The last %d days by project, %d entries.</p>'
             % (d["days"], d["entries"])]
    now = d["now"]
    if now and (now["wip"] or now["blocked"]):
        rows = []
        for c in now["wip"]:
            rows.append('<li><a class="ntl thing is-card" href="%s">%s</a> <span class="col-badge col-wip">WIP</span>%s%s%s%s</li>' % (
                card_url(c["slug"]), e(c["title"]),
                (' <span class="claim">%s</span>' % e(c["claim"])) if c["claim"] else "",
                (' <span class="when">%s</span>' % e(ago(c["updated"]))) if c["updated"] else "",
                (' <a class="nlink thing is-garden" href="%s/n/%s">garden</a>' % (base, quote(c["note_slug"]))) if c["note_slug"] else "",
                ('<p class="next">next: %s</p>' % e(c["next"])) if c["next"] else ""))
        for c in now["blocked"]:
            rows.append('<li><a class="ntl thing is-card" href="%s">%s</a> <span class="col-badge col-blocked">Blocked</span>%s%s</li>' % (
                card_url(c["slug"]), e(c["title"]),
                (' <a class="nlink thing is-garden" href="%s/n/%s">garden</a>' % (base, quote(c["note_slug"]))) if c["note_slug"] else "",
                ('<p class="blocked">blocked: %s</p>' % e(c["blocked_by"])) if c["blocked_by"] else ""))
        parts.append('<section class="gsec now"><h3 class="sechead">Now</h3><ul class="digest nowlist-s">%s</ul></section>' % "".join(rows))
    def reading_line(w):
        r = w.get("reading")
        if not r:
            return ""
        top = ", ".join("%s %d" % (e(k), n) for k, n in r["top"])
        return ('<p class="reading"><span class="kind ev-reading">read</span> <a href="%s">%d page%s saved</a>%s</p>'
                % (e(r["search"]), r["total"], "" if r["total"] == 1 else "s", (": " + top) if top else ""))

    for w in d["weeks"]:
        if w["current"]:
            days = "".join('<h4 class="dayhead">%s</h4><ul class="digest">%s</ul>'
                           % (day["date"].strftime("%a %b %d"), "".join(entry(x) for x in day["entries"])) for day in w["days"])
            parts.append('<section class="gsec week"><h3 class="sechead">%s</h3>%s%s</section>' % (e(w["label"]), reading_line(w), days))
        else:
            parts.append('<section class="gsec week"><details><summary><b>%s</b> <span class="wsum">%s</span></summary>'
                         '%s<ul class="digest">%s</ul></details></section>'
                         % (e(w["label"]), e(summary_text(w["summary"])), reading_line(w), "".join(entry(x) for x in w["entries"])))
    parts.append("</main>")
    return gpage(ctx, base, "Stream", "\n".join(parts), "stream")


def queue(ctx, base, g, cards):
    g.index()
    suggested = g.suggestions()
    linked = g.well_linked()

    def row(n):
        errs, warns = g.check_summary(n)
        if errs:
            chk = '<span class="chk chk-err">%d error%s</span>' % (errs, "" if errs == 1 else "s")
        elif warns:
            chk = '<span class="chk chk-warn">%d warning%s</span>' % (warns, "" if warns == 1 else "s")
        else:
            chk = '<span class="chk chk-ok">clean</span>'
        badge = ""
        sug = suggested.get(n.rel)
        if n.rel in g.held:
            badge = '<span class="sugg">held back: publish anyway to show it</span>'
        elif sug:
            badge = '<span class="sugg">suggested%s%s</span>' % ((" by " + e(sug["who"])) if sug["who"] else "",
                                                                  (": " + e(sug["reason"])) if sug["reason"] else "")
        elif n.rel in linked:
            badge = '<span class="sugg">linked from %d notes</span>' % linked[n.rel]
        forms = ('<form class="qpub" method="post" action="%s/publish"><input type="hidden" name="rel" value="%s">'
                 '<input type="hidden" name="on" value="1"><button type="submit" class="%s">%s</button></form>'
                 % (base, e(n.rel), "quiet" if errs else "", "Review" if errs else "Publish"))
        if sug:
            forms += ('<form class="qpub" method="post" action="%s/dismiss"><input type="hidden" name="rel" value="%s">'
                      '<button type="submit" class="quiet">Dismiss</button></form>' % (base, e(n.rel)))
        return ('<li class="qrow"><div class="qmain"><a class="ntl" href="%s/n/%s">%s</a> %s %s %s%s</div>'
                '<div class="qacts">%s</div></li>'
                % (base, quote(n.slug), e(n.title), stage_badge(n.stage, n.confidence), chk, badge,
                   ('<p class="summary">%s</p>' % e(n.description)) if n.description else "", forms))

    groups = {}
    for n in g.notes.values():
        if n.published or g.is_private(n.rel):
            continue
        if n.rel in g.held:
            groups.setdefault("Held Back", []).append(n)
        elif n.rel in suggested or n.rel in linked:
            groups.setdefault("Suggested", []).append(n)
        elif n.ntype == "map":
            groups.setdefault("Topic maps", []).append(n)
        else:
            groups.setdefault(n.rel.split("/")[0] if "/" in n.rel else "Vault root", []).append(n)
    order = {"Held Back": -1, "Suggested": 0, "Topic maps": 1}
    parts = [top(ctx, base, "queue"), '<main class="garden queue">',
             '<p class="none">Unpublished notes, suggestions first.%s Review shows what the pre-publish check found.</p>' % (
                 " Private notes (%s) are left out." % ", ".join(e(p) for p in g.private) if g.private else "")]
    for folder in sorted(groups, key=lambda k: (order.get(k, 2), k.lower())):
        notes = sorted(groups[folder], key=lambda n: (n.rel not in suggested, n.title.lower()))
        parts.append(section('%s <span class="colcount">%d</span>' % (e(folder), len(notes)), "",
                             '<ul class="garden-list qlist">%s</ul>' % "".join(row(n) for n in notes)))
    if not groups:
        parts.append(empty("Nothing to Publish", "Every note%s is already in the garden." % (
            " outside " + " and ".join(e(p) for p in g.private) if g.private else "")))
    parts.append("</main>")
    return gpage(ctx, base, "Queue", "\n".join(parts), "queue")


def today():
    return datetime.date.today()


# -- search: the room searches its own published notes, then hands off to Shiori -------------------------------------

MARKUP_RE = re.compile(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]|\[([^\]]*)\]\([^)]*\)|[#*_`>|~]+")


def plain(text):
    """A note body as searchable plain text: no frontmatter, [[links]] and [links](…) as their words, no markup."""
    body = FRONT_RE.sub("", text, count=1)
    return " ".join(MARKUP_RE.sub(lambda m: m.group(1) or m.group(2) or " ", body).split())


def find(g, q, limit=100):
    """Published notes matching every word of q, best first: [(note, snippet, marks)]. A word in the title counts
    most, then tags, the summary, the body."""
    terms = [t for t in q.lower().split()][:10]
    if not terms:
        return []
    found = []
    for n in g.published():
        body = plain(n.text)
        fields = ((n.title.lower(), 8), (" ".join(n.tags).lower(), 4), ((n.description or "").lower(), 2),
                  (body.lower(), 1))
        score = 0
        for t in terms:
            hit = sum(w for f, w in fields if t in f)
            if not hit:
                break
            score += hit
        else:
            found.append((score, n, body))
    found.sort(key=lambda x: (-x[0], x[1].title.lower()))
    out = []
    for _, n, body in found[:limit]:
        low = body.lower()
        at = min((low.find(t) for t in terms if t in low), default=-1)
        start = max(0, at - 60) if at >= 0 else 0
        snip = body[start:start + 200]
        snip = ("…" if start else "") + snip + ("…" if start + 200 < len(body) else "")
        marks = []
        for t in terms:
            for m in re.finditer(re.escape(t), snip, re.I):
                marks.append((m.start(), m.end()))
        out.append((n, snip if at >= 0 else (n.description or snip), sorted(set(marks)) if at >= 0 else []))
    return out


def marked(text, marks):
    out, i = [], 0
    for a, b in marks:
        if a < i:
            continue
        out.append(e(text[i:a]) + "<mark>" + e(text[a:b]) + "</mark>")
        i = b
    return "".join(out) + e(text[i:])


def search_page(ctx, base, g, q):
    q = " ".join((q or "").split())[:200]
    parts = [top(ctx, base, "", "Search", q=q), '<main class="garden search">']      # the header's pill is the field
    if not q:
        parts.append(empty("Search the Garden", "Published notes: their titles, tags, summaries and text."))
    else:
        hits = find(g, q)
        if hits:
            parts.append('<p class="none">%d published note%s</p><ul class="garden-list">%s</ul>' % (
                len(hits), "" if len(hits) == 1 else "s", "".join(
                    '<li><a class="ntl" href="%s/n/%s">%s</a> %s<p class="summary">%s</p></li>'
                    % (base, quote(n.slug), e(n.title), stage_badge(n.stage), marked(snip, marks))
                    for n, snip, marks in hits)))
        else:
            parts.append(empty("No Matches", "Nothing in the garden matches “%s”." % e(q)))
        if not modern.public(ctx):      # Shiori is the owner's
            parts.append(modern.house.handoff(q, modern.rooms()))
    parts.append("</main>")
    return gpage(ctx, base, (q + " - " if q else "") + "Search", "\n".join(parts), "")
