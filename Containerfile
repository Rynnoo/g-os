# Keep build-only files out of the final image layers.
FROM scratch AS ctx
COPY build_files /build_files
COPY system_files /system_files
COPY apps /apps
COPY catalog /catalog
COPY profiles /profiles

# G-OS starts from Universal Blue's KDE Plasma image. The floating tag is
# intentional during early development; pin a tested digest before a release.
FROM ghcr.io/ublue-os/kinoite-main:latest

LABEL org.opencontainers.image.title="G-OS" \
      org.opencontainers.image.description="A focused, approachable Linux desktop for speedrunning" \
      org.opencontainers.image.licenses="Apache-2.0"

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    /usr/bin/bash /ctx/build_files/build.sh

# Catch invalid bootc images during the container build.
RUN bootc container lint
