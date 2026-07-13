from pathlib import Path

from proofcode_core.analyzer import analyze_file
from proofcode_core.workspace import analyze_workspace


def test_function_evidence_records_call_names(
    tmp_path: Path,
) -> None:
    source = tmp_path / "service.py"
    source.write_text(
        """
def process(values):
    for value in values:
        if value > 0:
            result = normalize(value)
            if result:
                return result
    raise ValueError("not found")
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_file(str(source))
    symbol = result.structure.functions[0]

    assert symbol.evidence is not None
    assert symbol.evidence.return_count == 1
    assert symbol.evidence.call_count == 2
    assert symbol.evidence.call_names == [
        "normalize",
        "ValueError",
    ]
    assert symbol.evidence.raise_count == 1
    assert symbol.evidence.max_nesting_depth == 3


def test_nested_function_evidence_is_not_added_to_parent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "nested.py"
    source.write_text(
        """
def outer():
    def inner(value):
        if value:
            return helper(value)
        return None

    return inner
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_file(str(source))
    outer = next(
        item
        for item in result.structure.functions
        if item.name == "outer"
    )
    inner = next(
        item
        for item in result.structure.functions
        if item.name == "inner"
    )

    assert outer.complexity == 1
    assert outer.evidence is not None
    assert outer.evidence.call_count == 0
    assert outer.evidence.return_count == 1

    assert inner.complexity == 2
    assert inner.evidence is not None
    assert inner.evidence.call_names == ["helper"]


def test_workspace_hotspot_contains_file_hash(
    tmp_path: Path,
) -> None:
    source = tmp_path / "main.py"
    source.write_text(
        """
def choose(value):
    if value:
        return helper(value)
    return None
""".lstrip(),
        encoding="utf-8",
    )

    result = analyze_workspace(str(tmp_path))
    hotspot = result.hotspots[0]

    assert len(hotspot.file_sha256) == 64
    assert hotspot.evidence.return_count == 2
    assert hotspot.evidence.call_names == ["helper"]
