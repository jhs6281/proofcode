# Changelog

이 문서는 ProofCode의 주요 변경 이력을 기록한다.

형식은 Keep a Changelog의 개념을 참고하되, 초기 개발 단계에서는 프로젝트
상황에 맞게 간단히 유지한다.

## \[Unreleased\]

### Added

-   프로젝트 핵심 철학 정의
-   Developer Trust Platform 방향 확정
-   Evidence 기반 검증 개념 정의
-   VS Code Extension을 주요 UI로 결정
-   Python Core Engine 방향 결정
-   TypeScript Extension 방향 결정
-   Provider, Language, Benchmark Plugin 개념 정의
-   Replay 개념 추가
-   Explain Why Not 개념 추가
-   AI Court 개념 추가
-   Discord를 메인 UI가 아닌 선택적 알림 채널로 재정의
-   초기 문서 세트 생성

### Changed

-   초기 "AI 리팩토링 도구" 개념에서 "AI 제안 검증 플랫폼"으로 방향 변경
-   프로젝트 전체 자동 수정 방식에서 전체 분석 + 작은 단위 제안/검증
    방식으로 변경
-   AI 기반 점수 산정에서 Engine Evidence 중심 판정 방식으로 변경
-   단일 AI 중심 구조에서 Provider 추상화 방향으로 변경

### Security

-   원본 코드 직접 수정 금지 원칙 정의
-   외부 Provider 코드 전송 위험 식별
-   Local Provider 지원 방향 정의
-   격리 실행 필요성 식별
-   Secret 탐지 및 제외 정책 필요성 식별
-   악성 Repository 및 Prompt Injection 위험을 Architecture 고려사항에
    추가

## \[0.1.0-concept\] - 2026-07-11

### Added

-   ProofCode 초기 구상
-   핵심 문장 확정:
    -   AI는 코드를 변경하지 않는다.
    -   AI는 근거를 제시하고 검증한다.
    -   최종 결정은 개발자가 한다.
-   Slogan:
    -   AI proposes.
    -   ProofCode verifies.
    -   Developers decide.
