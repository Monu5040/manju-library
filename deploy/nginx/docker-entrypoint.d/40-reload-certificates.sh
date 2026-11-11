#!/bin/sh
# Reload Nginx every 6 hours so certificates renewed by the certbot container are picked up.
(
    while :; do
        sleep 6h
        nginx -s reload || echo "40-reload-certificates: nginx reload failed" >&2
    done
) &
