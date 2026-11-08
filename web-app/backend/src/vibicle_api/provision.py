"""Run the migration and provision the restricted app role as the migration user."""

import os

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from vibicle_api.config import get_settings
from vibicle_api.database import make_engine

ROLE_SQL = text("""
DO $provision$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vibicle_runtime') THEN
    CREATE ROLE vibicle_runtime LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOINHERIT;
  END IF;
  EXECUTE format('ALTER ROLE vibicle_runtime PASSWORD %L',
                 current_setting('vibicle.runtime_password'));
END
$provision$
""")
GRANTS = (
    "GRANT USAGE ON SCHEMA public TO vibicle_runtime",
    "GRANT SELECT, INSERT ON app_users TO vibicle_runtime",
    "GRANT SELECT, INSERT ON auth_sessions TO vibicle_runtime",
    "GRANT UPDATE (last_activity_at, revoked_at) ON auth_sessions TO vibicle_runtime",
    "GRANT SELECT, INSERT ON auth_rate_limit_buckets TO vibicle_runtime",
    "GRANT UPDATE (attempt_count) ON auth_rate_limit_buckets TO vibicle_runtime",
    "GRANT SELECT, INSERT ON vehicles TO vibicle_runtime",
    "GRANT UPDATE (brand, model, model_year, description, current_mileage_km, price_twd,"
    " is_listed, last_listed_at, current_image_id, row_version, updated_at) "
    "ON vehicles TO vibicle_runtime",
    "GRANT SELECT, INSERT ON maintenance_events TO vibicle_runtime",
    "GRANT UPDATE (current_version_id) ON maintenance_events TO vibicle_runtime",
    "GRANT SELECT, INSERT ON maintenance_record_versions, vehicle_mileage_changes "
    "TO vibicle_runtime",
    "GRANT SELECT, INSERT ON vehicle_images TO vibicle_runtime",
    "GRANT UPDATE (status, media_type, byte_size, width_px, height_px, work_token,"
    " lease_expires_at, last_error_code, updated_at, processed_at, deleted_at)"
    " ON vehicle_images TO vibicle_runtime",
)


def main() -> None:
    secret = os.environ["RUNTIME_PASSWORD"]
    if len(secret) < 32 or secret.startswith("replace_with_"):
        raise SystemExit("Set a separate runtime password of at least 32 characters.")
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(get_settings())
    try:
        with engine.begin() as connection:
            connection.execute(
                text("SELECT set_config('vibicle.runtime_password', :password, true)"),
                {"password": secret},
            )
            connection.execute(ROLE_SQL)
            for statement in GRANTS:
                connection.execute(text(statement))
        print("Migration and application grants ready.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
