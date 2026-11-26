"""Validate that every remote GitHub Actions workflow dependency is immutable."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


def validate_workflows(repository_root: Path) -> tuple[list[str], int, int]:
    """Return (errors, remote_action_count, workflow_count)."""
    workflow_dir = repository_root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return [f"workflow directory not found: {workflow_dir}"], 0, 0

    errors: list[str] = []
    action_count = 0
    workflow_count = 0
    paths = sorted((*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")))
    for path in paths:
        workflow_count += 1
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = USES_RE.match(line)
            if not match:
                continue
            reference = match.group(1)
            if reference.startswith(("./", "docker://")):
                continue
            action_count += 1
            if "@" not in reference:
                errors.append(
                    f"{path.relative_to(repository_root)}:{line_number}: "
                    f"remote action is not pinned: {reference}"
                )
                continue
            revision = reference.rsplit("@", 1)[1]
            if not FULL_SHA_RE.fullmatch(revision):
                errors.append(
                    f"{path.relative_to(repository_root)}:{line_number}: "
                    f"action ref must be a full 40-character commit SHA: {reference}"
                )

    if workflow_count == 0:
        errors.append(f"no workflow files found in {workflow_dir}")
    return errors, action_count, workflow_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of application/)",
    )
    args = parser.parse_args()
    errors, action_count, workflow_count = validate_workflows(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(
            f"Rejected {len(errors)} issue(s) across {workflow_count} workflow(s); "
            f"inspected {action_count} remote action reference(s)."
        )
        return 1
    print(
        f"PASS: all {action_count} remote action reference(s) across "
        f"{workflow_count} workflow(s) use immutable full commit SHAs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
