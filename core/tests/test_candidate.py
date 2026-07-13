import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from proofcode_core.candidate import (
    parse_pytest_summary,
    verify_candidate_file,
)
from proofcode_core.fingerprint import (
    workspace_fingerprint,
)
from proofcode_core.version import (
    APP_VERSION,
    BASELINE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)


def create_workspace(root: Path) -> tuple[Path, Path]:
    workspace = root / "workspace"
    core = workspace / "core"
    tests = core / "tests"
    source = core / "src" / "sample"

    tests.mkdir(parents=True)
    source.mkdir(parents=True)

    (core / "pyproject.toml").write_text(
        """
[project]
name = "sample"
version = "0.1.0"
""".lstrip(),
        encoding="utf-8",
    )
    target = source / "calculator.py"
    target.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    (tests / "test_calculator.py").write_text(
        """
from sample.calculator import add

def test_add():
    assert add(1, 2) == 3
""".lstrip(),
        encoding="utf-8",
    )

    return workspace, target


def create_baseline(workspace: Path) -> Path:
    fingerprint = workspace_fingerprint(str(workspace))
    path = (
        workspace
        / ".proofcode"
        / "evidence"
        / "baseline.json"
    )
    path.parent.mkdir(parents=True)

    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "workspace_path": str(workspace),
        "workspace_fingerprint": fingerprint,
        "verification": {
            "status": "passed",
            "command": {
                "name": "pytest",
                "command": [
                    sys.executable,
                    "-m",
                    "pytest",
                ],
                "working_directory": str(
                    workspace / "core"
                ),
                "interpreter_path": sys.executable,
                "interpreter_source": "test",
            },
            "python_version": "test",
            "duration_seconds": 0.2,
            "exit_code": 0,
            "stdout": "3 passed in 0.20s\n",
            "stderr": "",
        },
    }
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_parse_pytest_summary() -> None:
    summary = parse_pytest_summary(
        "2 failed, 14 passed, 1 skipped in 0.23s"
    )

    assert summary.passed == 14
    assert summary.failed == 2
    assert summary.skipped == 1


def test_passing_candidate_is_reviewable_and_original_unchanged(
    tmp_path: Path,
) -> None:
    workspace, target = create_workspace(tmp_path)
    create_baseline(workspace)

    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        "def add(a, b):\n    return sum((a, b))\n",
        encoding="utf-8",
    )
    original_text = target.read_text(encoding="utf-8")

    completed = subprocess.CompletedProcess(
        args=[sys.executable, "-m", "pytest"],
        returncode=0,
        stdout="3 passed in 0.21s\n",
        stderr="",
    )

    with patch(
        "proofcode_core.candidate._run_candidate_tests",
        return_value=completed,
    ):
        result = verify_candidate_file(
            str(workspace),
            str(target),
            str(candidate),
        )

    assert result.verdict == "reviewable"
    assert result.passed is True
    assert result.evidence_saved is True
    assert Path(result.evidence_path or "").exists()
    assert target.read_text(encoding="utf-8") == original_text
    assert result.original_sha256 != result.candidate_sha256


def test_failing_candidate_is_recorded_but_not_reviewable(
    tmp_path: Path,
) -> None:
    workspace, target = create_workspace(tmp_path)
    create_baseline(workspace)

    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        "def add(a, b):\n    return 0\n",
        encoding="utf-8",
    )

    completed = subprocess.CompletedProcess(
        args=[sys.executable, "-m", "pytest"],
        returncode=1,
        stdout="1 failed, 2 passed in 0.21s\n",
        stderr="",
    )

    with patch(
        "proofcode_core.candidate._run_candidate_tests",
        return_value=completed,
    ):
        result = verify_candidate_file(
            str(workspace),
            str(target),
            str(candidate),
        )

    assert result.verdict == "failed"
    assert result.passed is False
    assert result.candidate_summary.failed == 1
    assert result.evidence_saved is True


def test_stale_baseline_blocks_candidate_verification(
    tmp_path: Path,
) -> None:
    workspace, target = create_workspace(tmp_path)
    create_baseline(workspace)

    target.write_text(
        "def add(a, b):\n    return a - b\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Baseline을 만든 뒤 Workspace가 변경",
    ):
        verify_candidate_file(
            str(workspace),
            str(target),
            str(candidate),
        )


def test_candidate_extension_must_match_target(
    tmp_path: Path,
) -> None:
    workspace, target = create_workspace(tmp_path)
    create_baseline(workspace)

    candidate = tmp_path / "candidate.txt"
    candidate.write_text("candidate", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="확장자가 다릅니다",
    ):
        verify_candidate_file(
            str(workspace),
            str(target),
            str(candidate),
        )
