# Niwa (machiya-kobo/niwa): stdlib Python + markdown + pyyaml + git/ssh + openssl (the gemini certificate) + the Nogon
# CLI (link rot saves pages into Nogon, formerly Hister). Runs as uid 1000.
# NOGON_VERSION must match the Nogon server (0.19.0: was HISTER_VERSION v0.20.0). Since 0.20.0 the CLI is installed as
# `nogon` and takes the owner's token as NOGON__APP__ACCESS_TOKEN (v0.22 and later).
ARG NOGON_VERSION=v0.22.0
FROM ghcr.io/asciimoo/nogon:${NOGON_VERSION}@sha256:d1b427c7f876e64e6212e000df60d33c2e418b60372582b56cfee719eafd4107 AS nogon

FROM public.ecr.aws/docker/library/python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

# markdown >= 3.11: older ones run out of memory on one note under Python 3.13 (vaultkit refuses them at import).
RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssh-client openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "markdown>=3.11" pyyaml==6.0.3

# ssh refuses to run for a uid without a passwd entry (git pull/push).
RUN useradd --uid 1000 --home-dir /data --no-create-home --shell /usr/sbin/nologin niwa

COPY --from=nogon /usr/local/bin/nogon /usr/local/bin/nogon

WORKDIR /app
COPY . /app
# The vendored vault core (app/vaultkit/, from machiya-kobo/machiya) must match its manifest: edits go upstream.
RUN python3 -m vaultkit.verify

ENV HOME=/data PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
EXPOSE 8080 1965 7070
CMD ["python3", "-u", "/app/niwa.py"]
