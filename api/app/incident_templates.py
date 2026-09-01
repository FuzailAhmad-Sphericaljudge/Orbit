TEMPLATES = {
    "api-unreachable": {
        "name": "API unavailable",
        "service": "api",
        "severity": "SEV2",
        "customer_impact": "API requests may be failing or timing out.",
        "recovery_criteria": "API readiness is healthy and error rate remains below 1% for 10 minutes.",
        "actions": ["Verify API readiness and recent error rate", "Check deployment and dependency health", "Post a customer-safe status update"],
    },
    "database-degradation": {
        "name": "Database degradation",
        "service": "database",
        "severity": "SEV2",
        "customer_impact": "Requests may be slow or fail while database performance is degraded.",
        "recovery_criteria": "Database latency, errors, and connection saturation are within normal operating limits for 10 minutes.",
        "actions": ["Verify database connectivity and saturation", "Inspect slow queries and recent schema changes", "Confirm dependent services recover"],
    },
    "payment-outage": {
        "name": "Payment outage",
        "service": "payments",
        "severity": "SEV1",
        "customer_impact": "Customers may be unable to complete payments.",
        "recovery_criteria": "Payment success rate, latency, and queue health meet the agreed recovery criteria for 10 minutes.",
        "actions": ["Confirm customer impact and payment failure rate", "Assign payment and database investigation owners", "Prepare executive and support briefings"],
    },
}
