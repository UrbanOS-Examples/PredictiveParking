#!/usr/bin/env bash
service nginx start
(
cd /
hypercorn \
        --user $(id -u www-data) \
        --group $(id -g www-data) \
        --umask 113 \
        --workers 1 \
        --bind unix:/tmp/hypercorn.sock \
        --error-logfile - \
        --access-logfile - \
        app:app
)