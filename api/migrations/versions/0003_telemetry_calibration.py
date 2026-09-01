"""telemetry ledger and forecast calibration

Revision ID: 0003_telemetry_calibration
Revises: 0002_prediction_engine
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_telemetry_calibration"
down_revision = "0002_prediction_engine"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "telemetry_observations" not in existing:
        op.create_table("telemetry_observations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False), sa.Column("metric", sa.String(120), nullable=False), sa.Column("service", sa.String(120), nullable=False), sa.Column("region", sa.String(80), nullable=True), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("value", sa.Float(), nullable=False), sa.Column("baseline", sa.Float(), nullable=False), sa.Column("threshold", sa.Float(), nullable=False), sa.Column("higher_is_worse", sa.Boolean(), nullable=False), sa.Column("source", sa.String(120), nullable=False), sa.Column("source_event_id", sa.String(200), nullable=False), sa.Column("labels", sa.JSON(), nullable=False), sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("incident_id", "source", "source_event_id", name="uq_telemetry_incident_source_event"))
        for column in ("incident_id", "metric", "service", "region", "observed_at"):
            op.create_index(f"ix_telemetry_observations_{column}", "telemetry_observations", [column])
    if "forecast_evaluations" not in existing:
        op.create_table("forecast_evaluations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False), sa.Column("prediction_run_id", sa.String(36), sa.ForeignKey("prediction_runs.id"), nullable=False), sa.Column("outcome", sa.JSON(), nullable=False), sa.Column("calibration", sa.JSON(), nullable=False), sa.Column("drift", sa.JSON(), nullable=False), sa.Column("brier_score", sa.Float(), nullable=False), sa.Column("mean_absolute_error", sa.Float(), nullable=False), sa.Column("lead_time_minutes", sa.Float(), nullable=True), sa.Column("evaluated_by", sa.String(120), nullable=False), sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("prediction_run_id", name="uq_forecast_evaluation_prediction"))
        op.create_index("ix_forecast_evaluations_incident_id", "forecast_evaluations", ["incident_id"])
        op.create_index("ix_forecast_evaluations_prediction_run_id", "forecast_evaluations", ["prediction_run_id"])


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "forecast_evaluations" in existing:
        op.drop_table("forecast_evaluations")
    if "telemetry_observations" in existing:
        op.drop_table("telemetry_observations")
