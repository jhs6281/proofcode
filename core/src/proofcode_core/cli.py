from __future__ import annotations

import argparse
import json
from typing import Sequence

PROTOCOL_VERSION = "0.1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofcode-core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ping", help="Check whether ProofCode Core is available.")
    return parser


def ping_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "ProofCode Core is running",
        "protocol_version": PROTOCOL_VERSION,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "ping":
        print(json.dumps(ping_payload(), ensure_ascii=False))
        return 0

    return 1
