from pathlib import Path

import pytest

from proofcode_core.analyzer import analyze_file, detect_language

def test_detect_language() -> None:
    assert detect_language(Path("app.py")) == "python"
    assert detect_language(Path("app.js")) == "javascript"
    assert detect_language(Path("app.ts")) == "typescript"
    assert detect_language(Path("App.java")) == "java"
    assert detect_language(Path("README.md")) == "unknown"

def test_analyze_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("print('hello')\n\nname = 'ProofCode'\n", encoding="utf-8")

    result = analyze_file(str(source))

    assert result.file_name == "sample.py"
    assert result.language == "python"
    assert result.total_lines == 3
    assert result.non_empty_lines == 2
    assert result.empty_lines == 1
    assert result.size_bytes > 0
    assert len(result.sha256) == 64

def test_analyze_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        analyze_file("missing-file.py")
