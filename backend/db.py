import os
from pathlib import Path

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, JSON, MetaData,
    String, Table, UniqueConstraint, create_engine, event,
)

metadata = MetaData()
factories = Table("factories", metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(120), nullable=False),
)
users = Table("users", metadata,
    Column("id", String(36), primary_key=True),
    Column("factory_id", ForeignKey("factories.id"), nullable=False, index=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(256), nullable=False),
)
sessions = Table("sessions", metadata,
    Column("id_hash", String(64), primary_key=True),
    Column("user_id", ForeignKey("users.id"), nullable=False),
    Column("csrf_hash", String(64), nullable=False),
    Column("expires_at", Float, nullable=False),
)
machines = Table("machines", metadata,
    Column("id", String(36), primary_key=True),
    Column("factory_id", ForeignKey("factories.id"), nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("temperature_min", Float, nullable=False),
    Column("temperature_max", Float, nullable=False),
    Column("rpm_max", Float, nullable=False),
    Column("pressure_max", Float, nullable=False),
    UniqueConstraint("factory_id", "name"),
    CheckConstraint("temperature_min < temperature_max"),
    CheckConstraint("rpm_max > 0 AND pressure_max > 0"),
)
batches = Table("batches", metadata,
    Column("id", String(36), primary_key=True),
    Column("factory_id", ForeignKey("factories.id"), nullable=False, index=True),
    Column("machine_id", ForeignKey("machines.id"), nullable=False, index=True),
    Column("operator_id", ForeignKey("users.id"), nullable=False),
    Column("code", String(80), nullable=False),
    Column("produced_on", String(10), nullable=False, index=True),
    Column("phase", String(10), nullable=False),
    Column("polymer", String(10), nullable=False),
    Column("purity_pct", Float, nullable=False),
    Column("moisture_pct", Float, nullable=False),
    Column("temperature_c", Float, nullable=False),
    Column("screw_rpm", Float, nullable=False),
    Column("pressure_bar", Float, nullable=False),
    Column("total_kg", Float, nullable=False),
    Column("rejected_kg", Float, nullable=False),
    Column("quality_verified", Boolean, nullable=False, default=False),
    Column("quality_verified_by", ForeignKey("users.id")),
    Column("quality_verified_at", Float),
    UniqueConstraint("factory_id", "code"),
    CheckConstraint("total_kg > 0 AND rejected_kg >= 0 AND rejected_kg <= total_kg"),
    CheckConstraint("purity_pct >= 0 AND purity_pct <= 100 AND moisture_pct >= 0 AND moisture_pct <= 100"),
    CheckConstraint("phase IN ('baseline', 'pilot')"),
)
recommendations = Table("recommendations", metadata,
    Column("id", String(36), primary_key=True),
    Column("factory_id", ForeignKey("factories.id"), nullable=False, index=True),
    Column("machine_id", ForeignKey("machines.id"), nullable=False),
    Column("requested_by", ForeignKey("users.id"), nullable=False),
    Column("polymer", String(10), nullable=False),
    Column("purity_pct", Float, nullable=False),
    Column("moisture_pct", Float, nullable=False),
    Column("model_version", String(80), nullable=False),
    Column("training_count", Integer, nullable=False),
    Column("evaluation", JSON, nullable=False),
    Column("temperature_c", Float, nullable=False),
    Column("screw_rpm", Float, nullable=False),
    Column("pressure_bar", Float, nullable=False),
    Column("created_at", Float, nullable=False),
    Column("approved_by", ForeignKey("users.id")),
    Column("approved_at", Float),
)


def make_engine(url=None):
    default = "sqlite:///" + str(Path(__file__).resolve().parents[1] / "granovo.db")
    engine = create_engine(url or os.environ.get("DATABASE_URL", default), hide_parameters=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


if __name__ == "__main__":
    engine = make_engine()
    metadata.create_all(engine)
    engine.dispose()
    print("Initial schema ready. Existing tables were not changed.")
