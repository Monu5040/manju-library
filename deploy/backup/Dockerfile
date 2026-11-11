# pg_dump from PostgreSQL 18 can back up any older server version.
FROM postgres:18-alpine
RUN apk add --no-cache aws-cli
COPY --chmod=755 pg_backup.sh pg_restore_check.sh /usr/local/bin/
USER postgres
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/pg_backup.sh"]
