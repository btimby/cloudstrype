[![Build Status](https://travis-ci.org/btimby/cloudstrype.svg?branch=master)](https://travis-ci.org/btimby/cloudstrype)
[![Coverage Status](https://coveralls.io/repos/github/btimby/cloudstrype/badge.svg?branch=master)](https://coveralls.io/github/btimby/cloudstrype?branch=master)

Cloudstrype.io
==============

**Personal multi-cloud storage.**

Cloudstrype allows you to add many free (or paid) storage clouds to your account.
Once added the clouds are used together for form one large storage cloud that you
can access via Cloudstrype. The files are chunked, encrypted and striped across
your cloud accounts. You can choose the replica level (or RAID) to ensure
availability when one of the clouds is offline.

Cloudstrype provides an API for accessing your files. The API utilizes OAuth for
authentication, meaning that you can integrate your applications with Cloudstrype.

Open Source
-----------

Development of the Cloudstrype application is completely open. If there is a
feature you desire, you can submit a pull request to this repository or pay someone
to do it for you (or maybe just ask nicely). Continuous integration means that as
soon as your changes are approved and pass tests, the code will be "deployed" and
available to everyone at https://cloudstrype.io/.

A lot of Open Source software and free services go into providing Cloudstrype free
of charge. Below is a list of great projects you should check out.

- Travis CI
- Coveralls
- Github
- Python
- PostgreSQL
- Django
- Linux
- Letsencrypt
- Nginx
- Memcached
- Supervisord
- UWSGI
- djangorestframework
- django-environ
- django-mailjet
- django-filter
- django-extensions
- django-rest-auth
- django-oauth-toolkit
- oauthlib
- requests
- requests_oauthlib
- psycopg2
- hashids
- python-uptimerobot
- Mailjet
- UptimeRobot

Development
-----------

**Git Hooks**

Author uses and highly recommends flake8 and jshint. You can easily install the webhook
the folowing command:

    cp git.hooks.pre-commit .git/hooks/pre-commit

You will need to ensure you have jshint installed:

    npm install -g jshint

And then configure flake8 to prevent committing lint failures:

    git config --local --bool flake8.strict true

