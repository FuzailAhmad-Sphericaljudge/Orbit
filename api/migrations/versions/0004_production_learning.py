"""production learning audit runs

Revision ID: 0004_production_learning
Revises: 0003_telemetry_calibration
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004_production_learning"
down_revision: str | None = "0003_telemetry_calibration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "production_learning_runs" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "production_learning_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=True),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_learning_runs_incident_id", "production_learning_runs", ["incident_id"])
    op.create_index("ix_production_learning_runs_run_type", "production_learning_runs", ["run_type"])


def downgrade() -> None:
    op.drop_index("ix_production_learning_runs_run_type", table_name="production_learning_runs")
    op.drop_index("ix_production_learning_runs_incident_id", table_name="production_learning_runs")
    op.drop_table("production_learning_runs")
