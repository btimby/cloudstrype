FROM ubuntu:16.04
MAINTAINER btimby@gmail.com

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y python3 netcat python3-pip libffi-dev libssl-dev

ADD ./web/requirements/base.txt /tmp/base.txt
ADD ./web/requirements/dev.txt /tmp/dev.txt

RUN /usr/bin/env pip3 install -r /tmp/dev.txt
