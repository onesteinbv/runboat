#!/bin/bash

set -ex

if [ ! -f /odoo/data/initialized ] ; then
    echo "Build is not initialized. Cannot start."
    exit 1
fi

# Compatibility with oca-ci
export MODE="RunOnly"
export DB_HOST=$PGHOST
export DB_PORT=$PGPORT
export DB_USER=$PGUSER
export DB_PASSWORD=$PGPASSWORD
export MODULES=$MODULES
export WORKERS="0"
export DB_NAME=$PGDATABASE
export DB_FILTER=^$PGDATABASE$
export DOCKER="false"

wait_for_postgres.sh

/usr/local/bin/entrypoint.sh odoo
