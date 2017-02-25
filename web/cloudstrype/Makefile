.PHONY: lint
lint:
	flake8 .

.PHONY: test
test:
	coverage run manage.py test

.PHONY: coveralls
coveralls:
	coveralls -v

.PHONY: ci-test
ci-test:
	coverage run manage.py test

.PHONY: run
run:
	python manage.py runserver
