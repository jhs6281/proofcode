# ProofCode Core

Python 기반 ProofCode 검증 엔진입니다.

## 개발 환경

Windows PowerShell 기준:

```powershell
cd core
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## 실행 확인

```powershell
python -m proofcode_core ping
```

예상 결과:

```json
{"status": "ok", "message": "ProofCode Core is running", "protocol_version": "0.1"}
```

## 테스트

```powershell
pytest
```
