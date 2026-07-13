from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from proofcode_core.analyzer import analyze_file
from proofcode_core.workspace import analyze_workspace

PROTOCOL_VERSION = "0.4"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofcode-core")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ping")

    analyze_file_parser = subparsers.add_parser("analyze-file")
    analyze_file_parser.add_argument("file_path")

    analyze_workspace_parser = subparsers.add_parser("analyze-workspace")
    analyze_workspace_parser.add_argument("workspace_path")
    analyze_workspace_parser.add_argument("--hotspot-limit", type=int, default=10)

    return parser

def ping_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "ProofCode Core is running",
        "protocol_version": PROTOCOL_VERSION,
    }

def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "ping":
            payload = ping_payload()
        elif args.command == "analyze-file":
            payload = {
                "status": "ok",
                "protocol_version": PROTOCOL_VERSION,
                "analysis": analyze_file(args.file_path).to_dict(),
            }
        elif args.command == "analyze-workspace":
            payload = {
                "status": "ok",
                "protocol_version": PROTOCOL_VERSION,
                "workspace_analysis": analyze_workspace(
                    args.workspace_path,
                    hotspot_limit=args.hotspot_limit,
                ).to_dict(),
            }
        else:
            return 1

        print(json.dumps(payload, ensure_ascii=False))
        return 0

    except (FileNotFoundError, ValueError, OSError) as error:
        print(json.dumps({
            "status": "error",
            "protocol_version": PROTOCOL_VERSION,
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
            },
        }, ensure_ascii=False), file=sys.stderr)
        return 1
