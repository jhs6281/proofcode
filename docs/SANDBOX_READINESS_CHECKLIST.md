# ProofCode Container Sandbox Readiness Checklist

Step 12에서는 **코드 구현 상태**와 **사용자 컴퓨터에서의 실제 실행 검증 상태**를 분리합니다.

- `[x]` 코드로 구현됨
- `[ ]` 사용자 환경에서 실제 검증 필요

## 코드 구현 체크

- [x] 컨테이너 내부 실행
- [x] 네트워크 접근 제한 (`--network none`)
- [x] CPU 사용 제한 (`--cpus`)
- [x] 메모리 사용 제한 (`--memory`, 동일한 `--memory-swap`)
- [x] 실행 시간 제한과 강제 종료
- [x] 원본 Workspace 미마운트
- [x] 임시 Workspace만 쓰기 가능
- [x] Root filesystem 읽기 전용
- [x] Linux capability 전체 제거
- [x] 권한 상승 차단 (`no-new-privileges`)
- [x] PID 개수 제한
- [x] 컨테이너 삭제 후 존재 여부 확인
- [x] 임시 폴더 삭제 후 존재 여부 확인
- [x] stdout, stderr, exit code 기록
- [x] timeout, OOMKilled, container error 기록
- [x] image ID와 repo digest 기록
- [x] 실패 시 AI 실행 파이프라인 차단

## 사용자 환경 실행 체크

아래 항목은 실제 컴퓨터에서 `ProofCode: Verify Container Sandbox`를 실행한 뒤 확인합니다.

- [ ] Docker CLI 감지
- [ ] Docker daemon 연결
- [ ] ProofCode Sandbox image 감지
- [ ] 컨테이너 생성 성공
- [ ] 네트워크 `none` 적용
- [ ] CPU 1.0 제한 적용
- [ ] 메모리 512MB 제한 적용
- [ ] 실행 timeout 60초 적용
- [ ] 원본 Workspace 변경 없음
- [ ] Sandbox 소스 변경 없음
- [ ] OOMKilled와 종료 원인 확인
- [ ] 컨테이너 삭제 확인
- [ ] 임시 폴더 삭제 확인
- [ ] Sandbox Evidence JSON 저장
- [ ] 전체 판정 `passed`

## 통과 조건

다음 리포트가 나와야 AI Provider 단계로 넘어갈 수 있습니다.

```text
컨테이너 내부 실행            ✅
네트워크 접근 제한            ✅
CPU 사용 제한                 ✅
메모리 사용 제한              ✅
실행 시간 제한                ✅
원본 Workspace 쓰기 방지      ✅
임시 환경 완전 삭제 확인      ✅
실행 로그와 종료 원인 기록    ✅

종합 판정: 통과
```

하나라도 실패하면 AI가 생성한 코드를 자동 실행하지 않습니다.
