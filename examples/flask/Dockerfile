FROM python:alpine

WORKDIR /app

RUN apk update && apk add --no-cache gcc musl-dev python3-dev libffi-dev openssl-dev cargo mariadb-dev

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=1.0.0 \
  FLASK_APP=app.py

RUN pip install "poetry==$POETRY_VERSION"
RUN pip install mysqlclient

COPY poetry.lock pyproject.toml ./
RUN poetry check

RUN poetry config virtualenvs.create false \
  && poetry install --no-root --no-interaction --no-ansi

COPY app.py /app/app.py

CMD ["poetry", "run", "flask", "run", "--host=0.0.0.0"]
