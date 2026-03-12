# Build:
#     docker build -t reviewer-selector .
#
# Usage:
#     curl -L https://github.com/mozilla-firefox/infra-testing/pull/30.diff | docker run --rm -i reviewer-selector:latest
# or
#     docker run --rm -i -e PR=https://github.com/mozilla-firefox/infra-testing/pull/30 -e DIFF_URL=https://github.com/mozilla-firefox/infra-testing/pull/30.diff -e GITHUB_TOKEN=eee reviewer-selector
#
FROM python:3.14

RUN apt-get -y update \
  && apt-get -y install \
    gh \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app

RUN --mount=type=bind,src=requirements.txt,target=/app/requirements.txt pip install -r requirements.txt

COPY reviewer_selector.py entrypoint.sh /app/
COPY herald_rules.sample.json /app/herald_rules.json

CMD [ "herald_rules.json" ]

ENTRYPOINT [ "/app/entrypoint.sh" ]
