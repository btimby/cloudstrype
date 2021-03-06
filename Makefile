#: help - Display callable targets.
.PHONY: help
help:
	@echo "Reference card for usual actions in development environment."
	@echo "Here are available targets:"
	@egrep -o "^#: (.+)" [Mm]akefile | sed 's/#: /* /'

#: deps - Install dependencies.
.PHONY: deps
deps:
	pip install -r web/requirements/dev.txt

#: test - Runs tests.
.PHONY: test
test:
	$(MAKE) -C web test

#: coveralls - Submit coverage stats to coveralls
.PHONY: coveralls
coveralls:
	$(MAKE) -C web coveralls

#: coverage - Coverage report
.PHONY: coverage
coverage:
	$(MAKE) -C web coverage

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

#: run - Runs the application
.PHONY: run
run:
	$(MAKE) -C web run

#: deploy - Deploys application to server.
.PHONY: deploy
deploy:
	$(MAKE) -C deploy deploy

.git/hooks/pre-commit: git.hooks.pre-commit
	cp git.hooks.pre-commit .git/hooks/pre-commit

#: git-hooks - Installs git hooks
git-hooks: .git/hooks/pre-commit

#: deploy.tar.gz - Creates tarball with secret contents.
deploy.tar.gz: deploy/.ssh/deploy-id_rsa deploy/.ssh/deploy-id_rsa.pub deploy/.env
	tar czf deploy.tar.gz deploy/.ssh deploy/.env

#: deploy.tar.gz.enc - Encrypts secret tarball for Travis deploy.
deploy.tar.gz.enc: deploy.tar.gz
	travis encrypt-file -f deploy.tar.gz

#: clean - clean up build files.
.PHONY: clean
clean:
	rm -rf deploy.tar.gz venv
