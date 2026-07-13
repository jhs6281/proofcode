from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    BASELINE_SCHEMA_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)

COPY_EXCLUDED_NAMES = {
    ".git",
    ".proofcode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "out",
    "dist",
    "build",
}


@dataclass(frozen=True)
class PytestSummary:
    passed: int
    failed: int
    skipped: int
    errors: int
    xfailed: int
    xpassed: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateVerificationResult:
    verdict: str
    passed: bool
    timed_out: bool
    exit_code: int | None
    duration_seconds: float
    baseline_duration_seconds: float
    duration_delta_seconds: float
    duration_ratio: float | None
    target_path: str
    target_relative_path: str
    candidate_path: str
    original_sha256: str
    candidate_sha256: str
    baseline_fingerprint: str
    original_fingerprint_before: str
    original_fingerprint_after: str
    isolated_fingerprint_before: str
    isolated_fingerprint_after: str
    original_workspace_changed_during_run: bool
    isolated_workspace_changed_during_run: bool
    command: list[str]
    working_directory: str
    interpreter_path: str
    baseline_summary: PytestSummary
    candidate_summary: PytestSummary
    stdout: str
    stderr: str
    evidence_saved: bool
    evidence_path: str | None
    message: str
    security_scope: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["baseline_summary"] = self.baseline_summary.to_dict()
        data["candidate_summary"] = self.candidate_summary.to_dict()
        return data


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _load_baseline(workspace: Path) -> dict[str, Any]:
    path = workspace / ".proofcode" / "evidence" / "baseline.json"

    if not path.is_file():
        raise ValueError(
            "유효한 Baseline이 없습니다. "
            "먼저 ProofCode: Verify Baseline을 실행하세요."
        )

    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            "Baseline 파일을 읽을 수 없습니다. "
            "Baseline을 다시 생성하세요."
        ) from error

    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise ValueError(
            "Baseline 형식 버전이 현재 ProofCode와 다릅니다. "
            "Baseline을 다시 생성하세요."
        )

    verification = baseline.get("verification")

    if not isinstance(verification, dict):
        raise ValueError("Baseline 검증 정보가 없습니다.")

    if verification.get("status") != "passed":
        raise ValueError(
            "테스트를 통과한 Baseline이 아닙니다. "
            "Baseline을 다시 생성하세요."
        )

    return baseline


def _path_inside_workspace(path: Path, workspace: Path) -> Path:
    try:
        return path.relative_to(workspace)
    except ValueError as error:
        raise ValueError(
            f"대상 파일은 Workspace 안에 있어야 합니다: {path}"
        ) from error


def _parse_count(output: str, label: str) -> int:
    pattern = rf"(?<!\d)(\d+)\s+{re.escape(label)}\b"
    match = re.search(pattern, output, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def parse_pytest_summary(output: str) -> PytestSummary:
    return PytestSummary(
        passed=_parse_count(output, "passed"),
        failed=_parse_count(output, "failed"),
        skipped=_parse_count(output, "skipped"),
        errors=(
            _parse_count(output, "error")
            + _parse_count(output, "errors")
        ),
        xfailed=_parse_count(output, "xfailed"),
        xpassed=_parse_count(output, "xpassed"),
    )


def _candidate_pythonpath(isolated_workspace: Path) -> str:
    source_candidates = (
        isolated_workspace / "core" / "src",
        isolated_workspace / "src",
    )
    entries = [
        str(path)
        for path in source_candidates
        if path.is_dir()
    ]

    existing = os.environ.get("PYTHONPATH")

    if existing:
        entries.append(existing)

    return os.pathsep.join(entries)


def _run_candidate_tests(
    command: list[str],
    working_directory: Path,
    isolated_workspace: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(working_directory),
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
            "PYTHONPATH": _candidate_pythonpath(
                isolated_workspace
            ),
        },
    )


def _save_candidate_evidence(
    workspace: Path,
    result: CandidateVerificationResult,
) -> Path:
    directory = (
        workspace
        / ".proofcode"
        / "evidence"
        / "candidates"
    )
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    safe_stem = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "-",
        Path(result.target_relative_path).stem,
    ).strip("-") or "candidate"

    filename = (
        f"{timestamp}-{safe_stem}-"
        f"{result.candidate_sha256[:8]}.json"
    )
    path = directory / filename

    payload = {
        "schema_version": CANDIDATE_EVIDENCE_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_verification": result.to_dict(),
    }

    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)

    return path


def _result_with_evidence(
    workspace: Path,
    result: CandidateVerificationResult,
) -> CandidateVerificationResult:
    evidence_path = _save_candidate_evidence(
        workspace,
        result,
    )

    data = result.to_dict()
    data["evidence_saved"] = True
    data["evidence_path"] = str(evidence_path)

    return CandidateVerificationResult(
        **{
            key: value
            for key, value in data.items()
            if key not in {
                "baseline_summary",
                "candidate_summary",
            }
        },
        baseline_summary=result.baseline_summary,
        candidate_summary=result.candidate_summary,
    )


def verify_candidate_file(
    workspace_path: str,
    target_file_path: str,
    candidate_file_path: str,
    timeout_seconds: int = 60,
) -> CandidateVerificationResult:
    workspace = Path(workspace_path).expanduser().resolve()
    target = Path(target_file_path).expanduser().resolve()
    candidate = Path(candidate_file_path).expanduser().resolve()

    if not workspace.is_dir():
        raise ValueError(
            f"Workspace가 올바른 폴더가 아닙니다: {workspace}"
        )

    if not target.is_file():
        raise ValueError(
            f"원본 대상 파일을 찾을 수 없습니다: {target}"
        )

    if not candidate.is_file():
        raise ValueError(
            f"후보 파일을 찾을 수 없습니다: {candidate}"
        )

    relative_target = _path_inside_workspace(
        target,
        workspace,
    )

    if target.suffix.lower() != candidate.suffix.lower():
        raise ValueError(
            "원본 파일과 후보 파일의 확장자가 다릅니다. "
            f"원본={target.suffix}, 후보={candidate.suffix}"
        )

    baseline = _load_baseline(workspace)
    baseline_fingerprint = str(
        baseline["workspace_fingerprint"]
    )
    original_fingerprint_before = workspace_fingerprint(
        str(workspace)
    )

    if baseline_fingerprint != original_fingerprint_before:
        raise ValueError(
            "Baseline을 만든 뒤 Workspace가 변경되었습니다. "
            "먼저 ProofCode: Verify Baseline을 다시 실행하세요."
        )

    verification = baseline["verification"]
    baseline_command = verification["command"]

    if not isinstance(baseline_command, dict):
        raise ValueError("Baseline 테스트 명령이 올바르지 않습니다.")

    command = [
        str(item)
        for item in baseline_command.get("command", [])
    ]

    if not command:
        raise ValueError("Baseline 테스트 명령이 비어 있습니다.")

    original_working_directory = Path(
        str(baseline_command["working_directory"])
    ).expanduser().resolve()

    try:
        relative_working_directory = (
            original_working_directory.relative_to(workspace)
        )
    except ValueError as error:
        raise ValueError(
            "Baseline 테스트 실행 위치가 Workspace 밖에 있습니다."
        ) from error

    original_bytes = target.read_bytes()
    candidate_bytes = candidate.read_bytes()
    original_hash = _sha256_bytes(original_bytes)
    candidate_hash = _sha256_bytes(candidate_bytes)
    baseline_stdout = str(verification.get("stdout", ""))
    baseline_stderr = str(verification.get("stderr", ""))
    baseline_summary = parse_pytest_summary(
        baseline_stdout + "\n" + baseline_stderr
    )
    baseline_duration = float(
        verification.get("duration_seconds", 0.0)
    )

    timeout = False
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    duration = 0.0
    isolated_before = ""
    isolated_after = ""

    with tempfile.TemporaryDirectory(
        prefix="proofcode-candidate-"
    ) as temporary_directory:
        isolated_workspace = (
            Path(temporary_directory) / "workspace"
        )

        shutil.copytree(
            workspace,
            isolated_workspace,
            ignore=shutil.ignore_patterns(
                *COPY_EXCLUDED_NAMES
            ),
        )

        isolated_target = (
            isolated_workspace / relative_target
        )
        isolated_target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        isolated_target.write_bytes(candidate_bytes)

        isolated_working_directory = (
            isolated_workspace
            / relative_working_directory
        )

        if not isolated_working_directory.is_dir():
            raise ValueError(
                "임시 Workspace에서 테스트 실행 위치를 "
                "찾을 수 없습니다."
            )

        isolated_before = workspace_fingerprint(
            str(isolated_workspace)
        )
        started = time.perf_counter()

        try:
            completed = _run_candidate_tests(
                command=command,
                working_directory=(
                    isolated_working_directory
                ),
                isolated_workspace=isolated_workspace,
                timeout_seconds=timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as error:
            timeout = True
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

        duration = round(
            time.perf_counter() - started,
            3,
        )
        isolated_after = workspace_fingerprint(
            str(isolated_workspace)
        )

    original_fingerprint_after = workspace_fingerprint(
        str(workspace)
    )
    original_changed = (
        original_fingerprint_before
        != original_fingerprint_after
    )
    isolated_changed = isolated_before != isolated_after
    passed = (
        not timeout
        and exit_code == 0
        and not original_changed
        and not isolated_changed
    )

    if timeout:
        verdict = "blocked"
        message = (
            "후보 테스트가 시간 초과되어 검증을 완료하지 "
            "못했습니다."
        )
    elif original_changed:
        verdict = "blocked"
        message = (
            "후보 테스트 중 원본 Workspace가 변경되어 "
            "결과를 신뢰할 수 없습니다."
        )
    elif isolated_changed:
        verdict = "blocked"
        message = (
            "테스트 실행 중 임시 소스가 변경되어 결과를 "
            "신뢰할 수 없습니다."
        )
    elif exit_code != 0:
        verdict = "failed"
        message = (
            "후보 파일을 적용한 임시 복사본에서 테스트가 "
            "실패했습니다."
        )
    else:
        verdict = "reviewable"
        message = (
            "후보 파일이 Baseline과 같은 테스트를 통과했습니다. "
            "자동 적용하지 않고 개발자 검토를 기다립니다."
        )

    duration_delta = round(
        duration - baseline_duration,
        3,
    )
    duration_ratio = (
        round(duration / baseline_duration, 3)
        if baseline_duration > 0
        else None
    )
    candidate_summary = parse_pytest_summary(
        stdout + "\n" + stderr
    )

    result = CandidateVerificationResult(
        verdict=verdict,
        passed=passed,
        timed_out=timeout,
        exit_code=exit_code,
        duration_seconds=duration,
        baseline_duration_seconds=baseline_duration,
        duration_delta_seconds=duration_delta,
        duration_ratio=duration_ratio,
        target_path=str(target),
        target_relative_path=relative_target.as_posix(),
        candidate_path=str(candidate),
        original_sha256=original_hash,
        candidate_sha256=candidate_hash,
        baseline_fingerprint=baseline_fingerprint,
        original_fingerprint_before=(
            original_fingerprint_before
        ),
        original_fingerprint_after=(
            original_fingerprint_after
        ),
        isolated_fingerprint_before=isolated_before,
        isolated_fingerprint_after=isolated_after,
        original_workspace_changed_during_run=(
            original_changed
        ),
        isolated_workspace_changed_during_run=(
            isolated_changed
        ),
        command=command,
        working_directory=str(
            original_working_directory
        ),
        interpreter_path=str(command[0]),
        baseline_summary=baseline_summary,
        candidate_summary=candidate_summary,
        stdout=stdout,
        stderr=stderr,
        evidence_saved=False,
        evidence_path=None,
        message=message,
        security_scope=(
            "temporary-filesystem-copy; "
            "not-an-os-or-container-security-sandbox"
        ),
    )

    return _result_with_evidence(workspace, result)
