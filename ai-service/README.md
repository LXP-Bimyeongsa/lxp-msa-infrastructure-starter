# ai-service — LXP AI 튜터

강의와 미션 질문에 **강의 내용을 근거로 인용해** 답하는 서비스. 근거가 없으면 답하지 않는다.

이 폴더는 [lxp-msa-infrastructure-starter](https://github.com/LXP-Bimyeongsa/lxp-msa-infrastructure-starter)
저장소 안의 한 서비스다. 다른 서비스는 Gradle로 빌드하지만 여기만 Python·uv를 쓴다.

- 선행 문서: 기획·설계 / 2단계 인터페이스 설계 / 3단계 데이터 준비 / 4단계 뼈대 구현 / 4.5단계 2일 최소 구현 계획
- 레퍼런스: `potenup/19_langchain/11_serving_ops`

## 설계 원칙 셋

이 셋이 본체다. 빼면 남는 게 단순 RAG뿐이라 만들 이유가 없어진다.

| 원칙 | 구현 | 상태 |
|---|---|---|
| 검색 결과를 믿지 않는다 | `grade` 노드 + `rewrite` 루프 | S3·S4 |
| 모름을 정식 응답으로 | `no_evidence` 전용 경로 | S3 |
| 미션 정답은 힌트로 | `classify` 분기 + `visibility` 필터 + `hint` 노드 | S5 |

## 실행

전제는 uv 하나다. Python 3.12는 uv가 알아서 받는다.

**모든 명령은 이 폴더(`ai-service/`)에서 돈다.** 저장소 루트에서 돌리면
`error: Failed to spawn: uvicorn — program not found`가 난다. 디렉터리가 틀렸다는 말이
어디에도 없어서 의존성 문제로 착각하기 쉽다.

```bash
cd ai-service
```

```bash
uv sync
```

```bash
uv run uvicorn app.main:app --reload --port 8086
```

`.env`는 없어도 뜬다(AI-05). 키는 S1(색인)부터 필요하다.

```bash
cp .env.example .env
```

### 뜰 때 로그에서 볼 것 셋

```
WARNING:app.main:벡터 색인이 없다. S1 에서 scripts/init_vectorstore.py 를 돌린다
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8086
```

| 볼 것 | 정상 | 아니면 |
|---|---|---|
| 경고가 한글로 읽히는가 | 위 그대로 | `���� ������`면 UTF-8 설정이 빠졌다. `app/main.py`의 `sys.stdout.reconfigure` 확인 |
| 색인 경고가 떴는데도 `startup complete`인가 | 뜬다 | 여기서 죽으면 서버 기동과 색인 준비가 붙어버린 것이다. **이 둘이 분리돼 있어야 이후 문제가 AI 쪽인지 연동 쪽인지 구분된다** |
| 바인딩 주소 | `127.0.0.1` | 로컬은 이게 맞다. 나중에 컨테이너로 띄울 땐 `--host 0.0.0.0`이 필요하다 |

## 확인

**PowerShell에서는 `curl`이 아니라 `curl.exe`를 쓴다.** PowerShell의 `curl`은
`Invoke-WebRequest` 별칭이라 `-i`를 못 알아듣고
`Cannot process command because of one or more missing mandatory parameters: Uri`로 죽는다.
서버 문제로 보이지만 요청이 나가지도 않은 것이다. (Git Bash에서는 그냥 `curl`이면 된다)

```bash
curl.exe -i http://localhost:8086/health
```

```bash
curl.exe -i -H "X-Member-Id: 1" http://localhost:8086/api/ai/ping
```

```bash
curl.exe -i http://localhost:8086/api/ai/ping
```

| # | 요청 | 기대 | 다르게 나오면 |
|---|---|---|---|
| 1 | `/health` | `200` · `index_ready: false` | `index_ready: true`인데 S1 전이면 `data/chroma/`가 이미 있다는 뜻이다. 남은 디렉터리를 지운다 |
| 2 | `ping` + 헤더 | `200` · `{"message":"pong","member_id":1}` | `member_id`가 보낸 값과 다르면 헤더 전달이 끊긴 것이다 |
| 3 | `ping` 헤더 없음 | `401` | **가장 중요하다.** `200`이면 신뢰 경계가 아예 없는 것이고, `422`면 `require_member_id`를 안 거치고 `Header(...)`로 직접 받은 코드가 생긴 것이다(AI-03 위반) |
| 4 | `ping` + `X-Member-Id: abc` | `401` | `500`이면 `int()` 변환 예외를 안 잡은 것이다 |
| 5 | `/docs` | `200` | 스키마가 보이면 응답 모델이 제대로 붙은 것이다 |

3번이 이 단계의 유일한 보안 확인이다. 나머지 넷은 껍데기가 도는지만 본다.

```bash
uv run ruff check .
```

### 자주 걸리는 것

| 증상 | 원인 | 조치 |
|---|---|---|
| `Failed to spawn: uvicorn — program not found` | 저장소 루트에서 돌렸다 | `cd ai-service` |
| `missing mandatory parameters: Uri` | PowerShell의 `curl` 별칭 | `curl.exe`를 쓴다 |
| `[Errno 10048] ... bind on address ('127.0.0.1', 8086)` | 8086을 이미 누가 쓰고 있다 | 이전 서버를 끄거나 `--port`를 바꾼다 |
| 로그가 `���� ������` | Windows stdout이 cp949 | `app/main.py`의 UTF-8 설정 확인 |
| `OSError: Readme file does not exist` | `pyproject.toml`의 `readme =`가 없는 파일을 가리킨다 | README.md를 만든다. 의존성 문제가 아니다 |

## 지금 없는 것

4.5단계 판단으로 잘라낸 것들이다. 버린 게 아니라 순서를 미룬 것이다.

| 항목 | 잘라낸 대가 | 되살릴 순서 |
|---|---|---|
| 서비스 토큰 검증 (Keycloak JWKS) | `X-Member-Id`를 그대로 믿는다 | 1 |
| Consul 등록 · 게이트웨이 라우팅 | 저장소 안에 있지만 스택과는 연결되지 않는다 | 2 |
| compose 블록 · Jenkinsfile 스테이지 | 로컬에서 `uv run uvicorn`으로만 띄운다 | 3 |
| SSE 스트리밍 | 응답 시작 3초 지표를 못 잰다 | 4 |
| MySQL 대화 이력 | 이력 조회 API가 없다 | 5 |

**인증이 가장 아깝다.** 신뢰 지점을 `app/core/security.py`의 `require_member_id()` **한 함수로 모아뒀다.**
붙일 때 그 함수만 JWKS 검증으로 바꾸면 되고 호출부는 손대지 않는다.

## 루트를 건드리지 않기로 했다 (AI-07)

같은 저장소에 있지만 이 서비스 변경은 전부 이 폴더 안에서만 한다. 루트 `AGENTS.md`가
파일 수정에 승인을 요구하고, 뼈대 단계에서 루트를 고쳐봐야 아직 쓰지 않을 설정만 늘어난다.

미룬 것을 여기 적어둔다. **적어두지 않으면 "안 한 것"과 "잊은 것"이 구분되지 않는다.**

| 대상 | 붙일 때 할 일 | 안 하면 |
|---|---|---|
| 루트 `.env.example` | `GEMINI_API_KEY`·`LANGSMITH_*` 추가 | 클론한 사람이 무슨 키가 필요한지 모른다 |
| `ci/Jenkinsfile` | Python 스테이지 (`uv sync` → `ruff check` → `pytest`) | 저장소에 있는데 CI가 한 번도 안 보는 폴더가 된다 |
| `compose.yaml` | `ai-service` 블록 (8086, `ai-chroma` 볼륨) | 스택과 함께 뜨지 않는다 |
| `config-repo/gateway.yml` | `Path=/api/ai/**` → `lb://ai-service` | 게이트웨이가 이 서비스를 모른다 |
| 루트 `docs/DECISIONS.md` | 합치기로 하면 `AI-nn` → 빈 `D-nn` | 결정 기록이 두 군데로 남는다 |

두 번째가 조용히 나쁘다. 팀이 D-62에서 이미 겪은 **"검사하지 않은 것은 통과한 것처럼 보인다"**가
그대로 재발한다. 다만 4.5단계 판단상 CI는 우선순위 3이라 지금은 미룬다.

결정 기록은 `docs/DECISIONS.md`에 `AI-nn`으로 따로 매긴다. 루트의 `D-nn`과 겹치지 않게
하려는 것이다 — D-68은 조직 규정 QA 챗봇이 한 번 썼다가 되돌려진 번호라 비어 보일 뿐이다.

## 구조

```
app/
├─ main.py              # FastAPI 앱, lifespan, /health
├─ api/endpoints.py     # /api/ai/ping
├─ core/
│  ├─ config.py         # 설정, 경로 상수
│  └─ security.py       # 호출자 신원 — 나중에 교체할 단 하나의 자리
└─ schema/models.py     # 요청·응답 모델

data/raw/               # 강의 교안 원본 (S1)
data/chroma/            # 색인 — 산출물이라 커밋하지 않는다
scripts/                # init_vectorstore.py (S1)
```

`graph/` · `tools/` · `eval/`은 아직 없다. 쓸 때 만든다.

`.gitignore`를 이 폴더에 따로 둔 이유. `data/chroma/`나 `.venv/` 같은 건 이 서비스에만 있는
산출물이라 루트 `.gitignore`에 Python 규칙을 섞으면 Gradle 서비스들과 뒤엉킨다.

## 다음 슬라이스

| 슬라이스 | 만들 것 | 볼 것 |
|---|---|---|
| **S1 색인** | 마크다운 로딩 → 청킹 → `visibility` 메타 → Chroma | 없음 (04장에서 배움) |
| S2 최소 그래프 | `TutorState` + `retrieve` → `generate` 직선 | 09장 `01_graph_vs_chain`, `02_state_schema` |
| S3 분기 | `grade` + 세 갈래 + `no_evidence` | 09장 `04_conditional_edges` |
| S4 루프 | `rewrite` → `retrieve` 순환 + `retry` 상한 | 09장 `03_nodes_and_edges` |
| S5 의도·힌트 | `classify` + `route_intent` + `hint` + `visibility` 필터 | 02장 구조화 출력 |
| S6 가드레일 | 출력 유출 검사 | 없음 |
| S7 API | `POST /chat` | 11장 `01_fastapi_serving` |
| S8 체크포인터 | sqlite 체크포인터 + `thread_id` | 10장 `01_checkpointer_persistence` |
| S9 평가 | 15문항 + 지표 계산 | 05장 평가, 11장 `03_observability_eval` |

4.5단계 문서가 가리킨 `09장 03_routing_pitfalls`는 실제로 없다. 해당 장의 디렉터리는
`01_graph_vs_chain` · `02_state_schema` · `03_nodes_and_edges` · `04_conditional_edges` 넷뿐이다.

## 코드 작성 규약

가장 작은 단위의 기본 코드로 쓴다. 추상화를 미리 만들지 않는다.

- 파일 하나가 한 가지만 한다
- 함수는 한 화면 안에 들어온다
- 설정값은 상수로 빼되 계층은 만들지 않는다
- 안 쓰는 의존성·상수를 미리 넣지 않는다

주석은 네 경우에만 단다. 왜 그렇게 했는지가 코드에 안 보일 때, 안 하면 조용히 깨지는 것,
값의 근거가 임의일 때, 순서가 중요할 때. 코드를 그대로 읽은 주석은 달지 않는다.
