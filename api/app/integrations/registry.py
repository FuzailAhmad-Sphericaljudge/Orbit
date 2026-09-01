from ..config import get_settings
from ..models import IntegrationProvider
from .jira import JiraConnector
from .monitoring import MonitoringConnector
from .pagerduty import PagerDutyConnector
from .slack import SlackConnector


settings = get_settings()
integration_registry = {
    IntegrationProvider.slack: SlackConnector(settings.slack_bot_token, settings.slack_default_channel, settings.integration_timeout_seconds),
    IntegrationProvider.jira: JiraConnector(settings.jira_base_url, settings.jira_user_email, settings.jira_api_token, settings.jira_project_key, settings.jira_issue_type, settings.integration_timeout_seconds),
    IntegrationProvider.pagerduty: PagerDutyConnector(settings.pagerduty_api_token, settings.pagerduty_from_email, settings.pagerduty_service_id, settings.integration_timeout_seconds),
    IntegrationProvider.monitoring: MonitoringConnector(settings.monitoring_webhook_url, settings.monitoring_webhook_token, settings.integration_timeout_seconds),
}
