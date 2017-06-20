FROM ubuntu:16.04
MAINTAINER btimby@gmail.com

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y python3 netcat python3-pip libffi-dev libssl-dev

COPY /web/wait-for /wait-for
COPY /web/start /start

COPY ./web/requirements/base.txt /tmp/base.txt
COPY ./web/requirements/dev.txt /tmp/dev.txt

RUN /usr/bin/env pip3 install -r /tmp/dev.txt
