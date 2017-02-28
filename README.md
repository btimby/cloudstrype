[![Build Status](https://travis-ci.org/btimby/cloudstrype.svg?branch=master)](https://travis-ci.org/btimby/cloudstrype)
[![Coverage Status](https://coveralls.io/repos/github/btimby/cloudstrype/badge.svg?branch=master)](https://coveralls.io/github/btimby/cloudstrype?branch=master)

Cloudstrype.io
==============

Personal multi-cloud storage.

Cloudstrype allows you to add many free (or paid) storage clouds to your account.
Once added the clouds are used together for form one large storage cloud that you
can access via Cloudstrype. The files are chunked, encrypted and striped across
your cloud accounts. You can choose the replica level (or RAID) to ensure
availability when one of the clouds is offline.

Cloudstrype provides an API for accessing your files. The API utilizes OAuth for
authentication, meaning that you can integrate your applications with Cloudstrype.

Development of the Cloudstrype application is completely open. If there is a
feature you desire, you can submit a pull request to this repository or pay someone
to do it for you (or maybe just ask nicely). Continuous integration means that as
soon as your changes are approved and pass tests, the code will be "deployed" and
available to everyone at https://cloudstrype.io/.

There is no cost for using https://cloudstrype.io/ however, there are paid features
available in the commercial version at https://cloudstrype.com/.

*Paid features*

With a paid account (https://cloudstrype.com/) you get:

- No limit on number of added clouds.
- Access to additional cloud providers.
- Add your own storage via Cloudstrype Array &trade;

Development
-----------

Git Hooks
---------

Author uses and highly recommends flake8. You can easily install the webhook using
the folowing command:

    flake8 --install-hook

And then configure it to prevent committing lint failures.

    git config --local --bool flake8.strict true

