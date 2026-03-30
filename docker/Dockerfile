FROM python:3.12

ARG BUILTIN_HERALD_RULES=samples/herald_rules.json
# Lift the build argument into a runtime environment variable.
ENV DEFAULT_HERALD_RULES_JSON=${BUILTIN_HERALD_RULES}

RUN apt-get -y update \
  && apt-get -y install \
    gh \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app

RUN --mount=type=bind,src=../requirements.txt,target=/app/requirements.txt pip install -r requirements.txt

COPY . /app
RUN pip install /app

ENTRYPOINT [ "/app/docker/entrypoint.sh" ]
