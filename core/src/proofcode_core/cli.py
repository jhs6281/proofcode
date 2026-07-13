from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from proofcode_core.analyzer import analyze_file

PROTOCOL_VERSION = "0.2"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofcode-core")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ping", help="Check whether ProofCode Core is available.")

    analyze_parser = subparsers.add_parser(
        "analyze-file",
        help="Analyze basic information about one source file.",
    )
    analyze_parser.add_argument("file_path", help="Path to the source file to analyze.")
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
            print(json.dumps(ping_payload(), ensure_ascii=False))
            return 0

        if args.command == "analyze-file":
            result = analyze_file(args.file_path)
            print(json.dumps({
                "status": "ok",
                "protocol_version": PROTOCOL_VERSION,
                "analysis": result.to_dict(),
            }, ensure_ascii=False))
            return 0

        return 1

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
