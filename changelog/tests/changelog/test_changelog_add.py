import json

from typer.testing import CliRunner

from src.changelog import app

runner = CliRunner()


def _invoke_add(tmp_path, domain="database", entry_type="bug", message="A test fix", issue="42"):
    return runner.invoke(
        app,
        [
            "add",
            "--working-dir", str(tmp_path),
            "--domain", domain,
            "--type", entry_type,
            "--message", message,
            "--issue", issue,
        ],
    )


def test_add_creates_entry_file(tmp_path):
    result = _invoke_add(tmp_path)
    assert result.exit_code == 0
    file_path = result.output.strip()
    assert file_path.endswith(".json")
    with open(file_path) as f:
        entry = json.load(f)
    assert entry["message"] == "A test fix"
    assert entry["domain"] == "database"


def test_add_includes_issue_number(tmp_path):
    result = _invoke_add(tmp_path, issue="99")
    assert result.exit_code == 0
    file_path = result.output.strip()
    with open(file_path) as f:
        entry = json.load(f)
    assert entry["issue_number"] == 99


def test_add_without_issue(tmp_path):
    result = _invoke_add(tmp_path, issue="")
    assert result.exit_code == 0
    file_path = result.output.strip()
    with open(file_path) as f:
        entry = json.load(f)
    assert entry.get("issue_number") is None


def test_add_invalid_domain(tmp_path):
    result = _invoke_add(tmp_path, domain="not_a_real_domain")
    assert result.exit_code != 0


def test_add_invalid_type(tmp_path):
    result = _invoke_add(tmp_path, entry_type="not_a_real_type")
    assert result.exit_code != 0


def test_add_invalid_issue(tmp_path):
    result = _invoke_add(tmp_path, issue="not-a-number")
    assert result.exit_code != 0


def test_add_without_issue_flag_runs_noninteractively(tmp_path):
    result = runner.invoke(
        app,
        [
            "add",
            "--working-dir", str(tmp_path),
            "--domain", "database",
            "--type", "bug",
            "--message", "A test fix",
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip().endswith(".json")