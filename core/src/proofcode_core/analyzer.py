from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript-react",
    ".jsx": "javascript-react",
    ".java": "java",
    ".cs": "csharp",
    ".json": "json",
}

@dataclass(frozen=True)
class ComplexityBreakdown:
    conditions: int
    loops: int
    boolean_branches: int
    exception_handlers: int
    comprehensions: int
    match_cases: int

    @property
    def total_added(self) -> int:
        return (
            self.conditions
            + self.loops
            + self.boolean_branches
            + self.exception_handlers
            + self.comprehensions
            + self.match_cases
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

@dataclass(frozen=True)
class CodeSymbol:
    symbol_type: str
    name: str
    line_start: int
    line_end: int
    line_count: int
    complexity: int | None
    complexity_breakdown: ComplexityBreakdown | None
    parameters: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.complexity_breakdown is not None:
            data["complexity_breakdown"] = self.complexity_breakdown.to_dict()
        return data

@dataclass(frozen=True)
class StructureAnalysis:
    supported: bool
    parser: str | None
    classes: list[CodeSymbol]
    functions: list[CodeSymbol]
    total_symbols: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "parser": self.parser,
            "classes": [item.to_dict() for item in self.classes],
            "functions": [item.to_dict() for item in self.functions],
            "total_symbols": self.total_symbols,
        }

@dataclass(frozen=True)
class FileAnalysis:
    path: str
    file_name: str
    language: str
    size_bytes: int
    total_lines: int
    non_empty_lines: int
    empty_lines: int
    sha256: str
    structure: StructureAnalysis

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "file_name": self.file_name,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "total_lines": self.total_lines,
            "non_empty_lines": self.non_empty_lines,
            "empty_lines": self.empty_lines,
            "sha256": self.sha256,
            "structure": self.structure.to_dict(),
        }

def detect_language(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")

def _line_end(node: ast.AST) -> int:
    return getattr(node, "end_lineno", getattr(node, "lineno", 0))

def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names: list[str] = []

    for arg in node.args.posonlyargs:
        names.append(arg.arg)
    for arg in node.args.args:
        names.append(arg.arg)
    if node.args.vararg:
        names.append(f"*{node.args.vararg.arg}")
    for arg in node.args.kwonlyargs:
        names.append(arg.arg)
    if node.args.kwarg:
        names.append(f"**{node.args.kwarg.arg}")

    return names

def _complexity_breakdown(node: ast.AST) -> ComplexityBreakdown:
    conditions = 0
    loops = 0
    boolean_branches = 0
    exception_handlers = 0
    comprehensions = 0
    match_cases = 0

    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            conditions += 1
        elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
            loops += 1
        elif isinstance(child, ast.BoolOp):
            boolean_branches += max(1, len(child.values) - 1)
        elif isinstance(child, ast.ExceptHandler):
            exception_handlers += 1
        elif isinstance(child, ast.comprehension):
            comprehensions += 1
        elif isinstance(child, ast.Match):
            match_cases += len(child.cases)

    return ComplexityBreakdown(
        conditions=conditions,
        loops=loops,
        boolean_branches=boolean_branches,
        exception_handlers=exception_handlers,
        comprehensions=comprehensions,
        match_cases=match_cases,
    )

def _symbol_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> CodeSymbol:
    start = node.lineno
    end = _line_end(node)
    breakdown = _complexity_breakdown(node)

    return CodeSymbol(
        symbol_type=(
            "async_function"
            if isinstance(node, ast.AsyncFunctionDef)
            else "function"
        ),
        name=node.name,
        line_start=start,
        line_end=end,
        line_count=end - start + 1,
        complexity=1 + breakdown.total_added,
        complexity_breakdown=breakdown,
        parameters=_parameter_names(node),
    )

def _symbol_from_class(node: ast.ClassDef) -> CodeSymbol:
    start = node.lineno
    end = _line_end(node)

    return CodeSymbol(
        symbol_type="class",
        name=node.name,
        line_start=start,
        line_end=end,
        line_count=end - start + 1,
        complexity=None,
        complexity_breakdown=None,
        parameters=[],
    )

def analyze_python_structure(text: str, file_name: str) -> StructureAnalysis:
    try:
        tree = ast.parse(text, filename=file_name)
    except SyntaxError as error:
        message = f"Python syntax error at line {error.lineno}: {error.msg}"
        raise ValueError(message) from error

    classes: list[CodeSymbol] = []
    functions: list[CodeSymbol] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(_symbol_from_class(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_symbol_from_function(node))

    classes.sort(key=lambda item: item.line_start)
    functions.sort(key=lambda item: item.line_start)

    return StructureAnalysis(
        supported=True,
        parser="python-ast",
        classes=classes,
        functions=functions,
        total_symbols=len(classes) + len(functions),
    )

def analyze_structure(
    language: str,
    text: str,
    file_name: str,
) -> StructureAnalysis:
    if language == "python":
        return analyze_python_structure(text, file_name)

    return StructureAnalysis(
        supported=False,
        parser=None,
        classes=[],
        functions=[],
        total_symbols=0,
    )

def analyze_file(file_path: str) -> FileAnalysis:
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    raw_bytes = path.read_bytes()

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"File is not valid UTF-8 text: {path}") from error

    language = detect_language(path)
    lines = text.splitlines()
    non_empty_lines = sum(1 for line in lines if line.strip())

    return FileAnalysis(
        path=str(path),
        file_name=path.name,
        language=language,
        size_bytes=len(raw_bytes),
        total_lines=len(lines),
        non_empty_lines=non_empty_lines,
        empty_lines=len(lines) - non_empty_lines,
        sha256=sha256(raw_bytes).hexdigest(),
        structure=analyze_structure(language, text, path.name),
    )
