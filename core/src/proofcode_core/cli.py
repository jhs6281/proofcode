from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from proofcode_core.analyzer import analyze_file
from proofcode_core.benchmark import benchmark_candidate
from proofcode_core.candidate import verify_candidate_file
from proofcode_core.contract import (
    error_payload,
    success_payload,
)
from proofcode_core.decision import (
    list_benchmark_evidence,
    list_candidate_evidence,
    list_decisions,
    read_decision,
    record_candidate_decision,
)
from proofcode_core.sandbox import (
    DEFAULT_SANDBOX_IMAGE,
    SandboxPolicy,
    build_sandbox_image,
    check_sandbox_readiness,
    verify_container_sandbox,
)
from proofcode_core.verifier import verify_workspace
from proofcode_core.workspace import analyze_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofcode-core"
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser("ping")

    file_parser = subparsers.add_parser(
        "analyze-file"
    )
    file_parser.add_argument("file_path")

    workspace_parser = subparsers.add_parser(
        "analyze-workspace"
    )
    workspace_parser.add_argument("workspace_path")
    workspace_parser.add_argument(
        "--hotspot-limit",
        type=int,
        default=20,
    )
    workspace_parser.add_argument(
        "--include-tests",
        action="store_true",
    )
    workspace_parser.add_argument(
        "--include-examples",
        action="store_true",
    )

    verify_parser = subparsers.add_parser(
        "verify-workspace"
    )
    verify_parser.add_argument("workspace_path")
    verify_parser.add_argument(
        "--timeout",
        type=int,
        default=60,
    )

    candidate_parser = subparsers.add_parser(
        "verify-candidate"
    )
    candidate_parser.add_argument("workspace_path")
    candidate_parser.add_argument("target_file_path")
    candidate_parser.add_argument("candidate_file_path")
    candidate_parser.add_argument(
        "--timeout",
        type=int,
        default=60,
    )

    evidence_parser = subparsers.add_parser(
        "list-candidate-evidence"
    )
    evidence_parser.add_argument("workspace_path")

    benchmark_evidence_parser = subparsers.add_parser(
        "list-benchmark-evidence"
    )
    benchmark_evidence_parser.add_argument("workspace_path")

    record_parser = subparsers.add_parser(
        "record-decision"
    )
    record_parser.add_argument("workspace_path")
    record_parser.add_argument("evidence_path")
    record_parser.add_argument(
        "decision",
        choices=("apply", "hold", "reject"),
    )
    record_parser.add_argument(
        "--reason",
        required=True,
    )

    record_parser.add_argument(
        "--benchmark-evidence",
        default=None,
    )

    decisions_parser = subparsers.add_parser(
        "list-decisions"
    )
    decisions_parser.add_argument("workspace_path")

    read_decision_parser = subparsers.add_parser(
        "read-decision"
    )
    read_decision_parser.add_argument("workspace_path")
    read_decision_parser.add_argument("decision_path")

    benchmark_parser = subparsers.add_parser(
        "benchmark-candidate"
    )
    benchmark_parser.add_argument("workspace_path")
    benchmark_parser.add_argument("evidence_path")
    benchmark_parser.add_argument(
        "--runs",
        type=int,
        default=5,
    )
    benchmark_parser.add_argument(
        "--warmups",
        type=int,
        default=1,
    )
    benchmark_parser.add_argument(
        "--timeout",
        type=int,
        default=60,
    )


    sandbox_status_parser = subparsers.add_parser(
        "sandbox-status"
    )
    sandbox_status_parser.add_argument("workspace_path")
    sandbox_status_parser.add_argument(
        "--image",
        default=DEFAULT_SANDBOX_IMAGE,
    )

    sandbox_build_parser = subparsers.add_parser(
        "build-sandbox-image"
    )
    sandbox_build_parser.add_argument("workspace_path")
    sandbox_build_parser.add_argument(
        "--image",
        default=DEFAULT_SANDBOX_IMAGE,
    )

    sandbox_verify_parser = subparsers.add_parser(
        "verify-sandbox"
    )
    sandbox_verify_parser.add_argument("workspace_path")
    sandbox_verify_parser.add_argument(
        "--image",
        default=DEFAULT_SANDBOX_IMAGE,
    )
    sandbox_verify_parser.add_argument(
        "--cpus",
        type=float,
        default=1.0,
    )
    sandbox_verify_parser.add_argument(
        "--memory",
        default="512m",
    )
    sandbox_verify_parser.add_argument(
        "--pids-limit",
        type=int,
        default=128,
    )
    sandbox_verify_parser.add_argument(
        "--timeout",
        type=int,
        default=60,
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "ping":
            payload = success_payload(
                "ping",
                {
                    "message": (
                        "ProofCode Core is running"
                    ),
                },
            )

        elif args.command == "analyze-file":
            payload = success_payload(
                "file_analysis",
                {
                    "analysis": analyze_file(
                        args.file_path
                    ).to_dict(),
                },
            )

        elif args.command == "analyze-workspace":
            payload = success_payload(
                "workspace_analysis",
                {
                    "workspace_analysis": (
                        analyze_workspace(
                            args.workspace_path,
                            hotspot_limit=(
                                args.hotspot_limit
                            ),
                            include_tests=(
                                args.include_tests
                            ),
                            include_examples=(
                                args.include_examples
                            ),
                        ).to_dict()
                    ),
                },
            )

        elif args.command == "verify-workspace":
            payload = success_payload(
                "workspace_verification",
                {
                    "verification": verify_workspace(
                        args.workspace_path,
                        timeout_seconds=args.timeout,
                    ).to_dict(),
                },
            )

        elif args.command == "verify-candidate":
            payload = success_payload(
                "candidate_verification",
                {
                    "candidate_verification": (
                        verify_candidate_file(
                            workspace_path=(
                                args.workspace_path
                            ),
                            target_file_path=(
                                args.target_file_path
                            ),
                            candidate_file_path=(
                                args.candidate_file_path
                            ),
                            timeout_seconds=args.timeout,
                        ).to_dict()
                    ),
                },
            )

        elif args.command == "list-candidate-evidence":
            payload = success_payload(
                "candidate_evidence_list",
                {
                    "candidate_evidence": [
                        item.to_dict()
                        for item in list_candidate_evidence(
                            args.workspace_path
                        )
                    ],
                },
            )

        elif args.command == "list-benchmark-evidence":
            payload = success_payload(
                "benchmark_evidence_list",
                {
                    "benchmark_evidence": [
                        item.to_dict()
                        for item in list_benchmark_evidence(
                            args.workspace_path
                        )
                    ],
                },
            )

        elif args.command == "record-decision":
            payload = success_payload(
                "developer_decision",
                {
                    "developer_decision": (
                        record_candidate_decision(
                            workspace_path=(
                                args.workspace_path
                            ),
                            evidence_path=(
                                args.evidence_path
                            ),
                            decision=args.decision,
                            reason=args.reason,
                            benchmark_evidence_path=(
                                args.benchmark_evidence
                            ),
                        ).to_dict()
                    ),
                },
            )

        elif args.command == "list-decisions":
            payload = success_payload(
                "decision_list",
                {
                    "decisions": [
                        item.to_dict()
                        for item in list_decisions(
                            args.workspace_path
                        )
                    ],
                },
            )

        elif args.command == "read-decision":
            payload = success_payload(
                "developer_decision",
                {
                    "developer_decision": (
                        read_decision(
                            workspace_path=(
                                args.workspace_path
                            ),
                            decision_path=(
                                args.decision_path
                            ),
                        ).to_dict()
                    ),
                },
            )

        elif args.command == "benchmark-candidate":
            payload = success_payload(
                "candidate_benchmark",
                {
                    "candidate_benchmark": benchmark_candidate(
                        workspace_path=args.workspace_path,
                        evidence_path=args.evidence_path,
                        measured_runs=args.runs,
                        warmup_runs=args.warmups,
                        timeout_seconds=args.timeout,
                    ).to_dict(),
                },
            )

        elif args.command == "sandbox-status":
            policy = SandboxPolicy(image=args.image)
            payload = success_payload(
                "sandbox_readiness",
                {
                    "sandbox_readiness": (
                        check_sandbox_readiness(
                            args.workspace_path,
                            policy,
                        ).to_dict()
                    ),
                },
            )

        elif args.command == "build-sandbox-image":
            payload = success_payload(
                "sandbox_image_build",
                {
                    "sandbox_image_build": (
                        build_sandbox_image(
                            args.workspace_path,
                            image=args.image,
                        ).to_dict()
                    ),
                },
            )

        elif args.command == "verify-sandbox":
            policy = SandboxPolicy(
                image=args.image,
                cpus=args.cpus,
                memory=args.memory,
                memory_swap=args.memory,
                pids_limit=args.pids_limit,
                timeout_seconds=args.timeout,
            )
            payload = success_payload(
                "sandbox_verification",
                {
                    "sandbox_verification": (
                        verify_container_sandbox(
                            args.workspace_path,
                            policy,
                        ).to_dict()
                    ),
                },
            )

        else:
            return 1

        print(json.dumps(payload, ensure_ascii=True))
        return 0

    except (
        FileNotFoundError,
        ValueError,
        OSError,
    ) as error:
        print(
            json.dumps(
                error_payload(error),
                ensure_ascii=True,
            ),
            file=sys.stderr,
        )
        return 1
