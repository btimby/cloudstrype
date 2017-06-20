FROM zazukoians/hitch
MAINTAINER btimby@gmail.com

RUN apk add --update gettext

COPY hitch/wait-for /wait-for
COPY hitch/start /start
COPY hitch/hitch.conf.template /etc/hitch/hitch.conf.template
