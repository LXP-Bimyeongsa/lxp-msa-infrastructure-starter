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
**빌드·문법**

| 대상 | 상태 |
|---|---|
| payment / subscription / member / gateway `bootJar` | 통과 |
| compose 전체 문법 (`config`) | 통과 |
| `definitions.json` 파싱 | 통과 |

**런타임 — Docker 기동 후 실제 확인**

| 대상 | 결과 |
|---|---|
| 컨테이너 13개 기동 | 전부 healthy |
| MySQL 스키마 3개 · outbox 3개 생성 | 통과 |
| **서비스 계정 격리** (`member` → `payment_db`) | `ERROR 1044` 로 차단 확인 |
| **MongoDB 단일노드 RS 트랜잭션** | 동작 확인 (D-10 입증) |
| MinIO `course-videos` 버킷 생성 | 통과 |
| RabbitMQ exchange 3 · queue 3 · binding 6 | 통과 |
| **사가 이벤트 라우팅** | `subscription.created` → payment 큐, `payment.completed` → subscription 큐 각 1건 확인 |
| Consul 서비스 등록 6개 | auth-service 없음 확인 |
| **Gateway 라우팅 5개** | 전부 200 |
| `/api/auth/ping` 응답 주체 | `member-service` (D-04 입증) |
| `/api/payments/**` 응답 주체 | payment-service (D-03 입증) |
| 8081 (구 auth-service) | 연결 불가 (정상) |
| Prometheus 스크레이프 타깃 6개 | 전부 `up` |

**여전히 미검증**

| 대상 | 상태 |
|---|---|
| Jenkins 기동 · 파이프라인 실행 | 미검증 |
| Jenkinsfile Groovy 문법 | 미검증 (정적 검토만) |
| Grafana 대시보드 · Loki 로그 수집 | 미확인 |

### 기동 중 발견해 고친 것

**3306 포트 충돌.** 호스트에 네이티브 MySQL이 이미 떠 있어 mysql 컨테이너가 뜨지 못했습니다. 호스트 포트를 환경변수로 분리하고(`MYSQL_PORT` 등, 기본값은 표준 포트 유지) `.env.example`을 추가했습니다. 컨테이너끼리는 항상 기본 포트로 통신하므로 서비스 설정에는 영향이 없습니다.

### 알려진 함정

- **MySQL init 스크립트는 최초 기동에만 실행됩니다.** 스크립트를 고쳤다면 `docker compose -f compose.data.yaml down -v`로 볼륨을 지워야 반영됩니다.
- **비밀번호가 전부 기본값입니다** (`root`, `minioadmin`, `lxp`). 환경변수로 뺐지만 기본값이 소스에 있습니다.
- **Jenkins가 `docker.sock`을 마운트합니다.** 사실상 호스트 root 권한이라 로컬 학습 환경 전용입니다.
- **Jenkins 트리거는 폴링(5분)입니다.** 로컬에 공인 IP가 없어 webhook을 못 받습니다.
- **변경 탐지가 `HEAD~1` 기준**이라 여러 커밋을 한 번에 push하면 중간 변경을 놓칩니다.

### 다음

1. PR 13개 머지 (문서 #1~#5 → 코드 #6 → #7 → #12 → 독립 #8~#11)
2. Jenkins 기동 및 파이프라인 첫 실행 — 유일하게 남은 미검증 영역
3. Step 4 도메인 구현: 인증 → 강의+MinIO → 사가 → gRPC
4. `gh auth login` 완료 (터미널에 `✓ Logged in as` 확인까지)
5. Docker Hub 가입 후 `docker login` — 이미지 12개 이상 pull하므로 rate limit 회피
6. Slack Incoming Webhook URL 발급 (Grafana Alerting용)

### 미결

- **Consul이 아직 3노드 구성**(`bootstrap-expect=3`)입니다. D-14에 맞춰 개발용 1노드로 줄일지 미정 (P-02)
- `config-repo/payment-service.yml`이 포트 한 줄뿐 — 중앙 설정에 둘 이유가 있는지
- Outbox 릴레이 코드가 서비스마다 복사될 예정 — 공통 라이브러리로 뺄지 미정

## 2026-07-19

### 한 일

**Step 4 도메인 구현 완료** (회원탈퇴 사가 제외)

| PR | 내용 |
|---|---|
| #18 | course-service 강의 CRUD + MinIO Presigned URL |
| #19 | 정기 결제 스케줄러 |
| — | Keycloak(OIDC) 이관 |

### 실제로 터진 문제와 원인

**MinIO presigned URL 503** — SDK가 서명 전에 버킷 리전을 조회하려고 endpoint로 네트워크 호출을 하는데, presign 클라이언트의 endpoint는 컨테이너 밖 주소라 서버가 접속할 수 없었다. `.region()` 명시로 조회 자체를 제거. 예외 핸들러가 원인을 삼키고 있어 로그가 비어 있었던 것도 함께 고침.

**정기 결제 트랜잭션 오염** — 제약 위반을 트랜잭션 안에서 잡아 무시하면 rollback-only로 표시돼 커밋 시 `UnexpectedRollbackException`이 난다. 선검사 + 예외 전파로 교체.

**Keycloak "Account is not fully set up"** — 24+ 기본 VERIFY_PROFILE 필수 액션. 프로필은 member_db가 소유하므로 비활성화.

**member_id 클레임 누락** — Keycloak 24+는 선언되지 않은 사용자 속성을 조용히 버린다. declarative user profile에 속성 선언 필요.

**MongoDB 컨테이너 종료** — `docker-entrypoint-initdb.d`에서 `rs.initiate`를 실행하면 그 시점 mongod가 로컬 소켓에만 붙어 있어 자기 자신을 인식하지 못하고 죽는다. 이전에는 우연히 통과했던 레이스. initdb 마운트 제거.

**gRPC 테스트 포트 충돌** — 컨테이너가 9092를 점유한 상태에서 테스트가 같은 포트를 잡으려다 실패. 테스트는 임의 포트 사용.

### 검증 상태

전부 실제 기동으로 확인:
- Keycloak 가입 → 토큰 발급 → `member_id` 클레임 → gateway 검증 → 200
- 무토큰/변조 토큰/`X-Member-Id` 위장 → 전부 401
- 구독 생성 시 gRPC 회원 확인 + 사가(ACTIVE/APPROVED) 정상
- 정기 결제: 회차 진행, 중복 차단, 해지 시 중단 및 환불
- MinIO: presigned URL 업로드·재생 왕복, 내용 일치

### 남은 것

- 회원탈퇴 사가 (outbox 3번째 복사 → 공통화 판단 필요)
- 서비스 간 토큰 검증 (P-11)
- 재생 URL 접근 제어 (P-16)
- README 스모크 절차 갱신 — 인증이 Keycloak으로 바뀌어 기존 절차가 낡음

---

## 2026-07-19 — 회원탈퇴 사가 · Outbox 공통화 · 탈퇴 회원 인증 차단

PR 3개. Step 4의 마지막 도메인 조각을 끝냈다.

| PR | 내용 |
|---|---|
| #20 | Outbox 구현을 `common-outbox` 모듈로 추출 (D-30) |
| #21 | 회원탈퇴 사가 — 탈퇴 시 구독 해지·환불 (D-31) |
| #22 | 탈퇴 회원의 인증 차단 — Keycloak 계정 비활성화 + 토큰 수명 단축 (D-32) |

### 공통화를 먼저 한 이유

subscription과 payment의 outbox 4개 파일이 **패키지 선언 한 줄 빼고 완전히 동일**했다.
회원탈퇴 사가에서 member가 세 번째 복사본을 만들 참이었으므로, 복사가 늘기 전에 뽑았다.
차이가 없는 코드였기 때문에 "억지 추상화" 위험이 없었다 — 만약 세 구현이 조금씩
달랐다면 판단이 달라졌을 것이다.

동작 변화가 없는 PR로 분리해서, 리뷰가 "회귀가 없는가"만 보면 되게 했다.

### 실제로 터진 문제와 원인

**컴포지트 빌드 모듈의 인코딩** — `common-outbox`가 한국어 Windows(CP949)에서
컴파일에 실패했다. 소스는 UTF-8인데 javac이 빌드 호스트 기본 인코딩으로 읽었다.
컴포지트 빌드로 포함되는 모듈은 **소비 서비스의 빌드 설정을 상속받지 않는다.**
모듈 자신의 `build.gradle`에서 `options.encoding = 'UTF-8'`을 고정해야 한다.

**Jackson이 딸려오지 않음** — `spring-boot-starter-data-jpa`와 `-amqp`는
jackson-databind를 가져오지 않는다(web 스타터가 가져온다). `OutboxWriter`가
`ObjectMapper`를 생성자로 받으므로 공통 모듈이 직접 선언해야 했다.

**Keycloak realm import는 최초 기동에만 적용된다** — `accessTokenLifespan`을 고치고
컨테이너를 재기동했는데 값이 그대로였다. 로그에 `Realm 'lxp' already exists. Import skipped`.
**MySQL init 스크립트와 정확히 같은 함정**이다. realm 설정을 바꾸면 `docker compose down -v`가 필요하다.

**realm JSON에 주석을 달 수 없다** — 설명용 키(`_comment_...`)를 넣었더니 import가
통째로 실패했다(`Unrecognized field ... not marked as ignorable`). Keycloak은 알 수 없는
필드를 거부한다. 배경 설명은 DECISIONS에 둔다.

### 검증하다 발견한 것

탈퇴 후 인증이 정말 막히는지 세 경로를 각각 재봤더니 하나가 열려 있었다.

| 경로 | 결과 |
|---|---|
| 새 토큰 발급 | `invalid_grant` "Account disabled" — 차단 |
| refresh_token 갱신 | `invalid_grant` "Session not active" — 차단 |
| **기존 access token으로 API 호출** | **HTTP 200 — 열려 있음** |

realm의 `accessTokenLifespan`이 3600이라 탈퇴 후 **최대 1시간** API가 열려 있었다.
300초로 줄여 노출 창을 1/12로 좁혔다. 완전 차단은 gateway가 매 요청 회원 상태를
조회해야 해서 P-11로 넘긴다.

"계정을 비활성화했다"까지만 확인하고 끝냈으면 못 봤을 구멍이다.
**막았다고 생각한 것을 실제로 뚫어봐야 한다.**

### 검증 상태

마지막에 `docker compose down -v` 후 전체 스택을 클린 상태로 재기동해서 확인했다.

- realm 반영: `accessTokenLifespan` 300, 토큰 `expires_in` 300
- RabbitMQ: `member.events` 익스체인지 · `member.withdrawn` 바인딩 정상 생성
- 탈퇴 사가: ACTIVE + PENDING 구독 둘 다 CANCELLED → REFUNDED
- 예약 결제: `billing_schedule.active` 둘 다 0 (D-27 경로 재사용)
- 멱등: 재탈퇴 시 이벤트 재발행 없음, 중복 환불 0
- outbox 미발행 잔여 0 (member·subscription·payment), DLQ 0

### 남은 것

- 서비스 간 토큰 검증 (P-11) — D-32의 잔여 구멍도 여기서 함께
- 재생 URL 접근 제어 (P-16)
- 정기 결제 재시도 정책 (P-15)
- Jenkins 파이프라인 검증 — 유일한 미검증 영역
- README 스모크 절차 갱신
