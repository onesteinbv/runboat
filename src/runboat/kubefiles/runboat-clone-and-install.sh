#!/bin/bash

set -exo pipefail

# Remove initialization sentinel and data, in case we are reinitializing.
rm -fr /mnt/data/*

# Remove addons dir, in case we are reinitializing after a previously
# failed installation.
rm -fr $ADDONS_DIR
# Download the repository at git reference into $ADDONS_DIR.
# We use curl instead of git clone because the git clone method used more than 1GB RAM,
# which exceeded the default pod memory limit.
mkdir -p $ADDONS_DIR
cd $ADDONS_DIR
curl -sSL https://github.com/${RUNBOAT_GIT_REPO}/tarball/${RUNBOAT_GIT_REF} | tar zxf - --strip-components=1

# Install repo requirements.
if [[ -f requirements.txt ]] ; then
    pip install -r requirements.txt
fi

# Aggregate git repositories.
if [[ -f repos.yaml ]] ; then
    pip install git-aggregator
    gitaggregate -c repos.yaml
    ADDONS_PATH=$ADDONS_PATH,$(find $(pwd)/* -name .git -exec dirname {} \; | uniq | tr '\n' ',' | sed 's/,$//')
fi

# Install.
INSTALL_METHOD=${INSTALL_METHOD:-oca_install_addons}
if [[ "${INSTALL_METHOD}" == "oca_install_addons" ]] ; then
    oca_install_addons
elif [[ "${INSTALL_METHOD}" == "editable_pip_install" ]] ; then
    pip install -e .
else
    echo "Unsupported INSTALL_METHOD: '${INSTALL_METHOD}'"
    exit 1
fi

# Keep a copy of the venv that we can re-use for shorter startup time.
cp -ar /opt/odoo-venv/ /mnt/data/odoo-venv

touch /mnt/data/initialized
