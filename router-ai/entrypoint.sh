#!/bin/sh
if [ "$MTLS_ENABLED" = "true" ]; then
  exec python -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --ssl-keyfile "$MTLS_KEY_PATH" \
    --ssl-certfile "$MTLS_CERT_PATH" \
    --ssl-ca-certs "$MTLS_CA_PATH"
else
  exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
