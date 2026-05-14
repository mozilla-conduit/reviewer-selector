build: DOCKER_TAG=reviewer-selector
build: DOCKER_ARGS=
.PHONY: build
build:
	# This symlink is needed for non-TaskCluster/TaskGraph builds to succeed, ignoring extended Dockerfile syntax [0].
	# https://taskcluster-taskgraph.readthedocs.io/en/latest/howto/docker.html#special-dockerfile-syntax
	test -e topsrcdir || ln -sf .. topsrcdir
	docker build -f docker/Dockerfile -t ${DOCKER_TAG} ${DOCKER_ARGS} .

.PHONY: format
format:
	uv run ruff format
	uv run ruff check --fix
