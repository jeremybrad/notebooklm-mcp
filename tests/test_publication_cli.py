"""Command safety and offline execution, with fictional repositories only."""
import json

from notebooklm_mcp.doc_refresh.publication_cli import main
from tests.test_source_bundle import repo as source_repo, git


def arguments(tmp_path, repository, mode="plan"):
    revision = git(repository, "rev-parse", "HEAD")
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    return [mode, "--repo", str(repository), revision, "--map", str(tmp_path / "map.yaml"),
            "--receipts", str(receipts)]


def test_default_offline_plan_never_creates_map(tmp_path, capsys, source_repo):
    args = arguments(tmp_path, source_repo)
    assert main(args[1:]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "plan"
    assert result["status"] == "success"
    assert not (tmp_path / "map.yaml").exists()
    assert len(list((tmp_path / "receipts").glob("*.json"))) == 1


def test_cli_has_no_ambient_provider(tmp_path, capsys, monkeypatch, source_repo):
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "fictional-do-not-use-or-print")
    monkeypatch.setenv("GEMINI_API_KEY", "fictional-do-not-use-or-print")
    assert main(arguments(tmp_path, source_repo, "publish")) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed"
    assert "fictional-do-not" not in json.dumps(result)
    assert not (tmp_path / "map.yaml").exists()


def test_malformed_snapshot_is_redacted_and_never_executes(tmp_path, capsys, source_repo):
    path = tmp_path / "snapshots.json"
    path.write_text('{"secret":"never-report-this"')
    assert main(arguments(tmp_path, source_repo) + ["--snapshots", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "never-report-this" not in captured.err
    assert not list((tmp_path / "receipts").iterdir())


def test_duplicate_snapshot_keys_refused(tmp_path, capsys, source_repo):
    path = tmp_path / "snapshots.json"
    path.write_text('{"repo":{},"repo":{}}')
    assert main(arguments(tmp_path, source_repo) + ["--snapshots", str(path)]) == 2
    assert "Invalid snapshot input" in capsys.readouterr().err


def test_receipt_failure_is_nonzero_without_success_output(tmp_path, capsys, source_repo):
    args = arguments(tmp_path, source_repo)
    args[-1] = str(tmp_path / "missing" / "receipts")
    assert main(args) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Receipt persistence failed" in captured.err
