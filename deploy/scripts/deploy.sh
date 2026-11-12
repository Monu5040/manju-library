#!/bin/sh
# Deploy a git ref on this server: build images, run migrations (which also runs the
# deployment safety checks), restart, and wait for the health check. If the new version
# does not come up healthy, the previous one is started again.
#   scripts/deploy.sh                 deploy origin/main
#   scripts/deploy.sh <commit-sha>    deploy or roll back to a commit on main
#
# The Compose files come from COMPOSE_FILE in deploy/.env (default: docker-compose.prod.yml).
# Everything sits in main() so the shell reads the whole file before `git checkout`
# can change it underneath.
set -eu

KEEP_RELEASES=3

healthy() {
    attempts=0
    until docker compose exec -T backend python healthcheck.py >/dev/null 2>&1; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 45 ]; then
            return 1
        fi
        sleep 2
    done
}

roll_back() {
    previous="$1"
    if [ -z "$previous" ]; then
        echo "No earlier release is recorded, so nothing to roll back to." >&2
        return
    fi
    echo "Starting the previous release $previous again." >&2
    IMAGE_TAG="$previous" docker compose up -d --no-build --remove-orphans >&2 || true
}

prune_old_releases() {
    for repo in manju-library/backend manju-library/web; do
        docker images "$repo" --format '{{.Tag}}' | tail -n +$((KEEP_RELEASES + 1)) |
            while read -r tag; do docker rmi "$repo:$tag" >/dev/null 2>&1 || true; done
    done
    docker image prune -f >/dev/null
    docker builder prune -f --filter until=168h >/dev/null
}

main() {
    ref="${1:-origin/main}"
    cd "$(dirname "$0")/.."
    if [ ! -f .env ]; then
        echo "deploy/.env is missing. Copy .env.example and fill it in first." >&2
        exit 1
    fi
    # A missing or misspelt ENVIRONMENT would quietly turn off the production safety checks.
    if ! grep -Eq '^ENVIRONMENT=(staging|production)$' .env; then
        echo "deploy/.env must set ENVIRONMENT=staging or ENVIRONMENT=production." >&2
        exit 1
    fi
    if ! grep -q '^COMPOSE_FILE=' .env; then
        export COMPOSE_FILE=docker-compose.prod.yml
    fi

    git fetch --prune origin
    commit=$(git rev-parse --verify "$ref^{commit}")
    # Only what reached main (tested by CI) can be deployed; older main commits are rollbacks.
    if ! git merge-base --is-ancestor "$commit" origin/main; then
        echo "$ref is not on main. Merge it first." >&2
        exit 1
    fi
    previous=$(cat .deployed-tag 2>/dev/null || true)
    git checkout --detach "$commit"
    IMAGE_TAG=$(git rev-parse --short HEAD)
    export IMAGE_TAG
    echo "Deploying $IMAGE_TAG (running now: ${previous:-unknown})"

    # Fresh base images and services, so security updates arrive with every deploy.
    docker compose pull --ignore-buildable --quiet
    docker compose build --pull
    # Stops here if settings are unsafe (core.E00x) or a migration fails; the running
    # version keeps serving. Migrations must stay compatible with the previous release.
    docker compose run --rm backend python manage.py migrate --noinput

    if ! docker compose up -d --remove-orphans || ! healthy; then
        echo "$IMAGE_TAG did not come up healthy. See: docker compose logs backend" >&2
        roll_back "$previous"
        exit 1
    fi
    echo "$IMAGE_TAG" > .deployed-tag
    prune_old_releases
    echo "Deployed $IMAGE_TAG"
}

main "$@"
