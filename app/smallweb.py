"""Gemini and gopher mirrors of the garden (published notes only).

The same notes as the web garden, converted from Obsidian Markdown:
  gemini: gemtext (headings, `*` lists, `>` quotes, ``` blocks, and `=>` link
          lines after each paragraph for wikilinks, links and images)
  gopher: menus (type 1) for the index, tags and stream; notes as plain text
          (type 0) wrapped at 70 columns with a numbered link list; images as
          type I

Servers:
  gemini  :1965  TLS with a self-signed cert next to NIWA_DB (TOFU, as usual for Gemini)
  gopher  :7070  menus point at NIWA_HOST on port 70 (map 70 to 7070 in front of Niwa)
Who can reach them is the network's business (a tailnet ACL, a firewall): Niwa serves only published notes there.
"""
import os
import re
import socketserver
import ssl
import subprocess
import textwrap
import threading
from urllib.parse import quote, unquote

import garden as garden_module
from capped import Capped
from vaultkit import websafe
from garden import CALLOUT_RE, EMBED_RE, FRONT_RE, IMAGE_EXT, LINK_RE, MDIMG_RE, STAGES

# Gopher text is ASCII/ISO-8859-1; replace what it can't carry with ASCII.
TRANSLIT = {
    "—": "--", "–": "-", "→": "->", "←": "<-", "…": "...",
    "‘": "'", "’": "'", "“": '"', "”": '"', "•": "*",
    "✅": "[x]", "⚠": "[!]", "️": "", "✓": "v", "·": "-",
}


CONTROL_RE = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]+")


def clean(text):
    """One line of plain text for a gemini link or heading and a gopher menu row: every control character (CR, LF, tab,
    NEL, the Unicode line separators) becomes a space, so a title or a tag from a note or a URL can't start a new line,
    a fake menu item or a fake link."""
    return CONTROL_RE.sub(" ", str(text))


def translit(text):
    for k, v in TRANSLIT.items():
        text = text.replace(k, v)
    return text



MDLINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
EMPH_RE = re.compile(r"(\*\*|__)(.+?)\1|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
IMAGE_MIME = websafe.ASSET_TYPES      # the images a gemini or gopher client is given (the same list the web serves)


# -- conversion ---------------------------------------------------------------

def to_gemtext(garden, note):
    """Obsidian Markdown -> gemtext; links become `=>` lines after the block."""
    body = FRONT_RE.sub("", note.text, count=1)
    out, pending, in_code, table = [], [], False, []

    def flush_links():
        for target, label in pending:
            out.append("=> %s %s" % (target, label))
        pending.clear()

    def inline(text):
        def embed(m):
            name = m.group(1).strip()
            if name.lower().endswith(IMAGE_EXT):
                path = garden.assets.get(os.path.basename(name))
                if path:
                    pending.append(("/a/" + quote(path), "image: " + name))
                return "[image: %s]" % name
            return link_text(name, None, None)

        def link_text(target, _anchor, alias):
            rel = garden.resolve(target)
            n = garden.notes.get(rel) if rel else None
            label = alias or target.split("/")[-1]
            if n and n.published:
                pending.append(("/n/" + quote(n.slug), n.title))
            return label

        text = EMBED_RE.sub(embed, text)
        text = MDIMG_RE.sub(lambda m: "[image: %s]" % (m.group(1) or os.path.basename(m.group(2))), text)
        text = LINK_RE.sub(lambda m: link_text(m.group(1), m.group(2), m.group(3)), text)

        def mdlink(m):
            pending.append((m.group(2), m.group(1)))
            return m.group(1)

        text = MDLINK_RE.sub(mdlink, text)
        text = EMPH_RE.sub(lambda m: m.group(2) or m.group(3) or "", text)
        return text

    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if table:
                out.extend(["```"] + table + ["```"])
                table = []
            out.append("```")
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        if line.startswith("|"):
            if not re.match(r"^\|[\s:|-]+\|?$", line):
                table.append(inline(line))
            continue
        if table:
            out.extend(["```"] + table + ["```"])
            table = []
            flush_links()
        if not line.strip():
            flush_links()
            out.append("")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush_links()
            out.append("#" * min(len(m.group(1)), 3) + " " + inline(m.group(2)))
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            continue
        c = CALLOUT_RE.match(line)
        if c:
            out.append("> %s: %s" % (c.group(1).title(), inline(c.group(2))))
            continue
        m = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?(.*)", line)
        if m:
            box = m.group(1)
            out.append("* " + ("[x] " if box and "x" in box.lower() else "[ ] " if box else "") + inline(m.group(2)))
            continue
        if line.startswith(">"):
            out.append("> " + inline(line.lstrip("> ")))
            continue
        out.append(inline(line.strip()))
    if table:
        out.extend(["```"] + table + ["```"])
    flush_links()
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def to_gopher_text(gemtext, host, port):
    """gemtext -> plain text at 70 columns with numbered references."""
    lines, refs = [], []
    in_code = False
    for line in gemtext.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            lines.append(line[:79])
            continue
        if line.startswith("=> "):
            parts = line[3:].split(" ", 1)
            target, label = parts[0], parts[1] if len(parts) > 1 else parts[0]
            refs.append((label, target))
            lines.append("  [%d] %s" % (len(refs), label))
            continue
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            lines.extend(["", title.upper() if line.startswith("# ") else title,
                          ("=" if line.startswith("# ") else "-") * min(len(title), 70)])
            continue
        prefix = "  * " if line.startswith("* ") else "  | " if line.startswith("> ") else ""
        text = line[2:] if prefix else line
        wrapped = textwrap.wrap(text, 70 - len(prefix)) or [""]
        lines.append(prefix + wrapped[0])
        lines.extend(" " * len(prefix) + w for w in wrapped[1:])
    if refs:
        lines += ["", "REFERENCES", "----------"]
        for i, (label, target) in enumerate(refs, 1):
            where = target if re.match(r"\w+://", target) else "gopher://%s:%s/%s%s" % (
                host, port, "I" if target.startswith("/a/") else "0", unquote(target))
            lines.append("[%d] %s" % (i, label))
            lines.append("    %s" % where)
    return "\n".join(lines).strip("\n") + "\n"


# -- page builders shared by both protocols ------------------------------------

def intro_gemtext(garden):
    """The landing intro, as the web shows it: a published Garden.md (as gemtext), else NIWA_INTRO."""
    n = garden.notes.get("Garden.md")
    if n and n.published:
        return to_gemtext(garden, n).strip()
    return garden_module.INTRO


def intro_rows(garden):
    """The intro for a gopher menu: info lines wrapped at 70 columns (its links stay on the gemini and web pages)."""
    rows = []
    for line in intro_gemtext(garden).splitlines():
        if line.startswith("=>") or line.startswith("```"):
            continue
        line = line.lstrip("#> ").strip() if line.startswith(("#", ">")) else line
        rows += [("i", w, "") for w in textwrap.wrap(line, 70)] or [("i", "", "")]
    return rows


def index_items(garden):
    """(heading, [(path, label)]) groups for the garden index."""
    notes = garden.published()
    groups = []
    maps = garden.maps()
    if maps:
        groups.append(("Maps", [("/n/" + n.slug, "%s (%d notes)" % (clean(n.title), c)) for n, c in maps]))
    for key, name, _ in STAGES:
        group = sorted((n for n in notes if n.stage == key), key=lambda n: n.title.lower())
        if group:
            groups.append((name, [("/n/" + n.slug, clean(n.title)) for n in group]))
    return groups


def tag_items(garden, tag):
    return sorted((("/n/" + n.slug, clean(n.title)) for n in garden.published() if tag in n.tags),
                  key=lambda t: t[1].lower())


def stream_lines(garden, timeline):
    """The stream digest as (text, note_slug) lines: a heading is ("# ...", None)
    or ("## ...", None); an entry carries the slug of its published note. This is the public stream: garden
    events about published notes only, never the board's cards (stream.build public=True)."""
    import stream as digest
    d = digest.build(garden, links=getattr(garden, "links", None), public=True)
    out = [("%d entries from the last %d days." % (d["entries"], d["days"]), None)]

    def entry(x):
        return ("* %s: %s" % (clean(x["event"]), clean(x["title"])), x.get("note_slug") or None)

    for w in d["weeks"]:
        out.append(("## " + w["label"], None))
        if w["current"]:
            for day in w["days"]:
                out.append(("### " + day["date"].strftime("%a %b %d"), None))
                out += [entry(x) for x in day["entries"]]
        else:
            out.append((digest.summary_text(w["summary"]), None))
            out += [entry(x) for x in w["entries"]]
    return out


# -- gemini -------------------------------------------------------------------

class GeminiHandler(socketserver.StreamRequestHandler):
    garden = timeline = None
    timeout = 30        # a client that stops sending lets its thread go

    def handle(self):
        try:
            self.request.do_handshake()     # here, in the connection's thread: TLSServer.get_request doesn't wait for it
            url = self.rfile.readline(1100).decode("utf-8", "replace").strip()
        except (OSError, ssl.SSLError):
            return
        m = re.match(r"^gemini://[^/]*(/[^?\s]*)?", url)
        if not m:
            return self.reply("59 bad request")
        path = unquote(m.group(1) or "/")
        g = self.garden
        g.index()
        if path == "/":
            lines = ["# Niwa", "", intro_gemtext(g), ""]
            for heading, items in index_items(g):
                lines += ["## " + heading] + ["=> %s %s" % (quote(p), t) for p, t in items] + [""]
            if not g.published():
                lines.append("Nothing is published yet.")
            lines += ["=> /tags Tags", "=> /stream Stream (last 30 days)"]
            return self.reply("20 text/gemini; charset=utf-8", "\n".join(lines) + "\n")
        if path.startswith("/n/"):
            n = g.get(path[3:])
            if not n or not n.published:
                return self.reply("51 not found")
            head = "# %s\n\n%s · tended %s\n" % (clean(n.title), n.stage, g.tended.get(n.rel, "?"))
            body = to_gemtext(g, n)
            if body.startswith("# "):
                head = ""
            tags = "\n".join("=> /t/%s %s" % (quote(t), clean(t)) for t in n.tags
                             if t.startswith(("topic/", "area/")) and t != "area/projects")
            back = "\n".join("=> /n/%s %s" % (quote(x.slug), clean(x.title)) for x in g.linked_from(n))
            text = head + "\n" + body + ("\n## Tags\n" + tags if tags else "") + ("\n\n## Linked from\n" + back if back else "")
            return self.reply("20 text/gemini; charset=utf-8", text + "\n\n=> / garden\n")
        if path == "/tags":
            lines = ["# Tags", ""] + ["=> /t/%s %s (%d)" % (quote(t), clean(t), c) for t, c in g.tags()]
            return self.reply("20 text/gemini; charset=utf-8", "\n".join(lines) + "\n\n=> / garden\n")
        if path.startswith("/t/"):
            tag = path[3:]
            lines = ["# " + clean(tag), ""] + ["=> %s %s" % (quote(p), t) for p, t in tag_items(g, tag)]
            return self.reply("20 text/gemini; charset=utf-8", "\n".join(lines) + "\n\n=> / garden\n")
        if path == "/stream":
            lines = ["# Stream", ""]
            for text, slug in stream_lines(g, self.timeline):
                if text.startswith("#"):
                    lines += ["", text]
                elif slug:
                    lines.append("=> /n/%s %s" % (quote(slug), text[2:] if text.startswith("* ") else text))
                else:
                    lines.append(text)
            return self.reply("20 text/gemini; charset=utf-8", "\n".join(lines) + "\n\n=> / garden\n")
        if path.startswith("/a/"):
            full = g.public_asset_path(path[3:])
            mime = IMAGE_MIME.get(os.path.splitext(path)[1].lower())
            if full and mime:
                with open(full, "rb") as f:
                    return self.reply("20 " + mime, f.read())
        return self.reply("51 not found")

    def reply(self, header, body=b""):
        data = body.encode("utf-8") if isinstance(body, str) else body
        try:
            self.wfile.write(header.encode() + b"\r\n" + data)
        except (OSError, ssl.SSLError):
            pass


class TLSServer(Capped, socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    max_connections = 32

    def __init__(self, addr, handler, context):
        super().__init__(addr, handler)
        self.context = context

    def get_request(self):
        sock, addr = super().get_request()
        sock.settimeout(30)
        # No handshake on the accept thread: a client that connects and says nothing would hold up every other one.
        return self.context.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), addr


def ensure_cert(data_dir, hostname):
    crt, key = os.path.join(data_dir, "gemini.crt"), os.path.join(data_dir, "gemini.key")
    if not (os.path.exists(crt) and os.path.exists(key)):
        cmd = ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
               "-nodes", "-days", "3650", "-subj", "/CN=" + hostname,
               "-addext", "subjectAltName=DNS:%s,DNS:%s" % (hostname, hostname.split(".")[0]),
               "-keyout", key, "-out", crt]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Some systems (a clean NetBSD) have no openssl.cnf, and `req` refuses to run without one. Every option the
            # certificate needs is on the command line, so an empty configuration does.
            subprocess.run(cmd, check=True, capture_output=True, env=dict(os.environ, OPENSSL_CONF="/dev/null"))
        os.chmod(key, 0o600)
    return crt, key


def serve_gemini(garden, timeline, port, data_dir, hostname, bind=""):
    crt, key = ensure_cert(data_dir, hostname)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(crt, key)
    GeminiHandler.garden, GeminiHandler.timeline = garden, timeline
    TLSServer((bind, port), GeminiHandler, ctx).serve_forever()


# -- gopher -------------------------------------------------------------------

def gopher_handler(garden, timeline, host, port, allow=None):
    class Handler(socketserver.StreamRequestHandler):
        timeout = 30    # a client that stops sending lets its thread go

        def handle(self):
            if allow is not None and self.client_address[0] not in allow:
                return self.send(menu([("3", "forbidden", "")]))
            try:
                selector = self.rfile.readline(1100).decode("latin-1").strip().split("\t")[0]
            except OSError:
                return
            garden.index()
            sel = selector if selector.startswith("/") or not selector else "/" + selector
            if sel in ("", "/"):
                rows = [("i", "NIWA", ""), ("i", "", "")] + intro_rows(garden) + [("i", "", "")]
                for heading, items in index_items(garden):
                    rows.append(("i", heading.upper(), ""))
                    rows += [("0", t, p) for p, t in items]
                    rows.append(("i", "", ""))
                if not garden.published():
                    rows.append(("i", "Nothing is published yet.", ""))
                rows += [("1", "Tags", "/tags"), ("1", "Stream (last 30 days)", "/stream")]
                return self.send(menu(rows))
            if sel.startswith("/n/"):
                n = garden.get(sel[3:])
                if not n or not n.published:
                    return self.send(menu([("3", "not found", "")]))
                title = clean(n.title)
                text = "%s\n%s\n%s - tended %s\n\n" % (title.upper(), "=" * min(len(title), 70), n.stage,
                                                     garden.tended.get(n.rel, "?"))
                return self.send(text + to_gopher_text(to_gemtext(garden, n), host, port), text_mode=True)
            if sel == "/tags":
                return self.send(menu([("1", "%s (%d)" % (t, c), "/t/" + t) for t, c in garden.tags()]))
            if sel.startswith("/t/"):
                return self.send(menu([("i", sel[3:].upper(), "")] + [("0", t, p) for p, t in tag_items(garden, sel[3:])]))
            if sel == "/stream":
                rows = []
                for text, slug in stream_lines(garden, timeline):
                    if text.startswith("#"):
                        rows += [("i", "", ""), ("i", text.lstrip("# ").upper()[:70], "")]
                    elif slug:
                        rows.append(("0", (text[2:] if text.startswith("* ") else text)[:70], "/n/" + slug))
                    else:
                        rows.append(("i", text[:70], ""))
                return self.send(menu(rows))
            if sel.startswith("/a/"):
                full = garden.public_asset_path(sel[3:])
                if full:
                    with open(full, "rb") as f:
                        return self.send(f.read(), binary=True)
            return self.send(menu([("3", "not found", "")]))

        def send(self, payload, text_mode=False, binary=False):
            try:
                if binary:
                    self.wfile.write(payload)
                else:
                    text = payload.replace("\r\n", "\n").replace("\n", "\r\n")
                    if text_mode:
                        text = "\r\n".join(("." + l) if l.startswith(".") else l for l in text.split("\r\n"))
                        text += ".\r\n"
                    self.wfile.write(translit(text).encode("latin-1", "replace"))
            except OSError:
                pass

    def menu(rows):
        out = []
        for kind, label, sel in rows:
            label, sel = clean(label), clean(sel)       # no tab, CR or LF can start another menu row
            if kind in ("i", "3"):
                out.append("%s%s\tfake\t(NULL)\t0" % (kind, label))
            else:
                out.append("%s%s\t%s\t%s\t%s" % (kind, label, sel, host, port))
        return "\n".join(out) + "\n.\n"

    return Handler


class GopherServer(Capped, socketserver.ThreadingTCPServer):
    allow_reuse_address = True      # a restart within a minute of the last connection must still bind (TIME_WAIT)
    daemon_threads = True
    max_connections = 32


def serve_gopher(garden, timeline, bind_port, host, port, allow=None, bind=""):
    server = GopherServer((bind, bind_port), gopher_handler(garden, timeline, host, port, allow))
    server.serve_forever()


def start(garden, timeline, data_dir, host, bind="", gopher_public_port=70):
    """bind: the address both listeners use (niwa.py passes NIWA_BIND, the web listener's too). gopher_public_port is the
    port the gopher menus advertise (the listener itself is 7070)."""
    for target, args in ((serve_gemini, (garden, timeline, 1965, data_dir, host, bind)),
                         (serve_gopher, (garden, timeline, 7070, host, gopher_public_port, None, bind))):
        threading.Thread(target=target, args=args, daemon=True).start()
