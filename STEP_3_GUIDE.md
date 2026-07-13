# ProofCode 3단계 — Python 코드 구조 분석

## 목표

이번 단계에서는 Python의 AST를 사용해 실제 코드 구조를 읽습니다.

```text
Python 파일
    ↓
AST 변환
    ↓
클래스와 함수 검색
    ↓
줄 수와 복잡도 계산
    ↓
VS Code 결과 표시
```

## 새로 분석하는 항목

- 클래스 이름
- 함수와 메서드 이름
- 시작 줄과 끝 줄
- 함수 길이
- 매개변수
- 간단한 복잡도

## 1. 파일 적용

압축 파일을 ProofCode 저장소 루트에 덮어씁니다.

## 2. Python 테스트

```powershell
cd core
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## 3. 직접 분석

```powershell
python -m proofcode_core analyze-file .\tests\fixtures\sample_complexity.py
```

JSON 안에 `structure`, `classes`, `functions`가 나오면 성공입니다.

## 4. Extension 컴파일

```powershell
cd ..\extension
npm run compile
```

## 5. VS Code에서 확인

1. `extension` 폴더를 연 상태에서 `F5`
2. 새 창에서 ProofCode 저장소 루트 열기
3. `core/tests/fixtures/sample_complexity.py` 열기
4. `Ctrl + Shift + P`
5. `ProofCode: Analyze Current File`
6. 오른쪽 결과에서 클래스, 함수, 복잡도 확인

## 복잡도란?

복잡도는 코드가 얼마나 많은 갈림길을 갖는지 보여주는 숫자입니다.

```python
def hello():
    return "hello"
```

복잡도는 보통 1입니다.

```python
def choose(value):
    if value > 10:
        return "large"
    return "small"
```

`if`라는 갈림길이 하나 생겨 복잡도는 2가 됩니다.

복잡도가 높다고 무조건 나쁜 코드는 아닙니다. 다만 테스트와 유지보수가 어려워질 가능성이 높아집니다.

## 왜 Python만 먼저 지원하나?

언어마다 코드를 읽는 방법이 다르기 때문입니다.

- Python: 내장 `ast` 모듈
- JavaScript/TypeScript: TypeScript Compiler API 또는 별도 Parser
- Java: Java Parser 필요

한 번에 모두 만들면 구조를 이해하기 어렵습니다. 먼저 Python Plugin의 원형을 만든 뒤, 같은 규칙으로 JavaScript/TypeScript 분석기를 추가합니다.
