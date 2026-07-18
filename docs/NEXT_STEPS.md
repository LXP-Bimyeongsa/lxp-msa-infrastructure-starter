# Next Steps

> 단계마다 별도 브랜치 → PR → 리뷰 → 머지. 자세한 배경은 [DECISIONS.md](DECISIONS.md).

## Step 1 — 서비스 골격 재편

- [ ] payment-service 신규 생성 (8085, MySQL `payment_db`)
- [ ] auth-service를 member-service로 흡수 후 폴더 제거 (D-04)
- [ ] 전 서비스 패키지 구조 통일: `presentation / application / domain / infrastructure(persistence·outbox·grpc)`
- [ ] 서비스별 build.gradle 의존성 정리 (JPA/Mongo, gRPC, Resilience4J, AMQP)
- [ ] config-repo에 payment-service.yml 추가, gateway 라우팅에 `/api/payments/**` → payment-service 반영

## Step 2 — 데이터 · 메시징 인프라

- [ ] `compose.data.yaml` 작성: MySQL(단일, 스키마 3개) · MongoDB(단일노드 RS) · MinIO · RabbitMQ(1노드)
- [ ] `infrastructure/mysql/init/` 스키마 생성 SQL
- [ ] `infrastructure/mongo/init/` ReplicaSet 초기화 스크립트
- [ ] `infrastructure/minio/init/` 버킷 생성 (course-videos)
- [ ] `infrastructure/rabbitmq/definitions.json` — exchange·queue 선언
- [ ] Consul 개발 모드 1노드 전환 검토 (P-02)

## Step 3 — CI (Jenkins)

- [ ] `compose.ci.yaml` — Jenkins 컨테이너 (호스트 9080)
- [ ] `ci/Jenkinsfile` — 변경된 서비스만 빌드·테스트 → Docker 이미지 빌드
- [ ] 로컬 Jenkins ↔ GitHub 연동 (webhook은 공인 IP 없으므로 폴링 방식으로 시작)

## Step 4 — 도메인 구현

- [x] member-service 회원 영속성 + 가입 API
- [x] subscription-service ↔ payment-service 사가 (Outbox → RabbitMQ 코레오그래피)
- [x] payment-service 멱등키 처리
- [x] gRPC 계약 정의 + Resilience4J 서킷브레이커 (subscription → member, D-17)
- [x] course-service: 강의 메타 CRUD + MinIO Presigned URL 발급 (D-07)
- [x] 정기 결제 스케줄러 (D-25~D-27)
- [x] **Keycloak 이관** (D-20): 자체 JWT 발급 제거, gateway JWKS 검증, `password_hash` 삭제
- [x] **Outbox 구현 공통화** (D-30): `common-outbox` 모듈 + 컴포지트 빌드
- [x] **회원탈퇴 사가** (D-31): member → subscription 구독해지 → 환불(D-16)
- [x] **탈퇴 회원 인증 차단** (D-32): Keycloak 계정 비활성화 + 토큰 수명 300초
- [x] **서비스 간 호출 시 서비스 토큰 검증** (D-33): REST 경로 — gateway 우회 차단
- [x] **gRPC에도 서비스 토큰** (D-34) — 자격증명 거절은 서킷 집계 제외 + fail-closed
- [x] **탈퇴 회원의 잔여 access token 차단** (D-35) — introspection + 30초 캐시
- [ ] 재생 URL 구독 여부 확인 (course → subscription, D-17 재검토 필요)
- [ ] 정기 결제 재시도(dunning) 정책 (P-15)
- [ ] README 스모크 절차 갱신 (인증이 Keycloak으로 바뀜)

## Step 5 — 관측 · 검증

- [ ] Alloy OTLP→Zipkin 변환 설정 (D-15)
- [ ] Grafana 대시보드 + Slack Alerting
- [ ] Swagger/OpenAPI 추가
- [ ] HA 검증: RabbitMQ ×3 Quorum, MongoDB RS ×3, Consul 3노드 (`ha` 프로파일)
- [ ] Chaos Monkey 장애 주입 (P-03)
