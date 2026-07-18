# Conventions

## 브랜치 · PR

- `main`은 보호 브랜치: **PR + 승인 1명** 없이는 머지 불가 (Organization admin만 bypass).
- 브랜치 이름: `feat/<주제>`, `chore/<주제>`, `docs/<주제>`, `fix/<주제>`
  - 예: `feat/payment-service-skeleton`, `chore/compose-split`
- PR 작성자는 자기 PR을 승인할 수 없다 → 팀원 간 상호 리뷰.
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
- **동기 호출은 gRPC + 서킷브레이커**: REST는 Gateway ↔ 서비스 구간만. 서비스 간 동기 호출은 gRPC로 하고 Resilience4J를 반드시 붙인다.
- **비동기는 Outbox 경유**: 도메인 이벤트를 RabbitMQ에 직접 발행하지 않는다. 반드시 로컬 트랜잭션으로 outbox에 쓰고 릴레이가 발행한다.

## Outbox 규칙

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
