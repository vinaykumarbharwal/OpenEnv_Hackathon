"""
Tests for the shared heuristics module (server/heuristics.py).

These tests verify that component, severity, priority, and info-request logic
produce the expected outputs for representative ticket inputs.
"""

from __future__ import annotations

import pytest
from datetime import datetime
from models import TicketModel
from server.heuristics import (
    infer_component,
    infer_severity,
    infer_priority,
    needs_more_info,
    suggested_info_type,
    severity_to_priority,
    COMPONENT_TEAM_MAP,
)

AVAILABLE_COMPONENTS = [
    "api-gateway", "auth-service", "user-service", "payment-service",
    "web-app", "ios-app", "android-app", "database", "cache", "cdn",
]

AVAILABLE_TEAMS = [
    "backend-api", "frontend-web", "mobile-ios",
    "mobile-android", "infrastructure", "data-platform",
]


def _ticket(**kwargs) -> TicketModel:
    """Helper to construct a minimal TicketModel with sane defaults."""
    defaults = dict(
        ticket_id="BUG-TEST",
        title="Test ticket",
        description="A test description",
        reporter_type="user",
        service="api",
        component_candidates=["api-gateway"],
        created_at=datetime(2024, 1, 1),
        customer_tier="pro",
        repro_steps_present=True,
        logs_present=True,
        attachments_count=0,
        suspected_duplicate_ids=[],
    )
    defaults.update(kwargs)
    return TicketModel(**defaults)


# ---------------------------------------------------------------------------
# severity_to_priority
# ---------------------------------------------------------------------------

class TestSeverityToPriority:
    def test_sev0_maps_to_p0(self):
        assert severity_to_priority("sev0") == "p0"

    def test_sev3_maps_to_p3(self):
        assert severity_to_priority("sev3") == "p3"

    def test_unknown_defaults_to_p2(self):
        assert severity_to_priority("unknown") == "p2"


# ---------------------------------------------------------------------------
# infer_component
# ---------------------------------------------------------------------------

class TestInferComponent:
    def test_returns_first_candidate_when_no_available(self):
        t = _ticket(component_candidates=["ios-app", "auth-service"])
        result = infer_component(t, [])
        assert result == "api-gateway"  # fallback default

    def test_keyword_match_wins(self):
        t = _ticket(
            title="iOS login broken",
            description="tapping login does nothing on iPhone",
            service="mobile-app",
            component_candidates=["ios-app", "auth-service"],
        )
        result = infer_component(t, AVAILABLE_COMPONENTS)
        assert result == "ios-app"

    def test_payment_keyword_picks_payment_service(self):
        t = _ticket(
            title="Payment timeout",
            description="checkout is failing, billing error",
            service="payments",
            component_candidates=["payment-service", "api-gateway"],
        )
        result = infer_component(t, AVAILABLE_COMPONENTS)
        assert result == "payment-service"

    def test_cdn_keyword(self):
        t = _ticket(
            title="Images broken",
            description="CDN asset fails to load",
            service="web-app",
            component_candidates=["cdn", "web-app"],
        )
        result = infer_component(t, AVAILABLE_COMPONENTS)
        assert result == "cdn"

    def test_filters_out_unavailable_candidates(self):
        t = _ticket(component_candidates=["nonexistent-service", "database"])
        result = infer_component(t, AVAILABLE_COMPONENTS)
        assert result == "database"


# ---------------------------------------------------------------------------
# infer_severity
# ---------------------------------------------------------------------------

class TestInferSeverity:
    def test_security_keyword_is_sev0(self):
        t = _ticket(description="unauthorized access detected, security breach")
        assert infer_severity(t, "auth-service") == "sev0"

    def test_double_charge_is_sev0(self):
        t = _ticket(description="customer was double charged")
        assert infer_severity(t, "payment-service") == "sev0"

    def test_timeout_is_sev1(self):
        t = _ticket(description="service is timing out after 30s")
        assert infer_severity(t, "api-gateway") == "sev1"

    def test_outage_is_sev1(self):
        t = _ticket(description="full outage detected by monitoring")
        assert infer_severity(t, "api-gateway") == "sev1"

    def test_crash_is_sev2(self):
        t = _ticket(description="app crashes on launch every time")
        assert infer_severity(t, "android-app") == "sev2"

    def test_slow_db_free_tier_is_sev3(self):
        t = _ticket(
            description="dashboard is slow",
            customer_tier="free",
        )
        assert infer_severity(t, "database") == "sev3"

    def test_slow_db_enterprise_is_sev2(self):
        t = _ticket(
            description="dashboard is slow",
            customer_tier="enterprise",
        )
        assert infer_severity(t, "database") == "sev2"

    def test_incorrect_tax_enterprise_is_sev1(self):
        t = _ticket(description="incorrect tax calculation on invoice", customer_tier="enterprise")
        assert infer_severity(t, "payment-service") == "sev1"

    def test_incorrect_tax_free_is_sev2(self):
        t = _ticket(description="incorrect tax calculation on invoice", customer_tier="free")
        assert infer_severity(t, "payment-service") == "sev2"

    def test_low_signal_free_is_sev3(self):
        t = _ticket(description="something is wrong, signal quality is low", customer_tier="free")
        assert infer_severity(t, "web-app") == "sev3"

    def test_no_keywords_default_sev3(self):
        t = _ticket(title="Minor UI glitch", description="button looks slightly off")
        assert infer_severity(t, "web-app") == "sev3"


# ---------------------------------------------------------------------------
# infer_priority
# ---------------------------------------------------------------------------

class TestInferPriority:
    def test_sev2_enterprise_upgrades_to_p1(self):
        t = _ticket(customer_tier="enterprise")
        assert infer_priority(t, "sev2") == "p1"

    def test_sev2_monitoring_upgrades_to_p1(self):
        t = _ticket(reporter_type="monitoring", customer_tier="free")
        assert infer_priority(t, "sev2") == "p1"

    def test_sev2_payment_keyword_upgrades_to_p1(self):
        t = _ticket(description="payment gateway slow", customer_tier="free")
        assert infer_priority(t, "sev2") == "p1"

    def test_sev3_free_stays_p3(self):
        t = _ticket(customer_tier="free")
        assert infer_priority(t, "sev3") == "p3"


# ---------------------------------------------------------------------------
# needs_more_info
# ---------------------------------------------------------------------------

class TestNeedsMoreInfo:
    def test_no_repro_no_logs_needs_info(self):
        t = _ticket(repro_steps_present=False, logs_present=False)
        assert needs_more_info(t) is True

    def test_duplicate_overrides_info_need(self):
        t = _ticket(
            repro_steps_present=False,
            logs_present=False,
            suspected_duplicate_ids=["BUG-999"],
        )
        assert needs_more_info(t) is False

    def test_user_without_logs_needs_info(self):
        t = _ticket(reporter_type="user", repro_steps_present=True, logs_present=False)
        assert needs_more_info(t) is True

    def test_monitoring_without_repro_ok(self):
        """Monitoring reporters don't need manual repro steps."""
        t = _ticket(reporter_type="monitoring", repro_steps_present=False, logs_present=True)
        assert needs_more_info(t) is False

    def test_low_signal_flag_needs_info(self):
        t = _ticket(
            description="signal quality is low on this ticket",
            repro_steps_present=True,
            logs_present=True,
        )
        assert needs_more_info(t) is True

    def test_full_info_not_needed(self):
        t = _ticket(repro_steps_present=True, logs_present=True, reporter_type="user")
        assert needs_more_info(t) is False


# ---------------------------------------------------------------------------
# suggested_info_type
# ---------------------------------------------------------------------------

class TestSuggestedInfoType:
    def test_neither_present_returns_both(self):
        t = _ticket(repro_steps_present=False, logs_present=False)
        assert suggested_info_type(t) == "both"

    def test_only_logs_missing_returns_logs(self):
        t = _ticket(repro_steps_present=True, logs_present=False)
        assert suggested_info_type(t) == "logs"

    def test_only_repro_missing_returns_repro_steps(self):
        t = _ticket(repro_steps_present=False, logs_present=True)
        assert suggested_info_type(t) == "repro_steps"


# ---------------------------------------------------------------------------
# COMPONENT_TEAM_MAP sanity check
# ---------------------------------------------------------------------------

class TestComponentTeamMap:
    def test_all_components_have_teams(self):
        for component in AVAILABLE_COMPONENTS:
            assert component in COMPONENT_TEAM_MAP, f"{component} missing from COMPONENT_TEAM_MAP"

    def test_teams_are_valid(self):
        for team in COMPONENT_TEAM_MAP.values():
            assert team in AVAILABLE_TEAMS, f"Team '{team}' not in AVAILABLE_TEAMS"
