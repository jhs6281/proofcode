from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    DECISION_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)

DecisionValue = Literal["apply", "hold", "reject"]
VALID_DECISIONS = {"apply", "hold", "reject"}


@dataclass(frozen=True)
class CandidateEvidenceSummary:
    evidence_path: str
    created_at_utc: str
    verdict: str
    passed: bool
    target_relative_path: str
    candidate_path: str
    candidate_sha256: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    decision: DecisionValue
    reason: str
    created_at_utc: str
    decision_path: str
    candidate_evidence_path: str
    candidate_evidence_sha256: str
    source_verdict: str
    source_passed: bool
    target_relative_path: str
    candidate_path: str
    candidate_sha256: str
    workspace_fingerprint: str
    candidate_context_fingerprint: str
    workspace_matches_candidate_context: bool
    automatic_code_change_performed: bool
    apply_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionSummary:
    decision_id: str
    decision: DecisionValue
    reason: str
    created_at_utc: str
    decision_path: str
    target_relative_path: str
    candidate_sha256: str
    source_verdict: str
    workspace_matches_candidate_context: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _candidate_directory(workspace: Path) -> Path:
    return (
        workspace
        / ".proofcode"
        / "evidence"
        / "candidates"
    )


def _decision_directory(workspace: Path) -> Path:
    return workspace / ".proofcode" / "decisions"


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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


def _resolve_candidate_evidence(
    workspace: Path,
    evidence_path: str,
) -> Path:
    candidate_directory = _candidate_directory(
        workspace
    ).resolve()
    path = Path(evidence_path).expanduser().resolve()

    if not path.is_file():
        raise ValueError(
            f"Candidate Evidence 파일을 찾을 수 없습니다: {path}"
        )

    if not path.is_relative_to(candidate_directory):
        raise ValueError(
            "Candidate Evidence는 현재 Workspace의 "
            ".proofcode/evidence/candidates 안에 있어야 합니다."
        )

    return path


def _candidate_verification(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if (
        evidence.get("schema_version")
        != CANDIDATE_EVIDENCE_SCHEMA_VERSION
    ):
        raise ValueError(
            "Candidate Evidence 형식 버전이 현재 ProofCode와 "
            "다릅니다. Candidate를 다시 검증하세요."
        )

    verification = evidence.get(
        "candidate_verification"
    )

    if not isinstance(verification, dict):
        raise ValueError(
            "Candidate Evidence에 검증 결과가 없습니다."
        )

    required = {
        "verdict",
        "passed",
        "target_relative_path",
        "candidate_path",
        "candidate_sha256",
        "original_fingerprint_after",
        "message",
    }
    missing = required - verification.keys()

    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(
            f"Candidate Evidence 필수 항목이 없습니다: {names}"
        )

    return verification


def _summary_from_evidence(
    path: Path,
    evidence: dict[str, Any],
) -> CandidateEvidenceSummary:
    verification = _candidate_verification(evidence)

    return CandidateEvidenceSummary(
        evidence_path=str(path),
        created_at_utc=str(
            evidence.get("created_at_utc", "")
        ),
        verdict=str(verification["verdict"]),
        passed=bool(verification["passed"]),
        target_relative_path=str(
            verification["target_relative_path"]
        ),
        candidate_path=str(
            verification["candidate_path"]
        ),
        candidate_sha256=str(
            verification["candidate_sha256"]
        ),
        message=str(verification["message"]),
    )


def list_candidate_evidence(
    workspace_path: str,
) -> list[CandidateEvidenceSummary]:
    workspace = _workspace(workspace_path)
    directory = _candidate_directory(workspace)

    if not directory.is_dir():
        return []

    summaries: list[CandidateEvidenceSummary] = []

    for path in directory.glob("*.json"):
        try:
            evidence = _read_json(
                path,
                "Candidate Evidence",
            )
            summaries.append(
                _summary_from_evidence(path, evidence)
            )
        except ValueError:
            # 손상된 한 파일 때문에 전체 목록을 막지 않습니다.
            continue

    summaries.sort(
        key=lambda item: (
            item.created_at_utc,
            item.evidence_path,
        ),
        reverse=True,
    )
    return summaries


def _safe_file_part(value: str) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "-",
        value,
    ).strip("-")
    return cleaned or "decision"


def record_candidate_decision(
    workspace_path: str,
    evidence_path: str,
    decision: str,
    reason: str,
) -> DecisionRecord:
    workspace = _workspace(workspace_path)
    normalized_decision = decision.strip().lower()
    normalized_reason = reason.strip()

    if normalized_decision not in VALID_DECISIONS:
        raise ValueError(
            "Decision은 apply, hold, reject 중 하나여야 합니다."
        )

    if not normalized_reason:
        raise ValueError("결정 이유를 입력해야 합니다.")

    if len(normalized_reason) > 2000:
        raise ValueError(
            "결정 이유는 2000자 이하로 입력하세요."
        )

    path = _resolve_candidate_evidence(
        workspace,
        evidence_path,
    )
    evidence = _read_json(
        path,
        "Candidate Evidence",
    )
    verification = _candidate_verification(evidence)

    verdict = str(verification["verdict"])
    passed = bool(verification["passed"])
    candidate_context_fingerprint = str(
        verification["original_fingerprint_after"]
    )
    current_fingerprint = workspace_fingerprint(
        str(workspace)
    )
    context_matches = (
        current_fingerprint
        == candidate_context_fingerprint
    )

    if normalized_decision == "apply":
        if verdict != "reviewable" or not passed:
            raise ValueError(
                "테스트를 통과해 reviewable 판정을 받은 "
                "Candidate만 Apply로 기록할 수 있습니다."
            )

        if not context_matches:
            raise ValueError(
                "Candidate 검증 후 Workspace가 변경되었습니다. "
                "Baseline과 Candidate를 다시 검증한 뒤 "
                "Apply를 기록하세요."
            )

    created_at = datetime.now(
        timezone.utc
    ).isoformat()
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")
    evidence_hash = _sha256_file(path)
    short_uuid = uuid4().hex[:8]
    target_stem = _safe_file_part(
        Path(
            str(
                verification["target_relative_path"]
            )
        ).stem
    )
    decision_id = (
        f"{timestamp}-{normalized_decision}-"
        f"{target_stem}-{short_uuid}"
    )

    directory = _decision_directory(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    decision_path = directory / f"{decision_id}.json"

    record = DecisionRecord(
        decision_id=decision_id,
        decision=normalized_decision,  # type: ignore[arg-type]
        reason=normalized_reason,
        created_at_utc=created_at,
        decision_path=str(decision_path),
        candidate_evidence_path=str(path),
        candidate_evidence_sha256=evidence_hash,
        source_verdict=verdict,
        source_passed=passed,
        target_relative_path=str(
            verification["target_relative_path"]
        ),
        candidate_path=str(
            verification["candidate_path"]
        ),
        candidate_sha256=str(
            verification["candidate_sha256"]
        ),
        workspace_fingerprint=current_fingerprint,
        candidate_context_fingerprint=(
            candidate_context_fingerprint
        ),
        workspace_matches_candidate_context=(
            context_matches
        ),
        automatic_code_change_performed=False,
        apply_mode="manual-approval-only",
    )

    payload = {
        "schema_version": DECISION_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "developer_decision": record.to_dict(),
    }

    temporary_path = decision_path.with_suffix(
        ".json.tmp"
    )
    temporary_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, decision_path)

    return record


def _summary_from_decision(
    path: Path,
    payload: dict[str, Any],
) -> DecisionSummary:
    if payload.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise ValueError("지원하지 않는 Decision 형식입니다.")

    decision = payload.get("developer_decision")

    if not isinstance(decision, dict):
        raise ValueError("Decision 기록이 없습니다.")

    return DecisionSummary(
        decision_id=str(decision["decision_id"]),
        decision=str(decision["decision"]),  # type: ignore[arg-type]
        reason=str(decision["reason"]),
        created_at_utc=str(
            decision["created_at_utc"]
        ),
        decision_path=str(path),
        target_relative_path=str(
            decision["target_relative_path"]
        ),
        candidate_sha256=str(
            decision["candidate_sha256"]
        ),
        source_verdict=str(
            decision["source_verdict"]
        ),
        workspace_matches_candidate_context=bool(
            decision[
                "workspace_matches_candidate_context"
            ]
        ),
    )


def list_decisions(
    workspace_path: str,
) -> list[DecisionSummary]:
    workspace = _workspace(workspace_path)
    directory = _decision_directory(workspace)

    if not directory.is_dir():
        return []

    summaries: list[DecisionSummary] = []

    for path in directory.glob("*.json"):
        try:
            payload = _read_json(
                path,
                "Decision",
            )
            summaries.append(
                _summary_from_decision(path, payload)
            )
        except (KeyError, ValueError):
            continue

    summaries.sort(
        key=lambda item: (
            item.created_at_utc,
            item.decision_path,
        ),
        reverse=True,
    )
    return summaries


def read_decision(
    workspace_path: str,
    decision_path: str,
) -> DecisionRecord:
    workspace = _workspace(workspace_path)
    directory = _decision_directory(workspace).resolve()
    path = Path(decision_path).expanduser().resolve()

    if not path.is_file():
        raise ValueError(
            f"Decision 파일을 찾을 수 없습니다: {path}"
        )

    if not path.is_relative_to(directory):
        raise ValueError(
            "Decision 파일은 현재 Workspace의 "
            ".proofcode/decisions 안에 있어야 합니다."
        )

    payload = _read_json(path, "Decision")

    if payload.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise ValueError("지원하지 않는 Decision 형식입니다.")

    decision = payload.get("developer_decision")

    if not isinstance(decision, dict):
        raise ValueError("Decision 기록이 없습니다.")

    decision["decision_path"] = str(path)
    return DecisionRecord(**decision)
