from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from proofcode_core.fingerprint import workspace_fingerprint
from proofcode_core.version import (
    APP_VERSION,
    BASELINE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    SANDBOX_EVIDENCE_SCHEMA_VERSION,
)

DEFAULT_SANDBOX_IMAGE = "proofcode-sandbox-python:0.12.0"

COPY_EXCLUDED_NAMES = {
    ".git",
    ".proofcode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "out",
    "dist",
    "build",
}


@dataclass(frozen=True)
class SandboxPolicy:
    image: str = DEFAULT_SANDBOX_IMAGE
    network_mode: str = "none"
    cpus: float = 1.0
    memory: str = "512m"
    memory_swap: str = "512m"
    pids_limit: int = 128
    timeout_seconds: int = 60
    read_only_root: bool = True
    no_new_privileges: bool = True
    cap_drop_all: bool = True
    container_user: str = "10001:10001"
    tmpfs: str = "/tmp:rw,noexec,nosuid,size=64m"
    init_process: bool = True
    original_workspace_mounted: bool = False

    def validate(self) -> None:
        if self.network_mode != "none":
            raise ValueError(
                "Sandbox network_mode는 반드시 'none'이어야 합니다."
            )
        if self.cpus <= 0 or self.cpus > 4:
            raise ValueError("Sandbox CPU 제한은 0보다 크고 4 이하여야 합니다.")
        if not self.memory:
            raise ValueError("Sandbox 메모리 제한이 필요합니다.")
        if self.memory_swap != self.memory:
            raise ValueError(
                "Swap 추가 사용을 막기 위해 memory_swap은 memory와 같아야 합니다."
            )
        if self.pids_limit < 16 or self.pids_limit > 512:
            raise ValueError("Sandbox PID 제한은 16~512 범위여야 합니다.")
        if self.timeout_seconds < 5 or self.timeout_seconds > 600:
            raise ValueError("Sandbox timeout은 5~600초 범위여야 합니다.")
        if not self.read_only_root:
            raise ValueError("Sandbox root filesystem은 읽기 전용이어야 합니다.")
        if not self.no_new_privileges:
            raise ValueError("no-new-privileges가 반드시 활성화되어야 합니다.")
        if not self.cap_drop_all:
            raise ValueError("Linux capability는 모두 제거해야 합니다.")
        if self.original_workspace_mounted:
            raise ValueError("원본 Workspace는 컨테이너에 mount하면 안 됩니다.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxReadiness:
    ready: bool
    docker_cli_available: bool
    docker_daemon_available: bool
    image_available: bool
    docker_cli_path: str | None
    docker_server_version: str | None
    docker_operating_system: str | None
    image: str
    image_id: str | None
    image_repo_digests: list[str]
    policy_valid: bool
    checks: dict[str, bool]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxBuildResult:
    passed: bool
    image: str
    image_id: str | None
    image_repo_digests: list[str]
    duration_seconds: float
    exit_code: int | None
    stdout: str
    stderr: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxRunResult:
    status: str
    passed: bool
    termination_reason: str
    exit_code: int | None
    timed_out: bool
    oom_killed: bool
    duration_seconds: float
    container_id: str | None
    container_name: str
    image: str
    image_id: str | None
    image_repo_digests: list[str]
    command: list[str]
    container_working_directory: str
    policy: SandboxPolicy
    stdout: str
    stderr: str
    container_error: str | None
    container_started_at: str | None
    container_finished_at: str | None
    original_workspace_fingerprint_before: str
    original_workspace_fingerprint_after: str
    original_workspace_changed: bool
    sandbox_workspace_fingerprint_before: str
    sandbox_workspace_fingerprint_after: str
    sandbox_source_changed: bool
    original_workspace_mounted: bool
    mounted_sources: list[str]
    container_removed: bool
    temporary_directory_removed: bool
    cleanup_errors: list[str]
    evidence_saved: bool
    evidence_path: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["policy"] = self.policy.to_dict()
        return data


def _run(
    args: list[str],
    *,
    timeout: int | float | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _docker_cli() -> str | None:
    return shutil.which("docker")


def _docker_server() -> tuple[dict[str, Any] | None, str | None]:
    docker = _docker_cli()
    if docker is None:
        return None, "Docker CLI를 찾을 수 없습니다."

    try:
        result = _run(
            [docker, "version", "--format", "{{json .Server}}"],
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"Docker daemon 확인 실패: {error}"

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        return None, f"Docker daemon에 연결할 수 없습니다: {message}"

    try:
        value = json.loads(result.stdout.strip())
    except json.JSONDecodeError as error:
        return None, f"Docker version 응답을 해석할 수 없습니다: {error}"

    if not isinstance(value, dict):
        return None, "Docker Server 응답이 올바르지 않습니다."

    return value, None


def inspect_image(image: str) -> tuple[str | None, list[str], str | None]:
    docker = _docker_cli()
    if docker is None:
        return None, [], "Docker CLI를 찾을 수 없습니다."

    try:
        result = _run(
            [docker, "image", "inspect", image],
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, [], f"Docker image inspect 실패: {error}"

    if result.returncode != 0:
        return None, [], result.stderr.strip() or "Sandbox image가 없습니다."

    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return None, [], f"Docker image inspect JSON 오류: {error}"

    if not isinstance(values, list) or not values:
        return None, [], "Docker image inspect 결과가 비어 있습니다."

    value = values[0]
    if not isinstance(value, dict):
        return None, [], "Docker image inspect 결과가 올바르지 않습니다."

    image_id = str(value.get("Id") or "") or None
    repo_digests = value.get("RepoDigests") or []
    digests = [str(item) for item in repo_digests if item]

    return image_id, digests, None


def check_sandbox_readiness(
    workspace_path: str,
    policy: SandboxPolicy | None = None,
) -> SandboxReadiness:
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError(f"Workspace가 올바른 폴더가 아닙니다: {workspace}")

    selected_policy = policy or SandboxPolicy()
    errors: list[str] = []

    try:
        selected_policy.validate()
        policy_valid = True
    except ValueError as error:
        policy_valid = False
        errors.append(str(error))

    docker_path = _docker_cli()
    docker_cli_available = docker_path is not None

    server, server_error = _docker_server()
    docker_daemon_available = server is not None
    if server_error:
        errors.append(server_error)

    image_id: str | None = None
    repo_digests: list[str] = []
    image_error: str | None = None

    if docker_daemon_available:
        image_id, repo_digests, image_error = inspect_image(
            selected_policy.image
        )
        if image_error:
            errors.append(image_error)

    image_available = image_id is not None

    checks = {
        "container_runtime": docker_daemon_available and image_available,
        "network_disabled": selected_policy.network_mode == "none",
        "cpu_limited": selected_policy.cpus > 0,
        "memory_limited": bool(selected_policy.memory),
        "swap_limited": (
            selected_policy.memory_swap == selected_policy.memory
        ),
        "time_limited": selected_policy.timeout_seconds > 0,
        "read_only_root": selected_policy.read_only_root,
        "original_workspace_not_mounted": (
            not selected_policy.original_workspace_mounted
        ),
        "capabilities_dropped": selected_policy.cap_drop_all,
        "no_new_privileges": selected_policy.no_new_privileges,
        "pids_limited": selected_policy.pids_limit > 0,
        "cleanup_verification_enabled": True,
        "termination_logging_enabled": True,
    }

    ready = (
        docker_cli_available
        and docker_daemon_available
        and image_available
        and policy_valid
        and all(checks.values())
    )

    return SandboxReadiness(
        ready=ready,
        docker_cli_available=docker_cli_available,
        docker_daemon_available=docker_daemon_available,
        image_available=image_available,
        docker_cli_path=docker_path,
        docker_server_version=(
            str(server.get("Version"))
            if server and server.get("Version")
            else None
        ),
        docker_operating_system=(
            str(server.get("Os"))
            if server and server.get("Os")
            else None
        ),
        image=selected_policy.image,
        image_id=image_id,
        image_repo_digests=repo_digests,
        policy_valid=policy_valid,
        checks=checks,
        errors=errors,
    )


def build_sandbox_image(
    workspace_path: str,
    image: str = DEFAULT_SANDBOX_IMAGE,
) -> SandboxBuildResult:
    workspace = Path(workspace_path).expanduser().resolve()
    dockerfile_directory = workspace / "sandbox" / "python"

    if not dockerfile_directory.is_dir():
        raise ValueError(
            "Sandbox Dockerfile 폴더를 찾을 수 없습니다: "
            f"{dockerfile_directory}"
        )

    docker = _docker_cli()
    if docker is None:
        raise ValueError("Docker CLI를 찾을 수 없습니다.")

    server, server_error = _docker_server()
    if server is None:
        raise ValueError(server_error or "Docker daemon을 사용할 수 없습니다.")

    started = time.perf_counter()
    try:
        result = _run(
            [
                docker,
                "build",
                "--tag",
                image,
                "--label",
                f"proofcode.app_version={APP_VERSION}",
                str(dockerfile_directory),
            ],
            timeout=600,
            cwd=str(workspace),
        )
    except subprocess.TimeoutExpired as error:
        return SandboxBuildResult(
            passed=False,
            image=image,
            image_id=None,
            image_repo_digests=[],
            duration_seconds=round(time.perf_counter() - started, 3),
            exit_code=None,
            stdout=(
                error.stdout.decode("utf-8", errors="replace")
                if isinstance(error.stdout, bytes)
                else error.stdout or ""
            ),
            stderr=(
                error.stderr.decode("utf-8", errors="replace")
                if isinstance(error.stderr, bytes)
                else error.stderr or ""
            ),
            message="Sandbox image build가 시간 초과되었습니다.",
        )

    image_id, repo_digests, image_error = inspect_image(image)
    passed = result.returncode == 0 and image_id is not None

    if passed:
        message = "Sandbox image를 성공적으로 빌드했습니다."
    else:
        message = (
            image_error
            or result.stderr.strip()
            or "Sandbox image build에 실패했습니다."
        )

    return SandboxBuildResult(
        passed=passed,
        image=image,
        image_id=image_id,
        image_repo_digests=repo_digests,
        duration_seconds=round(time.perf_counter() - started, 3),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        message=message,
    )


def _load_baseline(workspace: Path) -> dict[str, Any]:
    path = workspace / ".proofcode" / "evidence" / "baseline.json"
    if not path.is_file():
        raise ValueError(
            "유효한 Baseline이 없습니다. "
            "먼저 ProofCode: Verify Baseline을 실행하세요."
        )

    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Baseline 파일을 읽을 수 없습니다.") from error

    if not isinstance(baseline, dict):
        raise ValueError("Baseline JSON이 올바르지 않습니다.")

    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise ValueError(
            "Baseline 형식이 현재 ProofCode와 다릅니다. "
            "Baseline을 다시 생성하세요."
        )

    verification = baseline.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("Baseline 검증 정보가 없습니다.")

    if verification.get("status") != "passed":
        raise ValueError("테스트를 통과한 Baseline이 아닙니다.")

    return baseline


def _relative_test_directory(
    workspace: Path,
    baseline: dict[str, Any],
) -> Path:
    verification = baseline["verification"]
    command = verification.get("command")

    if not isinstance(command, dict):
        raise ValueError("Baseline 테스트 명령 정보가 없습니다.")

    working_directory = Path(
        str(command.get("working_directory", ""))
    ).expanduser().resolve()

    try:
        return working_directory.relative_to(workspace)
    except ValueError as error:
        raise ValueError(
            "Baseline 테스트 실행 위치가 Workspace 밖에 있습니다."
        ) from error


def _copy_workspace(workspace: Path, destination: Path) -> None:
    shutil.copytree(
        workspace,
        destination,
        ignore=shutil.ignore_patterns(*COPY_EXCLUDED_NAMES),
    )


def _make_writable_for_container(root: Path) -> None:
    if os.name == "nt":
        return

    for path in [root, *root.rglob("*")]:
        try:
            mode = path.stat().st_mode
            if path.is_dir():
                path.chmod(mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            else:
                path.chmod(mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP |
                           stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        except OSError:
            continue


def build_container_create_command(
    *,
    docker_path: str,
    container_name: str,
    sandbox_workspace: Path,
    relative_working_directory: Path,
    policy: SandboxPolicy,
) -> list[str]:
    policy.validate()
    mount_source = str(sandbox_workspace.resolve())
    workdir = (
        Path("/workspace") / relative_working_directory
    ).as_posix()

    command = [
        docker_path,
        "create",
        "--name",
        container_name,
        "--label",
        "proofcode.sandbox=true",
        "--label",
        f"proofcode.app_version={APP_VERSION}",
        "--network",
        policy.network_mode,
        "--cpus",
        str(policy.cpus),
        "--memory",
        policy.memory,
        "--memory-swap",
        policy.memory_swap,
        "--pids-limit",
        str(policy.pids_limit),
        "--user",
        policy.container_user,
        "--mount",
        f"type=bind,source={mount_source},target=/workspace",
        "--workdir",
        workdir,
        "--env",
        "PYTHONPATH=/workspace/core/src",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        "PYTHONUNBUFFERED=1",
        "--tmpfs",
        policy.tmpfs,
        "--stop-timeout",
        "2",
    ]

    if policy.init_process:
        command.append("--init")
    if policy.read_only_root:
        command.append("--read-only")
    if policy.cap_drop_all:
        command.extend(["--cap-drop", "ALL"])
    if policy.no_new_privileges:
        command.extend(
            ["--security-opt", "no-new-privileges=true"]
        )

    command.extend(
        [
            policy.image,
            "python",
            "-m",
            "pytest",
        ]
    )
    return command


def _inspect_container(
    docker: str,
    container: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = _run(
            [docker, "container", "inspect", container],
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"Container inspect 실패: {error}"

    if result.returncode != 0:
        return None, result.stderr.strip() or "Container inspect 실패"

    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return None, f"Container inspect JSON 오류: {error}"

    if not isinstance(values, list) or not values:
        return None, "Container inspect 결과가 비어 있습니다."

    value = values[0]
    if not isinstance(value, dict):
        return None, "Container inspect 결과가 올바르지 않습니다."

    return value, None


def _container_logs(
    docker: str,
    container: str,
) -> tuple[str, str]:
    try:
        result = _run(
            [docker, "container", "logs", container],
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return "", f"Container logs 조회 실패: {error}"

    return result.stdout, result.stderr


def _save_sandbox_evidence(
    workspace: Path,
    result: SandboxRunResult,
) -> Path:
    directory = (
        workspace / ".proofcode" / "evidence" / "sandbox"
    )
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    path = directory / f"{timestamp}-{uuid4().hex[:8]}.json"
    temporary = path.with_suffix(".json.tmp")

    payload = {
        "schema_version": SANDBOX_EVIDENCE_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sandbox_run": result.to_dict(),
    }

    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def _with_saved_evidence(
    workspace: Path,
    result: SandboxRunResult,
) -> SandboxRunResult:
    path = _save_sandbox_evidence(workspace, result)
    return replace(
        result,
        evidence_saved=True,
        evidence_path=str(path),
    )


def verify_container_sandbox(
    workspace_path: str,
    policy: SandboxPolicy | None = None,
) -> SandboxRunResult:
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError(f"Workspace가 올바른 폴더가 아닙니다: {workspace}")

    selected_policy = policy or SandboxPolicy()
    selected_policy.validate()

    baseline = _load_baseline(workspace)
    relative_workdir = _relative_test_directory(
        workspace,
        baseline,
    )
    original_before = workspace_fingerprint(str(workspace))
    baseline_fingerprint = str(
        baseline.get("workspace_fingerprint", "")
    )

    if original_before != baseline_fingerprint:
        raise ValueError(
            "Baseline을 만든 뒤 Workspace가 변경되었습니다. "
            "Baseline을 다시 생성하세요."
        )

    readiness = check_sandbox_readiness(
        str(workspace),
        selected_policy,
    )
    if not readiness.ready:
        details = "; ".join(readiness.errors) or "Sandbox 준비 미완료"
        raise ValueError(
            "Container Sandbox가 준비되지 않았습니다: "
            f"{details}"
        )

    docker = readiness.docker_cli_path
    if docker is None:
        raise ValueError("Docker CLI를 찾을 수 없습니다.")

    temporary_root = Path(
        tempfile.mkdtemp(prefix="proofcode-sandbox-")
    )
    sandbox_workspace = temporary_root / "workspace"
    container_name = f"proofcode-sandbox-{uuid4().hex[:12]}"
    container_id: str | None = None
    create_command: list[str] = []
    stdout = ""
    stderr = ""
    inspect_value: dict[str, Any] | None = None
    inspect_error: str | None = None
    timed_out = False
    duration = 0.0
    sandbox_before = ""
    sandbox_after = ""
    mounted_sources: list[str] = []
    cleanup_errors: list[str] = []
    container_removed = False
    temp_removed = False

    try:
        _copy_workspace(workspace, sandbox_workspace)
        _make_writable_for_container(sandbox_workspace)
        sandbox_before = workspace_fingerprint(
            str(sandbox_workspace)
        )

        create_command = build_container_create_command(
            docker_path=docker,
            container_name=container_name,
            sandbox_workspace=sandbox_workspace,
            relative_working_directory=relative_workdir,
            policy=selected_policy,
        )
        mounted_sources = [str(sandbox_workspace.resolve())]

        create_result = _run(create_command, timeout=30)
        if create_result.returncode != 0:
            raise ValueError(
                "Sandbox container 생성 실패: "
                f"{create_result.stderr.strip()}"
            )

        container_id = create_result.stdout.strip() or container_name
        started = time.perf_counter()

        try:
            start_result = _run(
                [
                    docker,
                    "container",
                    "start",
                    "--attach",
                    container_id,
                ],
                timeout=selected_policy.timeout_seconds,
            )
            stdout = start_result.stdout
            stderr = start_result.stderr
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = (
                error.stdout.decode("utf-8", errors="replace")
                if isinstance(error.stdout, bytes)
                else error.stdout or ""
            )
            stderr = (
                error.stderr.decode("utf-8", errors="replace")
                if isinstance(error.stderr, bytes)
                else error.stderr or ""
            )
            kill_result = _run(
                [docker, "container", "kill", container_id],
                timeout=15,
            )
            if kill_result.returncode != 0:
                cleanup_errors.append(
                    "Timeout 후 container kill 실패: "
                    f"{kill_result.stderr.strip()}"
                )

        duration = round(time.perf_counter() - started, 3)

        log_stdout, log_stderr = _container_logs(
            docker,
            container_id,
        )
        if log_stdout:
            stdout = log_stdout
        if log_stderr:
            stderr = log_stderr

        inspect_value, inspect_error = _inspect_container(
            docker,
            container_id,
        )
        sandbox_after = workspace_fingerprint(
            str(sandbox_workspace)
        )

    finally:
        target = container_id or container_name
        try:
            remove_result = _run(
                [
                    docker,
                    "container",
                    "rm",
                    "--force",
                    "--volumes",
                    target,
                ],
                timeout=30,
            )
            if remove_result.returncode != 0:
                cleanup_errors.append(
                    "Container 삭제 실패: "
                    f"{remove_result.stderr.strip()}"
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            cleanup_errors.append(
                f"Container 삭제 명령 실패: {error}"
            )

        try:
            inspect_after, _ = _inspect_container(
                docker,
                target,
            )
            container_removed = inspect_after is None
            if not container_removed:
                cleanup_errors.append(
                    "Container 삭제 후에도 inspect 결과가 남아 있습니다."
                )
        except Exception as error:  # defensive cleanup check
            cleanup_errors.append(
                f"Container 삭제 확인 실패: {error}"
            )

        try:
            shutil.rmtree(temporary_root)
            temp_removed = not temporary_root.exists()
            if not temp_removed:
                cleanup_errors.append(
                    "임시 Sandbox 폴더가 남아 있습니다."
                )
        except OSError as error:
            temp_removed = False
            cleanup_errors.append(
                f"임시 Sandbox 폴더 삭제 실패: {error}"
            )

    state = {}
    if inspect_value is not None:
        raw_state = inspect_value.get("State")
        if isinstance(raw_state, dict):
            state = raw_state

    exit_code_value = state.get("ExitCode")
    exit_code = (
        int(exit_code_value)
        if isinstance(exit_code_value, int)
        else None
    )
    oom_killed = bool(state.get("OOMKilled", False))
    container_error = (
        str(state.get("Error") or "")
        or inspect_error
        or None
    )
    started_at = str(state.get("StartedAt") or "") or None
    finished_at = str(state.get("FinishedAt") or "") or None

    original_after = workspace_fingerprint(str(workspace))
    original_changed = original_before != original_after
    sandbox_changed = (
        bool(sandbox_before)
        and bool(sandbox_after)
        and sandbox_before != sandbox_after
    )

    if timed_out:
        status = "timeout"
        termination_reason = "timeout_killed"
        message = "실행 시간 제한을 초과해 컨테이너를 강제 종료했습니다."
    elif oom_killed:
        status = "oom_killed"
        termination_reason = "memory_limit_exceeded"
        message = "메모리 제한을 초과해 컨테이너가 종료되었습니다."
    elif inspect_value is None:
        status = "sandbox_error"
        termination_reason = "inspect_failed"
        message = "컨테이너 종료 상태를 확인하지 못했습니다."
    elif exit_code != 0:
        status = "failed"
        termination_reason = "container_exit_nonzero"
        message = "컨테이너 안의 테스트가 실패했습니다."
    elif original_changed:
        status = "blocked"
        termination_reason = "original_workspace_changed"
        message = "실행 중 원본 Workspace가 변경되어 결과를 차단했습니다."
    elif sandbox_changed:
        status = "blocked"
        termination_reason = "sandbox_source_changed"
        message = "실행 코드가 Sandbox 소스를 변경해 결과를 차단했습니다."
    elif not container_removed or not temp_removed:
        status = "cleanup_failed"
        termination_reason = "cleanup_incomplete"
        message = "실행은 끝났지만 Sandbox 정리가 완전히 확인되지 않았습니다."
    else:
        status = "passed"
        termination_reason = "completed"
        message = "Container Sandbox의 제한과 정리 검증을 통과했습니다."

    passed = status == "passed"

    result = SandboxRunResult(
        status=status,
        passed=passed,
        termination_reason=termination_reason,
        exit_code=exit_code,
        timed_out=timed_out,
        oom_killed=oom_killed,
        duration_seconds=duration,
        container_id=container_id,
        container_name=container_name,
        image=selected_policy.image,
        image_id=readiness.image_id,
        image_repo_digests=readiness.image_repo_digests,
        command=create_command,
        container_working_directory=(
            Path("/workspace") / relative_workdir
        ).as_posix(),
        policy=selected_policy,
        stdout=stdout,
        stderr=stderr,
        container_error=container_error,
        container_started_at=started_at,
        container_finished_at=finished_at,
        original_workspace_fingerprint_before=original_before,
        original_workspace_fingerprint_after=original_after,
        original_workspace_changed=original_changed,
        sandbox_workspace_fingerprint_before=sandbox_before,
        sandbox_workspace_fingerprint_after=sandbox_after,
        sandbox_source_changed=sandbox_changed,
        original_workspace_mounted=False,
        mounted_sources=mounted_sources,
        container_removed=container_removed,
        temporary_directory_removed=temp_removed,
        cleanup_errors=cleanup_errors,
        evidence_saved=False,
        evidence_path=None,
        message=message,
    )

    return _with_saved_evidence(workspace, result)
