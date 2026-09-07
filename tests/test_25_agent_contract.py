"""Feature 25: the ecosystem agent contract — agent.yaml, `friday --health`,
and the personal-token tier guarantee.

Friday is one specialist agent in a wider personal multi-agent ecosystem.
Each agent publishes a small contract (agent.yaml) other tooling can read
without running the agent, plus a health_check_command it can actually run.
"""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from friday import cli as C
from friday import config as CFG

REPO_ROOT = Path(__file__).resolve().parent.parent

runner = CliRunner()


# --- agent.yaml -------------------------------------------------------------
@pytest.fixture(scope="module")
def agent_manifest():
    path = REPO_ROOT / "agent.yaml"
    assert path.exists(), "agent.yaml must exist at the repo root"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_agent_yaml_is_valid_yaml(agent_manifest):
    assert isinstance(agent_manifest, dict)


def test_agent_yaml_has_required_fields(agent_manifest):
    required = {
        "name", "role", "default_sensitivity_tier", "entrypoint",
        "health_check_command", "vault_write_path", "sandboxed",
    }
    missing = required - agent_manifest.keys()
    assert not missing, f"agent.yaml missing fields: {sorted(missing)}"


def test_agent_yaml_identity_matches_rename(agent_manifest):
    assert agent_manifest["name"] == "Friday"
    assert agent_manifest["entrypoint"] == "friday"
    assert agent_manifest["health_check_command"] == "friday --health"


def test_agent_yaml_declares_personal_token_tier(agent_manifest):
    assert agent_manifest["default_sensitivity_tier"] == "personal-token"


def test_agent_yaml_sandboxed_is_bool(agent_manifest):
    assert isinstance(agent_manifest["sandboxed"], bool)


# --- `friday --health` -------------------------------------------------------
def test_health_flag_exits_cleanly():
    result = runner.invoke(C.cli, ["--health"])
    assert result.exit_code == 0


def test_health_flag_emits_valid_json():
    result = runner.invoke(C.cli, ["--health"])
    payload = json.loads(result.output)
    assert isinstance(payload, dict)


def test_health_report_shape(write_index):
    write_index([{"id": "1", "title": "N", "type": "concept", "domain": "d",
                  "date": "2026-07-22", "folder_path": "f", "filename": "n.md"}])
    result = runner.invoke(C.cli, ["--health"])
    payload = json.loads(result.output)

    assert "version" in payload
    assert set(payload["providers"].keys()) == {"groq", "gemini"}
    for info in payload["providers"].values():
        assert "reachable" in info and "model" in info

    assert payload["catalogue"].keys() == {"notes_on_disk", "notes_in_catalogue", "drift"}
    assert isinstance(payload["catalogue"]["notes_on_disk"], int)

    assert payload["personal_token_tier"]["tier"] == "personal-token"
    assert isinstance(payload["personal_token_tier"]["ok"], bool)

    assert "last_capture" in payload  # None or an ISO date string


def test_health_report_last_capture_reflects_index(write_index):
    write_index([
        {"id": "1", "title": "Old", "date": "2026-01-01", "folder_path": "f", "filename": "old.md"},
        {"id": "2", "title": "New", "date": "2026-08-30", "folder_path": "f", "filename": "new.md"},
    ])
    result = runner.invoke(C.cli, ["--health"])
    payload = json.loads(result.output)
    assert payload["last_capture"] == "2026-08-30"


def test_health_report_catalogue_counts_notes_in_index(write_index):
    write_index([])
    result = runner.invoke(C.cli, ["--health"])
    payload = json.loads(result.output)
    assert payload["catalogue"]["notes_in_catalogue"] == 0


def test_health_flag_does_not_mutate_catalogue(sandbox, clean_index):
    """--health reports drift but must not write it — it's a health check,
    not a reindex. Reconciliation happens explicitly via `friday reindex`,
    `friday doctor`, or `friday daily`."""
    note_dir = sandbox / "08-databases"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "unindexed.md").write_text(
        '---\ntitle: "Unindexed"\ndomain: databases\ntype: concept\n---\n'
        "# Unindexed\n\nShould not be added just by checking health.\n",
        encoding="utf-8",
    )

    result = runner.invoke(C.cli, ["--health"])
    payload = json.loads(result.output)
    assert payload["catalogue"]["drift"] >= 1

    notes = json.loads(clean_index.read_text(encoding="utf-8"))["notes"]
    assert not any(n["filename"] == "unindexed.md" for n in notes)


# --- personal-token tier guarantee ------------------------------------------
def test_assert_personal_token_tier_passes_with_clean_env(monkeypatch):
    for key in list(__import__("os").environ):
        if "SHARED_POOL" in key.upper() or "WORK_TIER" in key.upper():
            monkeypatch.delenv(key, raising=False)
    assert CFG.assert_personal_token_tier() is True


def test_assert_personal_token_tier_rejects_shared_pool_key(monkeypatch):
    monkeypatch.setenv("GROQ_SHARED_POOL_KEY", "fake-shared-key")
    with pytest.raises(RuntimeError, match="personal-token tier violation"):
        CFG.assert_personal_token_tier()


def test_assert_personal_token_tier_rejects_work_tier_key(monkeypatch):
    monkeypatch.setenv("GEMINI_WORK_TIER_TOKEN", "fake-work-key")
    with pytest.raises(RuntimeError):
        CFG.assert_personal_token_tier()


def test_health_report_flags_tier_violation(monkeypatch):
    monkeypatch.setenv("FRIDAY_SHARED_POOL_KEY", "fake")
    result = runner.invoke(C.cli, ["--health"])
    payload = json.loads(result.output)
    assert payload["personal_token_tier"]["ok"] is False
    assert payload["personal_token_tier"]["error"]
