# One Dockerfile, two products:
#  - plain image ghcr.io/<owner>/mcp-grocy : default args -> "docker" final stage (tini + CMD)
#  - Home Assistant app image             : BUILD_FROM=<hassio-addons base> and APP_TARGET=addon
#    (injected by build.yaml for Supervisor local builds and by the smoke job in
#    .github/workflows/app-lint.yml; publishing prebuilt images is a follow-up)
#    -> "addon" final stage: s6-overlay services from rootfs/, NO CMD. The base image's
#    ENTRYPOINT /init supervises the services; a CMD would run node without the
#    bashio-exported options and stop the container when it exits.
ARG BUILD_FROM=node:22-alpine
ARG APP_TARGET=docker
# Always passed by the Supervisor; declared so the build does not warn about unused args.
ARG BUILD_ARCH
ARG BUILD_VERSION

FROM ${BUILD_FROM} AS base
WORKDIR /app

# node:22-alpine already has Node; the hassio-addons base (Alpine) gets it from apk.
RUN ( command -v node >/dev/null 2>&1 || apk add --no-cache nodejs npm ) && rm -rf /tmp/* /var/tmp/*

COPY package*.json tsconfig.json ./
# --maxsockets 1 / long retry timeout: avoid QEMU network hangs when building arm64 on amd64
RUN npm config set fetch-retry-maxtimeout 600000 -g && \
    npm config set legacy-peer-deps true -g && \
    npm install --ignore-scripts --maxsockets 1

COPY . .

# Supervisor builds pass BUILD_VERSION (config.yaml version) instead of RELEASE_VERSION.
ARG BUILD_VERSION
ARG RELEASE_VERSION
ENV RELEASE_VERSION=${RELEASE_VERSION:-${BUILD_VERSION}}
RUN npm run build

# ---- plain Docker image ------------------------------------------------------
FROM base AS docker
RUN apk add --no-cache tini
CMD ["tini", "--", "node", "build/main.js"]

# ---- Home Assistant app (s6-overlay v3 layout) ------------------------------
FROM base AS addon
COPY rootfs/ /
RUN chmod a+x /etc/s6-overlay/s6-rc.d/*/run /etc/s6-overlay/s6-rc.d/*/finish

FROM ${APP_TARGET} AS final
