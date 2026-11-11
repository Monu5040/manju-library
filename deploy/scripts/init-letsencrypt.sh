#!/bin/sh
# Get the first HTTPS certificate. Run once on a new server, from the deploy/ folder, after
# DNS for SERVER_NAME points at this server and before the first deploy. Renewals after
# this are automatic (the certbot service).
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "deploy/.env is missing. Copy .env.example and fill it in first." >&2
    exit 1
fi
if ! grep -q '^COMPOSE_FILE=' .env; then
    export COMPOSE_FILE=docker-compose.prod.yml
fi

value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
SERVER_NAME=$(value SERVER_NAME)
LETSENCRYPT_EMAIL=$(value LETSENCRYPT_EMAIL || true)
: "${SERVER_NAME:?Set SERVER_NAME in deploy/.env}"

if [ -n "$LETSENCRYPT_EMAIL" ]; then
    contact="-m $LETSENCRYPT_EMAIL"
else
    contact="--register-unsafely-without-email"
fi

# Port 80 must be free: certbot answers the challenge itself.
docker compose stop nginx 2>/dev/null || true
# shellcheck disable=SC2086  # $contact is one or two words on purpose
docker compose run --rm -p 80:80 --entrypoint certbot certbot \
    certonly --standalone --non-interactive --agree-tos --no-eff-email \
    $contact -d "$SERVER_NAME"

echo "Certificate ready for $SERVER_NAME. Now run: scripts/deploy.sh"
