# Installing Niwa

[Back to the README](../README.md)

The [Quickstart](../README.md#quickstart) runs Niwa natively on Debian or Ubuntu. This page has the other ways, the
Machiya stack, and a real install on your own vault. `tools/quickstart-test` runs the Quickstart and the blocks here
from a fresh clone and checks their output.

## More ways to run it

Each starts with your system's packages (below) and a clone with the sample vault made a repository ([Quickstart](../README.md#quickstart) steps 2
and 3). **You need** `git`, `curl`, `openssl` and `nc`, plus `podman` 4 or `docker` 24 or newer for a container (the
build pulls its base images from the internet). Ports 8080 (web), 1965 (Gemini) and 7070 (Gopher) must be free.

## In a container

*Container with podman* (on Debian or Ubuntu, install it first):

<!-- quickstart: packages-podman-debian -->
```bash
sudo apt-get update && sudo apt-get install -y podman git curl openssl netcat-openbsd
```

<!-- quickstart: container-podman -->
```bash
podman build -q -t niwa-demo app
podman run -d --init --name niwa-demo --userns=keep-id \
  -p 127.0.0.1:8080:8080 -p 127.0.0.1:1965:1965 -p 127.0.0.1:7070:7070 \
  -v "$PWD/demo-data":/data -v "$PWD/demo-vault.git":"$PWD/demo-vault.git" \
  -e NIWA_AUTH=open -e NIWA_HOST=localhost -e NIWA_REPO_SUBDIR=personal \
  -e NIWA_REPO_URL="file://$PWD/demo-vault.git" niwa-demo
```

Rootless podman started over plain ssh (no systemd user session) needs `cgroup_manager = "cgroupfs"` under `[engine]` in
`~/.config/containers/containers.conf`; a desktop login does not.

*Container with docker* (it runs as your own user, so the mounted folders stay yours). On Debian or Ubuntu install docker first
and add yourself to its group (log in again afterwards, or run the next blocks with `sg docker -c '…'`):

<!-- quickstart: packages-docker-debian -->
```bash
sudo apt-get update && sudo apt-get install -y docker.io git curl openssl netcat-openbsd
sudo usermod -aG docker "$USER"
```

<!-- quickstart: container-docker -->
```bash
docker build -q -t niwa-demo app
docker run -d --init --name niwa-demo -u "$(id -u):$(id -g)" \
  -p 127.0.0.1:8080:8080 -p 127.0.0.1:1965:1965 -p 127.0.0.1:7070:7070 \
  -v "$PWD/demo-data":/data -v "$PWD/demo-vault.git":"$PWD/demo-vault.git" \
  -e NIWA_AUTH=open -e NIWA_HOST=localhost -e NIWA_REPO_SUBDIR=personal \
  -e NIWA_REPO_URL="file://$PWD/demo-vault.git" niwa-demo
```

## Natively on the BSDs

Packages for Python, PyYAML and git, then pip for `markdown` (vaultkit needs 3.11 or later; the BSD packages ship older ones), in a venv that keeps the packages. Run the install line for your system as root (OpenBSD has `doas` in base; on a fresh FreeBSD or NetBSD use `su -` first, or install `sudo` from packages), then the run block:

<!-- quickstart: packages-openbsd -->
```bash
doas pkg_add python%3 py3-yaml git curl
```

<!-- quickstart: packages-freebsd -->
```bash
sudo pkg install -y python312 py312-sqlite3 py312-pyyaml git-lite curl
sudo ln -sf /usr/local/bin/python3.12 /usr/local/bin/python3
```

<!-- quickstart: packages-netbsd -->
```bash
sudo env PKG_PATH="https://cdn.NetBSD.org/pub/pkgsrc/packages/NetBSD/$(uname -p)/$(uname -r | cut -d_ -f1)/All" \
  /usr/sbin/pkg_add python313 py313-yaml git-base curl
sudo ln -sf /usr/pkg/bin/python3.13 /usr/pkg/bin/python3
```

Then, in the clone, the venv (it keeps the packages' PyYAML and adds `markdown` 3.11 or later), the sample vault
([Quickstart](../README.md#quickstart) steps 2 and 3) and the run block:

<!-- quickstart: venv-bsd -->
```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -q 'markdown>=3.11'
```

<!-- quickstart: native-run-bsd background -->
```bash
NIWA_AUTH=open NIWA_BIND=127.0.0.1 NIWA_HOST=localhost NIWA_REPO_SUBDIR=personal \
  NIWA_REPO_URL="file://$PWD/demo-vault.git" NIWA_REPO_DIR="$PWD/demo-data/repo" \
  NIWA_DB="$PWD/demo-data/niwa.sqlite3" .venv/bin/python app/niwa.py
```

On FreeBSD and NetBSD the packages install `python3.12` or `python3.13`, so the install lines above also link it as
`python3` (OpenBSD's package already does). `docs/install/bsd.md` in
[machiya-kobo/machiya](https://github.com/machiya-kobo/machiya) is the full guide, with rc.d scripts and the env file.

## Check all three listeners

This checks all three listeners, whichever way Niwa runs (a native run: in a second terminal, same folder). It waits up
to four minutes while Niwa clones and indexes the vault:

<!-- quickstart: check -->
```bash
i=0; while [ $i -lt 240 ]; do curl -fs http://127.0.0.1:8080/api/status | grep -q '"ready": true' && break; i=$((i+1)); sleep 1; done
curl -s http://127.0.0.1:8080/api/status
curl -s http://127.0.0.1:8080/ | grep -o '<title>[^<]*'
curl -s http://127.0.0.1:8080/n/Projects/Lantern | grep -o '<title>[^<]*'
printf 'gemini://localhost/\r\n' | openssl s_client -connect 127.0.0.1:1965 -quiet -ign_eof 2>/dev/null | head -n 3
printf '\r\n' | nc -w 2 127.0.0.1 7070 | head -n 1
```

You should see:

<!-- quickstart-expect: check -->
```text
"published": 9
"ready": true
"error": null
<title>Niwa
<title>Lantern - Niwa
20 text/gemini
# Niwa
NIWA
```

Niwa has no read-only mode: a real vault needs a deploy key with write access (see [Your own vault](#your-own-vault)). Stop a
container with:

<!-- quickstart: stop-container-podman -->
```bash
podman rm -f niwa-demo
```

<!-- quickstart: stop-container-docker -->
```bash
docker rm -f niwa-demo
```
A native run stops with Ctrl-C. Then remove the demo files: `rm -rf demo-vault demo-vault.git demo-data`.

## As part of the Machiya stack

In the stack, Niwa shares the vault with the other apps and links to them. Start from
[machiya-kobo/machiya](https://github.com/machiya-kobo/machiya): its README has the stack's Quickstart, and
`compose/compose.yml` and `compose/mirror.yml` are the files. What changes for Niwa:

| Setting | In the stack |
|---|---|
| `NIWA_REPO_URL`, `NIWA_REPO_SUBDIR` | the same vault repository and folder as the other apps (a deploy key with write access; Kura only needs read access) |
| `NIWA_REPO_REFERENCE`, `NIWA_REPO_SPARSE` | the vault mirror's path, mounted read-only at the same absolute path, so Niwa borrows its objects instead of fetching a second copy; the folders to check out (`<notes folder>,.garden`) |
| `MACHIYA_COOKIE_DOMAIN`, `MACHIYA_ROOMS` | one cookie domain and the list of room URLs, so the Rooms menu and the theme settings are shared |
| `NIWA_KONBINI_URL`, `NIWA_KURA_URL` | the other rooms' addresses: Konbini adds board badges and its API feeds the owner's stream; Kura adds "View in Kura" links (both optional) |
| `NIWA_AUTH`, `NIWA_USERS`, `NIWA_BIND`, `MACHIYA_IDENTITY_FILE` | who may use it: see "Who can use it" |
| `NIWA_HISTER_URL`, `NIWA_HISTER_TOKEN_FILE`, `NIWA_AUTH=hister` … | the stack's Hister and its token; Hister's users as the sign-in through the stack's hister-login helper (see "Who can use it") |
| `NIWA_KONBINI_TOKEN_FILE` | Niwa's own token for its calls to Konbini: a room token for Konbini, or with the identity file an identity token (see Settings) |
| `NIWA_ENV_FILE` (or `--env-file`) | a file of `KEY=VALUE` settings, for a native install |
| `MACHIYA_SOURCE_URL` | the address of the source code, to show a "Source code" link as the AGPL asks of a networked service |

## Your own vault

Niwa needs a git repository of your vault (Markdown notes with YAML frontmatter) that it can push to.

**Container** (Docker or Podman; the image runs as uid 1000 and keeps everything under `/data`):

```sh
docker build -t niwa app
# HOME is /data: the deploy key (with write access to the vault repo) and known_hosts go in niwa-data/.ssh/
mkdir -p niwa-data/.ssh && cp /path/to/deploy_key niwa-data/.ssh/id_ed25519
ssh-keyscan git.example.net > niwa-data/.ssh/known_hosts
chmod 700 niwa-data/.ssh && chmod 600 niwa-data/.ssh/id_ed25519 && chown -R 1000:1000 niwa-data
docker run -d --name niwa --init --user 1000:1000 \
  -p 127.0.0.1:8080:8080 -p 1965:1965 -p 70:7070 \
  -v "$PWD/niwa-data:/data" \
  -e NIWA_REPO_URL=ssh://git@git.example.net/you/vault.git \
  -e NIWA_REPO_SUBDIR=notes \
  -e NIWA_HOST=garden.example.net \
  -e NIWA_AUTH=open \
  niwa
```

`NIWA_AUTH=open` has no login, so the example keeps the web port on 127.0.0.1. Gemini and Gopher serve only published
notes, so their ports can face the world. For everything else, see [Who can use it](access.md): the default
`tailscale` mode trusts the `Tailscale-User-Login` header that `tailscale serve` sets, and any proxy that sets it and
strips the client's own copy works too.

**Native:** Python 3 with `markdown` 3.11 or later (older ones can run out of memory under Python 3.13) and `pyyaml`,
plus `git`, `openssh` and `openssl`. From `app/`, run `python3 niwa.py`. Settings come from the environment, or a file
given with `--env-file PATH` or `NIWA_ENV_FILE` (the environment wins).

The web UI is on `NIWA_PORT` (8080), Gemini on 1965 and Gopher on 7070. Gopher menus point at port 70 on `NIWA_HOST`
(`NIWA_GOPHER_PUBLIC_PORT`), so map port 70 to 7070 as the example does (rootless Podman needs
`net.ipv4.ip_unprivileged_port_start=70` or lower).

## The Gemini certificate

On first start Niwa makes a self-signed certificate with `openssl` (EC P-256, ten years, for `NIWA_HOST` and its
first label) and keeps `gemini.crt` and `gemini.key` next to `NIWA_DB`. Gemini clients trust it on first use. It's
made once: after changing `NIWA_HOST`, delete both files and restart (clients will ask again). Back up the data
directory so the certificate survives rebuilds.
