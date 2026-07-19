# LXP MSA Infrastructure Starter

기존 모놀리식 도메인 코드를 옮기기 전에, **MSA 인프라와 독립 서버 골격부터 실행할 수 있도록 만든 프로젝트**입니다.

## 서버 구조

```text
Client
  ↓
Public API Gateway
  ├─ member-service         # 회원 프로필 (인증은 Keycloak, D-20)
  ├─ course-service
  ├─ subscription-service
  └─ payment-service

공통 인프라
  ├─ config-server
  ├─ Consul 3-node
  ├─ Prometheus : CPU, JVM, HTTP 요청 수 같은 메트릭 수집
  ├─ Grafana : 메트릭과 로그를 시각화
  ├─ Loki : 로그 저장
  ├─ Alloy : 서비스 로그를 Loki로 전달
  └─ Zipkin : 분산 트레이싱 저장/조회
```

모든 도메인 서비스는 Gateway를 단일 진입점으로 두고 경로 기반으로 라우팅합니다. `config-server`와 Consul 등 공통 인프라는 Gateway에 노출하지 않고 서비스가 직접 사용합니다.

> 인증·토큰 발급은 **Keycloak(OIDC)** 이 담당합니다(D-20). `member-service`는 도메인 프로필만 소유하고 Keycloak `sub`으로 연결합니다. Gateway가 JWKS로 서명을 검증하고 introspection으로 현재 유효성까지 확인한 뒤(D-35), `X-Member-Id`를 주입하고 서비스 토큰을 붙여 보냅니다(D-33).
> 구독과 결제는 사가 코레오그래피를 위해 `subscription-service`와 `payment-service`로 분리돼 있습니다.
> 배경은 [docs/DECISIONS.md](docs/DECISIONS.md)를 참고하세요.

## 프로젝트 구성

이 프로젝트는 **하나의 저장소 안에 서비스별 하위 프로젝트를 두는 모노레포**입니다. 각 하위 폴더는 자체 `settings.gradle`, `build.gradle`, Gradle Wrapper(
`gradlew`), `Dockerfile`, `src`를 가진 완전히 독립된 프로젝트이며, 각자 자기 폴더 안에서 단독으로 빌드·실행됩니다. **루트에는 빌드 설정을 두지 않습니다.**

```text
lxp-msa-infrastructure-starter
├─ gateway
├─ config-server
├─ member-service         # 회원 + 인증
├─ course-service
├─ subscription-service
├─ payment-service
├─ config-repo            # config-server가 서빙하는 설정 파일
├─ infrastructure         # prometheus·grafana·loki·alloy·mysql·mongo·minio·rabbitmq 설정
├─ ci                     # Jenkinsfile
├─ docs                   # 아키텍처 · 결정 기록 · 컨벤션
├─ compose.infra.yaml     # 공통 인프라(consul·관측성)만 실행
├─ compose.data.yaml      # 데이터·메시징(mysql·mongo·minio·rabbitmq)
├─ compose.ci.yaml        # Jenkins
└─ compose.yaml           # 전체 스택(인프라 + 모든 서비스) 실행
```

서비스별 빌드 설정(의존성, 포트 등)은 각 하위 폴더의 `build.gradle`에 있습니다.

## 사용 버전

- Java 17
- Spring Boot 3.5.15
- Spring Cloud 2025.0.3
- Consul 1.18
- Prometheus 3.1.0

## 실행 방법

모든 도메인 서비스는 **Consul(서비스 디스커버리)** 과 **config-server(중앙 설정)** 에 의존합니다. 따라서 무엇을 실행하든 이 공통 의존성이 함께 떠 있어야 합니다.

> ⚠️ Consul은 `bootstrap-expect=3` 구성이라 **consul-1·2·3 세 노드가 모두** 떠야 리더가 선출됩니다. 하나만 띄우면 서비스가 config-server를 기다리며 멈춥니다.

### 전체 실행

모든 서비스 + 인프라를 Docker로 한 번에 빌드·실행합니다.

```bash
docker compose up --build # 포그라운드
```

```bash
docker compose up --build -d # 백그라운드 
```

처음 실행할 때는 각 프로젝트의 Gradle 의존성을 내려받기 때문에 시간이 걸릴 수 있습니다.

### 특정 서비스만 개발 / 실행

특정 서비스 하나만 개발할 때 사용합니다. 서비스와 공통 의존성(Consul 3노드 + config-server)을 함께 띄웁니다.

**방법 A.도커로 실행**

```bash
# 예: member-service 개발 중인 경우
docker compose up --build consul-1 consul-2 consul-3 config-server member-service
```

여기에도 `-d`를 붙이면 백그라운드로 실행됩니다. (종료는 `docker compose down`)

관측성(Prometheus/Grafana/Zipkin 등)까지 필요하면 목록에 추가합니다.

```bash
docker compose up --build \
  consul-1 consul-2 consul-3 \
  prometheus grafana loki alloy zipkin \
  config-server member-service
```

**방법 B. 서비스만 IntelliJ에서 실행**

코드를 자주 고치는 개발 중에는 IDE로 돌리는 편이 재시작이 빨라 편합니다.

1. Consul·관측성을 도커로 기동합니다.

   ```bash
   docker compose -f compose.infra.yaml up -d
   ```

2. IntelliJ에서 `config-server`와 서비스 폴더를 Gradle 프로젝트로 엽니다. (Gradle JVM: Java 17)

3. `ConfigServerApplication`을 먼저 실행한 뒤, 서비스의 Application 클래스를 실행합니다.

> `compose.infra.yaml`에는 **config-server가 없습니다.** 모든 서비스의 공통 의존성이므로 IntelliJ에서 직접 실행해야 합니다.
> 전체를 IDE에서 띄운다면 `config-server → member → course → subscription → payment → gateway` 순서를 권장합니다.

## 확인 엔드포인트

**서비스** — 서비스는 포트로 직접 확인하고, Gateway 경유 라우팅까지 보려면 실행 목록에 `gateway`를 함께 띄웁니다.

| 담당                   | 직접 확인                                 | Gateway 경유                                |
|----------------------|---------------------------------------|-------------------------------------------|
| gateway              | http://localhost:8080/actuator/health | -                                         |
| member-service       | http://localhost:8082/actuator/health | http://localhost:8080/api/members/ping    |
| member-service (인증)  | http://localhost:8082/actuator/health | http://localhost:8080/api/auth/ping       |
| course-service       | http://localhost:8083/actuator/health | http://localhost:8080/api/courses/ping    |
| subscription-service | http://localhost:8084/actuator/health | http://localhost:8080/api/subscriptions/{id} |
| payment-service      | http://localhost:8085/actuator/health | http://localhost:8080/api/payments/subscriptions/{id} |

> ⚠️ **`/ping`과 회원 가입을 제외한 모든 `/api/**`는 토큰이 필요합니다.** 아래 스모크 테스트를 참고하세요.

## 스모크 테스트

인증은 **Keycloak**이 담당합니다. 토큰을 받아 API를 호출하는 전체 흐름입니다.

```bash
# 1. 가입 — member_db 프로필 + Keycloak 사용자가 함께 생성됩니다 (공개 엔드포인트)
curl -X POST http://localhost:8080/api/members \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@lxp.dev","password":"password1234","name":"Demo"}'

# 2. Keycloak에서 토큰 발급 (gateway가 아니라 Keycloak으로 직접)
TOKEN=$(curl -s -X POST http://localhost:8180/realms/lxp/protocol/openid-connect/token \
  -d "client_id=lxp-web" -d "grant_type=password" \
  -d "username=demo@lxp.dev" -d "password=password1234" \
  | sed 's/.*"access_token":"\([^"]*\)".*/\1/')

# 3. 토큰 없이 접근 → 401
curl -i http://localhost:8080/api/subscriptions/1

# 4. 구독 생성 → 사가 시작 (PENDING)
curl -X POST http://localhost:8080/api/subscriptions \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"plan":"BASIC"}'

# 5. 몇 초 뒤 ACTIVE로 바뀌고 결제가 APPROVED로 남습니다
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/subscriptions/1
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/payments/subscriptions/1
```

```bash
# 6. 탈퇴 — 구독 해지와 환불이 사가로 이어집니다 (D-31)
curl -X DELETE http://localhost:8080/api/members/me -H "Authorization: Bearer $TOKEN"

# 7. 몇 초 뒤 살아 있던 구독이 전부 CANCELLED, 결제는 REFUNDED가 됩니다
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/subscriptions/1

# 8. 탈퇴하면 Keycloak 계정이 비활성화돼 새 토큰을 받지 못합니다 (D-32)
curl -X POST http://localhost:8180/realms/lxp/protocol/openid-connect/token \
  -d "client_id=lxp-web" -d "grant_type=password" \
  -d "username=demo@lxp.dev" -d "password=password1234"
# => {"error":"invalid_grant","error_description":"Account disabled"}
```

> 이미 발행된 access token은 만료까지 유효합니다. JWT 검증이 상태를 보지 않기 때문이고,
> 노출 상한은 realm의 `accessTokenLifespan`(300초)입니다. 완전 차단은 P-11에서 다룹니다.

> 한글이 든 JSON을 Git Bash에서 `curl -d`로 보내면 CP949로 인코딩돼 400이 납니다.
> UTF-8 파일에 담아 `--data-binary @file`로 보내세요.

**서비스 직접 호출은 막혀 있습니다** (D-33). 다운스트림은 gateway가 붙인 서비스 토큰을 요구합니다.

```bash
# gateway를 건너뛰고 직접 호출 → 401
curl -i -H 'X-Member-Id: 1' http://localhost:8082/api/members/1

# 유효한 사용자 토큰을 들고 가도 401 (audience가 gateway 것이 아님)
curl -i -H "Authorization: Bearer $TOKEN" -H 'X-Member-Id: 1' http://localhost:8082/api/members/1

# actuator는 토큰 없이 열려 있습니다 (healthcheck·Prometheus용)
curl -i http://localhost:8082/actuator/health
```

> **초기화 스크립트는 최초 기동에만 실행됩니다.** `infrastructure/mysql/init/*.sql`과
> `infrastructure/keycloak/realm-lxp.json`을 고쳤다면 `docker compose down -v`가 필요합니다.
> Keycloak은 realm이 이미 있으면 `Realm 'lxp' already exists. Import skipped`를 남기고
> 조용히 건너뜁니다 — 재기동만 해서는 반영되지 않습니다.

**동영상 업로드** — 파일은 서비스를 거치지 않고 클라이언트가 MinIO와 직접 주고받습니다.

```bash
CID=$(curl -s -X POST http://localhost:8080/api/courses \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Demo","description":"d"}' | sed 's/.*"courseId":"\([^"]*\)".*/\1/')

URL=$(curl -s -X POST "http://localhost:8080/api/courses/$CID/video/upload-url" \
  -H "Authorization: Bearer $TOKEN" | sed 's/.*"url":"\([^"]*\)".*/\1/')

curl -X PUT -T video.mp4 "$URL"                      # MinIO로 직접 업로드
curl -X POST "http://localhost:8080/api/courses/$CID/video/complete" \
  -H "Authorization: Bearer $TOKEN"                  # 서버가 객체 존재를 확인한 뒤 완료 처리
```

**공통 인프라**

| 대상             | 주소                                    |
|----------------|---------------------------------------|
| Config Server  | http://localhost:8888/gateway/default |
| Keycloak       | http://localhost:8180 (admin / admin) |
| Consul UI      | http://localhost:8500                 |
| MinIO 콘솔      | http://localhost:9001 (minioadmin / minioadmin) |
| RabbitMQ UI    | http://localhost:15672 (lxp / lxp)    |
| Prometheus     | http://localhost:9090                 |
| Grafana        | http://localhost:3000 (admin / admin) |
| Loki readiness | http://localhost:3100/ready           |
| Zipkin         | http://localhost:9411                 |

## 현재 구현 범위

포함:

- Gateway 라우팅 + **Keycloak(OIDC) 토큰 검증** — 검증 통과 시 `X-Member-Id`를 다운스트림에 전달
- Config Server Native backend / Consul 서비스 등록 및 탐색
- **회원 가입** (member_db 프로필 + Keycloak 사용자 동시 생성, 실패 시 보상)
- **강의 CRUD + MinIO Presigned URL** — 동영상은 클라이언트가 MinIO와 직접 송수신
- **구독-결제 사가** (Outbox → RabbitMQ 코레오그래피, 환불 보상 포함)
- **정기 결제 스케줄러** — `(subscriptionId, billingCycle)` 멱등키
- **gRPC + 서킷브레이커** (subscription → member, fail-closed)
- 서비스별 DB — MySQL 스키마 분리 + MongoDB
- Actuator / Prometheus / Grafana / Loki + Alloy / Zipkin

이후 추가된 것:

- **Keycloak(OIDC) 이관** (D-20) + 탈퇴 회원 차단 (D-32·D-35)
- **서비스 토큰 검증** (D-33·D-34) — REST·gRPC 양쪽에서 Gateway 우회 차단
- **회원탈퇴 사가** (D-31) — 구독 해지 → 환불까지 코레오그래피로 연결
- **재생 권한** (D-36) — 이벤트로 복제한 읽기 모델, 동기 호출 없음
- **정기 결제 + dunning** (D-25~D-27·D-37)
- **PG 연동 경계 + 목 PG 컨테이너** (D-39)
- **CI 파이프라인** (D-38·D-40) — 폴링 → 변경 서비스만 빌드 → 이미지

미포함:

- 기존 모놀리식 도메인 코드
- **실제 PG 연동** — 목 PG로 경계까지만 (실키는 사업자등록 필요, P-01)
- HA 구성 (RabbitMQ·MongoDB 단일 노드, P-14)
- 배포 (현재 로컬 도커, P-07)
- Gateway Rate Limit

> 결정 배경은 [docs/DECISIONS.md](docs/DECISIONS.md), 진행 상황은 [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) 참고.
