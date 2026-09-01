"""staging certification and performance evidence

Revision ID: 0005_staging_certification
Revises: 0004_production_learning
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0005_staging_certification"
down_revision: str | None = "0004_production_learning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = inspect(op.get_bind()).get_table_names()
    if "certification_runs" not in tables:
        op.create_table(
            "certification_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("incident_id", sa.String(length=36), nullable=False),
            sa.Column("environment", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("checklist", sa.JSON(), nullable=False),
            sa.Column("performance", sa.JSON(), nullable=False),
            sa.Column("promotion_gates", sa.JSON(), nullable=False),
            sa.Column("notes", sa.JSON(), nullable=False),
            sa.Column("started_by", sa.String(length=120), nullable=False),
            sa.Column("certified_by", sa.String(length=120), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_certification_runs_incident_id", "certification_runs", ["incident_id"])
        op.create_index("ix_certification_runs_status", "certification_runs", ["status"])
    if "certification_measurements" not in tables:
        op.create_table(
            "certification_measurements",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("certification_run_id", sa.String(length=36), nullable=False),
            sa.Column("metric", sa.String(length=80), nullable=False),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(length=30), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=False),
            sa.Column("evidence_reference", sa.Text(), nullable=True),
            sa.Column("recorded_by", sa.String(length=120), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["certification_run_id"], ["certification_runs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_certification_measurements_certification_run_id", "certification_measurements", ["certification_run_id"])
        op.create_index("ix_certification_measurements_metric", "certification_measurements", ["metric"])


def downgrade() -> None:
    op.drop_index("ix_certification_measurements_metric", table_name="certification_measurements")
    op.drop_index("ix_certification_measurements_certification_run_id", table_name="certification_measurements")
    op.drop_table("certification_measurements")
    op.drop_index("ix_certification_runs_status", table_name="certification_runs")
    op.drop_index("ix_certification_runs_incident_id", table_name="certification_runs")
    op.drop_table("certification_runs")
