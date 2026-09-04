# Build the Vue SPA before copying it into the browser-facing Caddy image.
FROM node:24-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine AS production

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-builder /build/dist /srv/frontend

# Fail the image build if the tracked production configuration is invalid.
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && \
    DOMAIN=owlculus.example.com caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

EXPOSE 80 443

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
