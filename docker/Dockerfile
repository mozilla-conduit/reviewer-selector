FROM python:3.12

ARG GH_VERSION=2.89.0

ARG BUILTIN_HERALD_RULES=herald_rules.json

# Lift the build arguments into runtime environment variables.
ENV GH_VERSION=${GH_VERSION}
ENV DEFAULT_HERALD_RULES_JSON=${BUILTIN_HERALD_RULES}

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

RUN curl -L https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.deb -o /tmp/gh.deb \
  && dpkg -i /tmp/gh.deb

RUN mkdir /app
WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

# %include .

COPY topsrcdir/ /app
RUN uv sync --frozen \
  && uv pip install /app

ENTRYPOINT [ "/app/docker/entrypoint.sh" ]
