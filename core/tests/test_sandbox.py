from pathlib import Path
from unittest.mock import patch

import pytest

from proofcode_core.sandbox import (
    SandboxPolicy,
    build_container_create_command,
    check_sandbox_readiness,
)


def test_secure_policy_is_valid() -> None:
    policy = SandboxPolicy()
    policy.validate()

    assert policy.network_mode == "none"
    assert policy.memory == policy.memory_swap
    assert policy.read_only_root is True
    assert policy.cap_drop_all is True
    assert policy.no_new_privileges is True
    assert policy.original_workspace_mounted is False


def test_insecure_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="network_mode"):
        SandboxPolicy(network_mode="bridge").validate()

    with pytest.raises(ValueError, match="memory_swap"):
        SandboxPolicy(
            memory="512m",
            memory_swap="1g",
        ).validate()


def test_container_command_contains_all_security_limits(
    tmp_path: Path,
) -> None:
    sandbox_workspace = tmp_path / "copy"
    sandbox_workspace.mkdir()

    command = build_container_create_command(
        docker_path="docker",
        container_name="proofcode-test",
        sandbox_workspace=sandbox_workspace,
        relative_working_directory=Path("core"),
        policy=SandboxPolicy(),
    )
    joined = " ".join(command)

    assert "--network none" in joined
    assert "--cpus 1.0" in joined
    assert "--memory 512m" in joined
    assert "--memory-swap 512m" in joined
    assert "--pids-limit 128" in joined
    assert "--read-only" in command
    assert "--cap-drop ALL" in joined
    assert "--security-opt no-new-privileges=true" in joined
    assert "--user 10001:10001" in joined
    assert "--tmpfs /tmp:rw,noexec,nosuid,size=64m" in joined
    assert "--init" in command
    assert str(sandbox_workspace.resolve()) in joined
    assert "python -m pytest" in joined


def test_original_workspace_is_not_mounted(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    sandbox_copy = tmp_path / "sandbox-copy"
    original.mkdir()
    sandbox_copy.mkdir()

    command = build_container_create_command(
        docker_path="docker",
        container_name="proofcode-test",
        sandbox_workspace=sandbox_copy,
        relative_working_directory=Path("core"),
        policy=SandboxPolicy(),
    )
    joined = " ".join(command)

    assert str(sandbox_copy.resolve()) in joined
    assert str(original.resolve()) not in joined


def test_readiness_reports_missing_docker(
    tmp_path: Path,
) -> None:
    with patch(
        "proofcode_core.sandbox.shutil.which",
        return_value=None,
    ):
        readiness = check_sandbox_readiness(
            str(tmp_path)
        )

    assert readiness.ready is False
    assert readiness.docker_cli_available is False
    assert readiness.docker_daemon_available is False
    assert readiness.image_available is False
    assert readiness.checks["network_disabled"] is True


def test_readiness_requires_image(
    tmp_path: Path,
) -> None:
    with (
        patch(
            "proofcode_core.sandbox._docker_cli",
            return_value="docker",
        ),
        patch(
            "proofcode_core.sandbox._docker_server",
            return_value=(
                {"Version": "test", "Os": "linux"},
                None,
            ),
        ),
        patch(
            "proofcode_core.sandbox.inspect_image",
            return_value=(
                None,
                [],
                "image missing",
            ),
        ),
    ):
        readiness = check_sandbox_readiness(
            str(tmp_path)
        )

    assert readiness.docker_daemon_available is True
    assert readiness.image_available is False
    assert readiness.ready is False


def test_readiness_passes_with_daemon_and_image(
    tmp_path: Path,
) -> None:
    with (
        patch(
            "proofcode_core.sandbox._docker_cli",
            return_value="docker",
        ),
        patch(
            "proofcode_core.sandbox._docker_server",
            return_value=(
                {"Version": "test", "Os": "linux"},
                None,
            ),
        ),
        patch(
            "proofcode_core.sandbox.inspect_image",
            return_value=(
                "sha256:image",
                ["proofcode@sha256:digest"],
                None,
            ),
        ),
    ):
        readiness = check_sandbox_readiness(
            str(tmp_path)
        )

    assert readiness.ready is True
    assert all(readiness.checks.values())
