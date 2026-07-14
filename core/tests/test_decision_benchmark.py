import json
from pathlib import Path

import pytest

from proofcode_core.decision import (
    list_benchmark_evidence,
    read_decision,
    record_candidate_decision,
)
from proofcode_core.fingerprint import (
    workspace_fingerprint,
)
from proofcode_core.version import (
    APP_VERSION,
    BENCHMARK_EVIDENCE_SCHEMA_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)


def create_workspace(
    tmp_path: Path,
) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    source = workspace / "core" / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def value():\n    return 1\n",
        encoding="utf-8",
    )
    return workspace, source


def create_candidate_evidence(
    workspace: Path,
) -> Path:
    fingerprint = workspace_fingerprint(
        str(workspace)
    )
    path = (
        workspace
        / ".proofcode"
        / "evidence"
        / "candidates"
        / "candidate.json"
    )
    path.parent.mkdir(parents=True)

    payload = {
        "schema_version": (
            CANDIDATE_EVIDENCE_SCHEMA_VERSION
        ),
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": "2026-07-14T12:00:00+00:00",
        "candidate_verification": {
            "verdict": "reviewable",
            "passed": True,
            "target_relative_path": "core/src/app.py",
            "candidate_path": "C:/candidate/app.py",
            "candidate_sha256": "a" * 64,
            "original_fingerprint_after": fingerprint,
            "message": "candidate passed",
        },
    }
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def create_benchmark_evidence(
    workspace: Path,
    candidate_evidence: Path,
    *,
    verdict: str = "reviewable",
    candidate_sha256: str = "a" * 64,
) -> Path:
    fingerprint = workspace_fingerprint(
        str(workspace)
    )
    path = (
        workspace
        / ".proofcode"
        / "evidence"
        / "benchmarks"
        / "benchmark.json"
    )
    path.parent.mkdir(parents=True)

    payload = {
        "schema_version": (
            BENCHMARK_EVIDENCE_SCHEMA_VERSION
        ),
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": "2026-07-14T12:10:00+00:00",
        "candidate_benchmark": {
            "verdict": verdict,
            "observed_change": "similar",
            "message": "benchmark complete",
            "measured_runs": 5,
            "target_relative_path": "core/src/app.py",
            "candidate_path": "C:/candidate/app.py",
            "candidate_sha256": candidate_sha256,
            "candidate_evidence_path": str(
                candidate_evidence.resolve()
            ),
            "workspace_fingerprint_after": fingerprint,
            "baseline_stats": {
                "median_seconds": 0.6,
            },
            "candidate_stats": {
                "median_seconds": 0.59,
            },
            "observed_percent_change": -1.667,
        },
    }
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_list_benchmark_evidence(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    candidate = create_candidate_evidence(workspace)
    benchmark = create_benchmark_evidence(
        workspace,
        candidate,
    )

    summaries = list_benchmark_evidence(
        str(workspace)
    )

    assert len(summaries) == 1
    assert summaries[0].evidence_path == str(
        benchmark.resolve()
    )
    assert summaries[0].measured_runs == 5
    assert summaries[0].observed_change == "similar"


def test_decision_links_candidate_and_benchmark(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    candidate = create_candidate_evidence(workspace)
    benchmark = create_benchmark_evidence(
        workspace,
        candidate,
    )

    record = record_candidate_decision(
        workspace_path=str(workspace),
        evidence_path=str(candidate),
        benchmark_evidence_path=str(benchmark),
        decision="hold",
        reason="테스트와 Benchmark를 함께 검토함",
    )

    assert record.evidence_chain_complete is True
    assert record.benchmark_evidence_path == str(
        benchmark.resolve()
    )
    assert record.benchmark_measured_runs == 5
    assert (
        record.benchmark_observed_change
        == "similar"
    )

    loaded = read_decision(
        str(workspace),
        record.decision_path,
    )
    assert loaded.evidence_chain_complete is True


def test_mismatched_benchmark_is_rejected(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    candidate = create_candidate_evidence(workspace)
    benchmark = create_benchmark_evidence(
        workspace,
        candidate,
        candidate_sha256="b" * 64,
    )

    with pytest.raises(
        ValueError,
        match="Candidate SHA-256",
    ):
        record_candidate_decision(
            str(workspace),
            str(candidate),
            "hold",
            "다른 후보의 Benchmark",
            benchmark_evidence_path=str(benchmark),
        )


def test_apply_blocks_non_reviewable_benchmark(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    candidate = create_candidate_evidence(workspace)
    benchmark = create_benchmark_evidence(
        workspace,
        candidate,
        verdict="blocked",
    )

    with pytest.raises(
        ValueError,
        match="reviewable Benchmark",
    ):
        record_candidate_decision(
            str(workspace),
            str(candidate),
            "apply",
            "차단된 Benchmark로 Apply",
            benchmark_evidence_path=str(benchmark),
        )


def test_old_decision_schema_can_still_be_read(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    decision_path = (
        workspace
        / ".proofcode"
        / "decisions"
        / "old.json"
    )
    decision_path.parent.mkdir(parents=True)

    old_record = {
        "schema_version": "1",
        "developer_decision": {
            "decision_id": "old-1",
            "decision": "hold",
            "reason": "old decision",
            "created_at_utc": (
                "2026-07-14T12:00:00+00:00"
            ),
            "decision_path": str(decision_path),
            "candidate_evidence_path": "candidate.json",
            "candidate_evidence_sha256": "c" * 64,
            "source_verdict": "reviewable",
            "source_passed": True,
            "target_relative_path": "core/src/app.py",
            "candidate_path": "candidate.py",
            "candidate_sha256": "a" * 64,
            "workspace_fingerprint": "d" * 64,
            "candidate_context_fingerprint": "d" * 64,
            "workspace_matches_candidate_context": True,
            "automatic_code_change_performed": False,
            "apply_mode": "manual-approval-only",
        },
    }
    decision_path.write_text(
        json.dumps(old_record),
        encoding="utf-8",
    )

    loaded = read_decision(
        str(workspace),
        str(decision_path),
    )

    assert loaded.decision_id == "old-1"
    assert loaded.benchmark_evidence_path is None
    assert loaded.evidence_chain_complete is False
