#!/bin/sh
# Get the first HTTPS certificate. Run once on a new server, from the deploy/ folder, after
# DNS for SERVER_NAME points at this server and before the first `docker compose up`.
# Renewals after this are automatic (the certbot service).
set -eu
cd "$(dirname "$0")/.."

value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
SERVER_NAME=$(value SERVER_NAME)
LETSENCRYPT_EMAIL=$(value LETSENCRYPT_EMAIL)
: "${SERVER_NAME:?Set SERVER_NAME in deploy/.env}"
: "${LETSENCRYPT_EMAIL:?Set LETSENCRYPT_EMAIL in deploy/.env}"

# Port 80 must be free: certbot answers the challenge itself.
docker compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true
docker compose -f docker-compose.prod.yml run --rm -p 80:80 --entrypoint certbot certbot \
    certonly --standalone --non-interactive --agree-tos --no-eff-email \
    -m "$LETSENCRYPT_EMAIL" -d "$SERVER_NAME"

echo "Certificate ready for $SERVER_NAME. Now run: scripts/deploy.sh"
