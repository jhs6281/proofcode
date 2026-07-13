import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from proofcode_core.verifier import (
    detect_test_command,
    verify_workspace,
)


def _create_python_project(workspace: Path) -> Path:
    core = workspace / "core"
    core.mkdir()
    (core / "pyproject.toml").write_text(
        "[project]\nname = 'sample'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (core / "tests").mkdir()
    (core / "sample.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    return core


def test_detect_test_command_prefers_project_venv(
    tmp_path: Path,
) -> None:
    _create_python_project(tmp_path)

    if os.name == "nt":
        interpreter = (
            tmp_path
            / "core"
            / ".venv"
            / "Scripts"
            / "python.exe"
        )
    else:
        interpreter = (
            tmp_path
            / "core"
            / ".venv"
            / "bin"
            / "python"
        )

    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("", encoding="utf-8")

    command = detect_test_command(str(tmp_path))

    assert command.name == "pytest"
    assert command.interpreter_path == str(interpreter)
    assert command.interpreter_source == "core/.venv"
    assert command.command == [
        str(interpreter),
        "-m",
        "pytest",
    ]


def test_failed_tests_do_not_create_baseline(
    tmp_path: Path,
) -> None:
    _create_python_project(tmp_path)

    completed = subprocess.CompletedProcess(
        args=["python", "-m", "pytest"],
        returncode=1,
        stdout="1 failed\n",
        stderr="",
    )

    with patch(
        "proofcode_core.verifier._run_test_command",
        return_value=completed,
    ):
        result = verify_workspace(str(tmp_path))

    assert result.passed is False
    assert result.baseline_saved is False
    assert result.baseline_path is None
    assert not (
        tmp_path
        / ".proofcode"
        / "evidence"
        / "baseline.json"
    ).exists()


def test_passed_tests_create_baseline(
    tmp_path: Path,
) -> None:
    _create_python_project(tmp_path)

    completed = subprocess.CompletedProcess(
        args=["python", "-m", "pytest"],
        returncode=0,
        stdout="3 passed\n",
        stderr="",
    )

    with (
        patch(
            "proofcode_core.verifier._run_test_command",
            return_value=completed,
        ),
        patch(
            "proofcode_core.verifier._git_commit",
            return_value="abc123",
        ),
    ):
        result = verify_workspace(str(tmp_path))

    baseline = (
        tmp_path
        / ".proofcode"
        / "evidence"
        / "baseline.json"
    )

    assert result.passed is True
    assert result.baseline_saved is True
    assert result.baseline_path == str(baseline)
    assert baseline.exists()


def test_source_change_during_test_blocks_baseline(
    tmp_path: Path,
) -> None:
    core = _create_python_project(tmp_path)
    source = core / "sample.py"

    def run_and_change_source(*args: object, **kwargs: object):
        source.write_text("VALUE = 2\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=["python", "-m", "pytest"],
            returncode=0,
            stdout="3 passed\n",
            stderr="",
        )

    with patch(
        "proofcode_core.verifier._run_test_command",
        side_effect=run_and_change_source,
    ):
        result = verify_workspace(str(tmp_path))

    assert result.passed is True
    assert result.workspace_changed_during_run is True
    assert result.baseline_saved is False


def test_unsupported_project_is_reported(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="pytest"):
        detect_test_command(str(tmp_path))
