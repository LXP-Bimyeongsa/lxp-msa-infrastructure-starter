# Work Log

> 세션 단위 작업 기록. 무엇을 했고, 무엇이 **검증되지 않았고**, 다음에 뭘 해야 하는지.
> 결정의 배경은 [DECISIONS.md](DECISIONS.md), 단계별 계획은 [NEXT_STEPS.md](NEXT_STEPS.md).

## 2026-07-18

### 한 일

**저장소 구성**
- 팀 조직 `LXP-Bimyeongsa` 아래 Public 레포 생성, 원본(llllxxxxpppp)에서 이력 없이 초기 커밋 1개로 출발 (D-01)
- `main` 보호 ruleset — PR 필수, force push·삭제 차단. **승인은 0명**(중간에 폐기, D-02)

**문서 정비 — PR #1~#5**
컨벤션 → 결정 기록 → 아키텍처 → 폴더 구조 → 로드맵 순으로 스택 PR 구성.

**Step 1 서비스 골격 — PR #6, #7**
- payment-service 신규 생성 (8085, `com.lcs.payment`)
- `PaymentController`를 subscription-service에서 이관, gateway 라우팅 분리

**Step 2 데이터·메시징 — PR #9**
- `compose.data.yaml`: MySQL(스키마 3개) · MongoDB(단일노드 RS) · MinIO · RabbitMQ
- MySQL 서비스별 계정으로 스키마 접근을 DB 권한 수준에서 제한
- RabbitMQ 토폴로지를 `definitions.json`으로 선언

**Step 3 CI — PR #10**
- `ci/Jenkinsfile`: 변경된 서비스만 빌드, 공용 파일 변경 시 전체 빌드
- `compose.ci.yaml`: Jenkins 9080

**부수 정비 — PR #8, #9**
- `.gitignore`에 `**/bin/`·`.vscode/` 추가 (실제로 `.class` 파일이 커밋에 섞여 들어갔음)
- `.gitattributes`로 `*.sh` 등을 `eol=lf` 고정

### 검증 상태

| 대상 | 상태 |
|---|---|
| payment-service `gradlew bootJar` | 통과 |
| subscription-service `gradlew bootJar` | 통과 |
| `compose.data.yaml` 문법 | 통과 |
| infra + data 조합 문법 | 통과 |
| `compose.ci.yaml` 문법 | 통과 |
| `definitions.json` 파싱 | 통과 |
| **컨테이너 실제 기동** | **미검증** |
| **gateway 라우팅 동작** | **미검증** |
| **Jenkins 파이프라인 실행** | **미검증** |
| **Jenkinsfile Groovy 문법** | **미검증** (정적 검토만) |

Docker 데몬이 기동되지 않은 상태여서 런타임 검증을 하지 못했습니다. 머지 전 각 PR의 "테스트 방법"을 직접 확인해야 합니다.

### 알려진 함정

- **MySQL init 스크립트는 최초 기동에만 실행됩니다.** 스크립트를 고쳤다면 `docker compose -f compose.data.yaml down -v`로 볼륨을 지워야 반영됩니다.
- **비밀번호가 전부 기본값입니다** (`root`, `minioadmin`, `lxp`). 환경변수로 뺐지만 기본값이 소스에 있습니다.
- **Jenkins가 `docker.sock`을 마운트합니다.** 사실상 호스트 root 권한이라 로컬 학습 환경 전용입니다.
- **Jenkins 트리거는 폴링(5분)입니다.** 로컬에 공인 IP가 없어 webhook을 못 받습니다.
- **변경 탐지가 `HEAD~1` 기준**이라 여러 커밋을 한 번에 push하면 중간 변경을 놓칩니다.

### 다음

1. Docker Desktop 기동 후 각 PR "테스트 방법" 실행 → 머지
2. **auth-service를 member-service로 흡수** (D-04) — 이번 프로젝트의 유일한 파괴적 작업, 실행 전 확인 필요
3. Step 4 도메인 구현: 인증 → 강의+MinIO → 사가 → gRPC
4. `gh auth login` 완료 (터미널에 `✓ Logged in as` 확인까지)
5. Docker Hub 가입 후 `docker login` — 이미지 12개 이상 pull하므로 rate limit 회피
6. Slack Incoming Webhook URL 발급 (Grafana Alerting용)

### 미결

- **Consul이 아직 3노드 구성**(`bootstrap-expect=3`)입니다. D-14에 맞춰 개발용 1노드로 줄일지 미정 (P-02)
- `config-repo/payment-service.yml`이 포트 한 줄뿐 — 중앙 설정에 둘 이유가 있는지
- Outbox 릴레이 코드가 서비스마다 복사될 예정 — 공통 라이브러리로 뺄지 미정
