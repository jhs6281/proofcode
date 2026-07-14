import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from proofcode_core.benchmark import (
    BenchmarkRun,
    benchmark_candidate,
    calculate_stats,
    classify_observed_change,
)
from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    BASELINE_SCHEMA_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)


def create_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    core = workspace / "core"
    source = core / "src" / "sample"
    tests = core / "tests"

    source.mkdir(parents=True)
    tests.mkdir(parents=True)

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
    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        "def add(a, b):\n    return sum((a, b))\n",
        encoding="utf-8",
    )

    return workspace, target, candidate


def create_baseline_and_evidence(
    workspace: Path,
    target: Path,
    candidate: Path,
) -> Path:
    fingerprint = workspace_fingerprint(str(workspace))
    baseline_path = (
        workspace
        / ".proofcode"
        / "evidence"
        / "baseline.json"
    )
    baseline_path.parent.mkdir(parents=True)

    baseline = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
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
            "duration_seconds": 0.2,
            "stdout": "3 passed\n",
            "stderr": "",
        },
    }
    baseline_path.write_text(
        json.dumps(baseline),
        encoding="utf-8",
    )

    evidence_path = (
        workspace
        / ".proofcode"
        / "evidence"
        / "candidates"
        / "candidate.json"
    )
    evidence_path.parent.mkdir(parents=True)

    evidence = {
        "schema_version": (
            CANDIDATE_EVIDENCE_SCHEMA_VERSION
        ),
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "candidate_verification": {
            "verdict": "reviewable",
            "passed": True,
            "target_relative_path": (
                target.relative_to(workspace).as_posix()
            ),
            "candidate_path": str(candidate),
            "candidate_sha256": __import__(
                "hashlib"
            ).sha256(candidate.read_bytes()).hexdigest(),
            "original_fingerprint_after": fingerprint,
        },
    }
    evidence_path.write_text(
        json.dumps(evidence),
        encoding="utf-8",
    )

    return evidence_path


def successful_run(
    subject: str,
    round_number: int,
    warmup: bool,
    duration: float,
) -> BenchmarkRun:
    return BenchmarkRun(
        subject=subject,
        round_number=round_number,
        warmup=warmup,
        duration_seconds=duration,
        exit_code=0,
        timed_out=False,
        stdout="3 passed\n",
        stderr="",
    )


def test_calculate_stats() -> None:
    stats = calculate_stats([1.0, 2.0, 3.0])

    assert stats.runs == 3
    assert stats.mean_seconds == 2.0
    assert stats.median_seconds == 2.0
    assert stats.minimum_seconds == 1.0
    assert stats.maximum_seconds == 3.0


def test_observed_change_uses_noise_band() -> None:
    assert classify_observed_change(1.0, 0.8) == "faster"
    assert classify_observed_change(1.0, 1.2) == "slower"
    assert classify_observed_change(1.0, 1.03) == "similar"
    assert classify_observed_change(0.01, 0.005) == "similar"


def test_successful_benchmark_is_reviewable(
    tmp_path: Path,
) -> None:
    workspace, target, candidate = create_workspace(
        tmp_path
    )
    evidence = create_baseline_and_evidence(
        workspace,
        target,
        candidate,
    )

    durations = {
        "baseline": iter([1.0, 1.0, 1.1, 0.9]),
        "candidate": iter([0.8, 0.8, 0.9, 0.7]),
    }

    def fake_run(
        subject: str,
        round_number: int,
        warmup: bool,
        *args: object,
        **kwargs: object,
    ) -> BenchmarkRun:
        return successful_run(
            subject,
            round_number,
            warmup,
            next(durations[subject]),
        )

    with patch(
        "proofcode_core.benchmark._run_test",
        side_effect=fake_run,
    ):
        result = benchmark_candidate(
            str(workspace),
            str(evidence),
            measured_runs=3,
            warmup_runs=1,
        )

    assert result.verdict == "reviewable"
    assert result.observed_change == "faster"
    assert result.baseline_stats.runs == 3
    assert result.candidate_stats.runs == 3
    assert result.evidence_saved is True
    assert Path(result.evidence_path or "").exists()


def test_candidate_failure_marks_benchmark_failed(
    tmp_path: Path,
) -> None:
    workspace, target, candidate = create_workspace(
        tmp_path
    )
    evidence = create_baseline_and_evidence(
        workspace,
        target,
        candidate,
    )

    def fake_run(
        subject: str,
        round_number: int,
        warmup: bool,
        *args: object,
        **kwargs: object,
    ) -> BenchmarkRun:
        if subject == "candidate" and not warmup:
            return BenchmarkRun(
                subject=subject,
                round_number=round_number,
                warmup=False,
                duration_seconds=0.2,
                exit_code=1,
                timed_out=False,
                stdout="1 failed\n",
                stderr="",
            )

        return successful_run(
            subject,
            round_number,
            warmup,
            0.2,
        )

    with patch(
        "proofcode_core.benchmark._run_test",
        side_effect=fake_run,
    ):
        result = benchmark_candidate(
            str(workspace),
            str(evidence),
            measured_runs=3,
            warmup_runs=0,
        )

    assert result.verdict == "failed"
    assert result.observed_change == "not_comparable"


def test_changed_candidate_file_is_blocked(
    tmp_path: Path,
) -> None:
    workspace, target, candidate = create_workspace(
        tmp_path
    )
    evidence = create_baseline_and_evidence(
        workspace,
        target,
        candidate,
    )

    candidate.write_text(
        "def add(a, b):\n    return 0\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="후보 파일 내용이 변경",
    ):
        benchmark_candidate(
            str(workspace),
            str(evidence),
            measured_runs=3,
        )
