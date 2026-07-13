# ProofCode 4단계 — 프로젝트 전체 분석

## 이번 단계 목표

```text
프로젝트 폴더
    ↓
소스 파일 찾기
    ↓
제외 폴더 무시
    ↓
Python 함수와 클래스 분석
    ↓
복잡도가 높은 함수 순위 생성
    ↓
VS Code 결과 표시
```

## 제외 폴더

`.git`, `.venv`, `node_modules`, `out`, `dist`, `build`, `__pycache__`

## 적용

압축 파일 내용을 ProofCode 저장소 루트에 덮어씁니다.

## 테스트

```powershell
cd core
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
python -m proofcode_core analyze-workspace ..
```

## Extension 컴파일

```powershell
cd ..\extension
npm install
npm run compile
```

## VS Code 실행

1. `extension` 폴더를 연 VS Code에서 `F5`
2. 새 창에서 ProofCode 저장소 루트 열기
3. `Ctrl + Shift + P`
4. `ProofCode: Analyze Workspace`
5. 오른쪽 프로젝트 요약 확인

## Hotspot의 뜻

Hotspot은 문제가 확정된 코드가 아닙니다.

조건문, 반복문, 긴 함수처럼 먼저 검토할 가치가 있는 후보입니다.
