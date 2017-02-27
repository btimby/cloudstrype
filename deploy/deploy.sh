#!/bin/bash -xe

# Count how many times deploy.sh has been executed. Travis executes deploy
# after each build in the matrix. .travis.yml defines DEPLOY_LIMIT, which
# should be equal to the number of times deploy will be executed. Therefore
# when we reach that number, we should deploy, but until then, just keep
# counting.

source deploy/deploy_count.sh
DEPLOY_COUNT=$((DEPLOY_COUNT+1))
echo "DEPLOY_COUNT=$DEPLOY_COUNT" > deploy/deploy_count.sh

if [ "$DEPLOY_COUNT" -lt "$DEPLOY_LIMIT" ]; then
    echo "Build number $DEPLOY_COUNT, waiting for $DEPLOY_LIMIT... exiting."
    exit 0;
fi

# OK, this is our last build/deploy, so go ahead and perform the deploy.

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
