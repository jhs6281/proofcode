# ProofCode Roadmap

## 원칙

Roadmap은 기능 수를 늘리는 계획이 아니라, 신뢰 가능한 검증 흐름을
단계적으로 완성하는 계획이다. 각 단계는 독립적으로 실행 가능하고 데모
가능해야 한다.

## Phase 0 --- Foundation

목표: 오픈소스 프로젝트 기반 확립.

-   저장소 구조 확정
-   Vision, Proposal, Architecture 문서 작성
-   License 결정
-   Contributing 규칙 작성
-   Issue/PR Template 설계
-   Python Core와 TypeScript Extension 개발 환경 구성
-   CI 기본 구성
-   코드 스타일과 테스트 규칙 정의

완료 조건: 새 기여자가 문서를 읽고 개발 환경을 실행할 수 있다.

## Phase 1 --- First Proof (MVP)

목표: AI 제안 하나를 실제 실행으로 검증한다.

-   VS Code 명령 등록
-   현재 파일 또는 함수 선택
-   Extension → Core 요청
-   프로젝트/코드 Context 수집
-   단일 Provider 연결
-   구조화된 Proposal 생성
-   격리 작업 디렉터리 생성
-   Patch 후보 적용
-   기존 테스트 실행
-   간단한 벤치마크 실행
-   원본과 후보 결과 비교
-   VS Code 결과 패널 표시

완료 조건: 사용자가 하나의 변경 제안에 대해 Diff, 테스트 결과, 성능
비교를 확인할 수 있다.

## Phase 2 --- Evidence Engine

목표: 결과를 신뢰할 수 있는 형태로 만든다.

-   반복 측정
-   워밍업 정책
-   통계 요약
-   환경 메타데이터 저장
-   메모리/CPU 측정
-   Evidence Schema 확정
-   실패 이유 분류
-   Explain Why Not
-   결과 저장 및 조회

완료 조건: 같은 조건에서 재실행 가능한 분석 기록이 생성된다.

## Phase 3 --- Safety and Developer Control

목표: 개발자가 항상 통제권을 유지하도록 한다.

-   변경 단위 제한
-   Patch 검증
-   Git Diff 연동
-   안전한 임시 Branch 또는 Worktree 전략 검토 및 구현
-   Apply / Hold / Reject 흐름
-   위험도 표시
-   대규모 변경 차단 정책
-   테스트 실패 시 적용 차단

완료 조건: 원본 보호와 명시적 사용자 승인 흐름이 보장된다.

## Phase 4 --- Plugin Platform

목표: 특정 모델과 언어에 종속되지 않는 플랫폼을 만든다.

-   Provider SDK
-   Language Plugin SDK
-   Benchmark Plugin SDK
-   Plugin manifest
-   Plugin version compatibility
-   Plugin validation
-   예제 Plugin 제공

초기 우선순위:

1.  Python 분석 대상
2.  JavaScript/TypeScript 분석 대상
3.  Java 분석 대상
4.  추가 언어는 기여 기반 확장

## Phase 5 --- Multi-AI Verification

목표: 여러 AI의 제안을 동일 조건에서 비교한다.

-   복수 Provider 실행
-   동일 입력 조건 관리
-   Proposal normalization
-   동일 검증 환경 사용
-   AI Court 비교 화면
-   비용 및 토큰 사용량 표시

완료 조건: 여러 AI의 제안을 동일한 Evidence 기준으로 비교할 수 있다.

## Phase 6 --- Advanced Analysis

후보 기능:

-   프로젝트 수준 병목 후보 우선순위화
-   DB Query 분석 모듈
-   데이터 크기별 Benchmark Profile
-   회귀 성능 탐지
-   CI 연동
-   Pull Request 검증
-   Local LLM Provider
-   Secret/PII 제외 정책
-   조직 정책 파일

## Non-Goals for Early Versions

초기 버전에서 하지 않는다.

-   프로젝트 전체 자동 리팩토링
-   사용자 승인 없는 원본 수정
-   AI 설명만으로 점수 계산
-   모든 언어 동시 지원
-   모든 코드 품질 영역 동시 지원
-   DB, 보안, 성능, 동시성 분석을 한 번에 완성
