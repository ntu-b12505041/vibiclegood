"""SQLAlchemy Engine creation is lazy; it does not prove a database is reachable."""

from sqlalchemy import Engine, create_engine

from vibicle_api.config import Settings


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        pool_timeout=5,
        connect_args={
            "connect_timeout": 3,
            "options": "-c timezone=UTC -c lock_timeout=5000 -c statement_timeout=10000",
        },
        hide_parameters=True,
    )
