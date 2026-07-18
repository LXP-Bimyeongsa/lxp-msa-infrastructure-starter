# Project Structure

> 목표 폴더 구조. `[신규]`는 아직 없는 것, 나머지는 기존 유지·수정.

## 저장소 루트

```text
lxp-msa-infrastructure-starter/
├─ gateway/                  # JWT 검증 · 라우팅 · Rate Limit
├─ config-server/            # Spring Cloud Config
├─ member-service/           # MySQL(member_db) · 회원 + 인증(JWT 발급)  ← auth-service 흡수
├─ course-service/           # MongoDB(course_db) 메타·URL + MinIO 동영상
├─ subscription-service/     # MySQL(subscription_db) · 사가 시작점
├─ payment-service/          # MySQL(payment_db) · 결제 · 멱등키        [신규]
│
├─ config-repo/              # config-server가 서빙하는 중앙 설정 (+ payment-service.yml)
├─ infrastructure/
│  ├─ prometheus/            # (기존)
│  ├─ grafana/               # (기존)
│  ├─ loki/                  # (기존)
│  ├─ alloy/                 # (기존) + OTLP→Zipkin 변환 설정
│  ├─ mysql/init/            # 서비스별 스키마 생성 SQL                  [신규]
│  ├─ mongo/init/            # 단일노드 ReplicaSet 초기화               [신규]
│  ├─ minio/init/            # 버킷 생성 스크립트                       [신규]
│  └─ rabbitmq/              # definitions.json (exchange·queue 선언)  [신규]
├─ ci/
│  └─ Jenkinsfile            # 빌드·테스트·이미지 파이프라인             [신규]
│
├─ docs/                     # 아키텍처 · 결정 기록 · 컨벤션
├─ compose.yaml              # 전체 스택
├─ compose.infra.yaml        # consul + 관측성 (기존)
├─ compose.data.yaml         # mysql · mongo · minio · rabbitmq        [신규]
└─ compose.ci.yaml           # jenkins                                 [신규]
```

- 각 서비스는 자체 `settings.gradle` / `build.gradle` / `gradlew` / `Dockerfile`을 가진 완전 독립 프로젝트다. 루트에는 빌드 설정을 두지 않는다.
- `auth-service/` 폴더는 member-service 흡수 완료 후 제거한다 ([DECISIONS.md](DECISIONS.md) D-04).

## 서비스 내부 구조

```text
<service>/
├─ src/main/
│  ├─ java/com/lcs/<svc>/
│  │  ├─ presentation/        # REST 컨트롤러 (기존 관례 유지)
│  │  ├─ application/         # 유스케이스 · 사가 이벤트 핸들러
│  │  ├─ domain/              # 엔티티 · 도메인 이벤트
│  │  └─ infrastructure/
│  │     ├─ persistence/      # JPA/Mongo 리포지토리 구현
│  │     ├─ outbox/           # Outbox 엔티티 + @Scheduled 릴레이
│  │     └─ grpc/             # gRPC 서버/클라이언트
│  ├─ proto/                  # 이 서비스가 "제공"하는 gRPC 계약 원본
│  └─ resources/
│     └─ application.yml      # 부트스트랩 최소 설정 (나머지는 config-repo)
├─ build.gradle
├─ settings.gradle
├─ gradlew / gradlew.bat / gradle/
├─ Dockerfile
└─ README.md                  # 서비스 책임 · 포트 · 이벤트 목록
```

- proto 소유권: **제공하는 서비스의 `src/main/proto`가 원본**, 호출하는 서비스는 복사본을 가진다. 원본 변경 시 소비 측 복사본 갱신은 같은 PR에서 처리한다 (D-12).

## 포트 맵

| 대상 | 포트 | 비고 |
|---|---|---|
| API Gateway | 8080 | 단일 진입점 |
| member-service | 8082 | 8081은 auth 흡수로 폐기 |
| course-service | 8083 | |
| subscription-service | 8084 | |
| payment-service | 8085 | [신규] |
| config-server | 8888 | |
| Consul | 8500 | |
| MySQL | 3306 | 스키마: member_db · subscription_db · payment_db |
| MongoDB | 27017 | course_db |
| MinIO | 9000 / 9001 | API / 콘솔 |
| RabbitMQ | 5672 / 15672 | AMQP / 관리 UI |
| Jenkins | 9080 | 컨테이너 내부 8080 → 호스트 9080 (gateway와 충돌 회피) |
| Prometheus | 9090 | |
| Grafana | 3000 | |
| Loki | 3100 | |
| Zipkin | 9411 | |

## compose 실행 조합

| 상황 | 명령 |
|---|---|
| 서비스 개발 기본 | `docker compose -f compose.infra.yaml -f compose.data.yaml up -d` + IDE에서 config-server·해당 서비스 실행 |
| 사가/이벤트 작업 | 위 + rabbitmq (compose.data.yaml에 포함) |
| CI 학습 | `docker compose -f compose.ci.yaml up -d` |
| 전체 통합 검증 | `docker compose up --build` |

메모리 참고: 전체 동시 기동은 JVM 7개 + 데이터 5개 + 관측 6개 + Jenkins ≈ 12GB↑. 개발 중에는 필요한 조합만 기동한다 (D-14).
