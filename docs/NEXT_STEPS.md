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

- [ ] member-service: 회원 가입·로그인·JWT 발급 / Gateway JWT 검증
- [ ] course-service: 강의 메타 CRUD + MinIO Presigned URL 발급 (D-07)
- [ ] subscription-service ↔ payment-service 사가 (Outbox → RabbitMQ 코레오그래피)
- [ ] 회원탈퇴 사가: member-service → subscription-service 구독해지 (P-04 범위 확정 후)
- [ ] payment-service 멱등키 처리
- [ ] gRPC 계약 정의 + Resilience4J 서킷브레이커

## Step 5 — 관측 · 검증

- [ ] Alloy OTLP→Zipkin 변환 설정 (D-15)
- [ ] Grafana 대시보드 + Slack Alerting
- [ ] Swagger/OpenAPI 추가
- [ ] HA 검증: RabbitMQ ×3 Quorum, MongoDB RS ×3, Consul 3노드 (`ha` 프로파일)
- [ ] Chaos Monkey 장애 주입 (P-03)
