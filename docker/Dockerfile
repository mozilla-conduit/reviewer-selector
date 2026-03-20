FROM python:3.14

RUN apt-get -y update \
  && apt-get -y install \
    gh \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app

RUN --mount=type=bind,src=../requirements.txt,target=/app/requirements.txt pip install -r requirements.txt

COPY . /app
RUN pip install /app

CMD [ "samples/herald_rules.json" ]

ENTRYPOINT [ "/app/docker/entrypoint.sh" ]
