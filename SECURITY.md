# Security

## Reporting a vulnerability

Please report security problems privately, not in a public issue: use GitHub's private vulnerability reporting (this
repository's Security tab, then Report a vulnerability), with what you found, how to reproduce it, and what it
affects. You'll get an answer within a week, and a fix or a plan before anything is disclosed.

## What's in scope

- **The owner gate:** a way for an agent or a cross-site request to publish, unpublish, stage, pin or dismiss a note.
  Only the owner's same-origin form posts may; agents may only suggest. With Machiya's identity file
  (`MACHIYA_IDENTITY_FILE`) the power is the `niwa` `publish` grant: a principal without it doing any of these by
  any header (`Origin`, `X-Agent` or its absence), a request with an invalid token or session being served as
  someone else instead of 401, a principal reading or suggesting without `read` or `suggest`, or a header mode
  starting on a public bind without `NIWA_BIND_BEHIND_PROXY` is in scope.
- **Sign-in, pairing and preferences** (with an identity file): a cross-site request signing someone in or out or
  writing their preferences with a cookie or login; `next` sending a browser to another site; a sign-in accepted
  over plain http without `NIWA_PUBLIC_URL` as its origin; a password, a hash or a session or device token reaching
  a page, a log line or a JSON answer (other than the one token `/api/pair` hands out); one principal reading or
  writing another's preferences; any of these routes answering without an identity file.
- **Tokens:** Niwa's Konbini token (`NIWA_KONBINI_TOKEN_FILE`), the owner's Hister token (`NIWA_HISTER_TOKEN_FILE`) or a
  caller's token reaching a log line, a page, `/api/status`, the `hister` command line, or any host but the one it is for.
- **Hister sign-in** (`NIWA_AUTH=hister`): a Hister account outside `NIWA_HISTER_USERS` getting in, a signed-out caller
  getting the Tailscale fallback, `return=` sending a browser to another site, or the mode starting on a public bind
  without `NIWA_BIND_BEHIND_PROXY`.
- **Reading what isn't published:** an unpublished note, its title or its text, or an image only unpublished notes
  show, reaching the website, the public garden, Gemini or Gopher; a note under a `NIWA_PRIVATE_FOLDERS` folder being
  published; or a note with an unacknowledged scan error (see below) being served anywhere.
- **The public garden** (`NIWA_PUBLIC_PORT`): it is meant to face the internet, so anything on it beyond the published
  notes, their tags, the images they show, the public stream and the feed is in scope: a route outside its allow-list
  answering, a method other than GET or HEAD doing anything, a cookie read or set, an identity header
  (`Tailscale-User-Login`, a proxy's login header, `Authorization`) changing what it serves, a form or a link to a
  write, an absolute URL built from the request's `Host` instead of `NIWA_GARDEN_URL`, or anything from Konbini, Kura,
  Hister, the queue, Settings, the status line or `MACHIYA_ROOMS` appearing on it. Its `/search` is limited per
  address; serving it without TLS is a configuration choice, not a vulnerability.
- **Logins:** the owner's `Tailscale-User-Login` reaching gemini, gopher or the open `/api/status`.
- **The small-web stream:** the gemini and gopher `/stream` pages carry garden events about published notes only. A
  board card, a `next:` step, a blocked-by text, or the title of an unpublished note appearing there is in scope.
- **Private copies:** Hister results, copies or `private_url` reaching Gemini, Gopher, the public garden or any page
  an anonymous visitor can open.
- **Writes:** anything that edits more than the garden's frontmatter fields, or a note body.
- **Script injection** from note text, titles, link labels or archived-copy URLs, and requests to hosts the
  configuration doesn't name (the link checker visits only the links in the published notes, and archive.org unless
  `NIWA_ARCHIVE=none`).
- **The pre-publish check:** a credential, key or private address pattern it should catch and doesn't, or a
  `NIWA_SCAN_DENY` word it misses. A note whose scan finds an error is held back from every channel until the owner
  acknowledges exactly those findings on its page; a hold that lets a note through after its findings changed, or an
  acknowledgement made by anyone but the owner, is in scope. The scan is pattern matching, not a guarantee: names and
  details it has no pattern for are the owner's to review.

Hister, Kura, Konbini, the vendored vaultkit's upstream, Git and the web server or proxy in front of Niwa are
separate projects: report their problems to them. Running with `NIWA_AUTH=open` on a public address is a
configuration error, not a vulnerability.

## Supported versions

Fixes go into the latest release on the main branch.
