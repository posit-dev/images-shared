FROM docker:27-dind

ENV PYTHONUNBUFFERED=1

RUN apk add --update --no-cache curl python3 py3-pip  \
    && ln -sf python3 /usr/bin/python

WORKDIR /app
COPY . /app

RUN curl -sSL https://install.python-poetry.org | python - \
    && ln -s /root/.local/bin/poetry /usr/bin/poetry

RUN python -m venv /app/.venv \
    && source /app/.venv/bin/activate \
    && poetry install --no-cache \
    && deactivate

WORKDIR /data

ENTRYPOINT ["/entrypoint.sh"]
