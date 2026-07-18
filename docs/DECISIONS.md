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
