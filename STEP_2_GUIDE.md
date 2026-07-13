# ProofCode 2단계 — 현재 파일 분석

## 목표

```text
VS Code에서 파일 열기
        ↓
Analyze Current File 실행
        ↓
TypeScript가 파일 경로 전달
        ↓
Python Core가 파일 읽기
        ↓
JSON 분석 결과 반환
        ↓
VS Code가 결과 표시
```

## 적용

압축 파일의 내용을 ProofCode 저장소 루트에 덮어씁니다.

## Python 테스트

```powershell
cd core
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
python -m proofcode_core analyze-file .\src\proofcode_core\cli.py
```

## Extension 컴파일

```powershell
cd ..\extension
npm install
npm run compile
```

## VS Code 실행

1. VS Code에서 `extension` 폴더를 엽니다.
2. `F5`를 누릅니다.
3. 새 창에서 ProofCode 저장소 루트를 엽니다.
4. 분석할 `.py`, `.js`, `.ts`, `.java` 파일을 엽니다.
5. `Ctrl + Shift + P`
6. `ProofCode: Analyze Current File`
7. 오른쪽 Markdown 결과를 확인합니다.

## 현재 분석 항목

- 파일 이름
- 언어
- 파일 크기
- 전체 줄 수
- 빈 줄 수
- 내용이 있는 줄 수
- SHA-256 해시

SHA-256은 파일 내용이 달라졌는지 확인하는 고유 지문처럼 사용합니다.
