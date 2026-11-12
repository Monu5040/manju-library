#!/bin/sh
# Monthly restore test: restore the newest backup into a scratch database and count rows,
# proving the backups can actually be used. Needs everything pg_backup.sh needs, plus
# RESTORE_DATABASE_URL pointing at an empty scratch database (never the live one).
set -eu

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is not set (use a scratch database)}"
: "${DATABASE_URL:?DATABASE_URL is not set (needed to make sure the target is not the live database)}"
: "${BACKUP_BUCKET:?BACKUP_BUCKET is not set}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL is not set}"

without_password() { printf '%s' "$1" | sed 's|^\([a-z]*://[^:/@]*\):[^@]*@|\1@|'; }
password_of() { printf '%s' "$1" | sed -n 's|^[a-z]*://[^:/@]*:\([^@]*\)@.*|\1|p'; }
on() { url="$1"; shift; PGPASSWORD="$(password_of "$url")" "$@" "$(without_password "$url")"; }
# Ask each server which database it really is: two URLs can name the same database
# differently (a host name or an address, with or without the port).
identity() {
    on "$1" psql --no-psqlrc --tuples-only --no-align --command \
        "SELECT coalesce(host(inet_server_addr()), 'socket') || ':' || inet_server_port() || '/' || current_database()" \
        --dbname
}
if [ "$(identity "$RESTORE_DATABASE_URL")" = "$(identity "$DATABASE_URL")" ]; then
    echo "RESTORE_DATABASE_URL is the live database. Use an empty scratch database." >&2
    exit 1
fi
PREFIX="s3://${BACKUP_BUCKET}/postgres"

latest=$(aws s3 ls "${PREFIX}/" --endpoint-url "$S3_ENDPOINT_URL" | awk '{print $4}' | grep '^manju-.*\.dump$' | sort | tail -1)
if [ -z "$latest" ]; then
    echo "No backups found under ${PREFIX}/" >&2
    exit 1
fi

file="/tmp/${latest}"
trap 'rm -f "$file"' EXIT
aws s3 cp "${PREFIX}/${latest}" "$file" --endpoint-url "$S3_ENDPOINT_URL" --only-show-errors
PGPASSWORD="$(password_of "$RESTORE_DATABASE_URL")" pg_restore --clean --if-exists --no-owner \
    --no-privileges --dbname="$(without_password "$RESTORE_DATABASE_URL")" "$file"

echo "Restored ${latest}. Row counts:"
on "$RESTORE_DATABASE_URL" psql --no-psqlrc --tuples-only --command \
    "SELECT 'users', count(*) FROM accounts_user UNION ALL SELECT 'audit entries', count(*) FROM audit_auditlog;" \
    --dbname
