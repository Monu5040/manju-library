#!/bin/sh
# Back up the database to S3-compatible object storage and delete backups older than
# BACKUP_RETENTION_DAYS (default 30). Needs DATABASE_URL, BACKUP_BUCKET, S3_ENDPOINT_URL,
# AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.
set -eu

: "${DATABASE_URL:?DATABASE_URL is not set}"
: "${BACKUP_BUCKET:?BACKUP_BUCKET is not set}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL is not set}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
PREFIX="s3://${BACKUP_BUCKET}/postgres"

# The connection URL carries the password: pass it in PGPASSWORD, not on the command line
# (where anyone on the host can read it with `ps`).
without_password() { printf '%s' "$1" | sed 's|^\([a-z]*://[^:/@]*\):[^@]*@|\1@|'; }
password_of() { printf '%s' "$1" | sed -n 's|^[a-z]*://[^:/@]*:\([^@]*\)@.*|\1|p'; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
file="/tmp/manju-${stamp}.dump"
trap 'rm -f "$file"' EXIT

echo "Backing up database to ${PREFIX}/manju-${stamp}.dump"
# Sign-in sessions, login codes and authenticator secrets are left out: a backup must not
# let anyone sign in. After a restore, admins connect their authenticator app again.
PGPASSWORD="$(password_of "$DATABASE_URL")" pg_dump --format=custom --no-owner --no-privileges \
    --exclude-table-data=django_session \
    --exclude-table-data=accounts_logincode \
    --exclude-table-data=otp_totp_totpdevice \
    --dbname="$(without_password "$DATABASE_URL")" --file="$file"
aws s3 cp "$file" "${PREFIX}/manju-${stamp}.dump" --endpoint-url "$S3_ENDPOINT_URL" --only-show-errors

cutoff=$(date -u -d "@$(( $(date +%s) - RETENTION_DAYS * 86400 ))" +%Y%m%dT%H%M%SZ)
aws s3 ls "${PREFIX}/" --endpoint-url "$S3_ENDPOINT_URL" | awk '{print $4}' | while read -r key; do
    taken=$(echo "$key" | sed -n 's/^manju-\(.*\)\.dump$/\1/p')
    if [ -n "$taken" ] && expr "$taken" \< "$cutoff" >/dev/null; then
        echo "Deleting old backup $key"
        aws s3 rm "${PREFIX}/${key}" --endpoint-url "$S3_ENDPOINT_URL" --only-show-errors
    fi
done

echo "Backup finished: manju-${stamp}.dump"
