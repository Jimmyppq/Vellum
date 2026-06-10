from app.providers.base import BaseProvider


def get_provider(settings) -> BaseProvider:
    engine = settings.DB_ENGINE.lower()
    if engine == "postgres":
        from app.providers.postgres import PostgresProvider
        return PostgresProvider(settings)
    raise ValueError(
        f"Unknown DB_ENGINE '{engine}'. Supported values: postgres"
    )
