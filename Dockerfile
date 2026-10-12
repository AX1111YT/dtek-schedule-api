# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home app

COPY dtek_api ./dtek_api

USER app
EXPOSE 8000

CMD ["python", "-m", "dtek_api"]
