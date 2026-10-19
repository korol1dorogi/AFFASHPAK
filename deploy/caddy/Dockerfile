# Build context: repo root. Stage 1 builds the SPA, stage 2 is Caddy serving it.
FROM node:24.22.0-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2.11.7-alpine
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /build/frontend/dist /srv/site
