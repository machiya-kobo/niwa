# Who can use Niwa

[Back to the README](../README.md)

Here the **owner** is the person whose vault it is, and a **room** is one Machiya app (Niwa is the garden).

- **You, on localhost:** `NIWA_AUTH=open` with `NIWA_BIND=127.0.0.1`, as in the [Quickstart](../README.md#quickstart). No login: anyone who
  reaches the port can publish, so keep it on your own machine.
- **People on your tailnet:** bind `127.0.0.1`, put `tailscale serve` in front, and list their Tailscale logins in
  `NIWA_USERS` (`NIWA_AUTH=tailscale`, the default; `*` is anyone, unset is nobody).
- **People, agents and Shiori devices with their own sign-in:** Machiya's identity file.
  `python3 -m vaultkit.identity setup` prints the settings. See
  [Machiya's identity guide](https://github.com/machiya-kobo/machiya/blob/main/docs/identity.md) (Python 3.11 or newer).
- **Hister's users:** `NIWA_AUTH=hister` signs people in with their Hister account through Machiya's sign-in helper
  ([the guide](https://github.com/machiya-kobo/machiya/blob/main/docs/identity.md#hister-sign-in-authhister)). Only
  accounts in `NIWA_HISTER_USERS` get in. While sign-in is down, the owner's Tailscale login in `NIWA_USERS` gets in
  with a banner; a signed-out browser never does. Bind `127.0.0.1` behind `tailscale serve`, or set
  `NIWA_BIND_BEHIND_PROXY=1` in a sidecar: it refuses a public bind otherwise.
- **Anyone, on the public web (optional):** set `NIWA_PUBLIC_PORT` and `NIWA_GARDEN_URL`, and put a TLS proxy (Caddy,
  a Cloudflare Tunnel, Tailscale Funnel) in front of that port. It serves the published notes, their tags and images,
  the stream and the feed. No sign-in, queue, settings, writes or cookies, and nothing from Konbini, Kura or Hister.

Each mode's settings are under [Settings](settings.md). `/api/status` is always open.
