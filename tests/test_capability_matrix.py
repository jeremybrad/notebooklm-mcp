"""Offline tests for the WOR-185 capability matrix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "audits" / "wor185_capability_matrix.json"
SERVER_PATH = ROOT / "src" / "notebooklm_mcp" / "server.py"
SYNC_PATH = ROOT / "src" / "notebooklm_mcp" / "doc_refresh" / "notebook_sync.py"
CLIENT_PATH = ROOT / "src" / "notebooklm_mcp" / "api_client.py"

REQUIRED_OPERATIONS = (
    "create_notebook",
    "add_source",
    "replace_source",
    "delete_notebook",
    "list_notebooks",
    "validate_source_freshness",
)
ALLOWED_CAPABILITIES = {"supported", "partial", "unsupported"}
REQUIRED_PATH_IDS = (
    "official_consumer_api",
    "official_enterprise_api",
    "gemini_notebooks_ui_sync",
    "drive_linked_sources",
    "existing_mcp_text_sources",
    "browser_ui_fallback",
)
MCP_TOOL_NAMES = (
    "notebook_create",
    "notebook_list",
    "notebook_delete",
    "notebook_add_text",
    "notebook_add_url",
    "notebook_add_drive",
    "source_list_drive",
    "source_sync_drive",
    "source_delete",
)


@pytest.fixture(scope="module")
def matrix() -> dict:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_matrix_file_exists_and_names_wor185():
    assert MATRIX_PATH.is_file()
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert payload["issue"] == "WOR-185"
    assert payload["live_google_calls"] is False
    assert payload["live_notebooklm_calls"] is False
    assert payload["auth_installed"] is False


def test_required_operations_match_acceptance_criteria(matrix: dict):
    assert matrix["required_operations"] == list(REQUIRED_OPERATIONS)


def test_every_path_covers_every_required_operation(matrix: dict):
    path_ids = [path["id"] for path in matrix["paths"]]
    assert path_ids == list(REQUIRED_PATH_IDS)
    for path in matrix["paths"]:
        ops = path["operations"]
        assert set(ops) == set(REQUIRED_OPERATIONS)
        for name, value in ops.items():
            assert value in ALLOWED_CAPABILITIES, f"{path['id']}.{name}={value}"


def test_preferred_path_is_existing_mcp_and_covers_lifecycle(matrix: dict):
    assert matrix["preferred_path_id"] == "existing_mcp_text_sources"
    preferred = next(p for p in matrix["paths"] if p["id"] == "existing_mcp_text_sources")
    assert preferred["operations"]["create_notebook"] == "supported"
    assert preferred["operations"]["add_source"] == "supported"
    assert preferred["operations"]["delete_notebook"] == "supported"
    assert preferred["operations"]["list_notebooks"] == "supported"
    assert preferred["operations"]["replace_source"] == "partial"
    assert preferred["operations"]["validate_source_freshness"] == "partial"


def test_official_consumer_api_is_fully_unsupported(matrix: dict):
    consumer = next(p for p in matrix["paths"] if p["id"] == "official_consumer_api")
    assert set(consumer["operations"].values()) == {"unsupported"}
    assert "official_consumer_api" in matrix["rejected_path_ids"]


def test_enterprise_api_is_supported_but_rejected_as_product_mismatch(matrix: dict):
    enterprise = next(p for p in matrix["paths"] if p["id"] == "official_enterprise_api")
    assert enterprise["operations"]["create_notebook"] == "supported"
    assert enterprise["operations"]["add_source"] == "supported"
    assert enterprise["operations"]["list_notebooks"] == "supported"
    assert enterprise["operations"]["delete_notebook"] == "supported"
    assert enterprise["operations"]["validate_source_freshness"] == "unsupported"
    assert "official_enterprise_api" in matrix["rejected_path_ids"]
    methods = set(enterprise["rest_methods"])
    assert "notebooks.create" in methods
    assert "notebooks.sources.batchCreate" in methods


def test_gemini_notebooks_sync_is_not_an_automation_path(matrix: dict):
    gemini = next(p for p in matrix["paths"] if p["id"] == "gemini_notebooks_ui_sync")
    assert gemini["operations"]["validate_source_freshness"] == "unsupported"
    assert "gemini_notebooks_ui_sync" in matrix["rejected_path_ids"]


def test_drive_path_is_freshness_complement_not_notebook_lifecycle(matrix: dict):
    assert matrix["freshness_complement_path_id"] == "drive_linked_sources"
    drive = next(p for p in matrix["paths"] if p["id"] == "drive_linked_sources")
    assert drive["operations"]["validate_source_freshness"] == "partial"
    assert drive["operations"]["create_notebook"] == "unsupported"
    assert drive["operations"]["list_notebooks"] == "unsupported"
    assert drive["operations"]["delete_notebook"] == "unsupported"


def test_fallback_is_browser_and_not_preferred(matrix: dict):
    assert matrix["fallback_path_id"] == "browser_ui_fallback"
    assert matrix["fallback_path_id"] != matrix["preferred_path_id"]


def test_manual_gaps_are_named_before_implementation(matrix: dict):
    gap_ids = {gap["id"] for gap in matrix["manual_only_gaps"]}
    required_gaps = {
        "cookie_auth_install",
        "cookie_rotation",
        "live_account_proof",
        "pasted_text_freshness",
        "native_replace",
        "create_new_then_retire",
        "enterprise_sku",
        "gemini_notebooks_api",
    }
    assert required_gaps <= gap_ids
    assert len(matrix["manual_only_gaps"]) >= 8


def test_wor188_packet_reuses_mcp_and_forbids_rebuild(matrix: dict):
    packet = matrix["wor188_packet"]
    assert packet["implement"] == "existing_mcp_text_sources"
    assert packet["do_not_rebuild"] is True
    assert packet["do_not_switch_to_enterprise_without_jeremy"] is True
    assert "src/notebooklm_mcp/api_client.py" in packet["reuse"]
    assert any("second documentation manifest" in line for line in packet["stop_lines"])


def test_mcp_tools_named_in_matrix_still_exist_in_server():
    source = SERVER_PATH.read_text(encoding="utf-8")
    for name in MCP_TOOL_NAMES:
        assert f"def {name}(" in source, name


def test_destructive_mcp_tools_still_require_confirm():
    source = SERVER_PATH.read_text(encoding="utf-8")
    for name in ("notebook_delete", "source_delete", "source_sync_drive"):
        start = source.index(f"def {name}(")
        chunk = source[start : start + 400]
        assert "confirm: bool = False" in chunk, name


def test_client_exposes_freshness_and_drive_sync():
    source = CLIENT_PATH.read_text(encoding="utf-8")
    assert "def check_source_freshness(" in source
    assert "def sync_drive_source(" in source
    assert "def add_text_source(" in source
    assert "def add_drive_source(" in source
    assert "def create_notebook(" in source
    assert "def list_notebooks(" in source
    assert "def delete_notebook(" in source


def test_apply_sync_plan_still_adds_before_deleting_on_update():
    source = SYNC_PATH.read_text(encoding="utf-8")
    assert "Process updates (add first, then delete old source)." in source
    add_at = source.index("new_source = client.add_text_source(")
    delete_at = source.index("delete_source_with_retry", add_at)
    assert add_at < delete_at
