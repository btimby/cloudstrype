#!/bin/bash -x

SSHUSER="deploy"
SSHHOST="cloudstrype.io"
SSHARGS="-i .ssh/deploy-id_rsa -oStrictHostKeyChecking=no"
WEBROOT="/usr/share/nginx/cloudstrype/"

CONFIG_NGINX="/etc/nginx/conf.d/cloudstrype.conf"
CONFIG_SUPERVISORD="/etc/supervisord.d/cloudstrype.ini"

rsync -avr -e "ssh ${SSHARGS}" --exclude=*.pyc --exclude=__pycache__ --exclude=venv/* --exclude=.git* ../ ${SSHUSER}@${SSHHOST}:${WEBROOT}

# Build virtualenv
ssh ${SSHARGS} ${SSHUSER}@${SSHHOST} "cd ${WEBROOT} && python3 -m virtualenv venv && venv/bin/pip3 install -r web/requirements.txt"

# Migrate database
ssh ${SSHARGS} ${SSHUSER}@${SSHHOST} "cd ${WEBROOT}/web/cloudstrype && ../../venv/bin/python3 manage.py migrate"

# Collect static files
ssh ${SSHARGS} ${SSHUSER}@${SSHHOST} "cd ${WEBROOT}/web/cloudstrype && ../../venv/bin/python3 manage.py collectstatic --noinput"

# Copy config files.
ssh ${SSHARGS} ${SSHUSER}@${SSHHOST} "sudo mv ${WEBROOT}/deploy/nginx-cloudstrype.conf ${CONFIG_NGINX}"
ssh ${SSHARGS} ${SSHUSER}@${SSHHOST} "sudo mv ${WEBROOT}/deploy/supervisord-uwsgi.ini ${CONFIG_SUPERVISORD}"

# Restart serices
ssh ${SSHARGS} ${SSHUSER}@${SSHHOST} "sudo systemctl restart nginx && sudo systemctl restart supervisord"
