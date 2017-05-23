FROM ubuntu:16.04
MAINTAINER btimby@gmail.com

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y python3 netcat python3-pip

ADD ./web/requirements/base.txt /tmp/requirements.txt
RUN /usr/bin/env pip3 install -r /tmp/requirements.txt
