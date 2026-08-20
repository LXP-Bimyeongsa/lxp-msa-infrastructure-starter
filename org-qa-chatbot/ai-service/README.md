# ai-service

조직 규정 QA 챗봇. 규정 전문을 매 요청에 주입하고, 근거 청크ID를 인용해 답한다.

품질 측정과 프롬프트는 [`../org-qa-chatbot`](../org-qa-chatbot)에서 만들었다.
규정 문서, 평가셋 60문항, 채점 스크립트가 거기 있다.

## 이 서비스가 다른 서비스와 다른 점

**저장소의 유일한 비-JVM 서비스다.** 나머지 5개는 Spring Boot라서
spring-cloud-consul과 Actuator가 아래를 자동으로 해준다. 여기서는 직접 구현했다.

| | Spring | 여기서 |
| --- | --- | --- |
| Consul 등록/해제 | spring-cloud-consul | [`app/consul.py`](app/consul.py) |
| 설정 로딩 | Config Server 클라이언트 | [`app/config.py`](app/config.py) — REST API 직접 조회 |
| `/actuator/health` | Actuator | [`app/routes.py`](app/routes.py) |
| `/actuator/prometheus` | Actuator + micrometer | `prometheus_client` |
| 파일 로그 ECS JSON | `structured.format.file=ecs` | [`app/logging_setup.py`](app/logging_setup.py) |

**경로를 Spring과 똑같이 둔 것은 의도다.** Consul의 `health-check-path`와
Prometheus의 `metrics_path`는 서비스 단위가 아니라 전역/잡 단위 설정이다.
경로를 다르게 하면 두 곳을 다 고쳐야 하지만, 같게 두면 prometheus 잡에
타겟 한 줄만 추가하면 된다.

`config-repo/application.yml`의 공통 설정은 Spring 클라이언트가 해석하는 것이라
이 서비스에는 적용되지 않는다. 같은 값(헬스체크 10초, critical 1분 후 자동 해제,
graceful shutdown 시 등록 해제)을 코드에 옮겨 적었다.

## 엔드포인트

| | |
| --- | --- |
| `POST /api/ai/chat` | 질문에 답한다. gateway가 `/api/ai/**`로 라우팅한다 |
| `GET /actuator/health` | Consul이 10초마다 찌른다 |
| `GET /actuator/prometheus` | Prometheus 스크레이프 |
| `GET /actuator/docs` | OpenAPI 문서 (내부용) |

## 설정

비밀이 아닌 값은 [`../config-repo/ai-service.yml`](../config-repo/ai-service.yml)에
있고, 기동 시 config-server에서 읽어온다. config-server가 없거나 죽어 있어도
환경변수와 기본값으로 뜬다.

**`GEMINI_API_KEY`는 config-repo에 두지 않는다.** config-repo는 평문 git이고 이
저장소는 공개다. 저장소 루트 `.env`에 두고 compose가 환경변수로 주입한다.

우선순위는 환경변수 → config-server → 기본값이다. 환경변수를 위에 둔 것은
compose에서 값을 덮어써 디버깅할 수 있게 하기 위해서다.

## 로컬 실행

```bash
uv sync
uv run uvicorn app.main:app --port 8086 --reload
```

`CONSUL_HOST`와 `CONFIG_SERVER_URL`이 없으면 Consul 등록과 config 조회를 건너뛰고
기본값으로 뜬다. 엔드포인트 확인은 되지만 gateway 경유 호출은 안 된다.

## 컨테이너

```bash
docker compose up -d ai-service
```

빌드 컨텍스트는 저장소 루트다(다른 서비스와 같은 규칙). 워커는 1개다 —
규정 전문을 메모리에 들고 있고 무료 티어 상한이 분당 15요청이라, 프로세스를
늘려도 처리량은 늘지 않고 규정 전문만 중복 적재된다.

## 진행 상황

계획서 3단계 기준.

- [x] **9. 뼈대** — FastAPI, Consul 등록, config-server 조회, 메트릭, compose 등록
- [ ] **10. `generate_stream()` 인터페이스** — 처음부터 스트리밍 시그니처로
- [ ] **11. 런타임 청크ID 검증 가드** — 실측에서 인용 102건 중 1건이 존재하지 않는 ID였다
- [ ] **12. 429 재시도** — `org-qa-chatbot/scripts/run_eval.py`에 구현돼 있어 옮기면 된다
- [ ] **13. SSE 스트리밍** — 첫 토큰 1.5초. 캐시 히트/미스를 나눠 측정한다
- [ ] **14. 규정 재로드** — mtime 대신 내용 해시, 원자적 스왑

`POST /api/ai/chat`은 아직 고정 응답을 돌려준다. 뼈대와 모델 호출을 한꺼번에
넣으면 Consul·config-server 연동에서 막힐 때 원인이 섞인다.

### 10번에서 정할 것

프롬프트 조립 코드(`org-qa-chatbot/scripts/prompt.py`)를 두 곳에서 쓰게 된다.
복사하면 프롬프트가 둘로 갈라지고, 그 순간 평가 결과가 운영과 무관해진다.
공유 패키지로 빼거나, 서비스 쪽을 원본으로 두고 평가가 import하는 구조로 정해야 한다.
