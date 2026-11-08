"""Approved Authentication data dictionary only; no login business logic."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_app_users_email"),
        CheckConstraint(
            "email = lower(email) AND email = btrim(email)"
            " AND char_length(email) BETWEEN 1 AND 254",
            name="ck_app_users_email_canonical",
        ),
        CheckConstraint("char_length(password_hash) > 0", name="ck_app_users_password_hash"),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("octet_length(token_hash) = 32", name="ck_auth_sessions_token_length"),
        CheckConstraint("octet_length(csrf_secret) = 32", name="ck_auth_sessions_csrf_length"),
        CheckConstraint("kind IN ('authenticated', 'preauth')", name="ck_auth_sessions_kind"),
        CheckConstraint(
            "(kind = 'authenticated' AND user_id IS NOT NULL)"
            " OR (kind = 'preauth' AND user_id IS NULL)",
            name="ck_auth_sessions_kind_user",
        ),
        CheckConstraint(
            "created_at <= last_activity_at AND last_activity_at < absolute_expires_at",
            name="ck_auth_sessions_time_order",
        ),
        CheckConstraint(
            "kind <> 'authenticated' OR absolute_expires_at = created_at + INTERVAL '8 hours'",
            name="ck_auth_sessions_authenticated_ttl",
        ),
        CheckConstraint(
            "kind <> 'preauth' OR (absolute_expires_at = created_at + INTERVAL '15 minutes'"
            " AND last_activity_at = created_at)",
            name="ck_auth_sessions_preauth_ttl",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_sessions_revoked_time"
        ),
        Index("ix_auth_sessions_absolute_expires_at", "absolute_expires_at"),
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    csrf_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'authenticated'"))
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_users.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthRateLimitBucket(Base):
    __tablename__ = "auth_rate_limit_buckets"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('login', 'register', 'csrf_context')", name="ck_auth_buckets_scope"
        ),
        CheckConstraint("octet_length(subject_hash) = 32", name="ck_auth_buckets_subject_length"),
        CheckConstraint("attempt_count > 0", name="ck_auth_buckets_attempt_count"),
        CheckConstraint("expires_at > window_start", name="ck_auth_buckets_expiry"),
        Index("ix_auth_rate_limit_buckets_expires_at", "expires_at"),
    )
    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("vin", name="uq_vehicles_vin"),
        CheckConstraint("vin ~ '^[A-HJ-NPR-Z0-9]{17}$'", name="ck_vehicles_vin"),
        CheckConstraint(
            "brand = btrim(brand) AND char_length(brand) BETWEEN 1 AND 50",
            name="ck_vehicles_brand",
        ),
        CheckConstraint(
            "model = btrim(model) AND char_length(model) BETWEEN 1 AND 100",
            name="ck_vehicles_model",
        ),
        CheckConstraint("model_year BETWEEN 1900 AND 9999", name="ck_vehicles_year"),
        CheckConstraint("current_mileage_km BETWEEN 0 AND 2000000", name="ck_vehicles_mileage"),
        CheckConstraint("char_length(description) <= 2000", name="ck_vehicles_description"),
        CheckConstraint("price_twd BETWEEN 1 AND 100000000", name="ck_vehicles_price"),
        CheckConstraint(
            "NOT is_listed OR (price_twd IS NOT NULL AND current_image_id IS NOT NULL"
            " AND last_listed_at IS NOT NULL)",
            name="ck_vehicles_listing",
        ),
        CheckConstraint("row_version > 0", name="ck_vehicles_revision"),
        CheckConstraint("updated_at >= created_at", name="ck_vehicles_time_order"),
        ForeignKeyConstraint(
            ["id", "current_image_id"],
            ["vehicle_images.vehicle_id", "vehicle_images.id"],
            name="fk_vehicles_current_image",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
            use_alter=True,
        ),
        Index("ix_vehicles_garage", "owner_user_id", text("created_at DESC"), text("id DESC")),
        Index(
            "ix_vehicles_marketplace",
            text("last_listed_at DESC"),
            text("id DESC"),
            postgresql_where=text("is_listed"),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    vin: Mapped[str] = mapped_column(Text)
    brand: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    model_year: Mapped[int] = mapped_column(SmallInteger)
    current_mileage_km: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    price_twd: Mapped[int | None] = mapped_column(Integer)
    is_listed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_image_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    row_version: Mapped[int] = mapped_column(BigInteger, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )


class VehicleMileageChange(Base):
    __tablename__ = "vehicle_mileage_changes"
    __table_args__ = (
        UniqueConstraint("vehicle_id", "vehicle_revision", name="uq_vehicle_mileage_revision"),
        CheckConstraint("vehicle_revision > 0", name="ck_vehicle_mileage_revision"),
        CheckConstraint(
            "previous_mileage_km BETWEEN 0 AND 2000000 AND previous_mileage_km <> new_mileage_km",
            name="ck_vehicle_mileage_previous",
        ),
        CheckConstraint("new_mileage_km BETWEEN 0 AND 2000000", name="ck_vehicle_mileage_new"),
        CheckConstraint(
            "(reason IS NULL OR (reason = btrim(reason) AND char_length(reason) BETWEEN 1 AND 500))"
            " AND (previous_mileage_km IS NULL OR new_mileage_km >= previous_mileage_km"
            " OR reason IS NOT NULL)",
            name="ck_vehicle_mileage_reason",
        ),
        Index(
            "uq_vehicle_mileage_initial",
            "vehicle_id",
            unique=True,
            postgresql_where=text("previous_mileage_km IS NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    vehicle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    previous_mileage_km: Mapped[int | None] = mapped_column(Integer)
    new_mileage_km: Mapped[int] = mapped_column(Integer)
    vehicle_revision: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )


class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "current_version_id"],
            ["maintenance_record_versions.event_id", "maintenance_record_versions.id"],
            name="fk_maintenance_event_current_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index("ix_maintenance_events_vehicle", "vehicle_id"),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    vehicle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    current_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )


class MaintenanceRecordVersion(Base):
    __tablename__ = "maintenance_record_versions"
    __table_args__ = (
        UniqueConstraint("event_id", "id", name="uq_maintenance_version_event_id"),
        UniqueConstraint("event_id", "version_no", name="uq_maintenance_version_number"),
        UniqueConstraint("previous_version_id", name="uq_maintenance_version_previous"),
        ForeignKeyConstraint(
            ["event_id", "previous_version_id"],
            ["maintenance_record_versions.event_id", "maintenance_record_versions.id"],
            name="fk_maintenance_version_previous_same_event",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        CheckConstraint("version_no >= 1", name="ck_maintenance_version_number"),
        CheckConstraint(
            "previous_version_id IS NULL OR previous_version_id <> id",
            name="ck_maintenance_version_not_self",
        ),
        CheckConstraint(
            "(version_no = 1 AND previous_version_id IS NULL AND correction_reason IS NULL)"
            " OR (version_no > 1 AND previous_version_id IS NOT NULL"
            " AND correction_reason IS NOT NULL AND correction_reason = btrim(correction_reason)"
            " AND char_length(correction_reason) BETWEEN 1 AND 500)",
            name="ck_maintenance_version_shape",
        ),
        CheckConstraint("maintenance_date >= DATE '1900-01-01'", name="ck_maintenance_date"),
        CheckConstraint("mileage_km BETWEEN 0 AND 2000000", name="ck_maintenance_mileage"),
        CheckConstraint(
            "description = btrim(description) AND char_length(description) BETWEEN 1 AND 2000",
            name="ck_maintenance_description",
        ),
        CheckConstraint("source = 'owner_self_reported'", name="ck_maintenance_source"),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("maintenance_events.id", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    previous_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    version_no: Mapped[int] = mapped_column(Integer)
    maintenance_date: Mapped[date] = mapped_column(Date)
    mileage_km: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    correction_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default=text("'owner_self_reported'"))
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )


class VehicleImage(Base):
    __tablename__ = "vehicle_images"
    __table_args__ = (
        UniqueConstraint("vehicle_id", "id", name="uq_vehicle_images_vehicle_id"),
        CheckConstraint("expected_vehicle_version > 0", name="ck_vehicle_images_revision"),
        CheckConstraint(
            "status IN ('pending','processing','ready','failed','deleting','deleted')",
            name="ck_vehicle_images_status",
        ),
        CheckConstraint(
            "media_type IN ('image/jpeg','image/png','image/webp')", name="ck_vehicle_images_media"
        ),
        CheckConstraint("byte_size BETWEEN 1 AND 5242880", name="ck_vehicle_images_size"),
        CheckConstraint("width_px BETWEEN 1 AND 6000", name="ck_vehicle_images_width"),
        CheckConstraint("height_px BETWEEN 1 AND 6000", name="ck_vehicle_images_height"),
        CheckConstraint("width_px * height_px <= 12000000", name="ck_vehicle_images_pixels"),
        CheckConstraint(
            "status <> 'ready' OR (media_type IS NOT NULL AND byte_size IS NOT NULL"
            " AND width_px IS NOT NULL AND height_px IS NOT NULL AND processed_at IS NOT NULL)",
            name="ck_vehicle_images_ready",
        ),
        CheckConstraint(
            "(status IN ('pending','processing','deleting') AND work_token IS NOT NULL"
            " AND lease_expires_at IS NOT NULL AND lease_expires_at > created_at)"
            " OR (status IN ('ready','failed','deleted') AND work_token IS NULL"
            " AND lease_expires_at IS NULL)",
            name="ck_vehicle_images_lease",
        ),
        CheckConstraint(
            "status <> 'failed' OR (last_error_code IS NOT NULL AND length(last_error_code) > 0)",
            name="ck_vehicle_images_error",
        ),
        CheckConstraint(
            "(status = 'deleted') = (deleted_at IS NOT NULL)", name="ck_vehicle_images_deleted"
        ),
        CheckConstraint(
            "updated_at >= created_at AND (processed_at IS NULL OR processed_at >= created_at)"
            " AND (deleted_at IS NULL OR deleted_at >= created_at)",
            name="ck_vehicle_images_time",
        ),
        Index("ix_vehicle_images_cleanup", "status", "updated_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    vehicle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    expected_vehicle_version: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    media_type: Mapped[str | None] = mapped_column(Text)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    work_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("statement_timestamp()")
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
