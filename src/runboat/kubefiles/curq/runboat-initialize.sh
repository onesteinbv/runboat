#!/bin/bash

set -ex

# Compatibility with oca-ci
export MODE="InstallOnly"
export DB_HOST=$PGHOST
export DB_PORT=$PGPORT
export DB_USER=$PGUSER
export DB_PASSWORD=$PGPASSWORD
export WORKERS="0"
export DB_NAME=$PGDATABASE
export DB_FILTER="^$PGDATABASE$"
export DOCKER="false"

wait_for_postgres.sh

# Drop database, in case we are reinitializing.
dropdb --if-exists ${PGDATABASE}

# Get all bundles
export MODULES=$(manifestoo -d /odoo/custom list | grep _install | paste -sd,)

/usr/local/bin/entrypoint.sh
