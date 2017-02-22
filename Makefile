.PHONY: travis-ci
travis-ci:
	${MAKE} -C web

deploy.tar.gz: deploy/.ssh/deploy-id_rsa deploy/.ssh/deploy-id_rsa.pub
	tar czf deploy.tar.gz deploy/.ssh

deploy.tar.gz.enc: deploy.tar.gz
	travis encrypt-file -f deploy.tar.gz

