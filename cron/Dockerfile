FROM cloudstrype/web
MAINTAINER btimby@gmail.com

RUN apt-get update && apt-get install -y cron && \
    mkfifo --mode 0666 /var/log/cron.log && \
    sed --regexp-extended --in-place 's/^session\s+required\s+pam_loginuid.so$/session optional pam_loginuid.so/' \
    /etc/pam.d/cron
