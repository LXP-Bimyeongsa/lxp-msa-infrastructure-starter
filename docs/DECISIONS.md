# Decision Log

> 구조에 영향을 주는 결정과 그 이유를 기록한다. 뒤집을 때는 새 항목으로 추가하고 이전 항목에 링크한다.

| # | 날짜 | 결정 | 이유 | 대안(기각) |
|---|---|---|---|---|
| D-01 | 2026-07-18 | 팀 레포(`LXP-Bimyeongsa`)로 이전, 커밋 히스토리 없이 초기 커밋 1개로 시작 | 원본(llllxxxxpppp)은 개인 학습 이력이라 팀 레포는 깨끗하게 출발 | 히스토리 유지 push |
| D-02 | 2026-07-18 | `main` 보호: PR + 승인 1명 필수, Organization admin만 bypass | 팀장 단독 push 허용 + 팀원 상호 리뷰 강제 | 전원 직접 push |
| D-03 | 2026-07-18 | payment-service를 subscription-service에서 분리 | 사가 코레오그래피는 서비스가 분리돼야 성립. 구조도 기준 확정 | 임시 통합 유지 |
| D-04 | 2026-07-18 | auth-service를 member-service에 흡수 (JWT 발급 = member, 검증 = Gateway) | 구조도에 auth가 없음. 컨테이너 1개 절약 | 별도 auth-service 존치 — 인증 학습 필요 시 재분리 가능 |
| D-05 | 2026-07-18 | CI = Jenkins | 학습 목적. Public 레포라 GitHub Actions가 더 편하지만 Jenkins 경험이 우선 | GitHub Actions |
| D-06 | 2026-07-18 | 파일 저장 = MinIO (S3 호환 API) | 무료·로컬 도커 실행. SDK 동일해 추후 endpoint만 바꿔 S3 전환 가능 | Amazon S3 — 카드 등록·과금 발생 |
| D-07 | 2026-07-18 | 동영상 업로드는 Presigned URL 방식 | 파일이 서비스 JVM을 통과하지 않아 대용량 트래픽에 안전. course-service는 메타·URL만 저장 | 서비스 경유 업로드 |
| D-08 | 2026-07-18 | DB 매핑: course=MongoDB, member/subscription/payment=MySQL | 강의는 문서형(메타+URL), 나머지는 관계·트랜잭션 중심 | 전부 MySQL |
| D-09 | 2026-07-18 | MySQL 단일 컨테이너 + 서비스별 스키마(`member_db` 등) 분리 | 로컬 메모리 한계. DB per service는 "타 스키마 접근 금지" 규율로 유지 | 서비스별 MySQL 인스턴스 — 노트북에서 감당 불가 |
| D-10 | 2026-07-18 | MongoDB 단일 노드 ReplicaSet | 단일 노드여도 RS 초기화 시 다중 문서 트랜잭션 동작. 3노드는 HA 검증 시에만 | 3노드 상시 기동 |
| D-11 | 2026-07-18 | Outbox 릴레이 = 각 서비스 내부 `@Scheduled` | 외부 릴레이 서비스는 타 서비스 DB 직접 접근 필요 → DB per service 위반. Debezium+RabbitMQ는 Debezium Server 추가로 구성 복잡 | 별도 message-relay 서비스 / Debezium CDC |
| D-12 | 2026-07-18 | gRPC proto = 각 서비스 자체 보유 | 서비스 완전 독립 원칙 유지. **계약 원본은 제공 서비스가 소유, 호출 측은 복사본** — 변경 시 양쪽 동기화 필수 | 루트 `contracts/` 공유 — 동기화 부담 커지면 전환 |
| D-13 | 2026-07-18 | 사가 = 코레오그래피 (RabbitMQ 이벤트) | 구조도 기준. 서비스 2개 수준에서는 오케스트레이터가 과함 | 오케스트레이션 |
| D-14 | 2026-07-18 | compose를 용도별 분리: `infra` / `data` / `ci` / 전체 | 25개 컨테이너 동시 기동은 12~16GB RAM 필요 → 개발 시 필요한 조합만 기동 | 단일 compose 전체 기동 |
| D-15 | 2026-07-18 | 트레이싱 = Zipkin 유지, Alloy에서 OTLP→Zipkin 변환 | 기존 compose에 이미 구성됨. Zipkin은 OTLP 네이티브 수신 불가하므로 Alloy가 변환 | Tempo — Grafana 스택과 더 자연스럽지만 교체 비용 |
| D-16 | 2026-07-18 | 구독 해지 시 환불 포함: 해지 → `SubscriptionCancelled` → payment가 소비해 환불(REFUNDED) → `PaymentRefunded` 발행 | 해지와 환불이 항상 짝이므로 사가에 포함. 보상 실패는 재시도(멱등) → DLQ → 운영자 개입 | 환불을 수동 운영 처리로 분리 |
| D-18 | 2026-07-18 | 회원 확인 실패 시 **fail-closed** (503 반환, 구독 생성 거부) | 확인 없이 통과시키면 없는/탈퇴 회원의 구독이 생기고 뒤이어 결제까지 진행돼 되돌리기 어렵다. 결제가 걸린 흐름은 가용성보다 정합성 | fail-open(경고 로그 후 통과) |
| D-19 | 2026-07-18 | gRPC 주소는 Consul 메타데이터(`grpc-port`)로 전파, 채널은 대상별 재사용 | HTTP 포트와 gRPC 포트가 다르므로 디스커버리만으로는 부족. 로드밸런싱이 필요해지면 gRPC name resolver로 교체 | 정적 호스트 설정 / gRPC name resolver 즉시 도입 |
| D-20 | 2026-07-18 | **인증을 Keycloak(OIDC)으로 이관.** 발급·자격증명 = Keycloak, 도메인 프로필 = member-service(`sub`로 연결) | 비밀번호 재설정·MFA·소셜 로그인을 직접 구현하지 않는다. MSA에서 IdP를 분리하는 표준 구성을 학습 | 자체 JWT 발급 유지(D-04) — 대체됨 |
| D-21 | 2026-07-18 | D-04의 JWT 발급 코드는 **머지 후 Keycloak PR에서 교체**. `X-Member-Id` 헤더 규약은 유지 | #16·#17이 이 헤더에 의존하므로 지금 제거하면 사가·gRPC가 깨진다. 검증 지점이 gateway 한 곳이라 내부 구현만 갈아끼우면 된다 | #15를 닫고 재작성 — 스택이 깨져 기각 |
| D-22 | 2026-07-18 | **OpenTelemetry·Tempo 도입하지 않음.** Zipkin + Prometheus + Loki + Alloy 유지 | Tempo는 Zipkin의 대체재지 추가 기능이 아니다. 6개 서비스의 tracing 의존성을 교체할 만한 이득이 없다. traceId 로그 상관관계는 이미 동작 | OTel + Tempo 전환 |
| D-23 | 2026-07-18 | **External Secrets 도입하지 않음.** `.env` + gitignore 유지 | 쿠버네티스 전용 오퍼레이터라 Docker Compose에서는 설치 자체가 불가능. K8s 전환은 별도 결정 사항 | K8s 전환 후 도입 / Vault + Spring Cloud Vault |
| D-24 | 2026-07-18 | **ELB는 다이어그램에 "운영 구성"으로 표기만.** 로컬 스택에는 두지 않음 | 붙일 배포 대상(EC2/EKS)이 아직 없고, 실제 도입은 EC2 배포 파이프라인 구축(약 3일)과 월 $140 과금을 수반 | 실제 ALB 프로비저닝 / 로컬 nginx로 대체 |
| D-25 | 2026-07-18 | **정기 결제 도입.** 결제 스케줄을 payment-service가 소유하고 스케줄러도 payment-service가 돌린다 | 최종 구조도가 `Scheduler → payment service`와 payment DB의 `UNIQUE(subscriptionId, billingCycle)`를 명시. 스케줄을 subscription이 갖고 있으면 payment가 매번 되물어야 해 동기 호출이 생긴다 | subscription-service가 스케줄 소유 후 갱신 이벤트 발행 |
| D-26 | 2026-07-18 | 정기 결제 멱등키 = `(subscriptionId, billingCycle)` unique 제약 | 구조도 명시. 스케줄러가 다중 인스턴스로 돌거나 재실행돼도 같은 회차는 한 번만 청구된다. 이벤트 UUID 멱등키로는 "같은 회차의 다른 시도"를 막지 못한다 | 이벤트 ID만으로 멱등 처리 |
| D-27 | 2026-07-18 | 해지 시 예약된 다음 결제를 즉시 취소 | 해지했는데 스케줄이 남아 있으면 다음 주기에 청구된다. `SubscriptionCancelled` 소비 시 환불(D-16)과 함께 스케줄도 정리한다 | 스케줄 만료를 기다림 |
| D-17 | 2026-07-18 | 서킷브레이커 = subscription → member gRPC 하나로 시작 | payment → subscription 동기 호출은 만들지 않는다 — `SubscriptionCreated` 이벤트에 필요한 데이터(plan·amount·memberId)를 전부 실어 보내므로(event-carried state transfer) 되물을 일이 없음. 동기 호출을 추가하면 이벤트로 끊은 결합을 다시 묶는 셈 | payment→subscription 동기 조회 |

## 미결

| # | 항목 | 상태 |
|---|---|---|
| P-01 | PG사 연동 (실키는 사업자등록 필요) | 테스트 모드/Mock으로 시작, 실연동 시점 미정 |
| P-02 | Consul 개발 모드 노드 수 (현재 3노드 `bootstrap-expect=3`) | D-14에 맞춰 1노드 개발 모드 전환 검토 |
| P-03 | Chaos Monkey 적용 시점 | 사가·서킷브레이커 구현 완료 후 |
| ~~P-04~~ | 회원탈퇴 사가 범위 | **부분 확정(D-16)**: 해지 시 환불 포함. member.events 큐 정의는 회원탈퇴 사가 구현 시 |
| ~~P-05~~ | 서킷브레이커 대상 | **확정(D-17)**: subscription → member gRPC 하나 |
| P-06 | Config Server 백엔드 | 현재 config-repo 디렉터리 native. 다이어그램은 git 소스로 표기 — git 백엔드 전환 여부 |
| P-07 | 배포 대상 (EC2 / EKS / 로컬) | 미정. ELB 실제 도입(D-24)의 전제. EC2+compose 약 3일, EKS 1~2주 |
| P-08 | ELB 도입 시 필수 대응 | 헬스체크 경로를 `/actuator/health`로 지정(기본 `/`는 404라 정상 인스턴스를 죽은 것으로 판단), gateway에 `forward-headers-strategy: framework`(미설정 시 클라이언트 IP가 전부 ELB IP로 기록됨) |
| P-09 | Keycloak issuer URL 통일 | 토큰의 `iss`는 클라이언트 접속 주소 기준인데 gateway는 내부 주소로 검증하려 든다. `KC_HOSTNAME`과 gateway `issuer-uri`를 외부 주소 하나로 맞추지 않으면 401만 반복된다 |
| P-11 | **서비스 간 호출 시 서비스 토큰 검증** (Gateway 우회 차단) | 최종 구조도 신규 항목. 현재는 다운스트림이 `X-Member-Id` 헤더를 그대로 신뢰하므로, 네트워크에 접근 가능한 누구나 gateway를 건너뛰고 서비스를 직접 호출할 수 있다. Keycloak client credentials 방식이 자연스러움 → D-20 이후 |
| P-12 | Message Relay 표기 | 구조도는 별도 컴포넌트로 그렸으나 구현은 각 서비스 내부 릴레이(D-11). 외부 릴레이는 4개 서비스 DB에 모두 접속해야 해 DB per service·MySQL 계정 격리와 충돌. **구현은 D-11 유지**, 그림을 "각 서비스 내부 릴레이"로 읽는다 |
| P-13 | inbox 패턴 도입 여부 | 구조도의 `in/out box` 중 inbox는 미구현. 현재 중복 소비는 payment 멱등키 + subscription 상태 확인으로 방어. inbox 테이블을 실제로 둘지 미정 |
| P-14 | MySQL Replication ×3 / RabbitMQ ×3 Quorum / Mongo RS ×3 | 구조도의 운영 목표. 현재는 전부 단일 노드(D-09·D-10·D-14). 컨테이너 +8개 규모라 HA 검증 단계에서 별도 프로파일로 |
| P-10 | Keycloak ↔ member_db 가입 정합성 | Keycloak 사용자 생성과 member_db 프로필 생성은 두 시스템에 걸친 쓰기다. 한쪽만 성공하는 경우의 보상 처리 필요 |
