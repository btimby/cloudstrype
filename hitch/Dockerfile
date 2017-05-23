FROM zazukoians/hitch
MAINTAINER btimby@gmail.com

RUN apk add --update gettext
RUN addgroup -S hitch || echo "Group exists"
RUN adduser -S -g hitch hitch || echo "User exists"
