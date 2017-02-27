#!/bin/bash -xe

SSHUSER="deploy"
SSHHOST="cloudstrype.io"
SSHARGS="-i .ssh/deploy-id_rsa -oStrictHostKeyChecking=no"
WEBROOT="/usr/share/nginx/cloudstrype/"

SSHCMD="$SSHCMD"

CONFIG_NGINX="/etc/nginx/conf.d/cloudstrype.conf"
CONFIG_SUPERVISORD="/etc/supervisord.d/cloudstrype.ini"

# This script is run from inside deploy/, so we have to use .. to refer to
# local paths.

rsync -avr --del -e "ssh ${SSHARGS}" --exclude-from=rsync.excludes ../ ${SSHUSER}@${SSHHOST}:${WEBROOT}

# Build virtualenv
${SSHCMD} "cd ${WEBROOT} && python3 -m virtualenv venv && venv/bin/pip3 install -r web/requirements.txt"

# Migrate database
${SSHCMD} "cd ${WEBROOT}/web/cloudstrype && ../../venv/bin/python3 manage.py migrate"

# Collect static files
${SSHCMD} "cd ${WEBROOT}/web/cloudstrype && ../../venv/bin/python3 manage.py collectstatic --noinput"

# Copy config files.
${SSHCMD} "sudo mv ${WEBROOT}/deploy/nginx-cloudstrype.conf ${CONFIG_NGINX}"
${SSHCMD} "sudo mv ${WEBROOT}/deploy/supervisord-uwsgi.ini ${CONFIG_SUPERVISORD}"

# Restart serices
${SSHCMD} "sudo nginx -t -c /etc/nginx/nginx.conf"
if [ $? -ne "0" ]; then
    echo "ERROR: nginx config file has errors, aborting restart."
    exit 1;
fi

# I don't think supervisord can check it's config before reload.

${SSHCMD} "sudo systemctl restart supervisord && sudo systemctl restart nginx"
