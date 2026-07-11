# Contributing to ProofCode

ProofCode에 기여해 주셔서 감사합니다. 이 프로젝트는 AI 제안을 맹목적으로
적용하는 대신, 근거와 검증 결과를 개발자에게 제공하는 것을 목표로
합니다.

## Core Philosophy

모든 기여는 다음 원칙을 따라야 합니다.

1.  AI는 원본 코드를 자동으로 직접 변경하지 않는다.
2.  AI의 주장과 실측 Evidence를 구분한다.
3.  최종 적용 여부는 개발자가 결정한다.
4.  가능한 결과는 재현 가능해야 한다.
5.  특정 AI Provider에 Core가 종속되지 않도록 한다.
6.  큰 자동 변경보다 작고 검증 가능한 변경을 선호한다.

## Before Contributing

큰 기능을 구현하기 전에 Issue 또는 Discussion을 통해 문제와 접근 방법을
공유해 주세요. 특히 다음 변경은 설계 논의가 먼저 필요합니다.

-   Public API 변경
-   Plugin API 변경
-   Evidence Schema 변경
-   저장 형식 변경
-   실행 격리 모델 변경
-   새로운 보안 권한 요구

## Development Areas

기여 영역 예시:

-   Python Core
-   TypeScript VS Code Extension
-   Provider Adapter
-   Language Support
-   Benchmark Adapter
-   Documentation
-   Security Review
-   Test Fixtures
-   UX and Accessibility

## Pull Request Expectations

PR은 가능한 한 하나의 명확한 목적을 가져야 합니다.

포함 권장 항목:

-   해결하려는 문제
-   변경 내용
-   테스트 방법
-   사용자 영향
-   호환성 영향
-   보안 영향
-   스크린샷 또는 결과 예시(UI 변경 시)

## Testing

새 기능은 적절한 자동 테스트를 포함해야 합니다.

특히 Benchmark 관련 변경은 다음을 문서화해야 합니다.

-   측정 대상
-   워밍업 방식
-   반복 횟수
-   환경 의존성
-   결과 해석 제한

## AI-Generated Contributions

AI 도구를 사용한 기여를 금지하지 않는다. 그러나 제출자는 코드의 동작과
라이선스 적합성을 이해하고 검토할 책임이 있다.

AI가 생성했다는 이유만으로 검증을 생략할 수 없다.

## Security

취약점 가능성이 있는 내용은 공개 Issue 대신 프로젝트의 보안 신고 절차를
사용해야 한다. 정식 공개 전 `SECURITY.md`를 추가하고 신고 채널을
명시한다.

## Documentation

문서는 구현과 함께 갱신한다. Architecture에 영향을 주는 결정은 ADR
작성을 권장한다.

## Code of Conduct

커뮤니티 규모가 커지기 전에 `CODE_OF_CONDUCT.md`를 추가한다. 기술적 의견
충돌은 근거, 재현 가능한 실험, 테스트 결과를 중심으로 논의한다.

## License

프로젝트 License가 확정되면 모든 기여는 해당 License와 프로젝트의
Developer Certificate of Origin 또는 CLA 정책에 따라 처리한다. 초기
단계에서 DCO와 CLA 중 하나를 명시적으로 결정해야 한다.
