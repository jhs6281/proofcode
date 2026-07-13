from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from proofcode_core.analyzer import analyze_file
from proofcode_core.contract import error_payload, success_payload
from proofcode_core.verifier import verify_workspace
from proofcode_core.workspace import analyze_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofcode-core")
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser("ping")

    file_parser = subparsers.add_parser("analyze-file")
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

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "ping":
            payload = success_payload(
                "ping",
                {
                    "message": "ProofCode Core is running",
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
                    "workspace_analysis": analyze_workspace(
                        args.workspace_path,
                        hotspot_limit=args.hotspot_limit,
                        include_tests=args.include_tests,
                        include_examples=args.include_examples,
                    ).to_dict(),
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
