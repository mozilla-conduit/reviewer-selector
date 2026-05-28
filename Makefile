DOCKER_TAG=reviewer-selector

build: DOCKER_ARGS=--build-arg BUILTIN_HERALD_RULES=herald_rules.json
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

.PHONY:
requirements: requirements-dev.txt requirements.txt

requirements.txt: pyproject.toml
	uv pip install .[dev]
	uv run pip-compile --allow-unsafe --generate-hashes --output-file=${@}

requirements-dev.txt: pyproject.toml
	uv pip install .[dev]
	uv run pip-compile --allow-unsafe --generate-hashes --extra=dev --output-file=${@}

.PHONY: test
test:
	uv pip install .[dev]
	uv run pytest tests/

.PHONY: test-docker
test-docker:
	docker run --rm --entrypoint bash ${DOCKER_TAG} \
		-c 'pip install -r requirements-dev.txt && pytest tests/'
