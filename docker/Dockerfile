FROM python:3.14

RUN apt-get -y update \
  && apt-get -y install \
    gh \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app

RUN --mount=type=bind,src=../requirements.txt,target=/app/requirements.txt pip install -r requirements.txt

COPY ../src/reviewer_selector.py ../docker/entrypoint.sh /app/
# Example for self-contained quick tests.
COPY ../samples/herald_rules.sample.json /app/herald_rules.json

CMD [ "herald_rules.json" ]

ENTRYPOINT [ "/app/entrypoint.sh" ]
