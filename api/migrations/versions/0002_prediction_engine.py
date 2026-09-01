"""prediction engine and simulation persistence

Revision ID: 0002_prediction_engine
Revises: 0001_orbit_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_prediction_engine"
down_revision = "0001_orbit_baseline"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "prediction_runs" not in existing:
        op.create_table("prediction_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False), sa.Column("horizon_minutes", sa.Integer(), nullable=False), sa.Column("model_version", sa.String(40), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("input_snapshot", sa.JSON(), nullable=False), sa.Column("forecast", sa.JSON(), nullable=False), sa.Column("graphs", sa.JSON(), nullable=False), sa.Column("geospatial", sa.JSON(), nullable=False), sa.Column("provenance", sa.JSON(), nullable=False), sa.Column("limitations", sa.JSON(), nullable=False), sa.Column("created_by", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        op.create_index("ix_prediction_runs_incident_id", "prediction_runs", ["incident_id"])
    if "simulation_runs" not in existing:
        op.create_table("simulation_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False), sa.Column("prediction_run_id", sa.String(36), sa.ForeignKey("prediction_runs.id"), nullable=True), sa.Column("name", sa.String(180), nullable=False), sa.Column("iterations", sa.Integer(), nullable=False), sa.Column("scenario", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False), sa.Column("created_by", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        op.create_index("ix_simulation_runs_incident_id", "simulation_runs", ["incident_id"])
        op.create_index("ix_simulation_runs_prediction_run_id", "simulation_runs", ["prediction_run_id"])


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "simulation_runs" in existing:
        op.drop_table("simulation_runs")
    if "prediction_runs" in existing:
        op.drop_table("prediction_runs")
