from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from proofcode_core.analyzer import FileAnalysis, analyze_file

DEFAULT_EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "out", "dist", "build",
}

SUPPORTED_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".cs",
}

@dataclass(frozen=True)
class Hotspot:
    file_path: str
    file_name: str
    symbol_name: str
    symbol_type: str
    line_start: int
    line_end: int
    line_count: int
    complexity: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class WorkspaceAnalysis:
    workspace_path: str
    scanned_files: int
    supported_structure_files: int
    total_lines: int
    total_classes: int
    total_functions: int
    hotspots: list[Hotspot]
    files: list[FileAnalysis]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_path": self.workspace_path,
            "scanned_files": self.scanned_files,
            "supported_structure_files": self.supported_structure_files,
            "total_lines": self.total_lines,
            "total_classes": self.total_classes,
            "total_functions": self.total_functions,
            "hotspots": [item.to_dict() for item in self.hotspots],
            "files": [item.to_dict() for item in self.files],
        }

def _is_excluded(path: Path, workspace: Path) -> bool:
    relative_parts = path.relative_to(workspace).parts
    return any(part in DEFAULT_EXCLUDED_DIRS for part in relative_parts)

def discover_source_files(workspace_path: str) -> list[Path]:
    workspace = Path(workspace_path).expanduser().resolve()

    if not workspace.exists():
        raise FileNotFoundError(f"Workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"Workspace path is not a directory: {workspace}")

    files = [
        path for path in workspace.rglob("*")
        if path.is_file()
        and not _is_excluded(path, workspace)
        and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files)

def analyze_workspace(workspace_path: str, hotspot_limit: int = 10) -> WorkspaceAnalysis:
    workspace = Path(workspace_path).expanduser().resolve()
    analyses: list[FileAnalysis] = []
    hotspots: list[Hotspot] = []

    for path in discover_source_files(str(workspace)):
        try:
            analysis = analyze_file(str(path))
        except ValueError:
            continue

        analyses.append(analysis)

        for symbol in analysis.structure.functions:
            if symbol.complexity is None:
                continue

            hotspots.append(Hotspot(
                file_path=analysis.path,
                file_name=analysis.file_name,
                symbol_name=symbol.name,
                symbol_type=symbol.symbol_type,
                line_start=symbol.line_start,
                line_end=symbol.line_end,
                line_count=symbol.line_count,
                complexity=symbol.complexity,
            ))

    hotspots.sort(
        key=lambda item: (item.complexity, item.line_count, item.file_name),
        reverse=True,
    )

    return WorkspaceAnalysis(
        workspace_path=str(workspace),
        scanned_files=len(analyses),
        supported_structure_files=sum(
            1 for item in analyses if item.structure.supported
        ),
        total_lines=sum(item.total_lines for item in analyses),
        total_classes=sum(len(item.structure.classes) for item in analyses),
        total_functions=sum(len(item.structure.functions) for item in analyses),
        hotspots=hotspots[:hotspot_limit],
        files=analyses,
    )
