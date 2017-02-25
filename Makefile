#: help - Display callable targets.
.PHONY: help
help:
	@echo "Reference card for usual actions in development environment."
	@echo "Here are available targets:"
	@egrep -o "^#: (.+)" [Mm]akefile | sed 's/#: /* /'

#: deps - Install dependencies.
.PHONY: deps
deps:
	pip install -r web/requirements.txt

#: test - Runs tests.
.PHONY: test
test:
	$(MAKE) -C web test

#: coveralls - Submit coverage stats to coveralls
coveralls:
	$(MAKE) -C web coveralls

#: ci-test - Runs CI in Travis.
.PHONY: ci-test
ci-test:
	$(MAKE) -C web ci-test

#: lint - Runs linters.
.PHONY: lint
lint:
	$(MAKE) -C web lint

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

