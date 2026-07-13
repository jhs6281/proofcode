from __future__ import annotations

from hashlib import sha256
from pathlib import Path

EXCLUDED_DIRECTORIES = {
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

SOURCE_SUFFIXES = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cs",
    ".json",
}

CONFIG_FILE_NAMES = {
    "pyproject.toml",
    "pytest.ini",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
}


def _should_include(path: Path, workspace: Path) -> bool:
    relative = path.relative_to(workspace)

    if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
        return False

    return (
        path.suffix.lower() in SOURCE_SUFFIXES
        or path.name.lower() in CONFIG_FILE_NAMES
    )


def workspace_fingerprint(workspace_path: str) -> str:
    workspace = Path(workspace_path).expanduser().resolve()

    if not workspace.exists():
        raise FileNotFoundError(f"Workspace does not exist: {workspace}")

    if not workspace.is_dir():
        raise ValueError(f"Workspace path is not a directory: {workspace}")

    digest = sha256()

    files = sorted(
        path
        for path in workspace.rglob("*")
        if path.is_file() and _should_include(path, workspace)
    )

    for path in files:
        relative = path.relative_to(workspace).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    return digest.hexdigest()
