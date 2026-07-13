from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from proofcode_core.analyzer import (
    ComplexityBreakdown,
    FileAnalysis,
    FunctionEvidence,
    analyze_file,
)

CodeCategory = Literal["source", "test", "example"]

DEFAULT_EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "out", "dist", "build",
}
SUPPORTED_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".cs",
}
TEST_PATH_NAMES = {"test", "tests"}
EXAMPLE_PATH_NAMES = {
    "example", "examples", "fixture", "fixtures", "sample", "samples"
}

@dataclass(frozen=True)
class Hotspot:
    file_path: str
    relative_path: str
    file_name: str
    category: CodeCategory
    symbol_name: str
    symbol_type: str
    line_start: int
    line_end: int
    line_count: int
    complexity: int
    complexity_breakdown: ComplexityBreakdown
    evidence: FunctionEvidence
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["complexity_breakdown"] = self.complexity_breakdown.to_dict()
        data["evidence"] = self.evidence.to_dict()
        return data

@dataclass(frozen=True)
class CategoryCounts:
    source: int
    test: int
    example: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

@dataclass(frozen=True)
class WorkspaceAnalysis:
    workspace_path: str
    scanned_files: int
    supported_structure_files: int
    total_lines: int
    total_classes: int
    total_functions: int
    category_counts: CategoryCounts
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
            "category_counts": self.category_counts.to_dict(),
            "hotspots": [item.to_dict() for item in self.hotspots],
            "files": [item.to_dict() for item in self.files],
        }

def classify_code_path(path: Path, workspace: Path) -> CodeCategory:
    relative = path.relative_to(workspace)
    lowered_parts = {part.lower() for part in relative.parts}
    file_name = path.name.lower()

    if (
        lowered_parts & TEST_PATH_NAMES
        or file_name.startswith("test_")
        or file_name.endswith("_test.py")
        or file_name.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    ):
        return "test"

    if lowered_parts & EXAMPLE_PATH_NAMES:
        return "example"

    return "source"

def _is_excluded(path: Path, workspace: Path) -> bool:
    return any(
        part in DEFAULT_EXCLUDED_DIRS
        for part in path.relative_to(workspace).parts
    )

def discover_source_files(workspace_path: str) -> list[Path]:
    workspace = Path(workspace_path).expanduser().resolve()

    if not workspace.exists():
        raise FileNotFoundError(f"Workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"Workspace path is not a directory: {workspace}")

    return sorted(
        path
        for path in workspace.rglob("*")
        if path.is_file()
        and not _is_excluded(path, workspace)
        and path.suffix.lower() in SUPPORTED_SUFFIXES
    )

def build_reasons(
    line_count: int,
    breakdown: ComplexityBreakdown,
) -> list[str]:
    reasons: list[str] = []

    labels = (
        ("조건 분기", breakdown.conditions),
        ("반복문", breakdown.loops),
        ("논리 연산 분기", breakdown.boolean_branches),
        ("예외 처리 분기", breakdown.exception_handlers),
        ("컴프리헨션 반복", breakdown.comprehensions),
        ("match case", breakdown.match_cases),
    )

    reasons.extend(
        f"{label} {count}개"
        for label, count in labels
        if count
    )

    if line_count >= 30:
        reasons.append(f"함수 길이 {line_count}줄")

    return reasons or ["기본 복잡도만 존재"]

def analyze_workspace(
    workspace_path: str,
    hotspot_limit: int = 20,
    include_tests: bool = False,
    include_examples: bool = False,
) -> WorkspaceAnalysis:
    workspace = Path(workspace_path).expanduser().resolve()
    analyses: list[FileAnalysis] = []
    hotspots: list[Hotspot] = []
    category_totals = {"source": 0, "test": 0, "example": 0}

    for path in discover_source_files(str(workspace)):
        category = classify_code_path(path, workspace)
        category_totals[category] += 1

        try:
            analysis = analyze_file(str(path))
        except ValueError:
            continue

        analyses.append(analysis)

        if category == "test" and not include_tests:
            continue
        if category == "example" and not include_examples:
            continue

        for symbol in analysis.structure.functions:
            if (
                symbol.complexity is None
                or symbol.complexity_breakdown is None
                or symbol.evidence is None
            ):
                continue

            hotspots.append(
                Hotspot(
                    file_path=analysis.path,
                    relative_path=path.relative_to(workspace).as_posix(),
                    file_name=analysis.file_name,
                    category=category,
                    symbol_name=symbol.name,
                    symbol_type=symbol.symbol_type,
                    line_start=symbol.line_start,
                    line_end=symbol.line_end,
                    line_count=symbol.line_count,
                    complexity=symbol.complexity,
                    complexity_breakdown=symbol.complexity_breakdown,
                    evidence=symbol.evidence,
                    reasons=build_reasons(
                        symbol.line_count,
                        symbol.complexity_breakdown,
                    ),
                )
            )

    hotspots.sort(
        key=lambda item: (
            item.complexity,
            item.line_count,
            item.relative_path,
            item.symbol_name,
        ),
        reverse=True,
    )

    return WorkspaceAnalysis(
        workspace_path=str(workspace),
        scanned_files=len(analyses),
        supported_structure_files=sum(
            item.structure.supported for item in analyses
        ),
        total_lines=sum(item.total_lines for item in analyses),
        total_classes=sum(
            len(item.structure.classes) for item in analyses
        ),
        total_functions=sum(
            len(item.structure.functions) for item in analyses
        ),
        category_counts=CategoryCounts(**category_totals),
        hotspots=hotspots[:hotspot_limit],
        files=analyses,
    )
