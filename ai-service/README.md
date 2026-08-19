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

모든 명령은 이 폴더(`ai-service/`)에서 돈다. 저장소 루트에서 돌리면 `pyproject.toml`을 못 찾는다.

```bash
cd ai-service && uv sync
```

```bash
cp .env.example .env
```

```bash
uv run uvicorn app.main:app --reload --port 8086
```

`.env` 없이도 뜬다. 키는 S1(색인)부터 필요하다.

## 확인

```bash
curl -i http://localhost:8086/health
```

```bash
curl -i -H "X-Member-Id: 1" http://localhost:8086/api/ai/ping
```

```bash
curl -i http://localhost:8086/api/ai/ping
```

기대값은 `200` / `200` / `401`이다. `index_ready`는 색인 전이라 `false`가 정상이다.

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

## 저장소에 합칠 때 같이 고쳐야 하는 것

같은 저장소에 들어왔으므로 루트 쪽 파일과 짝이 맞아야 한다. 지금은 셋 다 안 했다.

| 대상 | 할 일 | 안 하면 |
|---|---|---|
| 루트 `docs/DECISIONS.md` | `ai-service/docs/DECISIONS.md`의 D-68~D-73을 옮겨 붙이고 이 파일은 지운다 | 결정 기록이 두 군데로 갈라진다 |
| 루트 `.env.example` | `GEMINI_API_KEY`·`LANGSMITH_*` 추가 | 클론한 사람이 무슨 키가 필요한지 모른다 |
| `ci/Jenkinsfile` | Python 스테이지 추가 (`uv sync` → `ruff check` → `pytest`) | 저장소에 있는데 CI가 한 번도 안 보는 폴더가 된다 |

세 번째가 조용히 나쁘다. **검사하지 않은 것은 통과한 것처럼 보인다.**

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
