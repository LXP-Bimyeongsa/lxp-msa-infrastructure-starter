# Project Structure

> **현재 폴더 구조** (2026-07-20 기준). 배경은 [DECISIONS.md](DECISIONS.md).

## 저장소 루트

```text
lxp-msa-infrastructure-starter/
├─ gateway/                  # JWKS 검증 · introspection · 라우팅 · 서비스 토큰 부착
├─ config-server/            # Spring Cloud Config (native, config-repo 서빙)
├─ member-service/           # MySQL(member_db) · 회원 프로필 + gRPC 서버  ← auth-service 흡수
├─ course-service/           # MongoDB(course_db) 메타·URL + MinIO 동영상
├─ subscription-service/     # MySQL(subscription_db) · 사가 시작점
├─ payment-service/          # MySQL(payment_db) · 결제 · 멱등키 · 정기결제
│
├─ common-outbox/            # Outbox 공통 모듈 (D-30) — member·subscription·payment가 링크
├─ common-security/          # 서비스 토큰 검증 공통 모듈 (D-33) — 5개 서비스가 링크
│
├─ config-repo/              # config-server가 서빙하는 중앙 설정
├─ infrastructure/
│  ├─ prometheus/            # 스크레이프 대상 정의
│  ├─ grafana/
│  ├─ loki/
│  ├─ alloy/                 # 로그 파일 → Loki (OTLP 변환은 미적용, D-15)
│  ├─ keycloak/              # realm-lxp.json (D-20)
│  ├─ mock-pg/               # WireMock 매핑 — 목 PG (D-39)
│  ├─ logs/                  # 전 서비스 로그 볼륨 마운트 지점 (Alloy 수집 대상)
│  ├─ mysql/init/            # 서비스별 스키마·계정 생성 SQL
│  ├─ mongo/init/            # ReplicaSet 초기화 (별도 잡에서 실행, D-29)
│  ├─ minio/init/            # 버킷 생성 스크립트 (course-videos)
│  └─ rabbitmq/              # definitions.json (exchange·queue 선언)
├─ ci/
│  ├─ Jenkinsfile            # 변경 서비스만 빌드·테스트 → 이미지 빌드
│  ├─ Dockerfile             # docker CLI를 얹은 Jenkins 이미지 (D-38)
│  ├─ jenkins.yaml           # JCasC — 잡·플러그인·보안 (D-40)
│  ├─ plugins.txt
│  └─ README.md
│
├─ .github/                  # PR·이슈 템플릿
├─ docs/                     # 아키텍처 · 결정 기록 · 컨벤션 · 작업 로그
├─ .env.example              # 포트 충돌 회피용 환경변수 예시
├─ compose.yaml              # 전체 스택 (compose.data.yaml을 include)
├─ compose.infra.yaml        # consul + 관측성
├─ compose.data.yaml         # mysql · mongo · minio · rabbitmq · mock-pg
└─ compose.ci.yaml           # jenkins
```

- 각 서비스는 자체 `settings.gradle` / `build.gradle` / `gradlew` / `Dockerfile`을 가진 완전 독립 프로젝트다. 루트에는 빌드 설정을 두지 않는다.
- `common-*` 모듈은 Gradle **컴포지트 빌드**(`includeBuild`)로 링크한다 (D-30). 소비 서비스의 빌드 설정을 상속하지 않으므로 인코딩 등은 각자 지정해야 한다.
- `auth-service/`는 member-service에 흡수돼 **제거 완료**다 (D-04·D-38).

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
│  │     ├─ messaging/        # RabbitMQ 이벤트 리스너
│  │     ├─ scheduler/        # @Scheduled 작업 (payment의 정기결제 등)
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
- Outbox는 서비스 안에 두지 않는다 — `common-outbox` 컴포지트 빌드로 주입된다 (D-30).

## 포트 맵

| 대상 | 포트 | 비고 |
|---|---|---|
| API Gateway | 8080 | 단일 진입점 |
| member-service | 8082 | 8081은 auth 흡수로 폐기 |
| member-service (gRPC) | 9092 | subscription-service가 호출 (D-19) |
| course-service | 8083 | |
| subscription-service | 8084 | |
| payment-service | 8085 | |
| config-server | 8888 | |
| **Keycloak** | **8180** | 컨테이너 8080 → 호스트 8180. issuer는 외부 주소, JWKS는 내부 주소 |
| **목 PG (WireMock)** | **8090** | 컨테이너 8080 → 호스트 8090 (D-39) |
| Consul | 8500 | 3노드 (`bootstrap-expect=3`) |
| MySQL | 3306 | 스키마: member_db · subscription_db · payment_db. **호스트 충돌 시 `.env`의 `MYSQL_PORT`로 변경** |
| MongoDB | 27017 | course_db |
| MinIO | 9000 / 9001 | API / 콘솔 |
| RabbitMQ | 5672 / 15672 | AMQP / 관리 UI |
| Jenkins | 9080 | 컨테이너 내부 8080 → 호스트 9080 (gateway와 충돌 회피) |
| Prometheus | 9090 | |
| Grafana | 3000 | |
| Loki | 3100 | |
| Zipkin | 9411 | 인메모리 저장소 — 상한·재시작 정책 적용 (D-44) |
| Alloy | 12345 | |

## compose 실행 조합

| 상황 | 명령 |
|---|---|
| 서비스 개발 기본 | `docker compose -f compose.infra.yaml -f compose.data.yaml up -d` + IDE에서 config-server·해당 서비스 실행 |
| 사가/이벤트 작업 | 위 + rabbitmq (compose.data.yaml에 포함) |
| CI 학습 | `docker compose -f compose.ci.yaml up -d` |
| 전체 통합 검증 | `docker compose up --build` |

메모리 참고: 전체 스택은 컨테이너 **22개**다 — 서비스 JVM 6 + Keycloak + Consul 3 + 데이터·메시징 5(mysql·mongo·minio·rabbitmq·mock-pg) + 관측 5(prometheus·grafana·loki·alloy·zipkin) + 일회성 init 2(mongo-init·minio-init). 여기에 Jenkins(`compose.ci.yaml`)를 더하면 23개이고, 상시 실행은 init 2개를 뺀 21개다. 전체 동시 기동은 12GB↑를 쓰므로 개발 중에는 필요한 조합만 기동한다 (D-14).
