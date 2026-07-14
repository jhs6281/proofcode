import json
from pathlib import Path

from proofcode_core.contract import success_payload
from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    PROTOCOL_VERSION,
)


REQUIRED_COMMANDS = {
    "proofcode.pingCore",
    "proofcode.analyzeCurrentFile",
    "proofcode.analyzeWorkspace",
    "proofcode.openHotspot",
    "proofcode.inspectHotspot",
    "proofcode.verifyBaseline",
    "proofcode.verifyCandidateFile",
    "proofcode.recordCandidateDecision",
    "proofcode.viewDecisionHistory",
    "proofcode.benchmarkCandidate",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_app_and_protocol_versions_are_separate() -> None:
    assert APP_VERSION == "0.10.0"
    assert PROTOCOL_VERSION == "1"
    assert APP_VERSION != PROTOCOL_VERSION


def test_success_payload_uses_shared_versions() -> None:
    payload = success_payload("test", {"value": 1})

    assert payload["app_version"] == APP_VERSION
    assert payload["protocol_version"] == PROTOCOL_VERSION


def test_protocol_schema_matches_protocol_version() -> None:
    schema_path = (
        repository_root()
        / "contracts"
        / "proofcode-protocol.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert (
        schema["properties"]["protocol_version"]["const"]
        == PROTOCOL_VERSION
    )


def test_extension_keeps_all_commands() -> None:
    package_path = (
        repository_root()
        / "extension"
        / "package.json"
    )
    package = json.loads(
        package_path.read_text(encoding="utf-8")
    )

    contributed = {
        item["command"]
        for item in package["contributes"]["commands"]
    }
    activation_events = {
        item.removeprefix("onCommand:")
        for item in package["activationEvents"]
    }

    assert REQUIRED_COMMANDS <= contributed
    assert REQUIRED_COMMANDS <= activation_events


def test_fingerprint_changes_for_source_but_ignores_baseline(
    tmp_path: Path,
) -> None:
    source = tmp_path / "app.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    first = workspace_fingerprint(str(tmp_path))

    baseline = (
        tmp_path
        / ".proofcode"
        / "evidence"
        / "baseline.json"
    )
    baseline.parent.mkdir(parents=True)
    baseline.write_text('{"test": true}\n', encoding="utf-8")

    second = workspace_fingerprint(str(tmp_path))
    assert second == first

    source.write_text("VALUE = 2\n", encoding="utf-8")
    third = workspace_fingerprint(str(tmp_path))

    assert third != first
