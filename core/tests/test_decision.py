import json
from pathlib import Path

import pytest

from proofcode_core.decision import (
    list_candidate_evidence,
    list_decisions,
    read_decision,
    record_candidate_decision,
)
from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)


def create_workspace(tmp_path: Path) -> tuple[Path, Path]:
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
    *,
    verdict: str = "reviewable",
    passed: bool = True,
    context_fingerprint: str | None = None,
) -> Path:
    fingerprint = (
        context_fingerprint
        or workspace_fingerprint(str(workspace))
    )
    directory = (
        workspace
        / ".proofcode"
        / "evidence"
        / "candidates"
    )
    directory.mkdir(parents=True)
    path = directory / "candidate.json"

    payload = {
        "schema_version": (
            CANDIDATE_EVIDENCE_SCHEMA_VERSION
        ),
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": "2026-07-14T12:00:00+00:00",
        "candidate_verification": {
            "verdict": verdict,
            "passed": passed,
            "target_relative_path": (
                "core/src/app.py"
            ),
            "candidate_path": "C:/candidate/app.py",
            "candidate_sha256": "a" * 64,
            "original_fingerprint_after": fingerprint,
            "message": "candidate result",
        },
    }
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_list_candidate_evidence(tmp_path: Path) -> None:
    workspace, _ = create_workspace(tmp_path)
    evidence = create_candidate_evidence(workspace)

    summaries = list_candidate_evidence(
        str(workspace)
    )

    assert len(summaries) == 1
    assert summaries[0].evidence_path == str(
        evidence.resolve()
    )
    assert summaries[0].verdict == "reviewable"
    assert summaries[0].target_relative_path == (
        "core/src/app.py"
    )


def test_apply_decision_is_recorded_without_code_change(
    tmp_path: Path,
) -> None:
    workspace, source = create_workspace(tmp_path)
    evidence = create_candidate_evidence(workspace)
    original = source.read_text(encoding="utf-8")

    record = record_candidate_decision(
        workspace_path=str(workspace),
        evidence_path=str(evidence),
        decision="apply",
        reason="테스트를 통과했고 Diff를 검토했습니다.",
    )

    assert record.decision == "apply"
    assert record.automatic_code_change_performed is False
    assert record.apply_mode == "manual-approval-only"
    assert record.workspace_matches_candidate_context is True
    assert Path(record.decision_path).exists()
    assert source.read_text(encoding="utf-8") == original

    loaded = read_decision(
        str(workspace),
        record.decision_path,
    )
    assert loaded.decision_id == record.decision_id


def test_apply_is_blocked_for_failed_candidate(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    evidence = create_candidate_evidence(
        workspace,
        verdict="failed",
        passed=False,
    )

    with pytest.raises(
        ValueError,
        match="reviewable",
    ):
        record_candidate_decision(
            str(workspace),
            str(evidence),
            "apply",
            "실패했지만 적용",
        )


def test_apply_is_blocked_when_workspace_is_stale(
    tmp_path: Path,
) -> None:
    workspace, source = create_workspace(tmp_path)
    evidence = create_candidate_evidence(workspace)

    source.write_text(
        "def value():\n    return 2\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Workspace가 변경",
    ):
        record_candidate_decision(
            str(workspace),
            str(evidence),
            "apply",
            "오래된 검증 결과",
        )


def test_hold_can_record_stale_context(
    tmp_path: Path,
) -> None:
    workspace, source = create_workspace(tmp_path)
    evidence = create_candidate_evidence(workspace)

    source.write_text(
        "def value():\n    return 2\n",
        encoding="utf-8",
    )

    record = record_candidate_decision(
        str(workspace),
        str(evidence),
        "hold",
        "Workspace 변경 후 다시 검증할 예정",
    )

    assert record.decision == "hold"
    assert (
        record.workspace_matches_candidate_context
        is False
    )


def test_reason_is_required(tmp_path: Path) -> None:
    workspace, _ = create_workspace(tmp_path)
    evidence = create_candidate_evidence(workspace)

    with pytest.raises(
        ValueError,
        match="결정 이유",
    ):
        record_candidate_decision(
            str(workspace),
            str(evidence),
            "reject",
            "   ",
        )


def test_list_decisions_returns_saved_record(
    tmp_path: Path,
) -> None:
    workspace, _ = create_workspace(tmp_path)
    evidence = create_candidate_evidence(workspace)

    record_candidate_decision(
        str(workspace),
        str(evidence),
        "hold",
        "Benchmark 필요",
    )

    decisions = list_decisions(str(workspace))

    assert len(decisions) == 1
    assert decisions[0].decision == "hold"
    assert decisions[0].reason == "Benchmark 필요"
