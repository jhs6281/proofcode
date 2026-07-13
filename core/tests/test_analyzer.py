from pathlib import Path

import pytest

from proofcode_core.analyzer import analyze_file, detect_language

def test_detect_language() -> None:
    assert detect_language(Path("app.py")) == "python"
    assert detect_language(Path("app.js")) == "javascript"
    assert detect_language(Path("app.ts")) == "typescript"
    assert detect_language(Path("App.java")) == "java"
    assert detect_language(Path("settings.json")) == "json"
    assert detect_language(Path("README.md")) == "unknown"

def test_analyze_python_structure(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        """
class Calculator:
    def add(self, a, b):
        return a + b

def choose(value):
    if value > 10:
        return "large"
    return "small"
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_file(str(source))

    assert result.language == "python"
    assert result.structure.supported is True
    assert result.structure.parser == "python-ast"
    assert result.structure.total_symbols == 3

    class_names = [item.name for item in result.structure.classes]
    function_names = [item.name for item in result.structure.functions]

    assert class_names == ["Calculator"]
    assert function_names == ["add", "choose"]

    choose = next(
        item for item in result.structure.functions if item.name == "choose"
    )
    assert choose.parameters == ["value"]
    assert choose.complexity == 2

def test_unsupported_language_has_empty_structure(tmp_path: Path) -> None:
    source = tmp_path / "sample.js"
    source.write_text("function hello() {}\n", encoding="utf-8")

    result = analyze_file(str(source))

    assert result.language == "javascript"
    assert result.structure.supported is False
    assert result.structure.total_symbols == 0

def test_invalid_python_reports_syntax_error(tmp_path: Path) -> None:
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Python syntax error"):
        analyze_file(str(source))

def test_analyze_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        analyze_file("missing-file.py")
