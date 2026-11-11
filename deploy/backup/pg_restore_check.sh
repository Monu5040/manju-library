#!/bin/sh
# Monthly restore test: restore the newest backup into a scratch database and count rows,
# proving the backups can actually be used. Needs everything pg_backup.sh needs, plus
# RESTORE_DATABASE_URL pointing at an empty scratch database (never the live one).
set -eu

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is not set (use a scratch database)}"
: "${BACKUP_BUCKET:?BACKUP_BUCKET is not set}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL is not set}"
if [ "${RESTORE_DATABASE_URL}" = "${DATABASE_URL:-}" ]; then
    echo "RESTORE_DATABASE_URL must not be the live database." >&2
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
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$RESTORE_DATABASE_URL" "$file"

echo "Restored ${latest}. Row counts:"
psql "$RESTORE_DATABASE_URL" --no-psqlrc --tuples-only --command \
    "SELECT 'users', count(*) FROM accounts_user UNION ALL SELECT 'audit entries', count(*) FROM audit_auditlog;"
