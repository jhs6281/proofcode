from pathlib import Path

from proofcode_core.analyzer import analyze_file
from proofcode_core.workspace import analyze_workspace

def test_function_evidence_is_collected(tmp_path: Path) -> None:
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
    assert symbol.evidence.call_count == 3
    assert symbol.evidence.raise_count == 1
    assert symbol.evidence.max_nesting_depth == 3

def test_workspace_hotspot_contains_evidence(tmp_path: Path) -> None:
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

    assert hotspot.evidence.return_count == 2
    assert hotspot.evidence.call_count == 1
    assert hotspot.evidence.max_nesting_depth == 1
