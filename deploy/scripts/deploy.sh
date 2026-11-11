#!/bin/sh
# Deploy a git ref on this server: build images, run migrations (which also runs the
# deployment safety checks), restart, and wait for the health check.
#   scripts/deploy.sh                 deploy origin/main
#   scripts/deploy.sh <commit-sha>    deploy or roll back to a specific commit
#
# Everything sits in main() so the shell reads the whole file before `git checkout`
# can change it underneath.
set -eu

main() {
    ref="${1:-origin/main}"
    cd "$(dirname "$0")/.."
    compose="docker compose -f docker-compose.prod.yml"

    git fetch --prune origin
    git checkout --detach "$ref"
    IMAGE_TAG=$(git rev-parse --short HEAD)
    export IMAGE_TAG
    echo "Deploying $IMAGE_TAG"

    $compose build
    # Stops here if settings are unsafe (core.E00x) or a migration fails; the running
    # version keeps serving. Migrations must stay compatible with the previous release.
    $compose run --rm backend python manage.py migrate --noinput
    $compose up -d --remove-orphans

    attempts=0
    until $compose exec -T backend python healthcheck.py; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 30 ]; then
            echo "Health check failed after deploying $IMAGE_TAG" >&2
            $compose logs --tail=100 backend >&2
            exit 1
        fi
        sleep 2
    done
    docker image prune -f >/dev/null
    echo "Deployed $IMAGE_TAG"
}

main "$@"
