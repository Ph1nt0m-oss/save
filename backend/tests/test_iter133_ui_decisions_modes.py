"""iter133 — Tests : estompage retiré, visite→simulation, décisions temporaires, MODES réduits."""
from pathlib import Path

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


class TestSiteModesReduced:
    def test_valid_site_modes_no_none_no_all(self):
        src = _read("server.py")
        assert '"none"' not in src.split("VALID_SITE_MODES = {")[1].split("}")[0]
        assert '"all"' not in src.split("VALID_SITE_MODES = {")[1].split("}")[0]

    def test_normalize_maps_legacy_none_all_to_public(self):
        src = _read("server.py")
        assert '"public" if m in ("none", "all") else m' in src

    def test_device_matches_no_all_none_branch(self):
        src = _read("server.py")
        # Le for-loop ne doit plus contenir les branches 'all'/'none'.
        assert 'if m == "all":' not in src
        assert 'elif m == "none":' not in src

    def test_frontend_MODES_has_only_6_entries(self):
        src = _rf("components/SiteModeBadge.jsx")
        # Recherche des IDs
        for mid in ("'private'", "'public'", "'guest'", "'modo'", "'admin'", "'creator'"):
            assert mid in src, f"{mid} missing"
        # 'none' / 'all' retirés
        assert "id: 'none'" not in src
        assert "id: 'all'" not in src


class TestViewModePickerNoDimming:
    def test_dimming_removed_for_active_simulation(self):
        src = _rf("components/ViewModePicker.jsx")
        assert "iter133" in src
        # Nouvelle règle : seuls les vues forcées sont dimmed.
        assert "const dimmed = dimmedByForced;" in src
        # Ancienne règle isActive && !active retirée.
        assert "isActive && !active" not in src


class TestVisitAccountAlwaysSimulation:
    def test_no_setVisiting_for_admin(self):
        src = _rf("pages/Dashboard.js")
        # La branche "if (effRole === 'creator' || effRole === 'admin')" doit être retirée.
        assert "effRole === 'creator' || effRole === 'admin'" not in src
        # Le nouveau code : "if (effRole === 'creator') return;"
        assert "if (effRole === 'creator') return;" in src

    def test_visit_target_keyid_passed(self):
        src = _rf("pages/Dashboard.js")
        assert "visitTargetKeyId: a?.key_id" in src

    def test_useDeviceIdentity_exports_readVisitTargetKeyId(self):
        src = _rf("hooks/useDeviceIdentity.js")
        assert "readVisitTargetKeyId" in src
        assert "codeforge_visit_target_keyid" in src


class TestStaffDecisions:
    def test_module_exists(self):
        assert (ROOT / "routes/staff_decisions_routes.py").is_file()

    def test_endpoints_declared(self):
        src = _read("routes/staff_decisions_routes.py")
        for ep in ("/staff-decisions/list", "/staff-decisions/validate", "/staff-decisions/revert"):
            assert f'"{ep}"' in src

    def test_creator_gated(self):
        src = _read("routes/staff_decisions_routes.py")
        assert src.count("require_creator_signature") >= 3

    def test_rollback_covers_all_events(self):
        src = _read("routes/staff_decisions_routes.py")
        for ev in ("staff_kind_admin", "staff_kind_modo", "mute", "unmute",
                   "exclude", "ban", "unban", "force_visitor_on", "force_visitor_off",
                   "rename_pseudo"):
            assert f'"{ev}"' in src

    def test_accounts_routes_tracks_non_creator_events(self):
        src = _read("routes/accounts_routes.py")
        assert "staff_decisions" in src
        assert "pending_creator_review" in src
        assert '"status": "pending"' in src

    def test_accounts_list_exposes_pending_flag(self):
        src = _read("routes/accounts_routes.py")
        assert 'd["pending_creator_review"] = bool(d.get("pending_creator_review"' in src

    def test_registered_in_server(self):
        src = _read("server.py")
        assert "build_staff_decisions_router" in src


class TestFrontendPendingReview:
    def test_badge_on_account_row(self):
        src = _rf("components/AccountsButton.jsx")
        assert "acc-pending-review-" in src
        assert "Validation temporaire" in src

    def test_panel_lists_decisions(self):
        src = _rf("components/AccountsButton.jsx")
        assert "accounts-pending-review-toggle" in src
        assert "pending-review-panel" in src
        assert "review-validate-" in src
        assert "review-revert-" in src
        assert "/staff-decisions/list" in src
        assert "/staff-decisions/${action}" in src
