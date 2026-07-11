# ProofCode Plugin SDK --- Draft

## 1. 목표

ProofCode는 특정 AI, 특정 언어, 특정 벤치마크 도구에 종속되지 않는다.
외부 기여자가 Core를 수정하지 않고도 기능을 확장할 수 있어야 한다.

## 2. Plugin Types

### Provider Plugin

역할:

-   AI Provider 인증
-   요청 변환
-   모델 호출
-   응답 파싱
-   Proposal Schema 변환
-   사용량/비용 메타데이터 제공

금지:

-   Core Verdict 직접 결정
-   테스트 결과 위조 또는 수정
-   원본 코드 직접 변경

### Language Plugin

역할:

-   언어 감지
-   프로젝트 파일 탐색
-   Build/Test 명령 탐지
-   코드 구조 추출
-   관련 Context 후보 제공
-   언어별 안전 규칙 제공

### Benchmark Plugin

역할:

-   Benchmark 환경 준비
-   Baseline과 Candidate 실행
-   반복 측정
-   결과 정규화
-   환경 정보 수집

## 3. Proposed Manifest

``` yaml
name: proofcode-python
type: language
version: 0.1.0
api_version: 1
entrypoint: proofcode_python.plugin:PythonLanguagePlugin
capabilities:
  - detect
  - context
  - test
```

## 4. Provider Interface Draft

``` python
from typing import Protocol

class ProviderPlugin(Protocol):
    @property
    def name(self) -> str:
        ...

    def healthcheck(self) -> bool:
        ...

    def propose(self, request):
        ...
```

## 5. Language Interface Draft

``` python
class LanguagePlugin(Protocol):
    def detect(self, workspace):
        ...

    def scan(self, workspace):
        ...

    def build_context(self, scope, budget):
        ...

    def discover_test_command(self, workspace):
        ...
```

## 6. Benchmark Interface Draft

``` python
class BenchmarkPlugin(Protocol):
    def supports(self, project):
        ...

    def prepare(self, workspace, scenario):
        ...

    def run(self, workspace, scenario):
        ...

    def normalize(self, raw_result):
        ...
```

## 7. Plugin Quality Requirements

공식 Plugin으로 포함되기 위한 기본 기준:

-   자동 테스트
-   문서
-   최소 예제
-   지원 버전 명시
-   실패 시 명확한 오류
-   Secret 로그 출력 금지
-   Core API Version 호환성 명시
-   Benchmark의 측정 방법 문서화

## 8. Plugin Safety

Plugin은 높은 권한을 가질 수 있으므로 다음을 검토한다.

-   서명 또는 신뢰 레벨
-   공식/커뮤니티 Plugin 구분
-   실행 권한 명시
-   네트워크 접근 여부 표시
-   파일 시스템 접근 범위 표시
-   Plugin 설치 전 권한 안내

## 9. Contribution Path

새 언어 지원 예시:

1.  Plugin Template 복제
2.  Manifest 작성
3.  Detect 구현
4.  Scan/Context 구현
5.  Test discovery 구현
6.  Benchmark Adapter 연결
7.  Fixture Project 추가
8.  Integration Test 작성
9.  문서 작성
10. Pull Request 제출

## 10. Initial SDK Priority

MVP에서는 완전한 외부 Plugin Runtime을 먼저 만들지 않는다. Core 내부
Interface를 안정화한 후, 실제 두 개 이상의 구현체가 필요해지는 시점에
Public Plugin SDK를 확정한다.

이는 지나친 초기 추상화를 방지하기 위한 원칙이다.
