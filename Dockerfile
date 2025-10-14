# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install system dependencies required by popular Python packages.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -e .

COPY docs ./docs
COPY scripts ./scripts
COPY infra ./infra

EXPOSE 8000

CMD ["uvicorn", "azt3knet.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
