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
    BENCHMARK_EVIDENCE_SCHEMA_VERSION,
    CANDIDATE_EVIDENCE_SCHEMA_VERSION,
    DECISION_SCHEMA_VERSION,
    PROTOCOL_VERSION,
)

DecisionValue = Literal["apply", "hold", "reject"]
VALID_DECISIONS = {"apply", "hold", "reject"}
SUPPORTED_DECISION_SCHEMA_VERSIONS = {"1", DECISION_SCHEMA_VERSION}


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
class BenchmarkEvidenceSummary:
    evidence_path: str
    created_at_utc: str
    verdict: str
    observed_change: str
    target_relative_path: str
    candidate_path: str
    candidate_sha256: str
    candidate_evidence_path: str
    measured_runs: int
    baseline_median_seconds: float
    candidate_median_seconds: float
    observed_percent_change: float | None
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
    benchmark_evidence_path: str | None
    benchmark_evidence_sha256: str | None
    benchmark_verdict: str | None
    benchmark_observed_change: str | None
    benchmark_measured_runs: int | None
    benchmark_baseline_median_seconds: float | None
    benchmark_candidate_median_seconds: float | None
    benchmark_observed_percent_change: float | None
    benchmark_context_fingerprint: str | None
    workspace_matches_benchmark_context: bool | None
    evidence_chain_complete: bool
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
    benchmark_linked: bool
    benchmark_observed_change: str | None
    evidence_chain_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def _candidate_directory(workspace: Path) -> Path:
    return workspace / ".proofcode" / "evidence" / "candidates"


def _benchmark_directory(workspace: Path) -> Path:
    return workspace / ".proofcode" / "evidence" / "benchmarks"


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


def _resolve_evidence_path(
    workspace: Path,
    evidence_path: str,
    directory: Path,
    description: str,
) -> Path:
    allowed_directory = directory.resolve()
    path = Path(evidence_path).expanduser().resolve()

    if not path.is_file():
        raise ValueError(
            f"{description} 파일을 찾을 수 없습니다: {path}"
        )

    if not path.is_relative_to(allowed_directory):
        raise ValueError(
            f"{description}는 현재 Workspace의 "
            f"{allowed_directory} 안에 있어야 합니다."
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

    verification = evidence.get("candidate_verification")

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


def _benchmark_result(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if (
        evidence.get("schema_version")
        != BENCHMARK_EVIDENCE_SCHEMA_VERSION
    ):
        raise ValueError(
            "Benchmark Evidence 형식 버전이 현재 ProofCode와 "
            "다릅니다. Benchmark를 다시 실행하세요."
        )

    benchmark = evidence.get("candidate_benchmark")

    if not isinstance(benchmark, dict):
        raise ValueError(
            "Benchmark Evidence에 측정 결과가 없습니다."
        )

    required = {
        "verdict",
        "observed_change",
        "message",
        "measured_runs",
        "target_relative_path",
        "candidate_path",
        "candidate_sha256",
        "candidate_evidence_path",
        "workspace_fingerprint_after",
        "baseline_stats",
        "candidate_stats",
    }
    missing = required - benchmark.keys()

    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(
            f"Benchmark Evidence 필수 항목이 없습니다: {names}"
        )

    if not isinstance(benchmark["baseline_stats"], dict):
        raise ValueError(
            "Benchmark Baseline 통계가 올바르지 않습니다."
        )

    if not isinstance(benchmark["candidate_stats"], dict):
        raise ValueError(
            "Benchmark Candidate 통계가 올바르지 않습니다."
        )

    return benchmark


def _summary_from_candidate(
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


def _summary_from_benchmark(
    path: Path,
    evidence: dict[str, Any],
) -> BenchmarkEvidenceSummary:
    benchmark = _benchmark_result(evidence)
    baseline_stats = benchmark["baseline_stats"]
    candidate_stats = benchmark["candidate_stats"]

    return BenchmarkEvidenceSummary(
        evidence_path=str(path),
        created_at_utc=str(
            evidence.get("created_at_utc", "")
        ),
        verdict=str(benchmark["verdict"]),
        observed_change=str(
            benchmark["observed_change"]
        ),
        target_relative_path=str(
            benchmark["target_relative_path"]
        ),
        candidate_path=str(
            benchmark["candidate_path"]
        ),
        candidate_sha256=str(
            benchmark["candidate_sha256"]
        ),
        candidate_evidence_path=str(
            benchmark["candidate_evidence_path"]
        ),
        measured_runs=int(
            benchmark["measured_runs"]
        ),
        baseline_median_seconds=float(
            baseline_stats.get("median_seconds", 0.0)
        ),
        candidate_median_seconds=float(
            candidate_stats.get("median_seconds", 0.0)
        ),
        observed_percent_change=(
            None
            if benchmark.get("observed_percent_change") is None
            else float(
                benchmark["observed_percent_change"]
            )
        ),
        message=str(benchmark["message"]),
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
                _summary_from_candidate(path, evidence)
            )
        except ValueError:
            continue

    summaries.sort(
        key=lambda item: (
            item.created_at_utc,
            item.evidence_path,
        ),
        reverse=True,
    )
    return summaries


def list_benchmark_evidence(
    workspace_path: str,
) -> list[BenchmarkEvidenceSummary]:
    workspace = _workspace(workspace_path)
    directory = _benchmark_directory(workspace)

    if not directory.is_dir():
        return []

    summaries: list[BenchmarkEvidenceSummary] = []

    for path in directory.glob("*.json"):
        try:
            evidence = _read_json(
                path,
                "Benchmark Evidence",
            )
            summaries.append(
                _summary_from_benchmark(path, evidence)
            )
        except ValueError:
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


def _load_benchmark_link(
    workspace: Path,
    benchmark_evidence_path: str | None,
    candidate_path: Path,
    candidate_verification: dict[str, Any],
) -> tuple[
    Path | None,
    dict[str, Any] | None,
    bool | None,
]:
    if not benchmark_evidence_path:
        return None, None, None

    path = _resolve_evidence_path(
        workspace=workspace,
        evidence_path=benchmark_evidence_path,
        directory=_benchmark_directory(workspace),
        description="Benchmark Evidence",
    )
    evidence = _read_json(path, "Benchmark Evidence")
    benchmark = _benchmark_result(evidence)

    if (
        str(benchmark["candidate_sha256"])
        != str(candidate_verification["candidate_sha256"])
    ):
        raise ValueError(
            "Benchmark Evidence의 Candidate SHA-256이 "
            "선택한 Candidate Evidence와 다릅니다."
        )

    if (
        str(benchmark["target_relative_path"])
        != str(candidate_verification["target_relative_path"])
    ):
        raise ValueError(
            "Benchmark Evidence의 대상 파일이 "
            "선택한 Candidate Evidence와 다릅니다."
        )

    recorded_candidate_path = Path(
        str(benchmark["candidate_evidence_path"])
    ).expanduser().resolve()

    if recorded_candidate_path != candidate_path:
        raise ValueError(
            "Benchmark Evidence가 다른 Candidate Evidence를 "
            "참조하고 있습니다."
        )

    current_fingerprint = workspace_fingerprint(str(workspace))
    benchmark_context = str(
        benchmark["workspace_fingerprint_after"]
    )

    return (
        path,
        benchmark,
        current_fingerprint == benchmark_context,
    )


def record_candidate_decision(
    workspace_path: str,
    evidence_path: str,
    decision: str,
    reason: str,
    benchmark_evidence_path: str | None = None,
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

    candidate_path = _resolve_evidence_path(
        workspace=workspace,
        evidence_path=evidence_path,
        directory=_candidate_directory(workspace),
        description="Candidate Evidence",
    )
    candidate_evidence = _read_json(
        candidate_path,
        "Candidate Evidence",
    )
    verification = _candidate_verification(
        candidate_evidence
    )

    verdict = str(verification["verdict"])
    passed = bool(verification["passed"])
    candidate_context_fingerprint = str(
        verification["original_fingerprint_after"]
    )
    current_fingerprint = workspace_fingerprint(
        str(workspace)
    )
    candidate_context_matches = (
        current_fingerprint
        == candidate_context_fingerprint
    )

    (
        benchmark_path,
        benchmark,
        benchmark_context_matches,
    ) = _load_benchmark_link(
        workspace=workspace,
        benchmark_evidence_path=benchmark_evidence_path,
        candidate_path=candidate_path,
        candidate_verification=verification,
    )

    if normalized_decision == "apply":
        if verdict != "reviewable" or not passed:
            raise ValueError(
                "테스트를 통과해 reviewable 판정을 받은 "
                "Candidate만 Apply로 기록할 수 있습니다."
            )

        if not candidate_context_matches:
            raise ValueError(
                "Candidate 검증 후 Workspace가 변경되었습니다. "
                "Baseline과 Candidate를 다시 검증한 뒤 "
                "Apply를 기록하세요."
            )

        if benchmark is not None:
            if str(benchmark["verdict"]) != "reviewable":
                raise ValueError(
                    "reviewable Benchmark Evidence만 Apply 결정에 "
                    "연결할 수 있습니다."
                )

            if benchmark_context_matches is not True:
                raise ValueError(
                    "Benchmark 실행 후 Workspace가 변경되었습니다. "
                    "Benchmark를 다시 실행한 뒤 Apply를 기록하세요."
                )

    benchmark_baseline_stats = (
        benchmark["baseline_stats"]
        if benchmark is not None
        else None
    )
    benchmark_candidate_stats = (
        benchmark["candidate_stats"]
        if benchmark is not None
        else None
    )

    created_at = datetime.now(
        timezone.utc
    ).isoformat()
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")
    candidate_evidence_hash = _sha256_file(
        candidate_path
    )
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
        candidate_evidence_path=str(candidate_path),
        candidate_evidence_sha256=(
            candidate_evidence_hash
        ),
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
            candidate_context_matches
        ),
        benchmark_evidence_path=(
            str(benchmark_path)
            if benchmark_path is not None
            else None
        ),
        benchmark_evidence_sha256=(
            _sha256_file(benchmark_path)
            if benchmark_path is not None
            else None
        ),
        benchmark_verdict=(
            str(benchmark["verdict"])
            if benchmark is not None
            else None
        ),
        benchmark_observed_change=(
            str(benchmark["observed_change"])
            if benchmark is not None
            else None
        ),
        benchmark_measured_runs=(
            int(benchmark["measured_runs"])
            if benchmark is not None
            else None
        ),
        benchmark_baseline_median_seconds=(
            float(
                benchmark_baseline_stats.get(
                    "median_seconds",
                    0.0,
                )
            )
            if benchmark_baseline_stats is not None
            else None
        ),
        benchmark_candidate_median_seconds=(
            float(
                benchmark_candidate_stats.get(
                    "median_seconds",
                    0.0,
                )
            )
            if benchmark_candidate_stats is not None
            else None
        ),
        benchmark_observed_percent_change=(
            None
            if benchmark is None
            or benchmark.get(
                "observed_percent_change"
            ) is None
            else float(
                benchmark["observed_percent_change"]
            )
        ),
        benchmark_context_fingerprint=(
            str(
                benchmark[
                    "workspace_fingerprint_after"
                ]
            )
            if benchmark is not None
            else None
        ),
        workspace_matches_benchmark_context=(
            benchmark_context_matches
        ),
        evidence_chain_complete=(
            benchmark is not None
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


def _normalize_decision(
    path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    schema_version = str(
        payload.get("schema_version", "")
    )

    if schema_version not in SUPPORTED_DECISION_SCHEMA_VERSIONS:
        raise ValueError("지원하지 않는 Decision 형식입니다.")

    decision = payload.get("developer_decision")

    if not isinstance(decision, dict):
        raise ValueError("Decision 기록이 없습니다.")

    normalized = dict(decision)
    normalized["decision_path"] = str(path)

    defaults: dict[str, Any] = {
        "benchmark_evidence_path": None,
        "benchmark_evidence_sha256": None,
        "benchmark_verdict": None,
        "benchmark_observed_change": None,
        "benchmark_measured_runs": None,
        "benchmark_baseline_median_seconds": None,
        "benchmark_candidate_median_seconds": None,
        "benchmark_observed_percent_change": None,
        "benchmark_context_fingerprint": None,
        "workspace_matches_benchmark_context": None,
        "evidence_chain_complete": False,
    }

    for key, value in defaults.items():
        normalized.setdefault(key, value)

    return normalized


def _summary_from_decision(
    path: Path,
    payload: dict[str, Any],
) -> DecisionSummary:
    decision = _normalize_decision(path, payload)

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
        benchmark_linked=bool(
            decision["benchmark_evidence_path"]
        ),
        benchmark_observed_change=(
            None
            if decision["benchmark_observed_change"] is None
            else str(
                decision[
                    "benchmark_observed_change"
                ]
            )
        ),
        evidence_chain_complete=bool(
            decision["evidence_chain_complete"]
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
            payload = _read_json(path, "Decision")
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
    decision = _normalize_decision(path, payload)

    return DecisionRecord(**decision)
