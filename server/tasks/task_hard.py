"""Task metadata and fixture data for bug_triage_hard."""

from __future__ import annotations

TASK_ID = "bug_triage_hard"
DIFFICULTY = "hard"
DESCRIPTION = "25 noisy tickets, strict SLA pressure"

TASK_DATA = {
    "task_id": "bug_triage_hard",
    "step_budget": 120,
    "available_teams": [
        "backend-api",
        "frontend-web",
        "mobile-ios",
        "mobile-android",
        "infrastructure",
        "data-platform",
    ],
    "available_components": [
        "api-gateway",
        "auth-service",
        "user-service",
        "payment-service",
        "web-app",
        "ios-app",
        "android-app",
        "database",
        "cache",
        "cdn",
    ],
    "tickets": [
        {
            "ticket_id": "BUG-3001",
            "title": "Unauthorized access to enterprise admin API",
            "description": (
                "A customer security contact reports unauthorized access to an internal admin API "
                "path through the public gateway. Sample responses contain account data that should "
                "never be exposed."
            ),
            "reporter_type": "user",
            "service": "api",
            "component_candidates": ["api-gateway", "auth-service", "payment-service"],
            "created_at": "2024-03-01T09:00:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3002",
            "title": "Auth requests timing out during login on web",
            "description": (
                "QA sees the login flow timing out after the redirect returns from the identity "
                "provider. The timeout only started after rotating session settings."
            ),
            "reporter_type": "qa",
            "service": "auth",
            "component_candidates": ["auth-service", "user-service", "web-app"],
            "created_at": "2024-03-01T09:13:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3003",
            "title": "Identity sync alert says profile fields contain wrong values",
            "description": (
                "Monitoring raised a user-service alert because a sample profile payload returned "
                "wrong values, but the incident has no logs and no reproduction details yet."
            ),
            "reporter_type": "monitoring",
            "service": "identity",
            "component_candidates": ["user-service", "payment-service", "ios-app"],
            "created_at": "2024-03-01T09:26:00",
            "customer_tier": "free",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3004",
            "title": "Checkout calls to payment service are timing out",
            "description": (
                "Merchants report that payment authorization requests are timing out during peak "
                "traffic and orders are sitting in a pending state."
            ),
            "reporter_type": "user",
            "service": "payments",
            "component_candidates": ["payment-service", "web-app", "android-app"],
            "created_at": "2024-03-01T09:39:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3005",
            "title": "Web app settings page is flaky but the report lacks depth",
            "description": (
                "QA says the settings page sometimes behaves oddly after navigation, but the note "
                "does not mention an outage, crash, or data issue and still needs clearer repro steps."
            ),
            "reporter_type": "qa",
            "service": "web-app",
            "component_candidates": ["web-app", "ios-app", "database"],
            "created_at": "2024-03-01T09:52:00",
            "customer_tier": "pro",
            "repro_steps_present": False,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3006",
            "title": "iOS app crashes when opening the billing screen",
            "description": (
                "Monitoring traces show the iOS app can crash when users open the billing screen "
                "from account settings."
            ),
            "reporter_type": "monitoring",
            "service": "mobile-app",
            "component_candidates": ["ios-app", "android-app", "cache"],
            "created_at": "2024-03-01T10:05:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3007",
            "title": "Android sign-in timing out for pro users on LTE",
            "description": (
                "The Android app keeps timing out during sign-in when users are on cellular data. "
                "Support could not reproduce it on Wi-Fi."
            ),
            "reporter_type": "user",
            "service": "mobile-app",
            "component_candidates": ["android-app", "database", "cdn"],
            "created_at": "2024-03-01T10:18:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3008",
            "title": "Analytics dashboard query returns wrong values",
            "description": (
                "QA found that an analytics query writes wrong values into the daily summary table. "
                "They attached a screenshot but skipped the exact repro sequence."
            ),
            "reporter_type": "qa",
            "service": "analytics",
            "component_candidates": ["database", "cache", "api-gateway"],
            "created_at": "2024-03-01T10:31:00",
            "customer_tier": "free",
            "repro_steps_present": False,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3009",
            "title": "Stale cache entries are returning wrong values",
            "description": (
                "Monitoring saw cache nodes serving wrong values for recently updated account data. "
                "The issue is user visible but not a full outage."
            ),
            "reporter_type": "monitoring",
            "service": "infra",
            "component_candidates": ["cache", "cdn", "auth-service"],
            "created_at": "2024-03-01T10:44:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3010",
            "title": "Broken image reports during login flow match active auth incident",
            "description": (
                "A customer ticket mentions missing images after sign-in, but the timing and trace "
                "samples match the same auth timeout already tracked in BUG-3002."
            ),
            "reporter_type": "user",
            "service": "media",
            "component_candidates": ["cdn", "api-gateway", "user-service"],
            "created_at": "2024-03-01T10:57:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": ["BUG-3002"],
        },
        {
            "ticket_id": "BUG-3011",
            "title": "Gateway error report is another view of the auth timeout",
            "description": (
                "QA filed an API-gateway incident because they saw 503 responses during login, but "
                "the trace lines up with the same auth-service timeout already in BUG-3002."
            ),
            "reporter_type": "qa",
            "service": "api",
            "component_candidates": ["api-gateway", "auth-service", "payment-service"],
            "created_at": "2024-03-01T11:10:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": ["BUG-3002"],
        },
        {
            "ticket_id": "BUG-3012",
            "title": "Security breach suspicion after invalid auth token escalation",
            "description": (
                "Monitoring caught a burst of unauthorized token exchanges in the auth service and "
                "the security team is treating it as a possible breach."
            ),
            "reporter_type": "monitoring",
            "service": "auth",
            "component_candidates": ["auth-service", "user-service", "web-app"],
            "created_at": "2024-03-01T11:23:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3013",
            "title": "Profile page ordering looks off but data is intact",
            "description": (
                "Users say the identity profile page sometimes renders sections in a strange order, "
                "but the account data itself still appears intact."
            ),
            "reporter_type": "user",
            "service": "identity",
            "component_candidates": ["user-service", "payment-service", "ios-app"],
            "created_at": "2024-03-01T11:36:00",
            "customer_tier": "free",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3014",
            "title": "Enterprise invoices use incorrect tax on EU renewals",
            "description": (
                "QA found incorrect tax on renewal invoices for enterprise accounts. The numbers are "
                "consistently wrong in the payment workflow."
            ),
            "reporter_type": "qa",
            "service": "payments",
            "component_candidates": ["payment-service", "web-app", "android-app"],
            "created_at": "2024-03-01T11:49:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3015",
            "title": "Admin console exposure is the same unauthorized API leak",
            "description": (
                "Synthetic browser checks flagged the web app admin console, but the underlying "
                "symptom still points to the unauthorized API access already tracked in BUG-3001."
            ),
            "reporter_type": "monitoring",
            "service": "web-app",
            "component_candidates": ["web-app", "ios-app", "database"],
            "created_at": "2024-03-01T12:02:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": ["BUG-3001"],
        },
        {
            "ticket_id": "BUG-3016",
            "title": "iOS receipt screen not working after last App Store build",
            "description": (
                "Users say the receipt screen in the iOS app is not working after the latest build. "
                "They attached logs but still skipped exact repro steps."
            ),
            "reporter_type": "user",
            "service": "mobile-app",
            "component_candidates": ["ios-app", "android-app", "cache"],
            "created_at": "2024-03-01T12:15:00",
            "customer_tier": "enterprise",
            "repro_steps_present": False,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3017",
            "title": "Android release is timing out before home screen loads",
            "description": (
                "QA says the current Android build times out while bootstrapping user data, so the "
                "home screen never becomes interactive."
            ),
            "reporter_type": "qa",
            "service": "mobile-app",
            "component_candidates": ["android-app", "database", "cdn"],
            "created_at": "2024-03-01T12:28:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3018",
            "title": "Sparse analytics alert says daily totals contain wrong values",
            "description": (
                "Monitoring noticed wrong values in analytics rollups, but the alert arrived without "
                "logs and without a reproducible query sample."
            ),
            "reporter_type": "monitoring",
            "service": "analytics",
            "component_candidates": ["database", "cache", "api-gateway"],
            "created_at": "2024-03-01T12:41:00",
            "customer_tier": "free",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3019",
            "title": "Cache warmup leaves some pages outdated for a few minutes",
            "description": (
                "Support noticed a mild cache warmup issue where pages look outdated briefly after "
                "deploys, but the data eventually catches up."
            ),
            "reporter_type": "user",
            "service": "infra",
            "component_candidates": ["cache", "cdn", "auth-service"],
            "created_at": "2024-03-01T12:54:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3020",
            "title": "Editorial previews show broken image placeholders",
            "description": (
                "Content editors are seeing broken image placeholders in preview mode, especially "
                "for recently uploaded assets."
            ),
            "reporter_type": "qa",
            "service": "media",
            "component_candidates": ["cdn", "api-gateway", "user-service"],
            "created_at": "2024-03-01T13:07:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3021",
            "title": "Multiple monitoring alerts on 500 internal server error at gateway",
            "description": (
                "The API edge started returning 500 Internal Server Error to several customer paths "
                "and multiple monitoring alerts fired at once."
            ),
            "reporter_type": "monitoring",
            "service": "api",
            "component_candidates": ["api-gateway", "auth-service", "payment-service"],
            "created_at": "2024-03-01T13:20:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3022",
            "title": "User thinks auth is broken but traces match Android timeout",
            "description": (
                "A user filed this under auth because login fails, but the timing and screenshots "
                "match the same Android timeout issue already captured in BUG-3017."
            ),
            "reporter_type": "user",
            "service": "auth",
            "component_candidates": ["auth-service", "user-service", "web-app"],
            "created_at": "2024-03-01T13:33:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": ["BUG-3017"],
        },
        {
            "ticket_id": "BUG-3023",
            "title": "Profile service is down for account settings requests",
            "description": (
                "QA reports the identity-backed profile service is down when account settings are "
                "opened, although login itself still succeeds."
            ),
            "reporter_type": "qa",
            "service": "identity",
            "component_candidates": ["user-service", "payment-service", "ios-app"],
            "created_at": "2024-03-01T13:46:00",
            "customer_tier": "free",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3024",
            "title": "Payment export returns wrong values but alert has no evidence",
            "description": (
                "Monitoring thinks a payments export job is returning wrong values for settlement "
                "rows, but the incident arrived without logs or a reproducible sample payload."
            ),
            "reporter_type": "monitoring",
            "service": "payments",
            "component_candidates": ["payment-service", "web-app", "android-app"],
            "created_at": "2024-03-01T13:59:00",
            "customer_tier": "enterprise",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-3025",
            "title": "Theme toggle leaves the web app with mixed spacing tokens",
            "description": (
                "Users noticed the web app keeps mixed spacing and font weights after switching "
                "themes, but the product remains usable."
            ),
            "reporter_type": "user",
            "service": "web-app",
            "component_candidates": ["web-app", "ios-app", "database"],
            "created_at": "2024-03-01T14:12:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
    ],
    "ground_truths": [
        {
            "ticket_id": "BUG-3001",
            "true_severity": "sev0",
            "true_priority": "p0",
            "true_component": "api-gateway",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3002",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "auth-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3003",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "user-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-3004",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "payment-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3005",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "web-app",
            "true_assignee_team": "frontend-web",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-3006",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "ios-app",
            "true_assignee_team": "mobile-ios",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3007",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "android-app",
            "true_assignee_team": "mobile-android",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3008",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "database",
            "true_assignee_team": "data-platform",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-3009",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "cache",
            "true_assignee_team": "infrastructure",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3010",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "cdn",
            "true_assignee_team": "infrastructure",
            "duplicate_of": "BUG-3002",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3011",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "api-gateway",
            "true_assignee_team": "backend-api",
            "duplicate_of": "BUG-3002",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3012",
            "true_severity": "sev0",
            "true_priority": "p0",
            "true_component": "auth-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3013",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "user-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3014",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "payment-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3015",
            "true_severity": "sev0",
            "true_priority": "p0",
            "true_component": "web-app",
            "true_assignee_team": "frontend-web",
            "duplicate_of": "BUG-3001",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3016",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "ios-app",
            "true_assignee_team": "mobile-ios",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-3017",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "android-app",
            "true_assignee_team": "mobile-android",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3018",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "database",
            "true_assignee_team": "data-platform",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-3019",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "cache",
            "true_assignee_team": "infrastructure",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3020",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "cdn",
            "true_assignee_team": "infrastructure",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3021",
            "true_severity": "sev0",
            "true_priority": "p0",
            "true_component": "api-gateway",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3022",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "auth-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": "BUG-3017",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3023",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "user-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-3024",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "payment-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-3025",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "web-app",
            "true_assignee_team": "frontend-web",
            "duplicate_of": None,
            "needs_more_info": False,
        },
    ],
}
