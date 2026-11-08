"""Development CLI's real database read; never used to fake E05 health."""

from typing import Any

from sqlalchemy import Engine, text


class DatabaseRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def probe(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            result = connection.execute(
                text(
                    "SELECT version() AS version, current_database() AS database,"
                    " current_setting('server_encoding') AS encoding,"
                    " d.datcollate AS lc_collate, d.datctype AS lc_ctype,"
                    " d.datlocprovider AS locale_provider, d.datcollversion AS collation_version"
                    " FROM pg_database AS d WHERE d.datname = current_database()"
                )
            )
            return dict(result.mappings().one())
