# docker build -t reviewer-selector .
# curl -L https://github.com/mozilla-firefox/infra-testing/pull/30.diff | docker run --rm -i reviewer-selector:latest
FROM python:3.14

RUN mkdir /app
WORKDIR /app

RUN --mount=type=bind,src=requirements.txt,target=/app/requirements.txt pip install -r requirements.txt

COPY reviewer_selector.py /app/reviewer_selector.py
COPY herald_rules.json /app/herald_rules.json

CMD [ "herald_rules.json" ]

ENTRYPOINT [ "/app/reviewer_selector.py" ]
