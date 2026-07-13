import json
import os
import subprocess
import sys
from pathlib import Path

from proofcode_core.version import (
    APP_VERSION,
    PROTOCOL_VERSION,
)


def test_ping_returns_valid_protocol_envelope() -> None:
    core_root = Path(__file__).resolve().parents[1]
    source_root = core_root / "src"

    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            [
                str(source_root),
                os.environ.get("PYTHONPATH", ""),
            ]
        ).rstrip(os.pathsep),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "proofcode_core",
            "ping",
        ],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        env=environment,
    )

    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["kind"] == "ping"
    assert payload["app_version"] == APP_VERSION
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert (
        payload["data"]["message"]
        == "ProofCode Core is running"
    )
