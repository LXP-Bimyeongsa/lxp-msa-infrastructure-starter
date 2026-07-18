# payment-service

결제 도메인 서비스. `subscription-service`에 임시 통합돼 있던 payment 도메인을 분리한 서비스입니다.

- Port: `8085`
- Application: `com.lcs.payment.PaymentServiceApplication`
- Health: `http://localhost:8085/actuator/health`
- DB: MySQL `payment_db` (예정)

## 책임

- 결제 처리와 상태 관리
- **멱등키** 기반 중복 결제 방지 — 사가 이벤트는 at-least-once라 같은 결제 요청이 두 번 올 수 있습니다.
- 구독 결제 사가에서 `SubscriptionCreated`를 소비하고 `PaymentCompleted` / `PaymentFailed`를 발행

## 패키지 구조

```text
com.lcs.payment
├─ presentation/        REST 컨트롤러
├─ application/         유스케이스 · 사가 이벤트 핸들러
├─ domain/              엔티티 · 도메인 이벤트
└─ infrastructure/
   ├─ persistence/      JPA 리포지토리 구현
   ├─ outbox/           Outbox 엔티티 + @Scheduled 릴레이
   └─ grpc/             gRPC 서버/클라이언트
```

`src/main/proto`에는 이 서비스가 **제공하는** gRPC 계약 원본을 둡니다. 호출하는 쪽은 복사본을 가집니다.

## 실행

```bash
# 도커
docker compose up --build consul-1 consul-2 consul-3 config-server payment-service

# IDE
# 1. docker compose -f compose.infra.yaml up -d
# 2. ConfigServerApplication 실행
# 3. PaymentServiceApplication 실행
```

## 현재 상태

골격만 있는 상태입니다. 도메인 코드와 API는 아직 없습니다.
진행 상황은 [docs/NEXT_STEPS.md](../docs/NEXT_STEPS.md) Step 1·4 참고.
