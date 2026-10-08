// Niwa's script for the garden pages, loaded after the shared machiya.js (settings, the Rooms menu). A module, so
// old browsers never run it; the pages and forms work without it. It holds only what Niwa uses: the
// service worker and offline banner, the installed app's back button, wikilink previews and Mermaid diagrams.
document.body.classList.add("js");

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const main = $("main");

function stored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch (e) { return fallback; }
}
function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function banner(cls, html) {
  const el = document.createElement("div");
  el.className = "banner " + cls;
  el.innerHTML = html;
  (main || document.body).prepend(el);
  return el;
}

// -- PWA: service worker, offline copy, install hint ----------------------
// the public garden (NIWA_PUBLIC_PORT) is a plain website: no service worker, no install hint
const isPublic = !!document.querySelector('meta[name="niwa-public"]');
if ("serviceWorker" in navigator && !isPublic) {
  navigator.serviceWorker.register("/sw.js").catch(() => { /* http on the LAN, or blocked */ });
}
if (document.body.dataset.offline !== undefined) {
  const at = Date.parse(document.body.dataset.offline || "");
  let when = "";
  if (!isNaN(at)) {
    const mins = Math.max(1, Math.round((Date.now() - at) / 60000));
    when = mins < 60 ? mins + " min ago" : mins < 1440 ? Math.round(mins / 60) + " h ago" : Math.round(mins / 1440) + " d ago";
  }
  banner("offline", "<span><b>Offline.</b> Niwa can't be reached right now; this is a saved copy" + (when ? " from " + when : "") + ".</span>");
}
const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
const standalone = navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;
// Installed apps have no browser chrome: give inner pages a back control.
const roots = ["/", "/stream", "/tags", "/queue"];
if (standalone && history.length > 1 && !roots.includes(location.pathname)) {
  const back = document.createElement("button");
  back.className = "back";
  back.type = "button";
  back.setAttribute("aria-label", "Back");
  back.textContent = "\u2039";
  back.addEventListener("click", () => history.back());
  $(".topbar")?.prepend(back);
}
if (ios && !standalone && !isPublic && !stored("app.hint", false)) {
  const el = banner("hint", "<span>Install this as an app: tap <b>Share</b>, then <b>Add to Home Screen</b>.</span>"
    + '<button type="button" aria-label="Dismiss">&times;</button>');
  $("button", el).addEventListener("click", () => { store("app.hint", true); el.remove(); });
}

// -- hover previews for wikilinks (pointer devices only; Settings > Garden > Link Previews) --
if (matchMedia("(hover: hover)").matches) {
  let pop, timer, hovered = null;
  let previews = stored("niwaSettings", {}).linkPreviews !== false;
  const hide = () => { clearTimeout(timer); if (pop) pop.hidden = true; };
  document.addEventListener("machiya:setting", (ev) => {
    if (ev.detail.key === "linkPreviews") { previews = ev.detail.value !== false; if (!previews) hide(); }
  });
  // delegated, so the live search results (machiya.js swaps <main> as you type) get previews too
  const links = "a.wikilink, .maps a.maptile, ul.garden-list a.ntl, ul.garden-list a.is-garden, ul.cards a.title[href*='/n/']";
  document.addEventListener("mouseover", (ev) => {
    const a = ev.target.closest?.(links);
    if (!a || a === hovered) return;
    hovered = a;
    if (!previews) return;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const r = await fetch(a.href + (a.href.includes("?") ? "&" : "?") + "preview=1", { headers: { Accept: "application/json" } });
        if (!r.ok || hovered !== a) return;
        const p = await r.json();
        if (!pop) { pop = document.createElement("div"); pop.className = "popover"; document.body.append(pop); }
        pop.innerHTML = "<b>" + esc(p.title) + "</b> <span class='chip stage stage-" + esc(p.stage) + "'>" + esc(p.stage_name || p.stage) + "</span>"
          + (p.description ? "<p>" + esc(p.description) + "</p>" : "")
          + (p.tended ? "<span class='when'>tended " + esc(p.tended) + "</span>" : "");
        const box = a.getBoundingClientRect();
        pop.style.left = Math.max(8, Math.min(box.left + scrollX, innerWidth - 340)) + "px";
        pop.style.top = (box.bottom + scrollY + 6) + "px";
        pop.hidden = false;
      } catch (e) { /* no preview */ }
    }, 250);
  });
  document.addEventListener("mouseout", (ev) => {
    const a = ev.target.closest?.(links);
    if (a && a === hovered && !a.contains(ev.relatedTarget)) { hovered = null; hide(); }
  });
  document.addEventListener("scroll", hide, { passive: true });
}

// Mermaid diagrams in notes (Niwa; Obsidian's ```mermaid blocks, which python-markdown renders as
// <pre><code class="language-mermaid">). The vendored library (static/mermaid.min.js, ~5.5 MB, MIT) is fetched only
// on a page that has a diagram, and cached for a year (bump MERMAID_V with the file). Colours follow the page theme
// (Tokyo Night / Day). securityLevel "strict": no scripts or click handlers from note text. A diagram that fails to
// render keeps its source visible.
const MERMAID_V = "12.0.0";
let mermaidN = 0, mermaidLoad = null;
function mermaidDiagrams(root = document) {
  const blocks = [...root.querySelectorAll("pre > code.language-mermaid")];
  if (!blocks.length) return;
  const body = document.body.classList;
  const dark = body.contains("theme-night") ||
    (!body.contains("theme-day") && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const vars = dark
    ? {background: "#1a1b26", primaryColor: "#24283b", primaryTextColor: "#c0caf5", primaryBorderColor: "#7aa2f7",
       secondaryColor: "#1f2335", tertiaryColor: "#16161e", lineColor: "#7aa2f7", textColor: "#c0caf5",
       clusterBkg: "#1f2335", clusterBorder: "#3b4261", edgeLabelBackground: "#1f2335", noteBkgColor: "#292e42",
       noteTextColor: "#c0caf5", actorBkg: "#24283b", actorBorder: "#7aa2f7", actorTextColor: "#c0caf5",
       signalColor: "#c0caf5", signalTextColor: "#c0caf5"}
    : {background: "#e1e2e7", primaryColor: "#e9e9ed", primaryTextColor: "#343b58", primaryBorderColor: "#155fc5",
       secondaryColor: "#d5d8e4", tertiaryColor: "#eef0f5", lineColor: "#155fc5", textColor: "#343b58",
       clusterBkg: "#eef0f5", clusterBorder: "#c4c8da", edgeLabelBackground: "#eef0f5", noteBkgColor: "#d5d8e4",
       noteTextColor: "#343b58", actorBkg: "#e9e9ed", actorBorder: "#155fc5", actorTextColor: "#343b58",
       signalColor: "#343b58", signalTextColor: "#343b58"};
  mermaidLoad = mermaidLoad || new Promise((ok) => {      // the library loads once per page
    const s = document.createElement("script");
    s.src = "/static/mermaid.min.js?v=" + MERMAID_V;
    s.onload = () => {
      window.mermaid.initialize({startOnLoad: false, securityLevel: "strict", theme: "base", themeVariables: vars,
                                 fontFamily: "inherit", flowchart: {htmlLabels: true, useMaxWidth: true}});
      ok(window.mermaid);
    };
    document.head.appendChild(s);
  });
  mermaidLoad.then(async (mm) => {
    for (const code of blocks) {
      const n = ++mermaidN;
      const pre = code.parentElement;
      try {
        const {svg} = await mm.render("mmd-" + n, code.textContent);
        const div = document.createElement("div");
        div.className = "mermaid-diagram";
        div.innerHTML = svg;
        pre.replaceWith(div);
      } catch (err) {
        pre.title = "Mermaid couldn't render this diagram: " + (err && err.message || err);
        document.querySelectorAll("#dmmd-" + n).forEach((x) => x.remove());   // mermaid's error box
      }
    }
  });
}
mermaidDiagrams();
