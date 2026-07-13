from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

def detect_language(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")

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

    lines = text.splitlines()
    non_empty_lines = sum(1 for line in lines if line.strip())

    return FileAnalysis(
        path=str(path),
        file_name=path.name,
        language=detect_language(path),
        size_bytes=len(raw_bytes),
        total_lines=len(lines),
        non_empty_lines=non_empty_lines,
        empty_lines=len(lines) - non_empty_lines,
        sha256=sha256(raw_bytes).hexdigest(),
    )
