$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$coreSrc = Join-Path $repoRoot "core\src"

$env:PYTHONPATH = if ($env:PYTHONPATH) {
    "$coreSrc;$env:PYTHONPATH"
} else {
    $coreSrc
}

python -m proofcode_core ping
