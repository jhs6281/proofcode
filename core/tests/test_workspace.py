from pathlib import Path

from proofcode_core.workspace import analyze_workspace, discover_source_files

def test_discover_source_files_ignores_generated_directories(tmp_path: Path) -> None:
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

def test_analyze_workspace_returns_hotspots(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        """
def easy(value):
    return value

def complex_function(values):
    total = 0
    for value in values:
        if value > 0:
            total += value
    if total > 100:
        return total
    return 0
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_workspace(str(tmp_path), hotspot_limit=5)

    assert result.scanned_files == 1
    assert result.total_functions == 2
    assert result.hotspots[0].symbol_name == "complex_function"
    assert result.hotspots[0].complexity == 4

def test_hotspot_limit(tmp_path: Path) -> None:
    source = tmp_path / "many.py"
    source.write_text(
        """
def one():
    return 1

def two():
    return 2

def three():
    return 3
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_workspace(str(tmp_path), hotspot_limit=2)
    assert len(result.hotspots) == 2
