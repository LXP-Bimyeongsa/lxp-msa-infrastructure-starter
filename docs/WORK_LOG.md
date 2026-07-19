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

---

## 2026-07-19 (이어서) — 서비스 간 토큰 검증 (P-11)

PR #24. gateway 우회를 막았다.

### 문제

다운스트림이 `X-Member-Id`를 무조건 신뢰했다. gateway가 검증 후 주입한다는
전제였지만, 네트워크에 닿으면 누구나 `member-service:8082`에 그 헤더를 직접
보낼 수 있었다. 신뢰 경계가 "gateway"라고 문서에는 적혀 있었지만
**그 경계를 강제하는 장치가 없었다.**

### 방식

gateway가 Keycloak client credentials로 받은 토큰(`aud: lxp-internal`)을
사용자 토큰 대신 실어 보내고, 각 서비스가 서명·issuer·audience를 검증한다.

audience까지 보는 것이 핵심이다. 서명만 보면 **사용자 토큰도 통과한다** —
같은 realm이 서명하기 때문이다. 그러면 사용자가 자기 토큰을 들고 서비스를
직접 호출하면서 `X-Member-Id`에 남의 id를 넣을 수 있다.

네 서비스가 같은 설정을 갖게 되므로 `common-security` 모듈로 뽑았다(D-30과 같은 방식).

### 검증 — 실제로 뚫어봤다

"막았다"를 코드로 확인하지 않고 공격을 재현했다.

| 공격 | 결과 |
|---|---|
| 서비스 직접 호출 + `X-Member-Id` 위조 | 4개 서비스 전부 401 |
| 가입 엔드포인트 직접 호출(공개 경로) | 401 |
| **유효한 사용자 토큰** + 남의 id 위조 | 401 |

세 번째가 audience 검증이 실제로 일하는 증거다. 서명이 유효한 진짜 토큰인데도
거부된다. 여기서 서명만 봤다면 통과했을 것이다.

동시에 **열려 있어야 하는 것**도 확인했다 — actuator 4개 전부 200,
compose healthcheck 정상, Prometheus 타깃 6개 up. 보안을 걸면서 헬스체크를
같이 막아버리면 컨테이너가 계속 재시작한다.

### 앞선 세션의 오판을 정정

#22 문서에서 "D-32의 잔여 구멍(발행된 access token이 만료까지 유효)은
P-11에서 함께 다룬다"고 적었는데 **틀렸다.**

D-33은 "이 요청이 gateway를 거쳤는가"를 증명할 뿐,
"그 사용자가 아직 유효한가"는 보지 않는다. 탈퇴한 회원의 토큰이라도
gateway를 거치면 서비스 토큰이 붙고, 다운스트림은 통과시킨다.

별도 항목(P-17)으로 분리했다. 해결하려면 상태를 보는 검증(introspection 또는
회원 상태 캐시)이 필요하고, 둘 다 매 요청 비용이 붙는 결정이라 따로 다뤄야 한다.

### 남은 것

- gRPC·스케줄러의 서비스 토큰 (P-18) — member-service의 9092 포트는 아직 열려 있다
- 탈퇴 회원의 잔여 access token (P-17)
- 재생 URL 접근 제어 (P-16)
- 정기 결제 재시도 정책 (P-15)
- Jenkins 파이프라인 검증

---

## 2026-07-19 (이어서) — gRPC 서비스 토큰 (P-18)

PR #26. D-33이 남겨둔 gRPC 구멍을 막았다.

### 문제

REST는 막았는데 member-service의 gRPC 포트(9092)는 열려 있었다.
grpcurl로 직접 붙으면 회원 정보가 그대로 나왔다.
**같은 데이터를 한쪽만 막으면 막지 않은 것과 같다.**

### 이번 판단의 핵심 — 실패를 어떻게 분류할 것인가

`UNAUTHENTICATED`를 서킷브레이커 실패로 셀 것인가?

세지 않기로 했다. 상대가 요청을 받아 판단하고 거절했다는 것은
**상대가 살아 있다는 증거**다. 장애로 세면 시크릿 설정이 틀렸을 때
멀쩡한 member-service의 서킷이 열리고, 진짜 원인은 "서킷 열림" 로그에 묻힌다.
운영자는 member-service를 들여다보게 되고, 거기엔 아무 문제가 없다.

D-17에서 `NOT_FOUND`를 뺀 것과 같은 기준이다 —
서킷브레이커는 "상대가 건강한가"를 재는 계기지 "내 요청이 성공했는가"가 아니다.

다만 `NOT_FOUND`와 다른 점이 하나 있다. `NOT_FOUND`는 그대로 전파해서
"없는 회원"이라는 정상적인 거절이 되지만, 자격증명 거절은 **fail-closed**다 —
회원을 확인하지 못한 채로 구독을 만들 수는 없다(D-18).
집계에서 빼는 것과 통과시키는 것은 다른 이야기다.

### 검증 — 두 실패를 갈라서 봤다

시크릿을 일부러 틀리게 주입해서 재기동했다.

| 상황 | HTTP | 서킷 | 로그 |
|---|---|---|---|
| 시크릿 오류 (상대는 멀쩡) | 503 ×10 | **closed 유지** | `서비스 토큰 거절 — 설정을 확인해야 한다` |
| 진짜 장애 (member 중지) | 503 ×10 | **open** | `서킷 열림 — member-service 확인 불가` |

같은 503인데 서킷 상태와 로그가 갈린다. 이게 이 PR이 하려던 일이다.
분류하지 않았다면 위쪽도 서킷이 열리고 로그는 엉뚱한 서비스를 가리켰을 것이다.

서킷이 여전히 제 일을 하는지도 같이 확인했다 — member 복구 후 자동 폐쇄,
서킷이 열린 동안 유령 구독 0건.

### 곁다리로 배운 것

- gRPC 리플렉션이 꺼져 있어 grpcurl이 스키마를 못 찾았다. proto 파일을
  마운트해서 넘겨야 했다. 리플렉션을 켜면 편하지만 스키마가 공개된다.
- **main에 직접 커밋했다.** 브랜치를 만들지 않고 작업했고, push 단계에서야
  알아차렸다. 원격에는 나가지 않아 브랜치로 옮기고 main을 되돌리는 것으로 정리했다.
  작업 시작 전에 브랜치를 먼저 만드는 습관이 이래서 필요하다.

### 남은 것

- 탈퇴 회원의 잔여 access token (P-17) — 층이 다른 문제
- 재생 URL 접근 제어 (P-16)
- 정기 결제 재시도 정책 (P-15)
- Jenkins 파이프라인 검증

---

## 2026-07-19 (이어서) — 탈퇴 회원의 잔여 토큰 (P-17)

PR #28. D-32에서 남긴 마지막 인증 구멍을 닫았다.

### 문제

계정을 비활성화하고 세션을 끊어도 **이미 발행된 access token은 만료까지 유효**했다.
JWT는 발급 시점의 사실을 담은 종이라, 그 뒤에 무슨 일이 있었는지 모른다.
서명이 맞으면 통과했다.

### 방식

gateway가 Keycloak introspection(RFC 7662)으로 "이 토큰 지금도 살아 있냐"를 묻는다.
탈퇴 시 세션을 끊었으므로(D-32) Keycloak이 inactive로 답한다.

**gateway에서만** 한다. 다운스트림은 이미 서비스 토큰만 받으므로(D-33·D-34)
사용자 토큰이 닿는 곳은 gateway 하나뿐이다. 확인 지점을 늘릴 이유가 없다.

### 두 가지 판단

**캐시를 둔다** — 매 요청 Keycloak을 부르면 gateway 처리량이 Keycloak에 묶인다.
활성 판정만 30초 캐시한다. 노출 창이 300초 → 30초로 줄어들 뿐 0이 되지는 않는다.
이건 숨길 게 아니라 교환 조건이고, TTL로 조정하면 된다.
비활성 판정은 캐시하지 않는다 — 재활성화가 즉시 반영돼야 한다.

**401과 503을 가른다** — "토큰이 죽었다"와 "살았는지 모르겠다"는 다르다.
섞으면 Keycloak 장애가 "당신 토큰이 잘못됐다"로 표시돼 사용자가 재로그인을 시도하고,
그 재로그인도 Keycloak이 죽어서 실패한다. 엉뚱한 곳을 헤매게 된다.

### 검증

캐시 때문에 테스트 설계에 함정이 있었다. 탈퇴 요청 자체가 그 토큰을 쓰므로,
탈퇴 직후엔 이미 캐시에 활성으로 올라가 있다. 그래서 **탈퇴 전에 미리 받아두고
한 번도 쓰지 않은 토큰**을 따로 준비해서 확인했다.

| 대상 | 결과 |
|---|---|
| 탈퇴 후, 캐시에 없는 토큰 | **401** (D-32에서는 200이었다) |
| 탈퇴 후, 캐시된 토큰 (TTL 이내) | 200 — 문서화된 노출 창 |
| 캐시 만료 후 | **401** |
| Keycloak 중지 상태 | **503** (401 아님) |
| 정상 회원 | 201 — 회귀 없음 |

### 남은 것

- 재생 URL 접근 제어 (P-16)
- 정기 결제 재시도 정책 (P-15)
- Jenkins 파이프라인 검증

---

## 2026-07-19 (이어서) — 재생 URL 구독 확인 (P-16)

PR #29.

### D-17을 재검토했지만 뒤집지 않았다

P-16은 "구독 확인을 넣으려면 course → subscription 동기 호출이 생겨
D-17 재검토가 필요하다"고 적혀 있었다. 재검토한 결과 **동기 호출을 넣지 않기로** 했다.

재생은 구독 생성보다 훨씬 잦은 경로다. 여기에 동기 호출을 걸면 subscription이
course의 가용성을 좌우하게 되고, D-17이 이벤트로 끊어둔 결합이 되살아난다.

대신 subscription이 발행하는 이벤트를 course가 소비해 읽기 모델을 둔다.
`SubscriptionCreated`로는 부족했다 — PENDING 시점이라 "이용 가능"이 아니다.
그래서 `SubscriptionActivated`를 새로 발행했다.

복제는 **"지금 볼 수 있는가"에 답하는 최소 형태**로만 했다.
금액·플랜·주기는 복제하지 않는다 — 필요 없는 것을 복제하면 그것도 맞춰야 할 상태가 된다.

`subscriptionId`를 `_id`로 쓴 덕에 소비가 자연히 멱등해졌다.
같은 이벤트가 두 번 와도 문서가 하나만 남는다.

### 403이지 404가 아니다

강의는 존재하고 회원도 정상이며 구독만 없다. 404로 감추면 사용자가
"구독하면 볼 수 있다"는 것을 알 수 없다. 숨겨야 할 것은 남의 자원의 존재 여부지,
자기가 접근할 수 없는 이유가 아니다.

### 겪은 것

**한글 JSON을 `curl -d`로 보내 400.** 저장소 README에 이미 적혀 있는 함정인데
그대로 밟았다. 강의 제목에 "유료 강의"를 넣었더니 CP949로 인코딩돼 거부됐다.
ASCII로 바꿔 진행했다.

**UnnecessaryStubbingException.** 재생 URL 스텁을 공통 헬퍼에 뒀는데,
거부 경로 테스트는 거기까지 가지 않아 스텁이 남았다. Mockito strict 모드가 잡아냈다.
성공을 기대하는 테스트가 직접 스텁하도록 분리했다.

### 검증

| 대상 | 결과 |
|---|---|
| 강의 소유자 (구독 없음) | 200 — 자기가 올린 것은 본다 |
| 구독 없는 시청자 | **403** — 예전엔 200이었다 |
| 구독 후 | 200 (전파 **1초 이내**) |
| 해지 후 | **403** (전파 **1초**) |
| Mongo 읽기 모델 | `active: true` → `active: false` |
| outbox 미발행 / DLQ | 0 / 0 |

### 남은 것

- 정기 결제 재시도 정책 (P-15)
- Jenkins 파이프라인 검증

---

## 2026-07-19 (이어서) — 정기 결제 재시도 (P-15)

PR #30.

### 왜 재시도인가

카드 한도 초과·일시적 승인 거절처럼 며칠 뒤면 풀리는 사유가 흔하다.
이미 서비스를 쓰고 있던 회원을 한 번의 실패로 끊는 것은 과하다.

다만 **최초 결제(1회차)는 다르다** — 아직 아무것도 제공하지 않은 상태라
즉시 취소가 맞다. 기존 동작을 그대로 뒀다.

### 걸림돌 — 멱등키가 재시도를 막고 있었다

실패한 결제를 Payment 행으로 남기면 `(subscription_id, billing_cycle)`
unique 제약(D-26)에 걸려 **같은 회차의 재시도가 영영 성공할 수 없다.**

그래서 재시도가 남은 실패는 행을 남기지 않기로 했다.
중복 청구 방지는 그대로다 — 승인된 건만 행이 생기고, 그 순간부터 제약이 막는다.
시도 횟수는 `billing_schedule.retry_count`가 센다.

D-26을 건드리지 않고 해결한 셈인데, 처음엔 제약을
`(subscription_id, cycle, attempt)`로 넓히려다 멱등키 설계가 복잡해져서 접었다.

### 또 하나 — 재시도 간격을 어디서부터 재는가

`nextBillingAt.plus(interval)`로 쓰면 이미 지난 예정일에 더하는 것이라
간격이 0이 되어 스케줄러가 곧바로 다시 집는다. **지금**부터 재야 한다.

반대로 성공 시 다음 청구일은 예정일 기준으로 더한다 —
재시도로 밀렸다고 청구 주기까지 뒤로 밀리면 안 된다.

### 수치는 코드가 정할 것이 아니다

"몇 번, 며칠 간격"은 사업 정책이다. 설정으로 뺐고 기본값만 "3일 간격 3회"로 뒀다.
`max-attempts: 1`이면 D-37 이전 동작(즉시 중단)으로 되돌아간다.

### 검증 — 실제로 실패시켜서 봤다

스케줄의 금액을 0으로 바꾸고 청구일을 과거로 당겨 재현했다.
데모용으로 스케줄러 10초·재시도 간격 15초로 줄였다.

```
[10s] retry=1 active=1  구독=ACTIVE
[30s] retry=2 active=1  구독=ACTIVE
[50s] retry=2 active=0  구독=CANCELLED
```

D-37 이전이라면 첫 줄에서 이미 CANCELLED였다.

- Payment 행: 1회차 APPROVED + 2회차 FAILED **1건만** (재시도 중에는 행 없음)
- `PaymentFailed` 발행 **1회** (소진 시점에만)
- 환불 0건 — 결제가 실패했으니 환불할 것이 없다
- outbox 미발행 0, DLQ 0

### 남은 것

- Jenkins 파이프라인 검증

---

## 2026-07-19 (이어서) — Jenkins 파이프라인 검증 (Step 3)

PR #31. 유일하게 미검증이던 영역이었고, **띄우자마자 버그 4개가 나왔다.**

파이프라인을 작성한 뒤 "문법은 맞으니 되겠지"로 남겨뒀던 것이 그대로 드러났다.
이 프로젝트에서 이미 두 번 겪은 패턴이다.

### 나온 것

**① `SERVICES`에 없어진 `auth-service`가 남아 있었다.**
D-04에서 member-service에 흡수했는데 목록을 고치지 않았다.
"전체 빌드" 경로로 들어가면 `dir('auth-service')`가 없는 디렉터리를 열어 죽는다.

**② `common-security/`가 변경 감지에서 빠져 있었다.**
`common-outbox/`는 PR #20에서 넣었는데, PR #24에서 `common-security`를 만들 때
같은 곳에 추가하는 것을 잊었다. **공통 모듈만 고친 커밋이 "변경 서비스 없음"으로
잡혀 아무것도 빌드하지 않고 통과한다** — 깨져도 알 수 없다.

하나씩 나열하는 방식 자체가 원인이라 `common-*` 접두사로 묶었다.
`infrastructure/`도 함께 넣었다 — SQL·RabbitMQ 정의가 바뀌면 서비스가 영향받는다.

**③ Jenkins 이미지에 docker CLI가 없었다.**
compose 주석에는 "docker CLI 설치를 위해 user: root"라고 적혀 있는데
정작 설치하는 부분이 없다. `docker: not found`로 이미지 빌드 단계만 실패한다.
`ci/Dockerfile`로 CLI만 얹었다(데몬은 넣지 않는다 — DooD 구성이라 불필요).

**④ `payment-service/gradlew`에 실행 권한이 없었다.**
git 인덱스 모드가 6개 중 그것 하나만 `100644`였다.
`sh: ./gradlew: Permission denied`.

이게 특히 고약한 이유 — **로컬 Windows에서도, Dockerfile에서도 드러나지 않는다.**
Windows는 실행 비트를 신경 쓰지 않고, Dockerfile은 `./gradlew`가 아니라
이미지에 든 `gradle`을 쓴다. `./gradlew`를 부르는 곳은 Jenkins뿐이다.

### 검증

Jenkins 컨테이너 안에서 파이프라인이 실제로 하는 일을 그대로 실행했다.

- `git clone` → 변경 파일 목록 추출 → 공용 파일 감지가 "전체 빌드"로 올바르게 걸림
- 컨테이너 안에서 `docker ps`로 호스트 Docker 조종 확인
- `./gradlew clean build`가 컨테이너 안에서 성공 —
  `:common-outbox:jar` → `:bootJar` → 테스트까지 통과.
  **컴포지트 빌드(D-30)가 CI 환경에서도 동작한다는 것을 처음 확인했다.**

### 남은 것

- 로컬 Jenkins ↔ GitHub 폴링 연동 (Step 3 마지막 항목)
- PG 실연동(P-01), HA 구성(P-14), 배포 대상(P-07)

---

## 2026-07-19 (이어서) — PG 목 연동 (D-39)

PR #32. 실키는 사업자등록이 있어야 받지만(P-01), **연동 경계는 지금 만들 수 있다.**

### 왜 프로세스 밖에 두는가

기존 `charge()`는 `amount > 0`이면 승인이었다. 이대로 두면 실연동에서
터지는 것이 하나도 드러나지 않는다 — 타임아웃, 거절 코드별 대응,
승인번호 보관, 환불 호출.

그래서 WireMock으로 **네트워크 건너편에 PG를 세웠다.**
목이지만 HTTP를 타고, 지연이 있고, 거절 코드를 돌려준다.

### 만들면서 드러난 것

**승인번호를 저장하지 않고 있었다.** 환불이 그냥 DB 상태를 REFUNDED로
바꾸는 것이었다. 실제 PG라면 **승인번호 없이는 취소 요청을 보낼 수 없다** —
돈은 그대로 나가 있는데 우리 기록만 "환불됨"이 된다.
`pg_transaction_id`를 추가하고 환불이 PG 취소를 실제로 부르게 했다.

**멱등키가 우리 DB에만 있었다.** D-26의 `(subscriptionId, billingCycle)`은
우리 쪽 중복만 막는다. 타임아웃 후 재시도하면 **PG에는 두 번 청구될 수 있다.**
멱등키를 PG 요청에도 실었다.

**통신 실패는 "실패"가 아니다.** 타임아웃이 나면 승인됐는지 알 수 없다.
실패로 단정하면 이미 청구된 건을 놓친다. `PgApproval.unreachable()`로
"모름 + 재시도 가능"으로 다룬다 — 멱등키가 있으니 재시도가 안전하다.

**거절에도 종류가 있다.** 한도 초과는 며칠 뒤 풀리지만 분실·도난 카드는
백 번 긁어도 안 된다. dunning(D-37)을 무조건 3회 돌리면 그 사이 회원은
서비스를 계속 쓴다. `retryable`을 보고 재시도를 건너뛰게 했다.

### 검증

목 PG는 실제 PG의 테스트 카드처럼 **금액으로 시나리오를 고른다**
(1004=한도초과, 1005=도난, 1006=지연).

| 항목 | 결과 |
|---|---|
| 승인 | `pg_transaction_id` 저장 확인 |
| 목 PG 호출 | `/v1/payments` 요청 기록 확인 |
| 환불 | `/v1/payments/cancel`에 **승인번호가 실려** 전송됨 |
| 재시도 불가 거절(1005) | **retry=0인 채 즉시 중단** → 구독 CANCELLED |
| 거절 코드 보관 | `pg_decline_code = STOLEN_CARD` |

마지막 두 줄이 D-37과 연결된 지점이다. dunning이 도는 경우(retry 1→2→중단)와
도는 것 자체가 낭비인 경우(retry 0에서 중단)가 갈린다.

### 남은 것

- 실키 발급 후 실연동 (P-01) — `PgHttpClient` 주소·인증 헤더, 목 매핑 교체
- 로컬 Jenkins ↔ GitHub 폴링 연동
- HA 구성(P-14), 배포 대상(P-07)

---

## 2026-07-19 (이어서) — Jenkins GitHub 폴링 연동 (D-40)

PR #33, #34. Step 3의 마지막 항목이자, **CI를 실제로 돌려본 첫 세션**이다.

### 잡을 코드로 정의했다

`ci/jenkins.yaml`(JCasC) + `ci/plugins.txt` + Dockerfile의 사전 설치.
UI로 만들면 컨테이너 볼륨을 지우는 순간 사라진다 — 이 프로젝트에서
MySQL init, Keycloak realm으로 **이미 두 번 겪은 패턴**이다.

public 저장소라 자격증명이 필요 없었다. private이면 `credentialsId`만 붙이면 된다.

### 돌려보니 나온 것

**① member-service 테스트 10개가 CI에서만 깨졌다.**

```
Could not resolve placeholder 'keycloak.issuer-uri'
```

`AuthController`가 요구하는 값이 `application-test.yml`에 없었다.
로컬에서 통과한 이유 — **호스트에 config-server 컨테이너가 떠 있어서**
`optional:configserver:`가 localhost:8888에서 실제 설정을 받아왔기 때문이다.

즉 테스트가 "실행 중인 인프라"에 의존하고 있었다.
`docker compose stop config-server`로 로컬에서 재현해 확정했고,
나머지 5개 서비스도 같은 조건으로 전부 돌려 이상 없음을 확인했다.

**이 프로젝트에서 세 번째 만나는 같은 종류다** — gRPC 테스트 포트 충돌,
mongo 초기화 레이스, 그리고 이번 건. 전부 "그때 환경이 우연히 맞아서" 통과했다.

**② Docker 이미지 빌드 단계가 통째로 건너뛰어지고 있었다.**

빌드 #2 로그: `Stage "Docker 이미지 빌드" skipped due to when conditional`

`when { branch 'main' }`은 `BRANCH_NAME`을 보는데, 이 값은 **멀티브랜치
파이프라인에서만** 채워진다. 단일 브랜치 잡에서는 비어 있어 조건이 영영 참이 되지 않는다.

빌드는 계속 SUCCESS였다 — 건너뛴 단계는 실패가 아니기 때문이다.
**아무도 이미지가 안 만들어지고 있다는 것을 몰랐을 것이다.**

`checkout scm`이 돌려주는 `GIT_BRANCH`를 직접 꺼내 판단하도록 고쳤다.

**③ Jenkins 버전을 올려야 했다.**
`2.492`에 플러그인 설치가 거부됐다(`workflow-api requires 2.504.1`).
`2.516.1-jdk17`로 올렸다.

### 폴링 확인

머지 후 실제로 관찰했다.

```
16:46:00  No changes
16:51:00  Changes found  → 빌드 #2 "Started by an SCM change"
빌드 대상 커밋: 76c098f
빌드 대상: gateway config-server member-service course-service subscription-service payment-service
6개 전부 BUILD SUCCESSFUL → Finished: SUCCESS
```

### 남은 것

- PG 실키 발급 후 실연동 (P-01)
- HA 구성(P-14), 배포 대상(P-07)

---

## 2026-07-19 (이어서) — 중복 회차 스킵이 정기 결제를 영구 중단시키던 버그 (D-41)

PR #35. Jenkins 이미지 빌드 단계를 실제로 돌려보려고 **서비스 코드에서 고칠 것을
찾다가** 나온 건이다. 찾는 김에 훑은 것이지 원래 알고 있던 문제가 아니다.

### 무엇이 잘못돼 있었나

`charge()`는 이미 청구된 회차를 만나면 PG를 부르지 않고 건너뛴다. 여기까지는 맞다.
문제는 **그 결과를 돌려주는 방식**이었다.

```java
return PgApproval.declined("DUPLICATE_CYCLE", false);   // 거절 + 재시도 불가
```

호출 측은 이렇게 받는다.

```java
} else if (lastChance || !result.retryable()) {
    schedule.deactivate();     // ← 여기로 들어온다
```

`retryable=false`라서 "재시도해도 소용없는 거절"과 **구분이 되지 않는다.**
결과적으로 *정상적인 멱등 스킵이 그 구독의 정기 결제를 영구히 껐다.*
로그는 `warn` 한 줄이라 조용히 끊긴다.

### 왜 이게 설계 근거를 무너뜨리는가

`BillingScheduler` 주석은 이렇게 단언하고 있었다.

> 인스턴스가 여러 개면 같은 스케줄을 동시에 집을 수 있다. 그래서 분산 락에
> 기대지 않고, unique 제약이 중복 청구를 DB 수준에서 막도록 설계했다 (D-26).

그런데 그 상황이 실제로 오면 **나중에 집은 쪽이 스케줄을 죽인다.**
락을 쓰지 않기로 한 근거 자체가 성립하지 않고 있었다.

### 기존 테스트가 이 경로를 이미 밟고 있었다

`sameCycleChargedOnlyOnce`는 "다중 인스턴스가 같은 스케줄을 집은 상황"을 그대로
재현하고 있었다. 다만 **Payment 행 개수만 검사하고 스케줄 상태는 보지 않았다.**
중복 청구는 안 되니 통과했고, 스케줄이 꺼진 것은 아무도 확인하지 않았다.

D-40의 "건너뛴 단계는 실패가 아니라서 아무도 몰랐다"와 같은 모양이다 —
**검사하지 않은 것은 통과한 것처럼 보인다.**

### 고친 방식

문자열 비교로 분기하지 않고 타입을 갈랐다. `PgApproval.duplicateCycle()` +
`isDuplicateCycle()`을 두고, 거절 분기보다 **먼저** 본다. 중복이면
`deactivate()`가 아니라 `advance()`로 다음 회차로 넘긴다.

낡은 사본에서 `advance()`를 불러도 안전하다 — 먼저 처리한 쪽과 같은 상태에서
같은 계산을 하므로 같은 값으로 수렴한다.

근본 원인은 어휘였다. **내부 멱등 스킵을 PG 응답 타입으로 표현한 순간**
호출 측이 그것을 거절로 다루는 것이 자연스러워졌다.

### 검증

먼저 단위 테스트로 버그를 재현했다(`isActive()`에서 실패) → 고친 뒤 통과.
그다음 실제 컨테이너로 재현했다.

| 단계 | 결과 |
|---|---|
| 구독 생성 | subscription 4 ACTIVE, 1회차 APPROVED |
| 2회차 강제 청구 | payment 6 APPROVED, 스케줄 회차 3으로 진행 |
| **회차를 2로 되돌려 재실행** | `이미 청구된 회차 — 다음 회차로 진행` |
| 스케줄 `active` | **1 유지** (고치기 전이면 0) |
| `next_billing_cycle` | 2 → **3** |
| 중복 결제 행 | 없음 (payment 2건 그대로) |

---

## 2026-07-19 (이어서) — 로그 원인 유실 + MinIO 오류 오분류 (D-42)

PR #36, #37. D-41을 찾다가 서비스 전반을 훑으면서 같이 나온 것들이다.

### PR #36 — 예외 원인이 로그에 남지 않던 곳 5건

전부 같은 모양이었다. `catch`해서 로그는 남기는데 **예외를 넘기지 않아
cause 체인과 스택트레이스가 통째로 사라진다.**

가장 나빴던 것은 gateway다. introspection 실패 로그가 `e.getMessage()`만
찍는데, 그 메시지가 예외 생성자에 **하드코딩된 상수**였다.

```java
super("Keycloak introspection 호출 실패", cause);
```

즉 매번 같은 줄만 나오고 진짜 원인은 버려진다. 전 사용자가 503을 맞는
장애인데 로그가 아무것도 말해주지 않는다.

Keycloak을 정지시켜 재현했더니 이제 이렇게 나온다.

```
Caused by: AnnotatedNoRouteToHostException: keycloak/172.21.0.7:8080
```

`CallNotPermittedException`(서킷 열림) 분기는 **일부러 그대로 뒀다.**
원인은 이미 앞 분기에서 남았고, 열려 있는 동안 스택트레이스를 반복하면
로그만 채운다. "전부 스택트레이스"가 답은 아니다.

### PR #37 — MinIO 오류를 전부 "객체 없음"으로 삼키던 것

```java
} catch (ErrorResponseException e) {
    // 객체 없음 — 장애가 아니라 정상적인 답이다
    return false;
}
```

주석과 실제 커버 범위가 달랐다. `ErrorResponseException`은 `NoSuchKey`만이
아니라 `AccessDenied`·`NoSuchBucket`·`SignatureDoesNotMatch`까지 전부 포괄한다.

즉 **자격증명이 틀리면 "사용자가 업로드를 안 했다"(409)로 표시된다.**
그리고 `e`는 어디에도 로그되지 않아 스택트레이스가 사라진다.
설정 오류를 사용자 탓으로 돌리면서 원인은 남기지 않는 조합이다.

응답 코드로 갈랐다. 시크릿을 일부러 틀리게 주입해 확인했다.

| 상황 | 고치기 전 | 고친 뒤 |
|---|---|---|
| 파일 안 올림(`NoSuchKey`) | 409 | 409 (유지) |
| 시크릿 오류(`AccessDenied`) | **409 + 로그 없음** | **503 + `code=AccessDenied` 로그** |

D-18·D-33의 fail-closed와 같은 기준이다 —
**확인하지 못한 것을 "없다"로 단정하지 않는다.**

### 곁가지로 드러난 것 — Consul에 죽은 인스턴스가 남는다

course-service 컨테이너를 재생성한 직후, gateway가 **`critical` 상태인
옛 인스턴스(172.21.0.17)로 라우팅해 500**이 났다. GET은 되고 POST는 안 되는
증상이었는데, 로드밸런서가 죽은 인스턴스와 산 인스턴스를 번갈아 고르고 있었다.

```
"Address":"172.21.0.17"  "Status":"critical"   ← 죽었는데 라우팅 대상
"Address":"172.21.0.18"  "Status":"passing"
```

수동 deregister로 넘어갔지만, **`critical` 인스턴스가 라우팅에서 빠지지 않는
것 자체가 문제**다. 개발 중 컨테이너 재생성에서만 본 것이라 이번 PR 범위에는
넣지 않았다. → P-19

### 검증

- PR #36: 5개 서비스 clean build, Keycloak 정지(gateway) / member-service
  정지(subscription) E2E 각각 확인. 유령 구독 0건
- PR #37: `NoSuchKey` → 409 유지, `AccessDenied` → 503 전환을 실제 컨테이너로 확인
- 두 PR 모두 Jenkins 폴링이 집어가 Docker 이미지 빌드 단계가 실제로 실행됨

---

## 2026-07-20 — 안정화 마무리 + 문서 정합성 (D-43 ~ D-45)

PR #38, #39, #40. "되는 데까지 밀어달라"는 요청으로 진행했다.
의견이 필요한 것(P-01 실키, P-07 배포 대상, P-14 HA 범위)은 손대지 않았다.

### P-19 — 기본값이 요청의 절반을 죽이고 있었다 (D-43)

전 세션에서 "GET은 되는데 POST는 안 되는" 증상으로 30분 가까이 헤맨 건이다.
원인은 `spring.cloud.consul.discovery.query-passing`의 **기본값이 `false`**.

디스커버리가 `critical` 인스턴스까지 돌려주고, 로드밸런서가 죽은 것과 산 것을
번갈아 고른다. 죽은 인스턴스를 등록하고 30회 호출해 재현했다.

```
query-passing: false → 15 성공 / 15 실패   ← 정확히 절반
query-passing: true  → 30 성공 /  0 실패
```

절반이라는 숫자가 라운드로빈이라는 증거였다.

`query-passing`만으로는 부족하다 — 라우팅만 막고 **등록은 그대로 쌓인다.**
정상 종료 시엔 앱이 스스로 해제하지만 `docker kill`·OOM·노드 다운에서는 못 한다.
`health-check-critical-timeout: 1m`을 함께 넣고, kill 후 1분 뒤 자동 해제되는 것을 봤다.

**증상이 코드 버그를 흉내내는 종류라 값이 비쌌다.**

### Zipkin OOM (D-44)

`Terminating due to java.lang.OutOfMemoryError: Java heap space`.
인메모리 상한 500000 + 샘플링 1.0이 겹쳤다.

더 나쁜 것은 죽은 뒤였다 — 재시작 정책도 헬스체크도 없어 **44분 동안 트레이스가
비어 있었는데 아무도 몰랐다.** 서비스 로그에는 span 전송 실패 스택트레이스만
쌓여 진짜 오류를 덮고 있었다(실제로 course-service 로그를 볼 때 걷어내야 했다).

**관측 도구 자체가 관측되지 않고 있었다.**

`docker kill`로는 재시작 정책을 검증할 수 없다는 것도 알았다 — Docker가 수동
중지로 취급한다. 컨테이너 안에서 `kill -9 1`도 커널이 막는다. 그래서 스스로
exit 1로 죽는 컨테이너를 따로 띄워 `RestartCount: 3`에서 멈추는 것을 확인했다.

### 문서 정합성 (D-45)

코드가 아니라 **문서가 실제와 어긋난 곳**을 훑었다. 20건 나왔다.

가장 나빴던 것들:

- `ARCHITECTURE.md`가 **gRPC 상대를 payment로** 적고 있었다 (실제는 member).
  D-17이 "payment → subscription 동기 호출은 만들지 않는다"고 명시하는데
  문서끼리 충돌하고 있었다
- 같은 문서에 **Keycloak이 아예 없었다** — 인증 주체가 D-20 이전 서술 그대로
- **Consul 노드 수가 반대로** 적혀 있었다 (문서 1노드 / 실제 3노드)
- **관측 경로가 미래 상태**로 적혀 있었다 — Alloy가 OTLP를 받아 Zipkin으로
  변환한다고 했지만 실제 `config.alloy`는 로그 파일만 Loki로 보낸다
- `NEXT_STEPS.md`의 **Step 1·2 11개 항목이 전부 `[ ]`** 인데 다 완료돼 있었다
- `PROJECT_STRUCTURE.md`에 `common-outbox`·`common-security`가 없었다 —
  D-30·D-33의 핵심 산출물인데 트리에서 빠져 있었다
- 포트 맵에 **Keycloak(8180)이 없었다** — 인증 진입점인데 없어서
  스모크 테스트를 따라할 수 없다

D-02("승인 1명 필수")는 실제(approvals=0)와 달랐다. 이 저장소 규약이
"뒤집을 때는 새 항목으로 추가하고 이전 항목에 링크한다"이므로 D-45로 철회했다.

### 이번에 다시 확인한 것

**검사하지 않은 것은 통과한 것처럼 보인다.** 이 프로젝트에서 여섯 번째다 —
gRPC 포트 충돌, mongo 레이스, config-server 의존, Docker 빌드 단계 스킵(D-40),
중복 회차(D-41), Zipkin 사망(D-44).

**기본값은 결정이다.** `query-passing: false`, `MEM_MAX_SPANS: 500000`,
빈 `BRANCH_NAME` — 아무도 고르지 않았지만 시스템의 동작을 정했다.

### 남은 것 (전부 결정이 먼저 필요)

- P-01 PG 실키 — 사업자등록
- P-07 배포 대상 — EC2 vs EKS
- P-14 HA — 컨테이너 +8개
- P-20 나머지 컨테이너 재시작 정책 — 부팅 시 자동 기동을 받아들일지
