from functools import lru_cache
import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./orbit.db"
    cors_origins: str = "http://localhost:5173"
    environment: str = "development"
    agora_app_id: str = ""
    agora_app_certificate: str = ""
    agora_area: str = "US"
    agora_agent_uid: str = "1"
    orbit_default_language: str = "en-US"
    auth_jwt_secret: str = "development-only-change-me"
    auth_jwt_issuer: str = "orbit"
    auth_jwt_audience: str = "orbit-api"
    oidc_jwks_url: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_roles_claim: str = "roles"
    slack_bot_token: str = ""
    slack_default_channel: str = ""
    jira_base_url: str = ""
    jira_user_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    jira_issue_type: str = "Task"
    pagerduty_api_token: str = ""
    pagerduty_from_email: str = ""
    pagerduty_service_id: str = ""
    monitoring_webhook_url: str = ""
    monitoring_webhook_token: str = ""
    prometheus_base_url: str = ""
    prometheus_username: str = ""
    prometheus_bearer_token: str = ""
    production_learning_enabled: bool = False
    telemetry_collector_enabled: bool = False
    telemetry_collection_interval_seconds: int = 60
    telemetry_collection_window_minutes: int = 20
    telemetry_query_catalog_json: str = "{}"
    forecast_evaluation_grace_minutes: int = 2
    integration_timeout_seconds: float = 10.0
    vision_analysis_url: str = ""
    vision_analysis_token: str = ""
    redis_url: str = "redis://localhost:6379/0"
    redis_required: bool = False
    auto_create_schema: bool = True
    rate_limit_requests_per_minute: int = 240
    max_request_body_bytes: int = 2_000_000
    retention_days: int = 90
    job_max_retries: int = 5
    job_stream_max_length: int = 10_000
    trusted_hosts: str = "localhost,127.0.0.1"
    auth_jwt_secret_file: str = ""
    database_url_file: str = ""
    redis_url_file: str = ""
    data_encryption_key: str = ""
    data_encryption_key_file: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def telemetry_query_catalog(self) -> dict:
        try:
            value = json.loads(self.telemetry_query_catalog_json or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("TELEMETRY_QUERY_CATALOG_JSON must contain valid JSON") from exc
        if not isinstance(value, dict) or not isinstance(value.get("queries", []), list):
            raise RuntimeError("TELEMETRY_QUERY_CATALOG_JSON must be an object with a queries list")
        return value

    def load_secret_files(self) -> None:
        for value_field, file_field in (("auth_jwt_secret", "auth_jwt_secret_file"), ("database_url", "database_url_file"), ("redis_url", "redis_url_file"), ("data_encryption_key", "data_encryption_key_file")):
            path_value = getattr(self, file_field)
            if path_value:
                path = Path(path_value)
                if not path.is_file():
                    raise RuntimeError(f"Secret file does not exist: {file_field}")
                setattr(self, value_field, path.read_text(encoding="utf-8").strip())

    def validate_runtime(self) -> None:
        self.load_secret_files()
        if self.environment != "development" and not self.oidc_jwks_url and (
            self.auth_jwt_secret == "development-only-change-me" or len(self.auth_jwt_secret) < 32
        ):
            raise RuntimeError("AUTH_JWT_SECRET must be a strong secret outside development")
        if self.oidc_jwks_url and not (self.oidc_issuer and self.oidc_audience):
            raise RuntimeError("OIDC_ISSUER and OIDC_AUDIENCE are required with OIDC_JWKS_URL")
        if self.environment != "development" and self.auto_create_schema:
            raise RuntimeError("AUTO_CREATE_SCHEMA must be false outside development; run Alembic migrations")
        if self.environment != "development" and not self.data_encryption_key:
            raise RuntimeError("DATA_ENCRYPTION_KEY or DATA_ENCRYPTION_KEY_FILE is required outside development")
        if self.rate_limit_requests_per_minute < 1 or self.max_request_body_bytes < 1024:
            raise RuntimeError("Rate limit and request body limits must be positive")
        if self.telemetry_collector_enabled and not self.prometheus_base_url:
            raise RuntimeError("PROMETHEUS_BASE_URL is required when telemetry collection is enabled")
        if self.telemetry_collection_interval_seconds < 15 or self.forecast_evaluation_grace_minutes < 0:
            raise RuntimeError("Telemetry interval must be at least 15 seconds and evaluation grace cannot be negative")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.load_secret_files()
    return settings
