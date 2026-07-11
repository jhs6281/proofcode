# ProofCode

> **AI proposes. ProofCode verifies. Developers decide.**

ProofCode는 AI가 제안한 코드 변경을 개발자가 신뢰할 수 있도록, **재현 가능한 검증 결과와 객관적인 근거(Evidence)**를 제공하는 오픈소스 Developer Trust Platform입니다.

AI는 변경 후보를 제안하고, ProofCode는 원본과 분리된 환경에서 빌드·테스트·벤치마크·자원 사용량을 검증합니다. 최종 적용 여부는 항상 개발자가 결정합니다.

> **현재 상태:** Concept / Foundation  
> 현재 저장소는 구현 전 설계 단계이며, 실행 가능한 Core Engine과 VS Code Extension은 아직 포함되어 있지 않습니다.

## Core Philosophy

> AI는 코드를 변경하지 않는다.  
> AI는 근거를 제시하고 검증한다.  
> 최종 결정은 개발자가 한다.

ProofCode는 다음 원칙을 따릅니다.

- AI의 설명과 실제 측정 결과를 구분합니다.
- 원본 코드는 사용자 승인 없이 직접 수정하지 않습니다.
- 프로젝트 전체를 분석하되, 변경 제안과 검증은 작은 단위로 수행합니다.
- 모든 분석 결과는 가능한 범위에서 재현 가능해야 합니다.
- 특정 AI 모델이나 Provider에 종속되지 않는 구조를 지향합니다.
- 성능 향상만이 아니라 테스트 결과, 자원 사용량, 복잡도와 유지보수 위험도 함께 확인합니다.

## Why ProofCode?

ChatGPT, Claude, Copilot 같은 AI 도구는 코드를 빠르게 생성하고 리팩토링 방안을 제안할 수 있습니다. 그러나 제안된 변경이 실제 환경에서도 더 나은지는 별도의 검증이 필요합니다.

ProofCode는 다음 질문에 Evidence로 답하는 것을 목표로 합니다.

> **“AI가 제안한 변경이 실제로 더 나은가?”**

검증 대상은 다음과 같습니다.

- 기존 테스트 통과 여부
- 실행 시간과 반복 측정 결과
- 메모리 및 CPU 사용량
- 기존 동작 유지 여부
- 변경 범위와 복잡도 변화
- 유지보수 위험 신호
- 분석 환경과 재현 정보

## How It Works

```text
개발자가 분석 범위 선택
        ↓
프로젝트 구조와 관련 Context 수집
        ↓
AI Provider가 변경 후보와 근거 제안
        ↓
원본과 분리된 환경에 후보 Patch 적용
        ↓
Build / Test / Benchmark / Resource 검증
        ↓
Diff와 Evidence 결과 제공
        ↓
개발자가 Apply / Hold / Reject 결정
```

## Planned Architecture

```text
VS Code Extension (TypeScript)
        |
        | Local IPC / JSON-RPC / Local HTTP
        v
ProofCode Core (Python)
        |
        +-- Project Scanner
        +-- Context Builder
        +-- Proposal Orchestrator
        +-- Validation Engine
        +-- Evidence Engine
        +-- Replay Store
        +-- Git Safety Layer
        |
        +-- Provider Interface
        +-- Language Plugin Interface
        +-- Benchmark Plugin Interface
```

### Main Components

| Component | Responsibility |
| --- | --- |
| VS Code Extension | 분석 대상 선택, 진행 상태 표시, Diff와 Evidence 확인, 사용자 결정 |
| Python Core | 전체 분석 흐름 조정, 후보 검증, Evidence 생성 |
| Provider Interface | OpenAI, Anthropic, Gemini, Local Model 등의 응답 형식 정규화 |
| Language Plugin | 언어 감지, 프로젝트 탐색, Build/Test 명령 및 Context 수집 |
| Benchmark Plugin | Baseline과 Candidate 반복 측정 및 결과 정규화 |
| Git Safety Layer | 원본 보호, 격리 작업 공간과 안전한 Patch 관리 |

## MVP Scope

첫 번째 목표는 기능을 넓게 만드는 것이 아니라, **AI 제안 하나를 실제 실행 결과로 검증하는 전체 흐름**을 완성하는 것입니다.

MVP에서는 다음 흐름을 구현할 예정입니다.

1. VS Code에서 파일 또는 함수 선택
2. TypeScript Extension에서 Python Core 호출
3. 단일 AI Provider를 통한 개선 후보 생성
4. 격리된 작업 공간에서 후보 Patch 검증
5. 기존 테스트와 간단한 벤치마크 실행
6. Diff와 Evidence를 VS Code 결과 화면에 표시

초기 버전에서는 다음 기능을 범위에서 제외합니다.

- 프로젝트 전체 자동 리팩토링
- 사용자 승인 없는 코드 적용
- 다중 AI 경쟁 및 AI Court
- DB 최적화
- 전체 보안 분석
- 모든 언어 동시 지원

## Documentation

| Document | Description |
| --- | --- |
| [Vision](docs/00_Vision.md) | 프로젝트의 미션, 문제 정의, 핵심 철학 |
| [Initial Proposal](docs/01_Proposal_v0.1.md) | 초기 아이디어와 방향 전환, 주요 위험 및 대응 |
| [Roadmap](docs/02_Roadmap.md) | Foundation부터 Multi-AI Verification까지의 단계별 계획 |
| [Architecture](docs/03_Architecture.md) | Core, Extension, Plugin, 격리 및 데이터 흐름 설계 |
| [API Draft](docs/04_API.md) | VS Code Extension과 Python Core 사이의 논리 API 초안 |
| [Plugin SDK Draft](docs/05_PluginSDK.md) | Provider, Language, Benchmark Plugin 인터페이스 방향 |
| [Contributing](docs/06_Contributing.md) | 기여 원칙, PR 기준, 테스트 및 보안 지침 |
| [Changelog](docs/07_Changelog.md) | 프로젝트 주요 결정과 변경 이력 |

## Roadmap Overview

- **Phase 0 — Foundation:** 저장소 구조, 문서, 개발 환경, CI 기반 확립
- **Phase 1 — First Proof:** 하나의 AI 변경 제안을 테스트와 벤치마크로 검증
- **Phase 2 — Evidence Engine:** 반복 측정, 통계, 환경 정보, Replay 지원
- **Phase 3 — Safety:** Git 기반 원본 보호와 Apply / Hold / Reject 흐름
- **Phase 4 — Plugin Platform:** Provider, Language, Benchmark SDK 확장
- **Phase 5 — Multi-AI Verification:** 여러 AI 제안을 동일 조건에서 비교
- **Phase 6 — Advanced Analysis:** CI, DB Query, Local LLM, 조직 정책 등 확장

자세한 내용은 [Roadmap](docs/02_Roadmap.md)을 참고하세요.

## Contributing

ProofCode는 초기 설계 단계이며, 다음 영역의 기여를 환영합니다.

- Python Core Engine
- TypeScript VS Code Extension
- Provider Adapter
- Language 및 Benchmark Plugin
- 테스트 Fixture와 문서화
- 보안, 격리 실행, UX 검토

큰 기능이나 Public API 변경을 구현하기 전에는 Issue 또는 Discussion에서 문제와 접근 방식을 먼저 공유해 주세요.

기여 전 [Contributing Guide](docs/06_Contributing.md)를 확인해 주세요.

## Security

ProofCode는 외부 AI Provider에 코드가 전달될 가능성과 로컬 프로젝트 코드를 실행하는 과정의 위험을 중요하게 다룹니다.

향후 다음 보호 기능을 설계할 예정입니다.

- Secret 및 민감 정보 탐지·제외
- 외부 Provider 전송 범위 표시
- 격리 실행과 리소스 제한
- 네트워크 접근 정책
- 악성 저장소와 Prompt Injection 대응
- 안전한 API Key 저장

보안 신고 절차는 정식 공개 전에 `SECURITY.md`로 추가할 예정입니다.

## License

라이선스는 아직 결정되지 않았습니다. 외부 기여를 본격적으로 받기 전에 오픈소스 라이선스와 DCO/CLA 정책을 확정할 예정입니다.

---

**ProofCode** — AI가 제안하고, ProofCode가 검증하며, 개발자가 결정합니다.
