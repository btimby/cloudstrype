.PHONY: test
test:
	coverage run --include=cloudstrype/* manage.py test

.PHONY: ci-test
ci-test:
	DJANGO_SETTINGS_MODULE="cloudstrype.settings_travis_ci" coverage run --include=cloudstrype/* manage.py test

.PHONY: run
run:
	python manage.py runserver
