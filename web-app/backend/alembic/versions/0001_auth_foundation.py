"""Three approved Authentication tables. No Login Attempt or business tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_auth_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_app_users"),
        sa.UniqueConstraint("email", name="uq_app_users_email"),
        sa.CheckConstraint(
            "email = lower(email) AND email = btrim(email)"
            " AND char_length(email) BETWEEN 1 AND 254",
            name="ck_app_users_email_canonical",
        ),
        sa.CheckConstraint("char_length(password_hash) > 0", name="ck_app_users_password_hash"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_secret", sa.LargeBinary(), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'authenticated'"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token_hash", name="pk_auth_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
            name="fk_auth_sessions_user_id",
        ),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="ck_auth_sessions_token_length"),
        sa.CheckConstraint("octet_length(csrf_secret) = 32", name="ck_auth_sessions_csrf_length"),
        sa.CheckConstraint("kind IN ('authenticated', 'preauth')", name="ck_auth_sessions_kind"),
        sa.CheckConstraint(
            "(kind = 'authenticated' AND user_id IS NOT NULL)"
            " OR (kind = 'preauth' AND user_id IS NULL)",
            name="ck_auth_sessions_kind_user",
        ),
        sa.CheckConstraint(
            "created_at <= last_activity_at AND last_activity_at < absolute_expires_at",
            name="ck_auth_sessions_time_order",
        ),
        sa.CheckConstraint(
            "kind <> 'authenticated' OR absolute_expires_at = created_at + INTERVAL '8 hours'",
            name="ck_auth_sessions_authenticated_ttl",
        ),
        sa.CheckConstraint(
            "kind <> 'preauth'"
            " OR (absolute_expires_at = created_at + INTERVAL '15 minutes'"
            " AND last_activity_at = created_at)",
            name="ck_auth_sessions_preauth_ttl",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_sessions_revoked_time"
        ),
    )
    op.create_index(
        "ix_auth_sessions_absolute_expires_at", "auth_sessions", ["absolute_expires_at"]
    )
    op.create_table(
        "auth_rate_limit_buckets",
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("subject_hash", sa.LargeBinary(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "scope", "subject_hash", "window_start", name="pk_auth_rate_limit_buckets"
        ),
        sa.CheckConstraint(
            "scope IN ('login', 'register', 'csrf_context')", name="ck_auth_buckets_scope"
        ),
        sa.CheckConstraint(
            "octet_length(subject_hash) = 32", name="ck_auth_buckets_subject_length"
        ),
        sa.CheckConstraint("attempt_count > 0", name="ck_auth_buckets_attempt_count"),
        sa.CheckConstraint("expires_at > window_start", name="ck_auth_buckets_expiry"),
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_expires_at", "auth_rate_limit_buckets", ["expires_at"]
    )


def downgrade() -> None:
    # Only use on a disposable DB; this intentionally removes the three tables.
    op.drop_index("ix_auth_rate_limit_buckets_expires_at", table_name="auth_rate_limit_buckets")
    op.drop_table("auth_rate_limit_buckets")
    op.drop_index("ix_auth_sessions_absolute_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("app_users")
