# Niwa (machiya-kobo/niwa): stdlib Python + markdown + pyyaml + git/ssh + openssl (the gemini certificate) + the hister
# CLI (link rot saves pages into Hister). Runs as uid 1000.
ARG HISTER_VERSION=v0.20.0
FROM ghcr.io/asciimoo/hister:${HISTER_VERSION} AS hister

FROM public.ecr.aws/docker/library/python:3.13-slim

# markdown >= 3.7: the BSD packages ship 3.7-3.10; the tests pass on 3.7 to 3.11.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssh-client openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "markdown>=3.7" pyyaml==6.0.3

# ssh refuses to run for a uid without a passwd entry (git pull/push).
RUN useradd --uid 1000 --home-dir /data --no-create-home --shell /usr/sbin/nologin niwa

COPY --from=hister /hister/hister /usr/local/bin/hister

WORKDIR /app
COPY . /app
# The vendored vault core (app/vaultkit/, from machiya-kobo/machiya) must match its manifest: edits go upstream.
RUN python3 -m vaultkit.verify

ENV HOME=/data PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080 1965 7070
CMD ["python3", "-u", "/app/niwa.py"]
