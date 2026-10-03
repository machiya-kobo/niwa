"""/feed.xml: RSS 2.0 of the garden's published notes, the most recently tended first (Kura's api.rss, for the garden).

Only published notes: never an unpublished one, the queue, a note under Archive/ or a private folder
(NIWA_PRIVATE_FOLDERS), nor the landing intro (Garden.md). Every title, link and description is escaped; a
description is the note's summary as plain text, never its rendered body.
"""
import datetime
from email.utils import formatdate
from html import escape
from urllib.parse import quote

LIMIT = 50


def notes(garden, never=("Archive/",)):
    """The feed's notes, newest-tended first: [(note, "YYYY-MM-DD" or "")]."""
    shown = [n for n in garden.published() if not n.rel.startswith(tuple(never)) and not garden.is_private(n.rel)]
    shown.sort(key=lambda n: (garden.tended.get(n.rel, ""), n.title.lower()), reverse=True)
    return [(n, garden.tended.get(n.rel, "")) for n in shown[:LIMIT]]


def pub_date(day):
    """"2026-09-01" -> an RFC 822 date (midnight UTC); "" when unreadable."""
    try:
        d = datetime.date.fromisoformat(day)
    except (TypeError, ValueError):
        return ""
    return formatdate(datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc).timestamp(), usegmt=True)


def rss(base, title, description, items):
    """base: Niwa's public origin (no trailing slash); items: notes()."""
    out = []
    for n, day in items:
        link = "%s/n/%s" % (base, quote(n.slug))
        when = pub_date(day)
        out.append("<item><title>%s</title><link>%s</link><guid isPermaLink=\"true\">%s</guid>%s<description>%s"
                   "</description></item>" % (escape(n.title), escape(link), escape(link),
                                              ("<pubDate>%s</pubDate>" % when) if when else "",
                                              escape(n.description or "")))
    return ('<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0"><channel><title>%s</title><link>%s/</link>'
            "<description>%s</description><language>en</language>%s</channel></rss>\n"
            % (escape(title), escape(base), escape(description), "".join(out)))
