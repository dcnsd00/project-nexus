from pathlib import Path

from tools_validate_github_action_pins import validate_workflows


def test_accepts_full_commit_shas_and_non_remote_actions(tmp_path: Path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ci.yml").write_text(
        "steps:\n"
        "  - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567 # v7\n"
        "  - uses: ./local-action\n"
        "  - uses: docker://alpine:3.20\n",
        encoding="utf-8",
    )

    errors, action_count, workflow_count = validate_workflows(tmp_path)

    assert errors == []
    assert action_count == 1
    assert workflow_count == 1


def test_rejects_mutable_tags_and_branches(tmp_path: Path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ci.yaml").write_text(
        "steps:\n"
        "  - uses: actions/checkout@v4\n"
        "  - uses: actions/setup-python@main\n"
        "  - uses: actions/upload-artifact\n",
        encoding="utf-8",
    )

    errors, action_count, workflow_count = validate_workflows(tmp_path)

    assert len(errors) == 3
    assert action_count == 3
    assert workflow_count == 1


def test_reports_missing_workflow_directory(tmp_path: Path):
    errors, action_count, workflow_count = validate_workflows(tmp_path)

    assert errors
    assert action_count == 0
    assert workflow_count == 0
