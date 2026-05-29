import logging
import logging.handlers
import os
import json
import datetime as dt


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "timestamp": dt.datetime.fromtimestamp(record.created, dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Añadir campos extra que los callers puedan inyectar con extra={}
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                base[key] = value
        return json.dumps(base, default=str)


def setup_logging(log_level: str, log_dir: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = JsonFormatter()

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # Handler stdout
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # Handler archivo rotativo (si el directorio es accesible)
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "router-ai.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as e:
        root.warning("No se pudo configurar el log en archivo: %s. Usando solo stdout.", e)
