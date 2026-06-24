"""create core data models

Revision ID: 202606240001
Revises:
Create Date: 2026-06-24 00:01:00.000000
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202606240001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", UUID, nullable=True),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE SCHEMA IF NOT EXISTS iam")
    op.execute("CREATE SCHEMA IF NOT EXISTS asset")
    op.execute("CREATE SCHEMA IF NOT EXISTS telemetry")
    op.execute("CREATE SCHEMA IF NOT EXISTS monitoring")

    op.create_table("tenants", *audit_columns(), sa.Column("name", sa.String(120), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="active"), schema="iam")
    op.create_table("organizations", *audit_columns(), sa.Column("name", sa.String(160), nullable=False), sa.Column("code", sa.String(80), nullable=False), sa.Column("parent_id", UUID, nullable=True), sa.ForeignKeyConstraint(["parent_id"], ["iam.organizations.id"], ondelete="SET NULL"), sa.UniqueConstraint("code", name="uq_organizations_code"), schema="iam")
    op.create_table("roles", *audit_columns(), sa.Column("name", sa.String(120), nullable=False), sa.Column("code", sa.String(80), nullable=False), sa.Column("description", sa.String(500), nullable=True), sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()), sa.UniqueConstraint("code", name="uq_roles_code"), schema="iam")
    op.create_table("users", *audit_columns(), sa.Column("tenant_id", UUID, nullable=True), sa.Column("organization_id", UUID, nullable=True), sa.Column("email", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="active"), sa.ForeignKeyConstraint(["tenant_id"], ["iam.tenants.id"]), sa.ForeignKeyConstraint(["organization_id"], ["iam.organizations.id"], ondelete="SET NULL"), sa.UniqueConstraint("email", name="uq_users_email"), schema="iam")
    op.create_table("user_roles", sa.Column("user_id", UUID, nullable=False), sa.Column("role_id", UUID, nullable=False), sa.ForeignKeyConstraint(["user_id"], ["iam.users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["role_id"], ["iam.roles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("user_id", "role_id"), schema="iam")

    op.create_table("refresh_tokens", *audit_columns(), sa.Column("user_id", UUID, nullable=False), sa.Column("token_hash", sa.String(128), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True), sa.Column("replaced_by_token_hash", sa.String(128), nullable=True), sa.ForeignKeyConstraint(["user_id"], ["iam.users.id"], ondelete="CASCADE"), sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"), schema="iam")

    op.create_table("pipelines", *audit_columns(), sa.Column("organization_id", UUID, nullable=True), sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("pipeline_type", sa.String(40), nullable=False), sa.Column("material", sa.String(80), nullable=True), sa.Column("diameter_mm", sa.Numeric(10, 2), nullable=True), sa.Column("depth_m", sa.Numeric(6, 2), nullable=True), sa.Column("length_m", sa.Numeric(12, 2), nullable=True), sa.Column("risk_grade", sa.String(1), nullable=True), sa.Column("installed_at", sa.Date(), nullable=True), sa.Column("geom", geoalchemy2.Geometry("LINESTRING", srid=4326, spatial_index=True), nullable=False), sa.Column("properties", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.ForeignKeyConstraint(["organization_id"], ["iam.organizations.id"], ondelete="SET NULL"), sa.UniqueConstraint("code", name="uq_pipelines_code"), schema="asset")
    op.create_table("pipeline_images", *audit_columns(), sa.Column("pipeline_id", UUID, nullable=False), sa.Column("image_url", sa.String(1000), nullable=False), sa.Column("thumbnail_url", sa.String(1000), nullable=True), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True), sa.Column("caption", sa.Text(), nullable=True), sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.ForeignKeyConstraint(["pipeline_id"], ["asset.pipelines.id"], ondelete="CASCADE"), schema="asset")
    op.create_table("sensors", *audit_columns(), sa.Column("pipeline_id", UUID, nullable=True), sa.Column("sensor_code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("sensor_type", sa.String(40), nullable=False), sa.Column("unit", sa.String(20), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="Online"), sa.Column("min_value", sa.Numeric(12, 4), nullable=True), sa.Column("max_value", sa.Numeric(12, 4), nullable=True), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True), sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326, spatial_index=True), nullable=False), sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.ForeignKeyConstraint(["pipeline_id"], ["asset.pipelines.id"], ondelete="SET NULL"), sa.UniqueConstraint("sensor_code", name="uq_sensors_sensor_code"), schema="asset")

    op.create_table("sensor_data", *audit_columns(), sa.Column("sensor_id", UUID, nullable=False), sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("value", sa.Numeric(14, 4), nullable=False), sa.Column("unit", sa.String(20), nullable=False), sa.Column("quality", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("raw_payload", JSONB, nullable=True), sa.ForeignKeyConstraint(["sensor_id"], ["asset.sensors.id"], ondelete="CASCADE"), schema="telemetry")

    op.create_table("ai_analyses", *audit_columns(), sa.Column("pipeline_id", UUID, nullable=True), sa.Column("sensor_id", UUID, nullable=True), sa.Column("model_name", sa.String(120), nullable=False), sa.Column("model_version", sa.String(80), nullable=False), sa.Column("analysis_type", sa.String(80), nullable=False), sa.Column("risk_score", sa.Numeric(5, 2), nullable=False), sa.Column("severity", sa.String(30), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True), sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.ForeignKeyConstraint(["pipeline_id"], ["asset.pipelines.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["sensor_id"], ["asset.sensors.id"], ondelete="SET NULL"), schema="monitoring")
    op.create_table("risk_events", *audit_columns(), sa.Column("pipeline_id", UUID, nullable=True), sa.Column("sensor_id", UUID, nullable=True), sa.Column("assignee_id", UUID, nullable=True), sa.Column("ai_analysis_id", UUID, nullable=True), sa.Column("event_code", sa.String(80), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("severity", sa.String(30), nullable=False), sa.Column("risk_score", sa.Numeric(5, 2), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="Open"), sa.Column("location", geoalchemy2.Geometry("POINT", srid=4326, spatial_index=True), nullable=True), sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False), sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True), sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.ForeignKeyConstraint(["pipeline_id"], ["asset.pipelines.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["sensor_id"], ["asset.sensors.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["assignee_id"], ["iam.users.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["ai_analysis_id"], ["monitoring.ai_analyses.id"], ondelete="SET NULL"), schema="monitoring")
    op.create_table("notifications", *audit_columns(), sa.Column("risk_event_id", UUID, nullable=True), sa.Column("recipient_id", UUID, nullable=True), sa.Column("channel", sa.String(40), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="Pending"), sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True), sa.Column("read_at", sa.DateTime(timezone=True), nullable=True), sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.ForeignKeyConstraint(["risk_event_id"], ["monitoring.risk_events.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["recipient_id"], ["iam.users.id"], ondelete="SET NULL"), schema="monitoring")
    op.create_table("action_work_orders", *audit_columns(), sa.Column("risk_event_id", UUID, nullable=False), sa.Column("assignee_id", UUID, nullable=True), sa.Column("issued_by_id", UUID, nullable=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("instruction", sa.Text(), nullable=False), sa.Column("priority", sa.String(30), nullable=False, server_default="Medium"), sa.Column("status", sa.String(30), nullable=False, server_default="Issued"), sa.Column("due_at", sa.DateTime(timezone=True), nullable=True), sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completion_summary", sa.Text(), nullable=True), sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("photo_urls", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")), sa.ForeignKeyConstraint(["risk_event_id"], ["monitoring.risk_events.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["assignee_id"], ["iam.users.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["issued_by_id"], ["iam.users.id"], ondelete="SET NULL"), schema="monitoring")
    op.create_table("action_histories", *audit_columns(), sa.Column("risk_event_id", UUID, nullable=True), sa.Column("actor_id", UUID, nullable=True), sa.Column("action_type", sa.String(80), nullable=False), sa.Column("status_from", sa.String(30), nullable=True), sa.Column("status_to", sa.String(30), nullable=True), sa.Column("comment", sa.Text(), nullable=True), sa.Column("action_at", sa.DateTime(timezone=True), nullable=False), sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("photo_urls", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")), sa.ForeignKeyConstraint(["risk_event_id"], ["monitoring.risk_events.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["actor_id"], ["iam.users.id"], ondelete="SET NULL"), schema="monitoring")

    for schema, table in [("iam", "tenants"), ("iam", "organizations"), ("iam", "roles"), ("iam", "users"), ("iam", "refresh_tokens"), ("asset", "pipelines"), ("asset", "pipeline_images"), ("asset", "sensors"), ("telemetry", "sensor_data"), ("monitoring", "ai_analyses"), ("monitoring", "risk_events"), ("monitoring", "notifications"), ("monitoring", "action_work_orders"), ("monitoring", "action_histories")]:
        op.create_foreign_key(f"fk_{table}_created_by_users", table, "users", ["created_by"], ["id"], source_schema=schema, referent_schema="iam", ondelete="SET NULL")
        op.create_index(f"ix_{table}_created_by", table, ["created_by"], schema=schema)

    op.create_index("ix_users_email", "users", ["email"], schema="iam")
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], schema="iam")
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], schema="iam")
    op.create_index("ix_pipelines_code", "pipelines", ["code"], schema="asset")
    op.create_index("ix_sensors_sensor_code", "sensors", ["sensor_code"], schema="asset")
    op.create_index("ix_sensor_data_sensor_time", "sensor_data", ["sensor_id", "measured_at"], schema="telemetry")
    op.create_index("ix_ai_analyses_pipeline", "ai_analyses", ["pipeline_id"], schema="monitoring")
    op.create_index("ix_risk_events_status_severity", "risk_events", ["status", "severity"], schema="monitoring")
    op.create_index("ix_risk_events_event_code", "risk_events", ["event_code"], unique=True, schema="monitoring")
    op.create_index("ix_risk_events_detected_at", "risk_events", ["detected_at"], schema="monitoring")
    op.create_index("ix_risk_events_assignee_id", "risk_events", ["assignee_id"], schema="monitoring")
    op.create_index("ix_notifications_recipient_status", "notifications", ["recipient_id", "status"], schema="monitoring")
    op.create_index("ix_action_work_orders_status_priority", "action_work_orders", ["status", "priority"], schema="monitoring")
    op.create_index("ix_action_work_orders_assignee_id", "action_work_orders", ["assignee_id"], schema="monitoring")


def downgrade() -> None:
    op.drop_table("action_histories", schema="monitoring")
    op.drop_table("action_work_orders", schema="monitoring")
    op.drop_table("notifications", schema="monitoring")
    op.drop_table("risk_events", schema="monitoring")
    op.drop_table("ai_analyses", schema="monitoring")
    op.drop_table("sensor_data", schema="telemetry")
    op.drop_table("sensors", schema="asset")
    op.drop_table("pipeline_images", schema="asset")
    op.drop_table("pipelines", schema="asset")
    op.drop_table("refresh_tokens", schema="iam")
    op.drop_table("user_roles", schema="iam")
    op.drop_table("users", schema="iam")
    op.drop_table("roles", schema="iam")
    op.drop_table("organizations", schema="iam")
    op.drop_table("tenants", schema="iam")
    op.execute("DROP SCHEMA IF EXISTS monitoring")
    op.execute("DROP SCHEMA IF EXISTS telemetry")
    op.execute("DROP SCHEMA IF EXISTS asset")
    op.execute("DROP SCHEMA IF EXISTS iam")
