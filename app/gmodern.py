"""The garden's HTML5 pages, in Machiya's shared shell (shell.py). `base` is the path prefix the pages are mounted
under ("" when Niwa serves them at its root).
Links to garden notes wear the garden's colour (.thing.is-garden), links into Kura the notes' (.thing.is-note)."""
import datetime
from urllib.parse import quote

import shell as modern
import re

from links import web_url
import garden as garden_mod
from garden import FRONT_RE, STAGES, TYPES, relative, stage_of
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


def stage_badge(stage):
    return '<span class="chip stage stage-%s">%s</span>' % (stage, STAGE_NAME[stage])


def note_row(ctx, base, g, n, cards, when=""):
    card = cards.get(n.rel)
    col = ('<span class="chip col-%s">%s</span>' % (card["board"], e(COLUMN_TITLES.get(card["board"], "")))
           if card and card["board"] else "")
    tended = g.tended.get(n.rel, "")
    label = when or (("tended " + relative(tended)) if tended else "")
    return ('<li class="card"><a class="title" href="%s/n/%s">%s</a>%s<div class="meta">%s%s%s</div></li>'
            % (base, quote(n.slug), e(n.title),
               ('<p class="snippet">%s</p>' % e(n.description)) if n.description else "", col, stage_badge(n.stage),
               ('<span class="tended">%s</span>' % e(label)) if label else ""))


def empty(title, line):
    """An empty state in Shiori's style: a Title Case heading and one line."""
    return '<div class="empty"><h2>%s</h2><p>%s</p></div>' % (title, line)


def section(title, cls, inner, sid=""):
    return '<section class="gsec"%s><h3 class="sechead %s">%s</h3>%s</section>' % (' id="%s"' % sid if sid else "", cls, title, inner)


from garden import DEFAULT_INTRO, INTRO  # noqa: E402,F401  (the landing intro; gemini and gopher use the same)


def home(ctx, base, g, cards, ntype="", here="/"):
    """The garden's home as visitors see it: the public garden's /, and the owner's /visit (`here`, where the type
    pills point), under a line that says so."""
    notes = g.published()
    parts = [top(ctx, base, "garden"), '<main class="garden landing">']
    if here != "/":
        parts.append('<p class="preview visiting"><b>Visitor View</b>: the garden\'s home as visitors see it. '
                     '<a href="%s/">Back to the Desk</a></p>' % base)
    intro = g.intro(base)
    if intro:
        parts.append('<div class="intro nbody is-garden">%s</div>' % intro)
    else:
        hint = "" if modern.public(ctx) else ' <span class="hint">(Publish <code>Garden.md</code> to write your own intro.)</span>'
        parts.append('<p class="intro none">%s%s</p>' % (e(INTRO), hint))
    if not notes:
        parts.append(empty("Nothing Published Yet", "Nothing is in the garden yet." if modern.public(ctx) else
                           'Pick notes to publish on the <a href="%s/">Desk</a>.' % base))
        parts.append("</main>")
        return gpage(ctx, base, "", "\n".join(parts), "garden")
    st = g.stats()
    pills = ['<a class="pill" href="%s%s"%s>All <span class="count">%d</span></a>' % (
        base, here, ' aria-current="page"' if not ntype else "", st["total"])]
    pills += ['<a class="pill" href="%s%s?type=%s"%s>%s <span class="count">%d</span></a>' % (
        base, here, k, ' aria-current="page"' if ntype == k else "", label, st["types"][k])
        for k, label in TYPES if st["types"].get(k)]
    parts.append('<p class="gstats"><b>%d notes</b> &middot; <span class="stage-evergreen">%d evergreen</span> &middot; '
                 '<span class="stage-budding">%d budding</span> &middot; <span class="stage-seedling">%d seedlings</span> &middot; '
                 '<a href="%s/random">random note</a></p><nav class="pills" aria-label="Note types">%s</nav>'
                 % (st["total"], st["evergreen"], st["budding"], st["seedling"], base, "".join(pills)))
    shown = [n for n in notes if n.ntype == ntype] if ntype else notes
    label = dict(TYPES).get(ntype, ntype) if ntype else ""
    if ntype:
        if not shown:
            parts.append(empty("No Published %s" % e(label), 'Nothing of this type is in the garden yet. <a href="%s%s">Show All</a>' % (base, here)))
            parts.append("</main>")
            return gpage(ctx, base, label, "\n".join(parts), "garden")
    else:
        maps = g.maps()
        if maps:
            tiles = "".join('<a class="card maptile" href="%s/n/%s"><span class="title">%s</span>%s<div class="meta">%d note%s</div></a>'
                            % (base, quote(n.slug), e(n.title),
                               ('<p class="snippet">%s</p>' % e(n.description)) if n.description else "", c, "" if c == 1 else "s")
                            for n, c in maps)
            parts.append(section("Topic Maps", "", '<div class="maps">%s</div>' % tiles))
    # every note once, the most recently tended first (it carries its own stage badge)
    shown = sorted(shown, key=lambda n: n.title.lower())
    shown.sort(key=lambda n: g.tended.get(n.rel, ""), reverse=True)
    parts.append(section('Notes <span class="chip">%d</span>' % len(shown), "",
                         '<ul class="cards">%s</ul>' % "".join(note_row(ctx, base, g, n, cards) for n in shown)))
    parts.append("</main>")
    return gpage(ctx, base, label, "\n".join(parts), "garden")


def meta_form(base, n, g):
    growth = _str(n.fm.get("growth")).lower()
    opts = '<option value=""%s>auto (%s)</option>' % ("" if growth else " selected", stage_of({k: v for k, v in n.fm.items() if k != "growth"}))
    opts += "".join('<option value="%s"%s>%s</option>' % (k, " selected" if growth == k else "", name) for k, name, _ in STAGES[::-1])
    return ('<form class="metaform" method="post" action="%s/meta"><input type="hidden" name="rel" value="%s">'
            '<label>Stage <select name="growth">%s</select></label>'
            '<button type="submit" class="quiet">Save</button></form>' % (base, e(n.rel), opts))


def note(ctx, base, g, n, cards, checks=None):
    card = cards.get(n.rel)
    tags = " ".join('<a class="tag" href="%s/t/%s">%s</a>' % (base, quote(t), e(t)) for t in n.tags
                    if t.startswith(("topic/", "area/")) and t != "area/projects")
    meta = [stage_badge(n.stage), '<span class="ntype">%s</span>' % e(dict(TYPES).get(n.ntype, n.ntype).lower().rstrip("s"))]
    dates = []
    if n.planted:
        dates.append('planted <span title="%s">%s</span>' % (e(n.planted), e(relative(n.planted))))
    if g.tended.get(n.rel):
        dates.append('tended <span title="%s">%s</span>' % (e(g.tended[n.rel]), e(relative(g.tended[n.rel]))))
    if dates:
        meta.append('<span class="tended">%s</span>' % " &middot; ".join(dates))
    if card and card["board"]:
        meta.append('<a class="chip link col-%s" href="%s">Board: %s</a>' % (
            card["board"], ("/p/" if base else modern.BOARD_URL + "/p/") + quote(card["slug"]),
            e(COLUMN_TITLES.get(card["board"], ""))))
    if card and card.get("post_url"):
        meta.append('<a class="chip link" href="%s">Blog Post</a>' % e(card["post_url"]))
    public = modern.public(ctx)
    if not public:
        meta.append(words_badge(g, n))
    if modern.KURA_URL and not public:
        meta.append('<a class="chip link is-note" href="%s/n/%s">View in Kura</a>' % (e(modern.KURA_URL), quote(n.slug)))
    if modern.GARDEN_URL and n.published and not public:
        meta.append('<a class="chip link is-garden" href="%s/n/%s">Public Page</a>' % (e(modern.GARDEN_URL), quote(n.slug)))
    held = g.held.get(n.rel)
    hits = []
    if not public and not n.published and checks is None:       # a note not in the garden: what publishing would accept
        found = g.check(n)
        if any(sev in ("error", "warn") for sev, _ in found):
            checks = found
    if checks and not public:
        hits = g.scan_hits(n)
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
        rel_links.append(section("Linked From", "", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s</li>' % glink(base, x) for x in linked)))
    near = g.nearby(n)
    if near:
        rel_links.append(section("Nearby", "", '<ul class="garden-list plain">%s</ul>' % "".join(
            '<li>%s %s</li>' % (glink(base, x), stage_badge(x.stage)) for x in near)))
    body = g.render(n, base, False, remote_images="click").lstrip()     # a remote image loads on a click
    if g.links:
        body = g.links.annotate(body, private=not public)  # the owner's pages: private copies are fine; never public
    if hits:
        body = highlight(body, hits)
    if body.startswith("<h1") and "</h1>" in body:
        cut = body.index("</h1>") + 5
        heading, body = body[:cut], body[cut:]
    else:
        heading = '<h1>%s</h1>' % e(n.title)
    if g.links:
        recs = g.links.for_note(n.rel)
        if recs:
            rows = "".join(
                '<li><span class="chip chk-%s">%s</span> <a href="%s">%s</a>%s</li>' % (
                    {"live": "ok", "dead": "err"}.get(r["status"], "warn"), e((r["status"] or "unchecked").capitalize()), e(r["url"]),
                    e(r["url"] if len(r["url"]) <= 70 else r["url"][:67] + "\u2026"),
                    ((' <a class="chip link" href="%s" title="archived %s">Archived Copy</a>' % (e(r["archive_url"]), e(r.get("archived_at") or "")))
                     if web_url(r.get("archive_url")) else "")
                    + ((' <a class="chip link" href="%s" title="%s %s">Private Copy</a>' % (
                        e(r["private_url"]), "Archived snapshot" if r.get("private_backend") == "cold" else "Hister copy",
                        e(r.get("private_at") or ""))) if web_url(r.get("private_url")) and not public else ""))
                for r in recs if web_url(r["url"]))
            rel_links.append(section("Links", "", '<ul class="garden-list plain linklist">%s</ul>' % rows))
    tend = "" if public else ('<section class="gsec owner" id="tend"><h3 class="sechead">Tend</h3>%s%s</section>'
                              % (meta_form(base, n, g), publish_form(ctx, base, n, checks, g.hold_digest(n), hits)))
    main = ('<main class="garden"><article class="note">%s<header class="nhead">%s'
            '<p class="nmeta">%s<br>%s</p></header><div class="nbody is-garden">%s</div></article>%s%s</main>'
            % ("" if public else banner, heading, " &middot; ".join(meta), tags, body, "".join(rel_links), tend))
    pin = modern.house.OFFLINE_PIN if n.fm.get("offline") is True else ""       # offline: true -> kept for good
    return gpage(ctx, base, n.title, top(ctx, base, "", n.title) + main, "", pin)


def highlight(html, hits):
    """Mark each scan finding's text in a rendered note, outside the tags: <mark class="found found-error">."""
    sev = {}
    for severity, _, texts in hits:
        for t in texts:
            if sev.get(t) != "error":
                sev[t] = severity
    if not sev:
        return html
    rx = re.compile("|".join(re.escape(e(t)) for t in sorted(sev, key=len, reverse=True)))
    sev = {e(t): v for t, v in sev.items()}
    mark = lambda m: '<mark class="found found-%s">%s</mark>' % (sev.get(m.group(0), "warn"), m.group(0))
    return "".join(part if part.startswith("<") else rx.sub(mark, part) for part in re.split(r"(<[^>]*>)", html))


def publish_label(checks):
    """What the Publish button accepts: 'Publish with 1 error and 1 warning'."""
    errs = sum(1 for s, _ in checks if s == "error")
    warns = sum(1 for s, _ in checks if s == "warn")
    said = ["%d %s%s" % (n, word, "" if n == 1 else "s") for n, word in ((errs, "error"), (warns, "warning")) if n]
    return "Publish with " + " and ".join(said) if said else "Publish to garden"


def words_label(g, n):
    """'1,196 words', or for a note that publishes an excerpt 'excerpt, 240 of 3,100 words'."""
    words, whole = g.word_count(n), g.full_words.get(n.rel)
    return ("excerpt, %s of %s words" % (format(words, ","), format(whole, ","))) if whole else "%s words" % format(words, ",")


def words_badge(g, n):
    long = garden_mod.LONG_WORDS and g.word_count(n) > garden_mod.LONG_WORDS
    return '<span class="words%s">%s</span>' % (" long" if long else "", e(words_label(g, n)))


def publish_form(ctx, base, n, checks=None, ack="", hits=()):
    """ack: the digest of the scan's errors shown here (garden.hold_digest): the button acknowledges exactly
    those, so a finding added since holds the note back again. hits: garden.scan_hits(), shown in full."""
    warn = ""
    if checks:
        scan = {label for _, label, _ in hits}
        rows = ['<li class="chk-%s"><b>%s</b>: %s: %s</li>' % (
            sev, sev, e(label), ", ".join('<mark class="found found-%s">%s</mark>' % (sev, e(t)) for t in texts))
            for sev, label, texts in hits]
        rows += ['<li class="chk-%s"><b>%s</b>: %s</li>' % (sev, sev, e(msg)) for sev, msg in checks
                 if not any(msg.startswith(label) for label in scan)]
        warn = '<ul class="checks">%s</ul>' % "".join(rows)
    if n.published:
        return ('<form class="pubform" method="post" action="%s/publish"><input type="hidden" name="rel" value="%s">'
                '<input type="hidden" name="on" value="0"><span>In the garden.</span> '
                '<button type="submit" class="quiet">Unpublish</button></form>' % (base, e(n.rel)))
    pending = [c for c in (checks or ()) if c[0] in ("error", "warn")]
    return ('<form class="pubform" method="post" action="%s/publish"><input type="hidden" name="rel" value="%s">'
            '<input type="hidden" name="on" value="1"><input type="hidden" name="confirm" value="%s">%s%s'
            '<button type="submit">%s</button></form>'
            % (base, e(n.rel), "1" if pending else "",
               ('<input type="hidden" name="ack" value="%s">' % e(ack)) if pending and ack else "", warn,
               publish_label(pending)))


def tag_page(ctx, base, g, tag, cards):
    notes = [n for n in g.published() if tag in n.tags]
    parts = [top(ctx, base, "tags", tag), '<main class="garden">']
    for key, name, color in STAGES:
        group = sorted((n for n in notes if n.stage == key), key=lambda n: n.title.lower())
        if group:
            parts.append(section(name, "stage-" + key, '<ul class="cards">%s</ul>'
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

    # Konbini's rows are another room's things in a mixed list: tinted (the style guide's rule 3); the public garden is plain
    tinted = "" if modern.public(ctx) else " card tinted is-card"
    kind = "" if modern.public(ctx) else '<span class="kind">Card \u00b7 Konbini</span>'
    digest_cls = "" if modern.public(ctx) else " cards"        # a list with cards in it
    week_label = lambda w: e(w["label"].replace("This week", "This Week"))

    def note_link(x):
        return (' <a class="chip link is-garden" href="%s/n/%s">Garden</a>' % (base, quote(x["note_slug"]))) if x.get("note_slug") else ""

    def entry(x):
        if x["kind"] == "systems":
            if modern.public(ctx):          # the roundup is on the board: the owner's
                return ""
            n = x["count"]
            return ('<li class="dentry systems"><span class="ev ev-systems">system</span> <b>%s</b>: '
                    '<a href="%s">%d change%s</a></li>' % (e(x["host"]), roundup_url(x["date"]), n, "" if n == 1 else "s"))
        if x["kind"] == "garden":
            title = ('<a class="thing is-garden" href="%s/n/%s">%s</a>' % (base, quote(x["note_slug"]), e(x["title"]))) if x.get("note_slug") else e(x["title"])
            return '<li class="dentry garden"><span class="ev ev-garden">%s</span> %s%s</li>' % (
                e(x["event"]), title, (' <span class="utext">%s</span>' % e(x["text"])) if x.get("text") else "")
        moves = "".join('<span class="chip">%s</span>' % e(m) for m in x["moves"])
        top = "".join("<li>%s</li>" % e(t if len(t) <= 170 else t[:167].rstrip() + "…") for t in x["top"])
        more = (' <span class="more">+%d update%s</span>' % (x["more"], "" if x["more"] == 1 else "s")) if x["more"] else ""
        nxt = ('<p class="next">next: %s</p>' % e(x["next"] if len(x["next"]) <= 140 else x["next"][:137] + "…")) \
            if x["next"] and x["board"] in ("ready", "wip", "blocked") else ""
        if tinted:          # the owner's: Konbini's card, as Shiori's result card (kind, title, what happened, meta)
            title = ('<a class="title thing is-card" href="%s">%s</a>' % (card_url(x["slug"]), e(x["title"]))) if x["has_card"] \
                else '<b class="title">%s</b>' % e(x["title"])
            return ('<li class="dentry project%s%s">%s%s%s%s<div class="meta">%s%s%s</div></li>'
                    % (" done" if x["done"] else "", tinted, kind, title, ('<ul class="top">%s</ul>' % top) if top else "", nxt,
                       moves, more, note_link(x)))
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
            rows.append('<li class="%s">%s<a class="title thing is-card" href="%s">%s</a>%s<div class="meta"><span class="chip col-wip">WIP</span>%s%s%s</div></li>' % (
                tinted.strip(), kind, card_url(c["slug"]), e(c["title"]),
                ('<p class="next">next: %s</p>' % e(c["next"])) if c["next"] else "",
                ('<span class="chip claim">%s</span>' % e(c["claim"])) if c["claim"] else "",
                ('<span class="when">%s</span>' % e(ago(c["updated"]))) if c["updated"] else "",
                ('<a class="chip link is-garden" href="%s/n/%s">Garden</a>' % (base, quote(c["note_slug"]))) if c["note_slug"] else ""))
        for c in now["blocked"]:
            rows.append('<li class="%s">%s<a class="title thing is-card" href="%s">%s</a>%s<div class="meta"><span class="chip col-blocked">Blocked</span>%s</div></li>' % (
                tinted.strip(), kind, card_url(c["slug"]), e(c["title"]),
                ('<p class="blocked">blocked: %s</p>' % e(c["blocked_by"])) if c["blocked_by"] else "",
                ('<a class="chip link is-garden" href="%s/n/%s">Garden</a>' % (base, quote(c["note_slug"]))) if c["note_slug"] else ""))
        parts.append('<section class="gsec now"><h3 class="sechead">Now</h3><ul class="digest nowlist-s%s">%s</ul></section>' % (digest_cls, "".join(rows)))
    def reading_line(w):
        r = w.get("reading")
        if not r:
            return ""
        top = ", ".join("%s %d" % (e(k), n) for k, n in r["top"])
        return ('<p class="reading"><span class="ev ev-reading">read</span> <a href="%s">%d page%s saved</a>%s</p>'
                % (e(r["search"]), r["total"], "" if r["total"] == 1 else "s", (": " + top) if top else ""))

    for w in d["weeks"]:
        if w["current"]:
            days = "".join('<h4 class="dayhead">%s</h4><ul class="digest%s">%s</ul>'
                           % (day["date"].strftime("%a %b %d"), digest_cls, "".join(entry(x) for x in day["entries"])) for day in w["days"])
            parts.append('<section class="gsec week"><h3 class="sechead">%s</h3>%s%s</section>' % (week_label(w), reading_line(w), days))
        else:
            parts.append('<section class="gsec week"><details><summary><b>%s</b> <span class="wsum">%s</span></summary>'
                         '%s<ul class="digest%s">%s</ul></details></section>'
                         % (week_label(w), e(summary_text(w["summary"])), reading_line(w), digest_cls, "".join(entry(x) for x in w["entries"])))
    parts.append("</main>")
    return gpage(ctx, base, "Stream", "\n".join(parts), "stream")


def queue_row(base, g, n, suggested, linked):
    """A note waiting to be published, as the Queue and the desk list it: its scan result, why it is listed, and Publish
    (or Review, when the scan found errors) and Dismiss for a suggestion."""
    errs, warns = g.check_summary(n)
    if errs:
        chk = '<span class="chip chk-err">%d Error%s</span>' % (errs, "" if errs == 1 else "s")
    elif warns:
        chk = '<span class="chip chk-warn">%d Warning%s</span>' % (warns, "" if warns == 1 else "s")
    else:
        chk = '<span class="chip chk-ok">Clean</span>'
    badge = ""
    sug = suggested.get(n.rel)
    if n.rel in g.held:
        badge = '<span class="chip sugg">Held Back by the Scan</span>'
    elif sug:
        badge = '<span class="chip sugg">Suggested%s</span>%s' % (
            (" by " + e(sug["who"])) if sug["who"] else "", (' <span class="reason">%s</span>' % e(sug["reason"])) if sug["reason"] else "")
    elif n.rel in linked:
        badge = '<span class="chip sugg">Linked from %d Notes</span>' % linked[n.rel]
    if errs:        # findings: the note's own page shows them in full and holds the button that accepts them
        forms = '<a class="button" href="%s/n/%s">Review</a>' % (base, quote(n.slug))
    else:
        forms = ('<form class="qpub" method="post" action="%s/publish"><input type="hidden" name="rel" value="%s">'
                 '<input type="hidden" name="on" value="1"><button type="submit">Publish</button></form>'
                 % (base, e(n.rel)))
    if sug:
        forms += ('<form class="qpub" method="post" action="%s/dismiss"><input type="hidden" name="rel" value="%s">'
                  '<button type="submit" class="quiet">Dismiss</button></form>' % (base, e(n.rel)))
    return ('<li class="card qrow"><div class="qmain"><a class="title" href="%s/n/%s">%s</a>%s'
            '<div class="meta">%s%s%s%s</div></div><div class="qacts">%s</div></li>'
            % (base, quote(n.slug), e(n.title), ('<p class="snippet">%s</p>' % e(n.description)) if n.description else "",
               stage_badge(n.stage), chk, words_badge(g, n), badge, forms))


def queue_groups(g, suggested, linked):
    """The Queue's unpublished notes by group: Held Back, Suggested, Topic Maps, then each top-level folder."""
    scope = g.queue_folders      # NIWA_QUEUE_FOLDERS: only these folders, plus held notes and what agents suggested
    groups = {}
    for n in g.notes.values():
        if n.published or g.is_private(n.rel):
            continue
        if scope and not (n.rel.startswith(scope) or n.rel in g.held or n.rel in suggested):
            continue
        if n.rel in g.held:
            groups.setdefault("Held Back", []).append(n)
        elif n.rel in suggested or n.rel in linked and (not scope or n.rel.startswith(scope)):
            groups.setdefault("Suggested", []).append(n)
        elif n.ntype == "map":
            groups.setdefault("Topic Maps", []).append(n)
        else:
            groups.setdefault(n.rel.split("/")[0] if "/" in n.rel else "Vault Root", []).append(n)
    return groups


def queue(ctx, base, g, cards):
    g.index()
    suggested = g.suggestions()
    linked = g.well_linked()
    row = lambda n: queue_row(base, g, n, suggested, linked)
    scope = g.queue_folders
    groups = queue_groups(g, suggested, linked)
    order = {"Held Back": -1, "Suggested": 0, "Topic Maps": 1}
    parts = [top(ctx, base, "garden", "Queue"), '<main class="garden queue">',
             '<p class="none">%s, suggestions first.%s Review shows what the pre-publish check found.</p>' % (
                 ("Unpublished notes in %s" % ", ".join(e(p) for p in scope)) if scope else "Unpublished notes",
                 " Private notes (%s) are left out." % ", ".join(e(p) for p in g.private) if g.private else "")]
    for folder in sorted(groups, key=lambda k: (order.get(k, 2), k.lower())):
        notes = sorted(groups[folder], key=lambda n: (n.rel not in suggested, n.title.lower()))
        parts.append(section('%s <span class="chip">%d</span>' % (e(folder), len(notes)), "",
                             '<ul class="cards qlist">%s</ul>' % "".join(row(n) for n in notes)))
    if not groups:
        parts.append(empty("Nothing to Publish", "Every note%s%s is already in the garden." % (
            (" in " + " and ".join(e(p) for p in scope)) if scope else "",
            (" outside " + " and ".join(e(p) for p in g.private)) if g.private else "")))
    parts.append("</main>")
    return gpage(ctx, base, "Queue", "\n".join(parts), "garden")      # the desk's full list: the Garden tab's


# -- the desk: the owner's home, for planting and tending the garden and readying it for the public ------------------

UNTENDED_DAYS = 60      # a seedling not tended for this long asks for care on the desk
PLANT_ROWS = 5          # the desk lists this many notes to plant, then links the Queue
TEND_ROWS = 8           # and this many to tend, then folds the rest away


def to_plant(g, suggested, linked):
    """The Queue's notes in the desk's order: suggested (newest first), then the most linked-to, then the most recently
    tended. A held-back note is tended, not planted."""
    notes = [n for group, ns in queue_groups(g, suggested, linked).items() if group != "Held Back" for n in ns]
    notes.sort(key=lambda n: n.title.lower())
    notes.sort(key=lambda n: g.tended.get(n.rel, ""), reverse=True)
    notes.sort(key=lambda n: -linked.get(n.rel, 0))
    notes.sort(key=lambda n: suggested[n.rel]["date"] if n.rel in suggested else "", reverse=True)
    return notes


def care(g, n, day=None):
    """Why a note in the garden (or held back from it) asks for care: [(severity, what)], the worst first; [] when it
    needs none. Errors the owner published anyway don't count; a missing summary is the mildest."""
    out = []
    if n.rel in g.held:
        k = len(g.held[n.rel])
        out.append(("error", "held back: %d finding%s" % (k, "" if k == 1 else "s")))
    for sev, msg in g.check(n):
        if sev == "warn":
            out.append(("warn", words_label(g, n) if msg.startswith("long:") else msg.split(": ", 1)[0]))
    tended = g.tended.get(n.rel, "")
    if n.stage == "seedling" and tended:
        try:
            idle = ((day or today()) - datetime.date.fromisoformat(tended[:10])).days
        except ValueError:
            idle = 0
        if idle >= UNTENDED_DAYS:
            out.append(("info", "untended %d days" % idle))
    if not _str(n.fm.get("summary")):
        out.append(("info", "no summary"))
    return out


def to_tend(g, day=None):
    """[(note, care)] for the notes in the garden and the held-back ones that ask for care: held back first, then the
    most warnings, then the rest by title."""
    notes = g.published() + [g.notes[rel] for rel in g.held if rel in g.notes]
    found = [(n, care(g, n, day)) for n in notes]
    found = sorted(((n, why) for n, why in found if why), key=lambda t: t[0].title.lower())
    rank = {"error": 0, "warn": 1, "info": 2}
    return sorted(found, key=lambda t: (rank[t[1][0][0]], -len(t[1])))


def tend_row(base, n, why):
    chips = "".join('<span class="chip chk-%s">%s</span>' % ({"error": "err"}.get(sev, sev), e(what)) for sev, what in why)
    return ('<li class="card qrow"><div class="qmain"><a class="title" href="%s/n/%s">%s</a>'
            '<div class="meta">%s%s</div></div><div class="qacts"><a class="button" href="%s/n/%s#tend">%s</a></div></li>'
            % (base, quote(n.slug), e(n.title), stage_badge(n.stage), chips, base, quote(n.slug),
               "Review" if why[0][0] == "error" else "Tend"))


def intro_published(g):
    n = g.notes.get("Garden.md")
    return bool(n and n.published)


def readiness(g, tend):
    """The checklist before the garden goes public: [(done, what, how)], what visitors would meet first."""
    notes = g.published()
    held = sum(1 for n, why in tend if why[0][0] == "error")
    warned = sum(1 for n, why in tend if any(sev == "warn" for sev, _ in why))
    bare = sum(1 for n in notes if not _str(n.fm.get("summary")))
    plural = lambda k, one, many: "%d %s" % (k, one if k == 1 else many)
    return [
        (bool(notes), "Notes in the garden", "Publish a first note from Plant."),
        (not held, "Nothing held back by the scan", "%s held back: review the findings, then fix or accept them."
         % plural(held, "note is", "notes are")),
        (not warned, "No warnings on published notes", "%s warnings: dead links, links to private notes, an address, "
         "a long text." % plural(warned, "note has", "notes have")),
        (not bare, "A summary on every published note",
         "%s none: lists and the feed show the first paragraph instead." % plural(bare, "note has", "notes have")),
        (bool(g.maps()), "A topic map to start from", "Publish a map note (type/map) that links your notes."),
        (intro_published(g), "An intro of your own", "Publish <code>Garden.md</code>: visitors read it first."),
    ]


def desk(ctx, base, g, cards, day=None):
    """The owner's home: the garden at a glance, the notes to plant (the Queue's first few), the notes to tend, and
    what is left before the garden goes public, beside them on a wide screen. The garden as visitors see it is /visit."""
    g.index()
    suggested, linked = g.suggestions(), g.well_linked()
    st = g.stats()
    plant, tend = to_plant(g, suggested, linked), to_tend(g, day)
    checks = readiness(g, tend)
    ready = sum(ok for ok, _, _ in checks)

    grown = [(k, st[k]) for k, _, _ in STAGES[::-1] if st[k]]      # seedlings first, as a note grows
    said = ", ".join("%d %s" % (c, k + "s" if k == "seedling" and c != 1 else k) for k, c in grown)
    bar = ('<div class="stagebar" role="img" aria-label="%s">%s</div>' % (e(said), "".join(
        '<span class="seg stage-%s" style="flex-grow:%d"></span>' % (k, c) for k, c in grown))) if grown else ""
    stat = lambda href, n, what: '<a class="card stat" href="%s"><b class="n">%s</b><span>%s</span></a>' % (href, n, what)
    tiles = ('<div class="card stat garden-stat"><b class="n">%d</b><span>in the garden</span>%s'
             '<small>%s<a href="%s/visit">Visitor View</a></small></div>'
             % (st["total"], bar, (e(said) + " &middot; ") if said else "", base)
             + stat("#plant", len(plant), "to plant") + stat("#tend", len(tend), "to tend")
             + stat("#ready", "%d of %d" % (ready, len(checks)), "ready to go public"))

    more = ('<a class="seclink" href="%s/queue">All %d in the Queue</a>' % (base, len(plant))) if len(plant) > PLANT_ROWS else ""
    planting = section('Plant <span class="chip">%d</span>%s' % (len(plant), more), "",
                       ('<ul class="cards qlist">%s</ul>' % "".join(queue_row(base, g, n, suggested, linked) for n in plant[:PLANT_ROWS]))
                       if plant else '<p class="none">Nothing waiting: every note the Queue would list is in the garden.</p>', "plant")
    rows = [tend_row(base, n, why) for n, why in tend]
    inner = ('<ul class="cards qlist">%s</ul>' % "".join(rows[:TEND_ROWS])) if rows else '<p class="none">Nothing needs care.</p>'
    if len(rows) > TEND_ROWS:
        inner += '<details class="more-rows"><summary>%d more</summary><ul class="cards qlist">%s</ul></details>' % (
            len(rows) - TEND_ROWS, "".join(rows[TEND_ROWS:]))
    tending = section('Tend <span class="chip">%d</span>' % len(rows), "", inner, "tend")

    items = "".join('<li class="%s"><span class="mark" role="img" aria-label="%s">%s</span><span><b>%s</b>%s</span></li>'
                    % ("done" if ok else "todo", "Done" if ok else "To do", "\u2713" if ok else "\u25cb", what,
                       "" if ok else '<span class="how">%s</span>' % how) for ok, what, how in checks)
    state = ('The public garden is on at <a href="%s/">%s</a>.' % (e(modern.GARDEN_URL), e(modern.GARDEN_URL))
             if modern.GARDEN_URL else
             'The public garden is off. It turns on with <code>NIWA_PUBLIC_PORT</code> and <code>NIWA_GARDEN_URL</code>.')
    public = ('<aside class="gsec ready" id="ready"><h3 class="sechead">Ready to Go Public <span class="chip">%d of %d</span></h3>'
              '<div class="card"><ul class="checklist">%s</ul><p class="pubstate">%s</p>'
              '<a class="button" href="%s/visit">Visitor View</a></div></aside>' % (ready, len(checks), items, state, base))
    body = ('<main class="garden desk"><div class="deskstats">%s</div><div class="deskcols"><div class="deskwork">%s%s</div>%s</div></main>'
            % (tiles, planting, tending, public))
    return gpage(ctx, base, "", top(ctx, base, "garden") + body, "garden")


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
            parts.append('<p class="none">%d published note%s</p><ul class="cards">%s</ul>' % (
                len(hits), "" if len(hits) == 1 else "s", "".join(
                    '<li class="card"><a class="title" href="%s/n/%s">%s</a><p class="snippet">%s</p><div class="meta">%s</div></li>'
                    % (base, quote(n.slug), e(n.title), marked(snip, marks), stage_badge(n.stage))
                    for n, snip, marks in hits)))
        else:
            parts.append(empty("No Matches", "Nothing in the garden matches “%s”." % e(q)))
        if not modern.public(ctx):      # Shiori is the owner's
            parts.append(modern.house.handoff(q, modern.rooms()))
    parts.append("</main>")
    return gpage(ctx, base, (q + " - " if q else "") + "Search", "\n".join(parts), "")
