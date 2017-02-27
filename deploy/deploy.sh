#!/bin/bash -xe

SSHUSER="deploy"
SSHHOST="cloudstrype.io"
SSHARGS="-i .ssh/deploy-id_rsa -oStrictHostKeyChecking=no"
WEBROOT="/usr/share/nginx/cloudstrype/"

SSHCMD="ssh ${SSHARGS} ${SSHUSER}@${SSHHOST}"

CONFIG_NGINX="/etc/nginx/conf.d/cloudstrype.conf"
CONFIG_SUPERVISORD="/etc/supervisord.d/cloudstrype.ini"

# This script is run from inside deploy/, so we have to use .. to refer to
# local paths.

rsync -avr --del -e "ssh ${SSHARGS}" --exclude-from=rsync.excludes ../ ${SSHUSER}@${SSHHOST}:${WEBROOT}

# Build virtualenv
${SSHCMD} "cd ${WEBROOT} && virtualenv-3.5 venv && venv/bin/pip install -r web/requirements/base.txt"

# Configure Django.
${SSHCMD} "cp ${WEBROOT}deploy/.env ${WEBROOT}.env"
${SSHCMD} "echo \"CLOUDSTRYPE_VERSION=${TRAVIS_COMMIT}\" > ${WEBROOT}.env-version"

# Migrate database
${SSHCMD} "cd ${WEBROOT}web/cloudstrype && ${WEBROOT}venv/bin/python manage.py migrate"

# Collect static files
${SSHCMD} "cd ${WEBROOT}web/cloudstrype && ${WEBROOT}venv/bin/python manage.py collectstatic --noinput"

# Configure services.
${SSHCMD} "sudo cp ${WEBROOT}deploy/nginx-cloudstrype.conf ${CONFIG_NGINX}"
${SSHCMD} "sudo cp ${WEBROOT}deploy/supervisord-uwsgi.ini ${CONFIG_SUPERVISORD}"

# Restart serices
if ! ${SSHCMD} "sudo nginx -t -c /etc/nginx/nginx.conf"; then
    echo "ERROR: nginx config file has errors, aborting restart."
    exit 1;
fi

# I don't think supervisord can check it's config before reload.

${SSHCMD} "sudo systemctl restart supervisord && sudo systemctl restart nginx"
