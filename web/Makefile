.PHONY: test
test:
	$(MAKE) -C cloudstrype test

.PHONY: coveralls
coveralls:
	$(MAKE) -C cloudstrype coveralls

.PHONY: travis-ci
ci-test:
	$(MAKE) -C cloudstrype ci-test

.PHONY: lint
lint:
	flake8 cloudstrype

.PHONY: run
run:
	$(MAKE) -C cloudstrype run
