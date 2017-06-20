FROM dimka2014/nginx-upload-with-progress-modules
MAINTAINER btimby@gmail.com

RUN apk add --update gettext

COPY nginx/wait-for /wait-for
COPY nginx/start /start
