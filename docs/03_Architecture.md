# ProofCode Architecture

## 1. Architectural Goal

ProofCode는 AI Provider, 분석 대상 언어, 벤치마크 도구, UI를 서로
분리한다. 핵심 검증 엔진은 특정 AI에 종속되지 않아야 한다.

## 2. High-Level Architecture

``` text
VS Code Extension (TypeScript)
        |
        | JSON-RPC / Local HTTP / Process IPC (초기 구현에서 결정)
        v
ProofCode Core (Python)
        |
        +-- Project Scanner
        +-- Context Builder
        +-- Proposal Orchestrator
        +-- Evidence Engine
        +-- Validation Engine
        +-- Replay Store
        |
        +-- Provider Interface
        |      +-- OpenAI Adapter
        |      +-- Anthropic Adapter
        |      +-- Gemini Adapter
        |      +-- Local Model Adapter
        |
        +-- Language Plugin Interface
        |
        +-- Benchmark Plugin Interface
        |
        +-- Git Safety Layer
```

## 3. Core Components

### Project Scanner

책임:

-   프로젝트 구조 파악
-   언어 및 빌드 시스템 감지
-   제외 경로 처리
-   파일 크기 및 범위 제한
-   관련 파일 후보 생성

Project Scanner는 AI 판단과 독립적으로 동작해야 한다.

### Context Builder

책임:

-   분석 대상 코드 주변의 관련 Context 선택
-   의존 관계 기반 파일 선택
-   토큰 예산 관리
-   Secret 제외 정책 적용
-   Provider에 전달할 구조화된 입력 생성

### Proposal Orchestrator

책임:

-   Provider 호출
-   Proposal Schema 검증
-   여러 Provider 결과 정규화
-   Patch 후보와 설명 분리
-   검증 가능한 가설 생성

### Validation Engine

검증 순서의 기본 원칙:

1.  후보 Patch 구문/형식 확인
2.  격리 환경 적용
3.  Build 또는 Syntax Check
4.  기존 Test 실행
5.  기능 동등성 검증 가능 여부 확인
6.  Benchmark 실행
7.  Resource Metrics 수집
8.  Evidence 생성

### Evidence Engine

AI의 설명과 실제 측정 결과를 구분한다.

Evidence 예시:

-   proposal_id
-   source_revision
-   target_scope
-   provider
-   model
-   prompt_version
-   build_result
-   test_result
-   benchmark_result
-   resource_result
-   static_analysis_result
-   environment
-   verdict
-   confidence_inputs

신뢰도는 임의의 AI 숫자가 아니라 명시된 계산 규칙과 Evidence 완성도에
기반해야 한다.

### Replay Store

저장 대상:

-   Source revision
-   Patch
-   Provider와 Model 정보
-   Prompt version
-   Parameters
-   실행 환경
-   Dependency lock 정보
-   Test command/result
-   Benchmark command/result
-   Timestamp
-   Tool version

완전한 bit-for-bit 재현은 환경에 따라 어려울 수 있으므로, 재현성 수준을
등급으로 표현하는 방안을 검토한다.

## 4. VS Code Extension Responsibilities

Extension은 무거운 분석 로직을 갖지 않는다.

책임:

-   Command 등록
-   대상 파일/함수 선택
-   Core 호출
-   진행 상태 표시
-   Evidence View
-   Diff View
-   Test/Benchmark 결과 표시
-   Apply/Hold/Reject 사용자 액션
-   설정 관리

## 5. Isolation Strategy

후보 코드는 원본 작업 트리에 직접 적용하지 않는다.

초기 후보:

-   Temporary copy
-   Git worktree
-   Container sandbox

MVP는 단순한 임시 작업 공간에서 시작할 수 있으나, 배포 수준에서는 실행
격리와 리소스 제한이 필요하다. 신뢰할 수 없는 프로젝트 코드 실행은 보안
위험이 있으므로 별도 Threat Model 문서를 추가해야 한다.

## 6. Plugin Boundaries

### Provider Plugin

AI 호출과 응답 정규화를 담당한다. 검증 결과를 조작하거나 최종 Verdict를
직접 결정하지 않는다.

### Language Plugin

언어 감지, 코드 구조 정보, Build/Test 명령 탐지, 언어별 Context 수집을
담당한다.

### Benchmark Plugin

언어별 Benchmark 실행, 측정 결과 수집, 결과 정규화를 담당한다.

## 7. Data Flow

``` text
User selects scope
  -> Scan project
  -> Build context
  -> Ask provider for proposal
  -> Validate proposal schema
  -> Create isolated workspace
  -> Apply candidate patch
  -> Build/Syntax check
  -> Run existing tests
  -> Run benchmark
  -> Collect resource metrics
  -> Build evidence
  -> Present verdict and details
  -> User decides
```

## 8. Security Considerations

필수 고려사항:

-   API Key를 저장소에 기록하지 않는다.
-   VS Code SecretStorage 또는 OS 보안 저장소 사용을 검토한다.
-   분석 전 Secret 탐지/제외 정책을 제공한다.
-   외부 Provider 전송 범위를 사용자에게 보여준다.
-   프로젝트 코드를 실행할 때 격리와 제한을 둔다.
-   네트워크 접근 정책을 설계한다.
-   악성 Repository가 Core를 공격할 가능성을 고려한다.
-   Prompt Injection이 코드 주석이나 문서에 포함될 수 있음을 고려한다.

## 9. Architecture Decision Records

중요한 결정은 `docs/adr/`에 기록하는 방식을 권장한다.

예:

-   ADR-001: Extension-Core 통신 방식
-   ADR-002: 격리 실행 방식
-   ADR-003: Evidence Schema
-   ADR-004: Plugin Loading Model
-   ADR-005: Replay Storage Format
