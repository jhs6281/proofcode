# ProofCode 개발환경 1단계

## 필요한 프로그램

- Python 3.11 이상
- Node.js LTS
- VS Code
- Git

## 1. 파일 복사

이 압축 파일의 내용을 ProofCode 저장소 루트에 복사합니다.

기존 `README.md`와 `docs/`는 그대로 유지합니다.

## 2. Python Core 초기화

PowerShell:

```powershell
cd core
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
python -m proofcode_core ping
cd ..
```

`py -3.11`이 동작하지 않으면 아래 명령을 사용합니다.

```powershell
python -m venv .venv
```

## 3. VS Code Extension 초기화

```powershell
cd extension
npm install
npm run compile
npm run test:connection
cd ..
```

## 4. VS Code에서 실제 연결 확인

1. VS Code에서 `extension` 폴더만 엽니다.
2. `F5`를 누릅니다.
3. 새 창이 열리면 그 창에서 ProofCode 저장소 루트를 엽니다.
4. `Ctrl + Shift + P`
5. `ProofCode: Ping Core`
6. 오른쪽 아래에 다음 메시지가 보이면 성공입니다.

```text
ProofCode Core is running (protocol 0.1)
```

## 5. Git 반영

```powershell
git add .
git commit -m "chore: initialize core and VS Code extension"
git push
```

## 현재 연결 구조

```text
VS Code Extension
        |
        | Python child process + JSON
        v
ProofCode Core
```

현재는 가장 단순하고 문제를 찾기 쉬운 연결 방식입니다. 이후 분석 작업이 길어지면 JSON-RPC 또는 Local HTTP 구조로 발전시킬 수 있습니다.
