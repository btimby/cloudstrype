#: help - Display callable targets.
.PHONY: help
help:
	@echo "Reference card for usual actions in development environment."
	@echo "Here are available targets:"
	@egrep -o "^#: (.+)" [Mm]akefile | sed 's/#: /* /'

#: travis-ci - Runs CI in Travis.
.PHONY: travis-ci
travis-ci:
	$(MAKE) -C web travis-ci

#: venv - Creates virtualenv.
.PHONY: venv
venv:
	python3 -m virtualenv venv

#: deps - Installs dependencies.
deps: web/requirements.txt
	pip install -r web/requirements.txt

#: run - Runs the application
.PHONY: run
run:
	$(MAKE) -C web run

#: deploy - Deploys application to server.
.PHONY: deploy
deploy:
	$(MAKE) -C deploy deploy

#: deploy.tar.gz - Creates tarball with secret contents.
deploy.tar.gz: deploy/.ssh/deploy-id_rsa deploy/.ssh/deploy-id_rsa.pub
	tar czf deploy.tar.gz deploy/.ssh

#: deploy.tar.gz.enc - Encrypts secret tarball for Travis deploy.
deploy.tar.gz.enc: deploy.tar.gz
	travis encrypt-file -f deploy.tar.gz
	rm -f deploy.tar.gz
