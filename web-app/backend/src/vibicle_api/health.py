"""Container readiness probe for the API listener and runtime database login."""

import socket
import sys

from sqlalchemy.exc import SQLAlchemyError

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine


def main() -> int:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=2):
            pass
    except OSError:
        print("API_UNAVAILABLE: listener check failed.", file=sys.stderr)
        return 1

    engine = make_engine(get_settings())
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except SQLAlchemyError:
        print("DB_UNAVAILABLE: readiness check failed.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
