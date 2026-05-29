FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/deps -r requirements.txt

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/deps

RUN useradd -m -s /bin/sh appuser

WORKDIR /app

COPY --from=builder /build/deps /app/deps
COPY app/ /app/app/
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app

VOLUME ["/logs", "/app/config"]

EXPOSE 8000

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
