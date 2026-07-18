# Conventions

## 브랜치 · PR

- `main`은 보호 브랜치: **직접 push 불가, PR을 거쳐야 머지 가능**.
- **승인은 필수가 아니다**(required approvals = 0) — 누구나 자기 PR을 머지할 수 있다. 초기 속도를 위한 선택이며, 리뷰 자체를 없애자는 뜻은 아니다.
- 브랜치 이름: `feat/<주제>`, `chore/<주제>`, `docs/<주제>`, `fix/<주제>`
  - 예: `feat/payment-service-skeleton`, `chore/compose-split`
- 강제되지 않을 뿐이므로, 도메인 로직·계약(proto/이벤트)·인프라 변경은 **머지 전 리뷰를 요청하는 것을 권장**한다.
- PR은 작게: 한 PR = 한 목적. 서비스 골격과 compose 변경을 한 PR에 섞지 않는다.
- 쪼개는 기준·크기 가이드·스택 PR 운용은 [PR_STRATEGY.md](PR_STRATEGY.md) 참고.

## 커밋 메시지

기존 이력 관례를 따른다: `<type>: <한국어 요약>`

| type | 용도 |
|---|---|
| `feat` | 기능 추가 |
| `fix` | 버그 수정 |
| `chore` | 빌드 · compose · 설정 · 의존성 |
| `docs` | 문서 |
| `refactor` | 동작 변경 없는 구조 개선 |
| `test` | 테스트 |

예: `feat: payment-service 결제 멱등키 처리 추가`

## 서비스 경계 규율

- **DB per service (스키마 단위)**: 자기 스키마만 접근한다. 타 서비스 스키마로의 JDBC 연결·조인·FK는 금지. 데이터가 필요하면 gRPC 호출 또는 이벤트 구독으로 가져온다.
- **JPA 연관관계는 ID 참조**: 서비스 간은 물론, 향후 분리 가능성이 있는 애그리거트 간에도 객체 참조 대신 ID를 든다.
- **동기 호출은 gRPC + 서킷브레이커**: REST는 Gateway ↔ 서비스 구간만. 서비스 간 동기 호출은 gRPC로 하고 Resilience4J를 반드시 붙인다. gRPC도 서비스 토큰을 싣고 서버는 인터셉터로 검증한다 (D-34).
- **서킷브레이커는 "상대가 건강한가"만 센다** (D-17·D-34): 원격이 요청을 받아 판단하고 돌려준 결과(`NOT_FOUND`, `UNAUTHENTICATED`)는 `ignoreExceptions`로 집계에서 뺀다. 이걸 실패로 세면 잘못된 요청이나 우리 쪽 설정 오류로 멀쩡한 서비스의 서킷이 열리고, 진짜 원인이 "서킷 열림" 로그에 묻힌다. **집계에서 뺀다고 통과시키는 것은 아니다** — 결제가 걸린 흐름은 여전히 fail-closed(D-18).
- **HTTP 엔드포인트는 gateway를 거친 요청만 받는다** (D-33): `common-security` 모듈을 의존하면 자동으로 적용된다. 서비스에 새 컨트롤러를 추가할 때 따로 할 일은 없다. 토큰 없이 열어야 하는 경로(actuator 등)가 생기면 모듈 쪽 `SecurityFilterChain`에 모아 둔다 — 서비스마다 예외를 두면 어디가 열려 있는지 추적할 수 없다.
- **비동기는 Outbox 경유**: 도메인 이벤트를 RabbitMQ에 직접 발행하지 않는다. 반드시 로컬 트랜잭션으로 outbox에 쓰고 릴레이가 발행한다.

## Outbox 규칙

- **구현은 `common-outbox` 모듈을 쓴다** (D-30). 서비스마다 복사하지 않는다.
  - `settings.gradle`에 `includeBuild '../common-outbox'`, `build.gradle`에 `implementation 'com.lcs:common-outbox:0.0.1-SNAPSHOT'`
  - 빈은 자동 등록된다. 발행하는 서비스는 `@EnableScheduling`과 `outbox.relay.exchange` 설정만 추가하면 된다.
  - 이벤트를 소비만 하는 서비스는 `outbox.relay.enabled=false`로 릴레이를 끈다.
- 테이블명 `outbox`, 서비스마다 자기 스키마에 소유.
- 필수 컬럼: `id(UUID)`, `aggregate_type`, `aggregate_id`, `event_type`, `payload(JSON)`, `created_at`, `published_at(null=미발행)`
- 릴레이는 `@Scheduled`로 `published_at IS NULL` 을 폴링, RabbitMQ publisher confirm 수신 후 마킹.
- 소비자는 **멱등하게** 구현한다 — 같은 이벤트가 두 번 와도 결과가 같아야 한다 (at-least-once 전제).

## gRPC proto 소유권

- 계약 원본은 **제공(서버) 서비스의 `src/main/proto`**.
- 호출(클라이언트) 서비스는 복사본을 가진다.
- 원본을 변경하는 PR은 소비 측 복사본 갱신을 **같은 PR**에 포함한다.
- 하위 호환을 깨는 변경(필드 번호 재사용·삭제)은 금지. 새 필드는 추가만.

## 이벤트 네이밍

- 형식: `<Aggregate><과거형동사>` — 예: `SubscriptionCreated`, `PaymentCompleted`, `PaymentFailed`
- exchange: `<service>.events` (topic), routing key: `<aggregate>.<event>` 소문자
  - 예: `subscription.events` / `subscription.created`

## 설정

- 서비스 로컬 `application.yml`에는 부트스트랩 최소값만 (이름, config-server 주소).
- 나머지 설정은 전부 `config-repo/<service>.yml` 중앙 관리.
- 비밀값(DB 비밀번호, MinIO 키)은 커밋하지 않는다 — 환경변수 또는 `.env`(gitignore) 주입.

## 언어 · 문서

- 커밋 메시지 · 문서 · PR 본문은 한국어.
- 구조에 영향을 주는 결정은 [DECISIONS.md](DECISIONS.md)에 항목 추가 후 작업한다.
