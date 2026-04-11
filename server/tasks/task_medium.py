"""Task metadata and fixture data for bug_triage_medium."""

from __future__ import annotations

TASK_ID = "bug_triage_medium"
DIFFICULTY = "medium"
DESCRIPTION = "15 mixed-quality tickets, several duplicates"

TASK_DATA = {
    "task_id": "bug_triage_medium",
    "step_budget": 80,
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
            "ticket_id": "BUG-2001",
            "title": "Enterprise API requests timing out at the edge gateway",
            "description": (
                "Several enterprise tenants report that requests to the public API are timing out "
                "after 12 to 15 seconds. Support says the issue started right after yesterday's "
                "gateway config rollout."
            ),
            "reporter_type": "user",
            "service": "api",
            "component_candidates": ["api-gateway", "auth-service", "payment-service"],
            "created_at": "2024-02-01T09:00:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2002",
            "title": "SSO login spins forever after password reset",
            "description": (
                "QA could reproduce an auth flow where the login screen never finishes and the app "
                "is effectively not working after a password reset. The report is still missing "
                "repro steps and server logs."
            ),
            "reporter_type": "qa",
            "service": "auth",
            "component_candidates": ["auth-service", "user-service", "web-app"],
            "created_at": "2024-02-01T09:13:00",
            "customer_tier": "pro",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2003",
            "title": "Identity sync returns wrong values for display names",
            "description": (
                "A sparse monitoring alert says the identity pipeline is returning wrong values "
                "for some user profile fields. The alert has no attached logs and no reliable "
                "reproduction details yet."
            ),
            "reporter_type": "monitoring",
            "service": "identity",
            "component_candidates": ["user-service", "payment-service", "ios-app"],
            "created_at": "2024-02-01T09:26:00",
            "customer_tier": "free",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2004",
            "title": "Checkout hangs after the session silently re-auths",
            "description": (
                "A customer opened this as a payments problem because pressing Pay appears to do "
                "nothing, but the attached note matches the same login loop already being tracked "
                "in BUG-2002."
            ),
            "reporter_type": "user",
            "service": "payments",
            "component_candidates": ["payment-service", "web-app", "android-app"],
            "created_at": "2024-02-01T09:39:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": ["BUG-2002"],
        },
        {
            "ticket_id": "BUG-2005",
            "title": "Operations dashboard is down after the morning deploy",
            "description": (
                "The internal web app for account managers is down for every tested browser. QA "
                "confirmed the outage on staging and production after the latest frontend release."
            ),
            "reporter_type": "qa",
            "service": "web-app",
            "component_candidates": ["web-app", "ios-app", "database"],
            "created_at": "2024-02-01T09:52:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2006",
            "title": "Sparse alert about iOS launch retries with no device evidence",
            "description": (
                "Monitoring noticed elevated retries during iOS app startup, but the note is light "
                "on detail and shipped without device logs or a reliable reproduction path."
            ),
            "reporter_type": "monitoring",
            "service": "mobile-app",
            "component_candidates": ["ios-app", "android-app", "cache"],
            "created_at": "2024-02-01T10:05:00",
            "customer_tier": "enterprise",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2007",
            "title": "Android sign-in requests keep timing out on mobile data",
            "description": (
                "Users on the latest Android release say the app times out during sign-in over "
                "cellular networks, while Wi-Fi works most of the time."
            ),
            "reporter_type": "user",
            "service": "mobile-app",
            "component_candidates": ["android-app", "database", "cdn"],
            "created_at": "2024-02-01T10:18:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2008",
            "title": "Analytics export shows wrong values in the CSV totals",
            "description": (
                "QA found that several analytics exports return wrong values in revenue summary "
                "columns. They attached screenshots but forgot the exact repro steps."
            ),
            "reporter_type": "qa",
            "service": "analytics",
            "component_candidates": ["database", "cache", "api-gateway"],
            "created_at": "2024-02-01T10:31:00",
            "customer_tier": "free",
            "repro_steps_present": False,
            "logs_present": True,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2009",
            "title": "Monitoring page about stale responses appears tied to dashboard outage",
            "description": (
                "Infra monitoring opened a cache-flavored incident, but the screenshots line up "
                "with the same web dashboard outage already being tracked in BUG-2005."
            ),
            "reporter_type": "monitoring",
            "service": "infra",
            "component_candidates": ["cache", "cdn", "auth-service"],
            "created_at": "2024-02-01T10:44:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": ["BUG-2005"],
        },
        {
            "ticket_id": "BUG-2010",
            "title": "Product gallery renders broken image icons for some SKUs",
            "description": (
                "Merchandising reports broken image icons on product detail pages even though the "
                "rest of the page loads normally."
            ),
            "reporter_type": "user",
            "service": "media",
            "component_candidates": ["cdn", "api-gateway", "user-service"],
            "created_at": "2024-02-01T10:57:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2011",
            "title": "Unauthorized access to admin API observed during QA sweep",
            "description": (
                "QA discovered that an unprivileged account can hit an admin API route and receive "
                "data it should never see. This looks like unauthorized access through the edge API."
            ),
            "reporter_type": "qa",
            "service": "api",
            "component_candidates": ["api-gateway", "auth-service", "payment-service"],
            "created_at": "2024-02-01T11:10:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2012",
            "title": "Background auth probe is noisy but missing useful evidence",
            "description": (
                "A lightweight auth probe started flapping, but the alert arrived with no logs and "
                "no clear repro path, so the report is mostly observational right now."
            ),
            "reporter_type": "monitoring",
            "service": "auth",
            "component_candidates": ["auth-service", "user-service", "web-app"],
            "created_at": "2024-02-01T11:23:00",
            "customer_tier": "pro",
            "repro_steps_present": False,
            "logs_present": False,
            "attachments_count": 4,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2013",
            "title": "Profile edits save but return wrong values on refresh",
            "description": (
                "Users can update profile settings, but the response payload comes back with wrong "
                "values after the save completes."
            ),
            "reporter_type": "user",
            "service": "identity",
            "component_candidates": ["user-service", "payment-service", "ios-app"],
            "created_at": "2024-02-01T11:36:00",
            "customer_tier": "free",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 1,
            "suspected_duplicate_ids": [],
        },
        {
            "ticket_id": "BUG-2014",
            "title": "Billing retry complaint traces back to the API timeout incident",
            "description": (
                "Finance support believed this was a payment-service issue, but the attached trace "
                "matches the same API timeout already captured in BUG-2001."
            ),
            "reporter_type": "qa",
            "service": "payments",
            "component_candidates": ["payment-service", "web-app", "android-app"],
            "created_at": "2024-02-01T11:49:00",
            "customer_tier": "enterprise",
            "repro_steps_present": True,
            "logs_present": False,
            "attachments_count": 2,
            "suspected_duplicate_ids": ["BUG-2001"],
        },
        {
            "ticket_id": "BUG-2015",
            "title": "Locale switch leaves the settings page visually misaligned",
            "description": (
                "Monitoring from the synthetic browser run shows the web app settings page drifting "
                "after a locale switch, but there is no outage and the rest of the flow still works."
            ),
            "reporter_type": "monitoring",
            "service": "web-app",
            "component_candidates": ["web-app", "ios-app", "database"],
            "created_at": "2024-02-01T12:02:00",
            "customer_tier": "pro",
            "repro_steps_present": True,
            "logs_present": True,
            "attachments_count": 3,
            "suspected_duplicate_ids": [],
        },
    ],
    "ground_truths": [
        {
            "ticket_id": "BUG-2001",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "api-gateway",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2002",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "auth-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-2003",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "user-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-2004",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "payment-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": "BUG-2002",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2005",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "web-app",
            "true_assignee_team": "frontend-web",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2006",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "ios-app",
            "true_assignee_team": "mobile-ios",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-2007",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "android-app",
            "true_assignee_team": "mobile-android",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2008",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "database",
            "true_assignee_team": "data-platform",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-2009",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "cache",
            "true_assignee_team": "infrastructure",
            "duplicate_of": "BUG-2005",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2010",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "cdn",
            "true_assignee_team": "infrastructure",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2011",
            "true_severity": "sev0",
            "true_priority": "p0",
            "true_component": "api-gateway",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2012",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "auth-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": True,
        },
        {
            "ticket_id": "BUG-2013",
            "true_severity": "sev2",
            "true_priority": "p2",
            "true_component": "user-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": None,
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2014",
            "true_severity": "sev1",
            "true_priority": "p1",
            "true_component": "payment-service",
            "true_assignee_team": "backend-api",
            "duplicate_of": "BUG-2001",
            "needs_more_info": False,
        },
        {
            "ticket_id": "BUG-2015",
            "true_severity": "sev3",
            "true_priority": "p3",
            "true_component": "web-app",
            "true_assignee_team": "frontend-web",
            "duplicate_of": None,
            "needs_more_info": False,
        },
    ],
}
