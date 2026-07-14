# ProofCode Sandbox Readiness Checklist

이 문서는 Step 11 기준 코드 구조를 점검한 결과입니다.

상태:

- `[x]` 현재 요구 수준 충족
- `[~]` 일부 구현됐지만 보안 Sandbox 요구 수준에는 부족
- `[ ]` 아직 구현되지 않음

## 현재 상태

### [ ] 컨테이너 내부 실행

현재 Candidate와 Benchmark는 임시 폴더 복사본에서 실행됩니다.

```text
임시 폴더 격리
≠
컨테이너 격리
```

Docker 또는 호환 컨테이너 런타임 연결이 필요합니다.

### [ ] 네트워크 접근 제한

현재 subprocess는 사용자 컴퓨터의 네트워크를 그대로 사용할 수 있습니다.

필요한 목표:

```text
기본값: 네트워크 없음
명시적으로 허용한 경우에만 제한적 접근
```

### [ ] CPU 사용 제한

현재 CPU 코어와 사용량 제한이 없습니다.

필요한 목표 예:

```text
--cpus 1.0
```

### [ ] 메모리 사용 제한

현재 프로세스 메모리 제한이 없습니다.

필요한 목표 예:

```text
--memory 512m
--memory-swap 512m
```

### [~] 실행 시간 제한

현재 Python subprocess timeout이 있습니다.

부족한 점:

- 자식 프로세스 전체가 확실히 종료되는지 보장하지 못함
- 컨테이너 강제 종료 원인 분류 없음
- 단계별 timeout 정책 없음

Step 12에서 컨테이너 자체 timeout과 강제 삭제를 추가해야 합니다.

### [~] 원본 Workspace 쓰기 방지

현재 원본을 임시 폴더로 복사하고 해시 변화도 검사합니다.

부족한 점:

- 원본 Workspace를 읽기 전용 mount로 강제하지 않음
- 실행 코드가 절대 경로로 원본에 접근할 가능성을 OS 수준에서 막지 않음
- 사용자 홈 디렉터리 등 다른 경로 접근도 제한하지 않음

Step 12 목표:

```text
원본 Workspace: read-only mount
실행 Workspace: 별도 writable volume
호스트 다른 경로: mount하지 않음
```

### [~] 임시 환경 완전 삭제 확인

현재 `TemporaryDirectory`가 정상 종료 시 임시 폴더를 삭제합니다.

부족한 점:

- 비정상 종료 뒤 잔여 폴더 검사 없음
- 삭제 실패 로그 없음
- 재시작 시 잔여 환경 청소 없음

Step 12에서 삭제 후 존재 여부 검사와 잔여 환경 정리를 추가해야 합니다.

### [~] 실행 로그와 종료 원인 기록

현재 기록되는 값:

- stdout
- stderr
- exit code
- timeout 여부
- 실행 시간
- 소스 해시 변화

아직 필요한 값:

- container id
- container exit code
- OOMKilled 여부
- timeout에 의한 강제 종료
- 네트워크 정책
- CPU/메모리 제한값
- 임시 환경 삭제 결과
- Sandbox 준비 실패 원인

## Step 12 통과 기준

아래 항목이 모두 `[x]`가 되기 전에는 AI가 생성한 코드를 자동 실행하지 않습니다.

- [ ] 컨테이너 런타임 감지
- [ ] 컨테이너 이미지 고정 또는 digest 기록
- [ ] 네트워크 기본 차단
- [ ] CPU 제한
- [ ] 메모리 및 swap 제한
- [ ] 컨테이너 timeout 및 강제 종료
- [ ] 원본 Workspace read-only mount
- [ ] 실행용 writable 복사본 분리
- [ ] 호스트 임의 경로 미노출
- [ ] 컨테이너 종료 사유 기록
- [ ] 임시 컨테이너와 volume 삭제 확인
- [ ] 실패 시 AI 실행 파이프라인 차단
