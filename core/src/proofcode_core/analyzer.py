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
        return sum(asdict(self).values())

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class FunctionEvidence:
    return_count: int
    call_count: int
    call_names: list[str]
    raise_count: int
    max_nesting_depth: int

    def to_dict(self) -> dict[str, Any]:
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
    evidence: FunctionEvidence | None
    parameters: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        if self.complexity_breakdown is not None:
            data["complexity_breakdown"] = (
                self.complexity_breakdown.to_dict()
            )

        if self.evidence is not None:
            data["evidence"] = self.evidence.to_dict()

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


def _parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    names: list[str] = []
    names.extend(arg.arg for arg in node.args.posonlyargs)
    names.extend(arg.arg for arg in node.args.args)

    if node.args.vararg:
        names.append(f"*{node.args.vararg.arg}")

    names.extend(arg.arg for arg in node.args.kwonlyargs)

    if node.args.kwarg:
        names.append(f"**{node.args.kwarg.arg}")

    return names


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr

    return node.__class__.__name__


class _FunctionBodyVisitor(ast.NodeVisitor):
    """Collect facts from one function without entering nested functions."""

    def __init__(self) -> None:
        self.conditions = 0
        self.loops = 0
        self.boolean_branches = 0
        self.exception_handlers = 0
        self.comprehensions = 0
        self.match_cases = 0
        self.return_count = 0
        self.call_names: list[str] = []
        self.raise_count = 0
        self.current_nesting = 0
        self.max_nesting = 0

    def _visit_nested_block(self, node: ast.AST) -> None:
        self.current_nesting += 1
        self.max_nesting = max(
            self.max_nesting,
            self.current_nesting,
        )
        self.generic_visit(node)
        self.current_nesting -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Nested function evidence belongs to the nested function itself.
        return

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_If(self, node: ast.If) -> None:
        self.conditions += 1
        self._visit_nested_block(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.conditions += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.loops += 1
        self._visit_nested_block(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.loops += 1
        self._visit_nested_block(node)

    def visit_While(self, node: ast.While) -> None:
        self.loops += 1
        self._visit_nested_block(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_nested_block(node)

    def visit_With(self, node: ast.With) -> None:
        self._visit_nested_block(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_nested_block(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.match_cases += len(node.cases)
        self._visit_nested_block(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.boolean_branches += max(1, len(node.values) - 1)
        self.generic_visit(node)

    def visit_ExceptHandler(
        self,
        node: ast.ExceptHandler,
    ) -> None:
        self.exception_handlers += 1
        self.generic_visit(node)

    def visit_comprehension(
        self,
        node: ast.comprehension,
    ) -> None:
        self.comprehensions += 1
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.return_count += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.call_names.append(_call_name(node.func))
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        self.raise_count += 1
        self.generic_visit(node)


def _inspect_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ComplexityBreakdown, FunctionEvidence]:
    visitor = _FunctionBodyVisitor()

    for statement in node.body:
        visitor.visit(statement)

    breakdown = ComplexityBreakdown(
        conditions=visitor.conditions,
        loops=visitor.loops,
        boolean_branches=visitor.boolean_branches,
        exception_handlers=visitor.exception_handlers,
        comprehensions=visitor.comprehensions,
        match_cases=visitor.match_cases,
    )

    evidence = FunctionEvidence(
        return_count=visitor.return_count,
        call_count=len(visitor.call_names),
        call_names=visitor.call_names,
        raise_count=visitor.raise_count,
        max_nesting_depth=visitor.max_nesting,
    )

    return breakdown, evidence


def _symbol_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> CodeSymbol:
    start = node.lineno
    end = _line_end(node)
    breakdown, evidence = _inspect_function(node)

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
        evidence=evidence,
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
        evidence=None,
        parameters=[],
    )


def analyze_python_structure(
    text: str,
    file_name: str,
) -> StructureAnalysis:
    try:
        tree = ast.parse(text, filename=file_name)
    except SyntaxError as error:
        raise ValueError(
            f"Python syntax error at line {error.lineno}: {error.msg}"
        ) from error

    classes: list[CodeSymbol] = []
    functions: list[CodeSymbol] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(_symbol_from_class(node))
        elif isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
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
        raise ValueError(
            f"File is not valid UTF-8 text: {path}"
        ) from error

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
