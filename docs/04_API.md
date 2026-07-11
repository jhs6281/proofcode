# ProofCode API Specification --- Draft

Status: Draft. 구현 전에 변경 가능하다.

## 1. 목적

VS Code Extension과 Python Core Engine 사이의 계약을 정의한다. 초기
구현에서는 Local HTTP, JSON-RPC, stdio 기반 IPC 중 하나를 Architecture
Decision Record로 결정한다.

이 문서는 전송 방식과 무관한 논리 API를 정의한다.

## 2. Analyze Request

`POST /v1/analyses`

Request:

``` json
{
  "workspace_path": "/project",
  "scope": {
    "type": "file",
    "path": "src/service/user_service.py"
  },
  "provider": "openai",
  "profile": "balanced",
  "options": {
    "run_tests": true,
    "run_benchmark": true,
    "collect_resources": true
  }
}
```

Response:

``` json
{
  "analysis_id": "anl_123",
  "status": "queued"
}
```

## 3. Analysis Status

`GET /v1/analyses/{analysis_id}`

Response:

``` json
{
  "analysis_id": "anl_123",
  "status": "running",
  "stage": "benchmark",
  "progress": 72
}
```

상태 후보:

-   queued
-   scanning
-   proposing
-   validating
-   testing
-   benchmarking
-   completed
-   failed
-   cancelled

## 4. Analysis Result

`GET /v1/analyses/{analysis_id}/result`

Response 개념:

``` json
{
  "analysis_id": "anl_123",
  "proposal": {
    "title": "Replace repeated linear membership lookup",
    "summary": "Use a set for repeated membership checks",
    "scope": "src/service/user_service.py",
    "risk": "low"
  },
  "evidence": {
    "build": {"passed": true},
    "tests": {"passed": 42, "failed": 0},
    "benchmark": {
      "baseline_ms": 151.2,
      "candidate_ms": 43.7,
      "iterations": 50
    },
    "resources": {
      "memory_delta_mb": 2.1
    }
  },
  "verdict": "recommended"
}
```

## 5. Diff

`GET /v1/analyses/{analysis_id}/diff`

반환값은 unified diff 또는 구조화된 hunk 목록을 지원할 수 있다.

## 6. User Decision

`POST /v1/analyses/{analysis_id}/decision`

Request:

``` json
{
  "decision": "hold",
  "note": "Review with team before applying"
}
```

지원 값:

-   apply
-   hold
-   reject

중요: `apply` 동작은 사용자 명시적 요청 이후에만 실행한다. 실제 적용
방식은 Git Safety Layer 정책을 따른다.

## 7. Replay

`POST /v1/analyses/{analysis_id}/replay`

Replay는 저장된 조건을 최대한 복원하여 재검증을 시도한다. 환경 차이가
존재하면 결과에 재현성 경고를 포함한다.

## 8. Provider API Contract

개념적 Python Interface:

``` python
class Provider:
    def propose(self, request: ProposalRequest) -> Proposal:
        ...
```

Provider 응답은 자유 텍스트가 아니라 검증 가능한 구조화 Schema로
정규화한다.

## 9. Error Model

``` json
{
  "error": {
    "code": "BENCHMARK_FAILED",
    "message": "Benchmark process exited with code 1",
    "details": {
      "stage": "benchmark"
    }
  }
}
```

초기 Error Code 후보:

-   INVALID_SCOPE
-   UNSUPPORTED_LANGUAGE
-   PROVIDER_ERROR
-   PROPOSAL_INVALID
-   PATCH_APPLY_FAILED
-   BUILD_FAILED
-   TEST_FAILED
-   BENCHMARK_FAILED
-   ISOLATION_FAILED
-   INTERNAL_ERROR

## 10. Versioning

-   Public API prefix: `/v1`
-   Plugin API는 Core API와 별도 버전 정책을 가진다.
-   Breaking change는 migration note와 deprecation period를 제공하는
    방향을 검토한다.
