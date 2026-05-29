FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir --target=/build/deps \
        fastapi uvicorn[standard] pydantic pydantic-settings \
        anthropic openai httpx pyyaml

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/deps

WORKDIR /app

COPY --from=builder /build/deps /app/deps
COPY app/ /app/app/

VOLUME ["/logs", "/app/config"]

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
