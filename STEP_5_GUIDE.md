# ProofCode 5단계 — 코드 분류와 Hotspot 이동

## 이번 단계 목표

```text
프로젝트 전체 분석
        ↓
제품 / 테스트 / 예제 코드 분류
        ↓
복잡도 근거 표시
        ↓
Hotspot 선택
        ↓
해당 파일과 줄로 이동
```

## 1. 파일 적용

압축 파일 내용을 ProofCode 저장소 루트에 덮어씁니다.

## 2. Python 테스트

```powershell
cd core
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## 3. 터미널 분석

기본값은 테스트와 예제 코드를 Hotspot 순위에서 제외합니다.

```powershell
python -m proofcode_core analyze-workspace ..
```

테스트 코드까지 포함:

```powershell
python -m proofcode_core analyze-workspace .. --include-tests
```

테스트와 예제 모두 포함:

```powershell
python -m proofcode_core analyze-workspace .. --include-tests --include-examples
```

## 4. Extension 컴파일

```powershell
cd ..\extension
npm install
npm run compile
```

## 5. VS Code에서 실행

1. `extension` 폴더를 연 창에서 `F5`
2. 새 창에서 ProofCode 저장소 루트 열기
3. `Ctrl + Shift + P`
4. `ProofCode: Analyze Workspace`
5. 분석 결과에서 분류와 근거 확인
6. 다시 `Ctrl + Shift + P`
7. `ProofCode: Open Hotspot`
8. 목록에서 함수를 선택
9. 해당 파일과 줄이 선택되는지 확인

## 6. 설정 변경

VS Code 설정에서 `ProofCode`를 검색합니다.

- `Proofcode: Include Tests`
- `Proofcode: Include Examples`

기본값은 둘 다 꺼져 있습니다.

## 7. 이번 단계에서 배우는 것

### 코드 분류

파일 경로를 기준으로 다음처럼 구분합니다.

- `source`: 제품 코드
- `test`: 테스트 코드
- `example`: 예제 또는 Fixture

완벽한 분류는 아니지만, 단순히 모든 파일을 같은 중요도로 다루는 것보다 안전합니다.

### 복잡도 근거

이제 숫자만 표시하지 않고 왜 복잡도가 올라갔는지 보여줍니다.

예:

```text
조건 분기 3개
반복문 2개
예외 처리 분기 1개
함수 길이 45줄
```

### Quick Pick

VS Code 위쪽에 선택 목록을 보여주는 기능입니다.

사용자는 Hotspot을 선택하고 바로 코드 위치로 이동할 수 있습니다.
