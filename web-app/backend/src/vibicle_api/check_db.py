"""Development-only CLI, not an HTTP diagnostic endpoint."""

import json
import sys

from sqlalchemy.exc import SQLAlchemyError

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine
from vibicle_api.repositories.database import DatabaseRepository


def main() -> int:
    settings = get_settings()
    if settings.api_env != "development":
        print("DB_DIAGNOSTIC_DISABLED: development only.", file=sys.stderr)
        return 2
    engine = make_engine(settings)
    try:
        print(json.dumps(DatabaseRepository(engine).probe(), ensure_ascii=False))
        return 0
    except SQLAlchemyError:
        # No exception string: it may contain connection parameters.
        print("DB_UNAVAILABLE: connection/query failed; no empty-data result.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
