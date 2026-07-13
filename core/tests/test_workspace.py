from pathlib import Path

from proofcode_core.workspace import (
    analyze_workspace,
    classify_code_path,
    discover_source_files,
)

def test_classify_code_path(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    test = tmp_path / "tests" / "test_service.py"
    example = tmp_path / "examples" / "sample.py"

    assert classify_code_path(source, tmp_path) == "source"
    assert classify_code_path(test, tmp_path) == "test"
    assert classify_code_path(example, tmp_path) == "example"

def test_discover_source_files_ignores_generated_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "def hello():\n    return 'hello'\n",
        encoding="utf-8",
    )

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text(
        "function ignored() {}\n",
        encoding="utf-8",
    )

    discovered = discover_source_files(str(tmp_path))
    relative = [path.relative_to(tmp_path).as_posix() for path in discovered]

    assert relative == ["src/main.py"]

def test_tests_are_excluded_from_hotspots_by_default(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    (tmp_path / "src" / "main.py").write_text(
        """
def source_function(values):
    for value in values:
        if value:
            return value
    return None
""".lstrip(),
        encoding="utf-8",
    )

    (tmp_path / "tests" / "test_main.py").write_text(
        """
def test_complex():
    for first in range(3):
        for second in range(3):
            if first == second:
                assert first == second
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_workspace(str(tmp_path))

    names = [item.symbol_name for item in result.hotspots]
    assert "source_function" in names
    assert "test_complex" not in names
    assert result.category_counts.source == 1
    assert result.category_counts.test == 1

def test_include_tests_adds_test_hotspots(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text(
        """
def test_complex():
    for value in range(3):
        if value:
            assert value
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_workspace(str(tmp_path), include_tests=True)

    assert result.hotspots[0].category == "test"
    assert result.hotspots[0].reasons == [
        "조건 분기 1개",
        "반복문 1개",
    ]
