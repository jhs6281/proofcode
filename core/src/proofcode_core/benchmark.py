from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    BASELINE_SCHEMA_VERSION,
    BENCHMARK_EVIDENCE_SCHEMA_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)

ObservedChange = Literal[
    "faster",
    "slower",
    "similar",
    "not_comparable",
]

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
class BenchmarkRun:
    subject: str
    round_number: int
    warmup: bool
    duration_seconds: float
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkStats:
    runs: int
    mean_seconds: float
    median_seconds: float
    minimum_seconds: float
    maximum_seconds: float
    standard_deviation_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateBenchmarkResult:
    verdict: str
    observed_change: ObservedChange
    message: str
    measured_runs: int
    warmup_runs: int
    target_relative_path: str
    candidate_path: str
    candidate_sha256: str
    candidate_evidence_path: str
    candidate_evidence_sha256: str
    baseline_fingerprint: str
    workspace_fingerprint_before: str
    workspace_fingerprint_after: str
    workspace_changed_during_run: bool
    baseline_copy_changed_during_run: bool
    candidate_copy_changed_during_run: bool
    baseline_stats: BenchmarkStats
    candidate_stats: BenchmarkStats
    median_delta_seconds: float
    median_ratio: float | None
    observed_percent_change: float | None
    command: list[str]
    working_directory: str
    interpreter_path: str
    runs: list[BenchmarkRun]
    evidence_saved: bool
    evidence_path: str | None
    security_scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "baseline_stats": self.baseline_stats.to_dict(),
            "candidate_stats": self.candidate_stats.to_dict(),
            "runs": [item.to_dict() for item in self.runs],
        }


def calculate_stats(values: list[float]) -> BenchmarkStats:
    if not values:
        return BenchmarkStats(
            runs=0,
            mean_seconds=0.0,
            median_seconds=0.0,
            minimum_seconds=0.0,
            maximum_seconds=0.0,
            standard_deviation_seconds=0.0,
        )

    rounded_values = [round(value, 6) for value in values]

    return BenchmarkStats(
        runs=len(rounded_values),
        mean_seconds=round(
            statistics.fmean(rounded_values),
            6,
        ),
        median_seconds=round(
            statistics.median(rounded_values),
            6,
        ),
        minimum_seconds=round(
            min(rounded_values),
            6,
        ),
        maximum_seconds=round(
            max(rounded_values),
            6,
        ),
        standard_deviation_seconds=round(
            statistics.pstdev(rounded_values),
            6,
        ),
    )


def classify_observed_change(
    baseline_median: float,
    candidate_median: float,
) -> ObservedChange:
    if baseline_median <= 0 or candidate_median <= 0:
        return "not_comparable"

    delta = candidate_median - baseline_median
    ratio = candidate_median / baseline_median

    # 너무 작은 차이는 측정 잡음일 가능성이 높습니다.
    if abs(delta) < 0.01 or 0.95 <= ratio <= 1.05:
        return "similar"

    if ratio < 0.95:
        return "faster"

    return "slower"


def _workspace(workspace_path: str) -> Path:
    workspace = Path(workspace_path).expanduser().resolve()

    if not workspace.exists():
        raise FileNotFoundError(
            f"Workspace does not exist: {workspace}"
        )

    if not workspace.is_dir():
        raise ValueError(
            f"Workspace path is not a directory: {workspace}"
        )

    return workspace


def _read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(
            f"{description} 파일을 읽을 수 없습니다: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{description} 파일이 올바른 JSON이 아닙니다: {path}"
        ) from error

    if not isinstance(value, dict):
        raise ValueError(
            f"{description} JSON의 최상위 값은 객체여야 합니다."
        )

    return value


def _candidate_evidence_path(
    workspace: Path,
    evidence_path: str,
) -> Path:
    directory = (
        workspace
        / ".proofcode"
        / "evidence"
        / "candidates"
    ).resolve()
    path = Path(evidence_path).expanduser().resolve()

    if not path.is_file():
        raise ValueError(
            f"Candidate Evidence 파일을 찾을 수 없습니다: {path}"
        )

    if not path.is_relative_to(directory):
        raise ValueError(
            "Candidate Evidence는 현재 Workspace의 "
            ".proofcode/evidence/candidates 안에 있어야 합니다."
        )

    return path


def _load_baseline(workspace: Path) -> dict[str, Any]:
    path = (
        workspace
        / ".proofcode"
        / "evidence"
        / "baseline.json"
    )

    if not path.is_file():
        raise ValueError(
            "유효한 Baseline이 없습니다. "
            "먼저 ProofCode: Verify Baseline을 실행하세요."
        )

    baseline = _read_json(path, "Baseline")

    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise ValueError(
            "Baseline 형식이 현재 ProofCode와 다릅니다. "
            "Baseline을 다시 생성하세요."
        )

    verification = baseline.get("verification")

    if not isinstance(verification, dict):
        raise ValueError("Baseline 검증 정보가 없습니다.")

    if verification.get("status") != "passed":
        raise ValueError(
            "테스트를 통과한 Baseline이 아닙니다."
        )

    return baseline


def _load_candidate_evidence(
    workspace: Path,
    evidence_path: str,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path = _candidate_evidence_path(
        workspace,
        evidence_path,
    )
    payload = _read_json(path, "Candidate Evidence")

    if (
        payload.get("schema_version")
        != CANDIDATE_EVIDENCE_SCHEMA_VERSION
    ):
        raise ValueError(
            "Candidate Evidence 형식이 현재 ProofCode와 "
            "다릅니다. Candidate를 다시 검증하세요."
        )

    verification = payload.get(
        "candidate_verification"
    )

    if not isinstance(verification, dict):
        raise ValueError(
            "Candidate Evidence에 검증 결과가 없습니다."
        )

    if (
        verification.get("verdict") != "reviewable"
        or verification.get("passed") is not True
    ):
        raise ValueError(
            "테스트를 통과해 reviewable 판정을 받은 "
            "Candidate만 Benchmark할 수 있습니다."
        )

    return path, payload, verification


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _relative_working_directory(
    workspace: Path,
    baseline: dict[str, Any],
) -> tuple[list[str], Path, str]:
    verification = baseline["verification"]
    command_data = verification.get("command")

    if not isinstance(command_data, dict):
        raise ValueError("Baseline 테스트 명령이 없습니다.")

    command = [
        str(item)
        for item in command_data.get("command", [])
    ]

    if not command:
        raise ValueError("Baseline 테스트 명령이 비어 있습니다.")

    original_working_directory = Path(
        str(command_data["working_directory"])
    ).expanduser().resolve()

    try:
        relative = original_working_directory.relative_to(
            workspace
        )
    except ValueError as error:
        raise ValueError(
            "Baseline 테스트 실행 위치가 Workspace 밖에 있습니다."
        ) from error

    return command, relative, str(command[0])


def _pythonpath(isolated_workspace: Path) -> str:
    entries = [
        str(path)
        for path in (
            isolated_workspace / "core" / "src",
            isolated_workspace / "src",
        )
        if path.is_dir()
    ]

    existing = os.environ.get("PYTHONPATH")

    if existing:
        entries.append(existing)

    return os.pathsep.join(entries)


def _run_test(
    subject: str,
    round_number: int,
    warmup: bool,
    command: list[str],
    working_directory: Path,
    isolated_workspace: Path,
    timeout_seconds: int,
) -> BenchmarkRun:
    started = time.perf_counter()

    try:
        completed = subprocess.run(
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
                "PYTHONPATH": _pythonpath(
                    isolated_workspace
                ),
            },
        )

        return BenchmarkRun(
            subject=subject,
            round_number=round_number,
            warmup=warmup,
            duration_seconds=round(
                time.perf_counter() - started,
                6,
            ),
            exit_code=completed.returncode,
            timed_out=False,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    except subprocess.TimeoutExpired as error:
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

        return BenchmarkRun(
            subject=subject,
            round_number=round_number,
            warmup=warmup,
            duration_seconds=round(
                time.perf_counter() - started,
                6,
            ),
            exit_code=None,
            timed_out=True,
            stdout=stdout,
            stderr=stderr,
        )


def _copy_workspace(
    workspace: Path,
    destination: Path,
) -> None:
    shutil.copytree(
        workspace,
        destination,
        ignore=shutil.ignore_patterns(
            *COPY_EXCLUDED_NAMES
        ),
    )


def _save_evidence(
    workspace: Path,
    result: CandidateBenchmarkResult,
) -> Path:
    directory = (
        workspace
        / ".proofcode"
        / "evidence"
        / "benchmarks"
    )
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")
    target_stem = Path(
        result.target_relative_path
    ).stem
    filename = (
        f"{timestamp}-{target_stem}-"
        f"{result.candidate_sha256[:8]}.json"
    )
    path = directory / filename
    temporary = path.with_suffix(".json.tmp")

    payload = {
        "schema_version": (
            BENCHMARK_EVIDENCE_SCHEMA_VERSION
        ),
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "candidate_benchmark": result.to_dict(),
    }

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


def _with_saved_evidence(
    workspace: Path,
    result: CandidateBenchmarkResult,
) -> CandidateBenchmarkResult:
    path = _save_evidence(workspace, result)
    values = result.to_dict()
    values["evidence_saved"] = True
    values["evidence_path"] = str(path)
    values["baseline_stats"] = result.baseline_stats
    values["candidate_stats"] = result.candidate_stats
    values["runs"] = result.runs

    return CandidateBenchmarkResult(**values)


def benchmark_candidate(
    workspace_path: str,
    evidence_path: str,
    measured_runs: int = 5,
    warmup_runs: int = 1,
    timeout_seconds: int = 60,
) -> CandidateBenchmarkResult:
    if measured_runs < 3:
        raise ValueError(
            "Benchmark 측정 횟수는 최소 3회여야 합니다."
        )

    if measured_runs > 30:
        raise ValueError(
            "Benchmark 측정 횟수는 최대 30회입니다."
        )

    if warmup_runs < 0 or warmup_runs > 5:
        raise ValueError(
            "Warm-up 횟수는 0~5회여야 합니다."
        )

    workspace = _workspace(workspace_path)
    baseline = _load_baseline(workspace)
    path, _, candidate_verification = (
        _load_candidate_evidence(
            workspace,
            evidence_path,
        )
    )

    current_fingerprint = workspace_fingerprint(
        str(workspace)
    )
    baseline_fingerprint = str(
        baseline["workspace_fingerprint"]
    )
    candidate_context_fingerprint = str(
        candidate_verification[
            "original_fingerprint_after"
        ]
    )

    if current_fingerprint != baseline_fingerprint:
        raise ValueError(
            "Baseline을 만든 뒤 Workspace가 변경되었습니다. "
            "Baseline을 다시 생성하세요."
        )

    if current_fingerprint != candidate_context_fingerprint:
        raise ValueError(
            "Candidate 검증 후 Workspace가 변경되었습니다. "
            "Candidate를 다시 검증하세요."
        )

    candidate_path = Path(
        str(candidate_verification["candidate_path"])
    ).expanduser().resolve()

    if not candidate_path.is_file():
        raise ValueError(
            "Candidate 원본 파일을 찾을 수 없습니다: "
            f"{candidate_path}"
        )

    expected_candidate_hash = str(
        candidate_verification["candidate_sha256"]
    )
    current_candidate_hash = _sha256_file(
        candidate_path
    )

    if current_candidate_hash != expected_candidate_hash:
        raise ValueError(
            "Candidate 검증 후 후보 파일 내용이 변경되었습니다. "
            "Candidate를 다시 검증하세요."
        )

    target_relative_path = Path(
        str(
            candidate_verification[
                "target_relative_path"
            ]
        )
    )
    command, relative_working_directory, interpreter = (
        _relative_working_directory(
            workspace,
            baseline,
        )
    )

    runs: list[BenchmarkRun] = []
    workspace_before = current_fingerprint
    baseline_before = ""
    candidate_before = ""
    baseline_after = ""
    candidate_after = ""

    with tempfile.TemporaryDirectory(
        prefix="proofcode-benchmark-"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        baseline_workspace = (
            temporary_root / "baseline"
        )
        candidate_workspace = (
            temporary_root / "candidate"
        )

        _copy_workspace(
            workspace,
            baseline_workspace,
        )
        _copy_workspace(
            workspace,
            candidate_workspace,
        )

        candidate_target = (
            candidate_workspace / target_relative_path
        )

        if not candidate_target.is_file():
            raise ValueError(
                "임시 Candidate Workspace에서 대상 파일을 "
                "찾을 수 없습니다."
            )

        candidate_target.write_bytes(
            candidate_path.read_bytes()
        )

        baseline_working_directory = (
            baseline_workspace
            / relative_working_directory
        )
        candidate_working_directory = (
            candidate_workspace
            / relative_working_directory
        )

        baseline_before = workspace_fingerprint(
            str(baseline_workspace)
        )
        candidate_before = workspace_fingerprint(
            str(candidate_workspace)
        )

        for warmup_index in range(1, warmup_runs + 1):
            runs.append(
                _run_test(
                    "baseline",
                    warmup_index,
                    True,
                    command,
                    baseline_working_directory,
                    baseline_workspace,
                    timeout_seconds,
                )
            )
            runs.append(
                _run_test(
                    "candidate",
                    warmup_index,
                    True,
                    command,
                    candidate_working_directory,
                    candidate_workspace,
                    timeout_seconds,
                )
            )

        for round_number in range(1, measured_runs + 1):
            order = (
                ("baseline", "candidate")
                if round_number % 2 == 1
                else ("candidate", "baseline")
            )

            for subject in order:
                if subject == "baseline":
                    run = _run_test(
                        "baseline",
                        round_number,
                        False,
                        command,
                        baseline_working_directory,
                        baseline_workspace,
                        timeout_seconds,
                    )
                else:
                    run = _run_test(
                        "candidate",
                        round_number,
                        False,
                        command,
                        candidate_working_directory,
                        candidate_workspace,
                        timeout_seconds,
                    )

                runs.append(run)

                if run.timed_out or run.exit_code != 0:
                    break

            if runs[-1].timed_out or runs[-1].exit_code != 0:
                break

        baseline_after = workspace_fingerprint(
            str(baseline_workspace)
        )
        candidate_after = workspace_fingerprint(
            str(candidate_workspace)
        )

    workspace_after = workspace_fingerprint(
        str(workspace)
    )
    workspace_changed = workspace_before != workspace_after
    baseline_changed = baseline_before != baseline_after
    candidate_changed = candidate_before != candidate_after

    measured_baseline_runs = [
        item
        for item in runs
        if item.subject == "baseline"
        and not item.warmup
        and not item.timed_out
        and item.exit_code == 0
    ]
    measured_candidate_runs = [
        item
        for item in runs
        if item.subject == "candidate"
        and not item.warmup
        and not item.timed_out
        and item.exit_code == 0
    ]

    baseline_stats = calculate_stats(
        [
            item.duration_seconds
            for item in measured_baseline_runs
        ]
    )
    candidate_stats = calculate_stats(
        [
            item.duration_seconds
            for item in measured_candidate_runs
        ]
    )

    failed_baseline = next(
        (
            item
            for item in runs
            if item.subject == "baseline"
            and (
                item.timed_out
                or item.exit_code != 0
            )
        ),
        None,
    )
    failed_candidate = next(
        (
            item
            for item in runs
            if item.subject == "candidate"
            and (
                item.timed_out
                or item.exit_code != 0
            )
        ),
        None,
    )

    enough_measurements = (
        baseline_stats.runs == measured_runs
        and candidate_stats.runs == measured_runs
    )

    if workspace_changed:
        verdict = "blocked"
        message = (
            "Benchmark 실행 중 원본 Workspace가 변경되어 "
            "결과를 신뢰할 수 없습니다."
        )
    elif baseline_changed or candidate_changed:
        verdict = "blocked"
        message = (
            "Benchmark 테스트가 임시 소스 파일을 변경하여 "
            "결과를 신뢰할 수 없습니다."
        )
    elif failed_baseline is not None:
        verdict = "blocked"
        message = (
            "격리된 Baseline 복사본의 테스트가 실패했습니다. "
            "Benchmark 환경을 확인하세요."
        )
    elif failed_candidate is not None:
        verdict = "failed"
        message = (
            "Candidate 복사본의 테스트가 Benchmark 도중 "
            "실패했습니다."
        )
    elif not enough_measurements:
        verdict = "blocked"
        message = (
            "요청한 반복 횟수를 모두 측정하지 못했습니다."
        )
    else:
        verdict = "reviewable"
        message = (
            "Baseline과 Candidate가 모든 반복 테스트를 "
            "통과했습니다. 관측된 시간 차이는 개발자가 "
            "추가로 검토해야 합니다."
        )

    observed_change = (
        classify_observed_change(
            baseline_stats.median_seconds,
            candidate_stats.median_seconds,
        )
        if verdict == "reviewable"
        else "not_comparable"
    )
    median_delta = round(
        candidate_stats.median_seconds
        - baseline_stats.median_seconds,
        6,
    )
    median_ratio = (
        round(
            candidate_stats.median_seconds
            / baseline_stats.median_seconds,
            6,
        )
        if baseline_stats.median_seconds > 0
        else None
    )
    observed_percent_change = (
        round((median_ratio - 1) * 100, 3)
        if median_ratio is not None
        else None
    )

    result = CandidateBenchmarkResult(
        verdict=verdict,
        observed_change=observed_change,
        message=message,
        measured_runs=measured_runs,
        warmup_runs=warmup_runs,
        target_relative_path=(
            target_relative_path.as_posix()
        ),
        candidate_path=str(candidate_path),
        candidate_sha256=current_candidate_hash,
        candidate_evidence_path=str(path),
        candidate_evidence_sha256=_sha256_file(path),
        baseline_fingerprint=baseline_fingerprint,
        workspace_fingerprint_before=workspace_before,
        workspace_fingerprint_after=workspace_after,
        workspace_changed_during_run=workspace_changed,
        baseline_copy_changed_during_run=baseline_changed,
        candidate_copy_changed_during_run=candidate_changed,
        baseline_stats=baseline_stats,
        candidate_stats=candidate_stats,
        median_delta_seconds=median_delta,
        median_ratio=median_ratio,
        observed_percent_change=observed_percent_change,
        command=command,
        working_directory=str(
            workspace / relative_working_directory
        ),
        interpreter_path=interpreter,
        runs=runs,
        evidence_saved=False,
        evidence_path=None,
        security_scope=(
            "two-temporary-filesystem-copies; "
            "alternating-test-order; "
            "not-an-os-or-container-security-sandbox"
        ),
    )

    return _with_saved_evidence(workspace, result)
