import json
import subprocess
import sys


def test_ping_returns_valid_json() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "proofcode_core", "ping"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["message"] == "ProofCode Core is running"
    assert payload["protocol_version"] == "0.1"
