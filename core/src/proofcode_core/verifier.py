from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    BASELINE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)


@dataclass(frozen=True)
class TestCommand:
    name: str
    command: list[str]
    working_directory: str
    interpreter_path: str
    interpreter_source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    status: str
    passed: bool
    timed_out: bool
    exit_code: int | None
    duration_seconds: float
    command: TestCommand
    python_version: str
    stdout: str
    stderr: str
    fingerprint_before: str
    fingerprint_after: str
    workspace_changed_during_run: bool
    baseline_saved: bool
    baseline_path: str | None
    baseline_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "passed": self.passed,
            "timed_out": self.timed_out,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "command": self.command.to_dict(),
            "python_version": self.python_version,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "fingerprint_before": self.fingerprint_before,
            "fingerprint_after": self.fingerprint_after,
            "workspace_changed_during_run": (
                self.workspace_changed_during_run
            ),
            "baseline_saved": self.baseline_saved,
            "baseline_path": self.baseline_path,
            "baseline_message": self.baseline_message,
        }


def _interpreter_candidates(workspace: Path) -> list[tuple[Path, str]]:
    if os.name == "nt":
        relative_paths = (
            ("core/.venv/Scripts/python.exe", "core/.venv"),
            (".venv/Scripts/python.exe", ".venv"),
        )
    else:
        relative_paths = (
            ("core/.venv/bin/python", "core/.venv"),
            (".venv/bin/python", ".venv"),
        )

    return [
        (workspace / relative_path, source)
        for relative_path, source in relative_paths
    ]


def resolve_python_interpreter(
    workspace_path: str,
) -> tuple[str, str]:
    workspace = Path(workspace_path).expanduser().resolve()

    for candidate, source in _interpreter_candidates(workspace):
        if candidate.is_file():
            return str(candidate), source

    return sys.executable, "current-core-process"


def detect_test_command(workspace_path: str) -> TestCommand:
    workspace = Path(workspace_path).expanduser().resolve()

    if not workspace.exists():
        raise FileNotFoundError(
            f"Workspace does not exist: {workspace}"
        )

    if not workspace.is_dir():
        raise ValueError(
            f"Workspace path is not a directory: {workspace}"
        )

    interpreter, interpreter_source = (
        resolve_python_interpreter(str(workspace))
    )

    for candidate in (workspace, workspace / "core"):
        if not candidate.is_dir():
            continue

        has_python_project = any(
            (candidate / marker).exists()
            for marker in (
                "pyproject.toml",
                "pytest.ini",
                "setup.cfg",
            )
        )
        has_tests = (candidate / "tests").is_dir()

        if has_python_project or has_tests:
            return TestCommand(
                name="pytest",
                command=[interpreter, "-m", "pytest"],
                working_directory=str(candidate),
                interpreter_path=interpreter,
                interpreter_source=interpreter_source,
            )

    raise ValueError(
        "지원되는 테스트 설정을 찾지 못했습니다. "
        "현재 단계에서는 pytest 프로젝트를 지원합니다."
    )


def _run_test_command(
    command: TestCommand,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command.command,
        cwd=command.working_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        },
    )


def _python_version(interpreter_path: str) -> str:
    if Path(interpreter_path).resolve() == Path(sys.executable).resolve():
        return platform.python_version()

    try:
        completed = subprocess.run(
            [
                interpreter_path,
                "-c",
                "import platform; print(platform.python_version())",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"

    if completed.returncode != 0:
        return "unknown"

    return completed.stdout.strip() or "unknown"


def _git_commit(workspace: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    return completed.stdout.strip() or None


def _baseline_path(workspace: Path) -> Path:
    return workspace / ".proofcode" / "evidence" / "baseline.json"


def _save_baseline(
    workspace: Path,
    command: TestCommand,
    python_version: str,
    duration_seconds: float,
    fingerprint: str,
    stdout: str,
    stderr: str,
) -> Path:
    path = _baseline_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)

    baseline = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_path": str(workspace),
        "workspace_fingerprint": fingerprint,
        "git_commit": _git_commit(workspace),
        "verification": {
            "status": "passed",
            "command": command.to_dict(),
            "python_version": python_version,
            "duration_seconds": duration_seconds,
            "exit_code": 0,
            "stdout": stdout,
            "stderr": stderr,
        },
    }

    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(
            baseline,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, path)

    return path


def verify_workspace(
    workspace_path: str,
    timeout_seconds: int = 60,
) -> VerificationResult:
    workspace = Path(workspace_path).expanduser().resolve()
    command = detect_test_command(str(workspace))
    python_version = _python_version(command.interpreter_path)
    fingerprint_before = workspace_fingerprint(str(workspace))
    started_at = time.perf_counter()

    try:
        completed = _run_test_command(
            command,
            timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        duration = round(time.perf_counter() - started_at, 3)
        fingerprint_after = workspace_fingerprint(str(workspace))

        stdout = error.stdout or ""
        stderr = error.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        return VerificationResult(
            status="timeout",
            passed=False,
            timed_out=True,
            exit_code=None,
            duration_seconds=duration,
            command=command,
            python_version=python_version,
            stdout=stdout,
            stderr=stderr,
            fingerprint_before=fingerprint_before,
            fingerprint_after=fingerprint_after,
            workspace_changed_during_run=(
                fingerprint_before != fingerprint_after
            ),
            baseline_saved=False,
            baseline_path=None,
            baseline_message=(
                "테스트가 시간 초과되어 Baseline을 저장하지 않았습니다."
            ),
        )

    duration = round(time.perf_counter() - started_at, 3)
    fingerprint_after = workspace_fingerprint(str(workspace))
    workspace_changed = fingerprint_before != fingerprint_after
    passed = completed.returncode == 0

    baseline_saved = False
    baseline_path: str | None = None

    if not passed:
        baseline_message = (
            "테스트가 실패하여 Baseline을 저장하지 않았습니다."
        )
    elif workspace_changed:
        baseline_message = (
            "테스트 실행 중 소스가 변경되어 Baseline을 저장하지 않았습니다."
        )
    else:
        saved_path = _save_baseline(
            workspace=workspace,
            command=command,
            python_version=python_version,
            duration_seconds=duration,
            fingerprint=fingerprint_after,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        baseline_saved = True
        baseline_path = str(saved_path)
        baseline_message = "유효한 Baseline을 저장했습니다."

    return VerificationResult(
        status="passed" if passed else "failed",
        passed=passed,
        timed_out=False,
        exit_code=completed.returncode,
        duration_seconds=duration,
        command=command,
        python_version=python_version,
        stdout=completed.stdout,
        stderr=completed.stderr,
        fingerprint_before=fingerprint_before,
        fingerprint_after=fingerprint_after,
        workspace_changed_during_run=workspace_changed,
        baseline_saved=baseline_saved,
        baseline_path=baseline_path,
        baseline_message=baseline_message,
    )
