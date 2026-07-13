from __future__ import annotations

from typing import Any

from proofcode_core.version import APP_VERSION, PROTOCOL_VERSION


def success_payload(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok",
        "kind": kind,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "data": data,
    }
    validate_payload(payload)
    return payload


def error_payload(error: Exception) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
        "kind": "error",
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "error": {
            "type": error.__class__.__name__,
            "message": str(error),
        },
    }
    validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> None:
    required = {
        "status",
        "kind",
        "app_version",
        "protocol_version",
    }
    missing = required - payload.keys()

    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Protocol payload is missing fields: {names}")

    if payload["status"] not in {"ok", "error"}:
        raise ValueError("Protocol status must be 'ok' or 'error'.")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("Protocol version does not match the Core version.")

    if payload["status"] == "ok" and "data" not in payload:
        raise ValueError("Successful protocol payload requires data.")

    if payload["status"] == "error" and "error" not in payload:
        raise ValueError("Error protocol payload requires error details.")
