# Next Steps

> 단계마다 별도 브랜치 → PR → 리뷰 → 머지. 자세한 배경은 [DECISIONS.md](DECISIONS.md).

## Step 1 — 서비스 골격 재편 ✅

- [x] payment-service 신규 생성 (8085, MySQL `payment_db`)
- [x] auth-service를 member-service로 흡수 후 폴더 제거 (D-04)
- [x] 전 서비스 패키지 구조 통일: `presentation / application / domain / infrastructure(persistence·messaging·grpc)`
- [x] 서비스별 build.gradle 의존성 정리 (JPA/Mongo, gRPC, Resilience4J, AMQP)
- [x] config-repo에 payment-service.yml 추가, gateway 라우팅에 `/api/payments/**` → payment-service 반영

## Step 2 — 데이터 · 메시징 인프라 ✅

- [x] `compose.data.yaml` 작성: MySQL(단일, 스키마 3개) · MongoDB(단일노드 RS) · MinIO · RabbitMQ(1노드)
- [x] `infrastructure/mysql/init/` 스키마 생성 SQL
- [x] `infrastructure/mongo/init/` ReplicaSet 초기화 스크립트 (D-29 — initdb.d가 아니라 별도 잡)
- [x] `infrastructure/minio/init/` 버킷 생성 (course-videos)
- [x] `infrastructure/rabbitmq/definitions.json` — exchange·queue 선언
- [ ] Consul 개발 모드 1노드 전환 검토 (P-02) — 현재 3노드 `bootstrap-expect=3`

## Step 3 — CI (Jenkins)

- [x] `compose.ci.yaml` — Jenkins 컨테이너 (호스트 9080)
- [x] `ci/Jenkinsfile` — 변경된 서비스만 빌드·테스트 → Docker 이미지 빌드
- [x] **로컬 Jenkins ↔ GitHub 폴링 연동** (D-40) — 5분 주기, JCasC로 정의

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
- [x] **재생 URL 구독 확인** (D-36) — 이벤트 복제 읽기 모델, 동기 호출 없음
- [x] **정기 결제 재시도(dunning)** (D-37) — 기본 3일 간격 3회, 설정으로 조정
- [x] **PG 연동 경계 + 목 PG 컨테이너** (D-39) — 승인번호 보관, 환불 시 PG 취소 호출
- [x] README 스모크 절차 갱신 (인증이 Keycloak으로 바뀜)

## Step 5 — 안정화 (2026-07-19 ~ 20)

CI를 실제로 돌리고 실행 중인 스택을 관찰하면서 나온 것들이다.

- [x] **중복 회차 스킵이 정기 결제를 영구 중단시키던 버그** (D-41)
- [x] **예외 원인이 로그에 남지 않던 곳 5건** — gateway·member·course·subscription·payment
- [x] **MinIO 오류를 전부 "객체 없음"으로 삼키던 것** (D-42)
- [x] **죽은 인스턴스로 라우팅되던 것** (D-43) — `query-passing` 기본값이 false였다
- [x] **Zipkin OOM + 죽은 채 방치** (D-44) — 메모리 상한·재시작 정책·헬스체크

## Step 6 — 관측 · 검증

- [ ] Alloy OTLP→Zipkin 변환 설정 (D-15) — 현재는 서비스가 Zipkin에 직접 전송
- [ ] Grafana 대시보드 + Slack Alerting
- [ ] Swagger/OpenAPI 추가
- [ ] Gateway Rate Limit (문서에만 있고 미구현)
- [ ] 나머지 컨테이너 재시작 정책·헬스체크 (P-20)
- [ ] HA 검증: RabbitMQ ×3 Quorum, MongoDB RS ×3, Consul 3노드 (`ha` 프로파일, P-14)
- [ ] Chaos Monkey 장애 주입 (P-03)

## Step 7 — 배포 (결정 필요)

- [ ] **배포 대상 확정** (P-07) — EC2 + compose 약 3일 / EKS 1~2주
- [ ] ELB 도입 시 대응 (P-08) — 헬스체크 경로, `forward-headers-strategy`
- [ ] PG 실연동 (P-01) — 사업자등록 후 실키 발급 필요
