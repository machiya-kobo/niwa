# API

[Back to the README](../README.md)

- `POST /api/suggest {"path": "Notes/X.md" | "slug", "reason": "…"}`: an agent suggests a note for the garden (the old Konbini path `/api/garden/suggest` also works). 201, or 409 if it's already published.
- `GET /feed.xml`: RSS 2.0 of the published notes, the 50 most recently tended first (title, link, summary; never an unpublished note, the queue, `Archive/` or a private folder). Behind the same gate as the pages; every page links it in its head and footer.
- `GET /api/suggestions[?days=60]`: the open suggestions, newest first (`days` 1 to 365), as `{"suggestions": [{"path", "reason", "agent", "date"}], "days"}`; same access as the pages.
- `GET /api/changelog`: `app/CHANGELOG.md` as `text/markdown` (ETag, 304; 404 without the file), open like `/api/status`, for the stack's landing page.
- `GET /api/status`: version, vaultkit, head, notes, published, sync, konbini, hister, links, ready, error, auth. Open to anyone for monitoring; only the owner sees the Konbini and Hister addresses and their errors, and credentials in a remote URL are never shown.

The public garden (`NIWA_PUBLIC_PORT`) answers only `GET` and `HEAD` on `/`, `/n/…` (published notes; anything else
is 404), `/t/…`, `/tags`, `/stream`, `/search` (60 a minute per address; behind a proxy every visitor shares the
proxy's), `/random`, `/a/…` (images a published note shows), `/feed.xml`, `/robots.txt` and `/static/…`. Every
other path is 404 and every other method 405. It reads no identity header or cookie and sets none.

With an identity file (`MACHIYA_IDENTITY_FILE`), vaultkit's `signin` adds the first three (without one they answer 404):

- `GET /signin[?next=/path]`, `POST /signin`: the built-in sign-in (`NIWA_SIGNIN=1`, else 404). The post is a same-origin form (`name`, `password`, `next`, at most 4 KB); success is 303 to `next` (a local path only) with the session cookie; a wrong name or password 401, too many tries 429.
- `POST /signout`: same-origin only; clears the session cookie, 303 to `/`.
- `POST /api/pair {"code": "ABCD-EFGH", "device": "iPhone"}`: a Shiori device pairs with a one-time code (`python3 -m vaultkit.identity pair NAME --label iPhone`) and gets `{"token": "mcd_…", "principal"}`, its own token to send as `Authorization: Bearer`. No cookie, so no same-origin rule; 401 for an unknown or expired code, 429 when throttled; at most 1 KB.
- `GET /api/prefs`, `PUT /api/prefs {"prefs": {"key": "value" or null}}`: the caller's own preferences (keys `[a-z0-9_.-]`, string values up to 4 KB, 100 keys; `null` removes one), stored in `prefs.sqlite3` next to `NIWA_DB`. Needs the `niwa` `read` grant. A PUT made with a session cookie, a Tailscale or proxy login must be same-origin; one with a token needn't. Without an identity file it is there too: `NIWA_USERS` (or open mode) decides who gets in, and the preferences are the Tailscale login's (stored under a hash of it) or, with `NIWA_AUTH=open`, the one local owner's. Every page then carries `<meta name="machiya-prefs">`, so theme and text size follow the person to another device.

Publishing, stages and dismissals are same-origin form posts from the owner's pages; agents get 403 and may only
suggest. With an identity file that takes the `niwa` `publish` grant. Agents send their token as
`Authorization: Bearer mch_…`, and `X-Agent` names them in the garden's events.
