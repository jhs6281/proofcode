# ProofCode VS Code Extension

VS Code와 Python Core를 연결하는 사용자 인터페이스입니다.

## 설치

```powershell
cd extension
npm install
npm run compile
```

## Core 연결 단독 테스트

저장소 루트의 Python을 찾을 수 있어야 합니다.

```powershell
npm run test:connection
```

Python 명령이 `python`이 아닌 경우:

```powershell
$env:PROOFCODE_PYTHON = "py"
npm run test:connection
```

## VS Code에서 실행

1. VS Code에서 `extension` 폴더를 엽니다.
2. `F5`를 누릅니다.
3. 새로 열린 Extension Development Host에서 ProofCode 저장소 루트를 엽니다.
4. `Ctrl+Shift+P`를 누릅니다.
5. `ProofCode: Ping Core`를 실행합니다.
6. `ProofCode Core is running` 알림을 확인합니다.
