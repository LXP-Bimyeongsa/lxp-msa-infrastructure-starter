# 커리큘럼 로드맵 — 처음 오는 사람용

배경 지식 없이 읽어도 되게 썼다. 설계를 왜 그렇게 했는지는 [README.md](README.md)에 있다.
여기는 **돌려보고 고치기 시작하는 데까지**만 다룬다.

---

## 뭘 하는 건가

학습자가 **목표·기간·주당 시간·현재 수준**을 넣으면 기존 강의 중에서 골라 순서를 짜준다.

```
입력   "백엔드 개발자가 되고 싶다" · 8주 · 주 15시간 · L1(완전 입문)
출력   강의 5개 · 118시간 / 예산 120시간 · 8주치 주차별 배분
```

강의를 새로 만들지 않는다. **이미 있는 43개 중에서 고르고 배열할 뿐이다.**

---

## 5분 안에 돌려보기

```bash
docker compose -f compose.curriculum.yaml up -d --build
```

`http://localhost:8087/` 을 연다. 화면이 나온다.

API 키가 없으면 **화면은 뜨고 생성만 실패한다.** 키는 저장소 루트 `.env` 에 넣는다.

```
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
```

키는 [Google AI Studio](https://aistudio.google.com/apikey)에서 무료로 받는다.
무료 한도가 **모델별로 하루 20건**이라 다 쓰면 `GEMINI_MODEL` 만 다른 이름으로 바꾼다.
코드도 이미지도 안 건드리고 `up -d` 만 다시 하면 된다.

**지금 어느 모델로 도는지는 세 곳에서 본다.**

```text
화면 오른쪽 위 배지
GET /actuator/health      {"model": "..."}
로드맵 응답의 model 필드
```

모델이 바뀌면 같은 입력에도 결과가 달라진다. 그래서 기록을 남긴다.

내릴 때는 이렇게 한다. 메인 스택은 안 건드린다.

```bash
docker compose -f compose.curriculum.yaml down
```

---

## 한 요청이 도는 길

화면에서 "생성"을 누르면 이 순서로 돈다.

```
1. 강의 43개를 통째로 프롬프트에 넣고 모델에게 고르라고 한다
2. 모델이 번호 목록을 준다        {"selected": [{"index": 12, "reason": "..."}]}
3. 코드가 검사한다                번호가 맞나 · 겹치나 · 예산을 넘나 · 순서가 역순인가
4. 걸리면 뭐가 틀렸는지 적어서 2번으로 되돌아간다   (최대 3회)
5. 통과하면 주차별로 나눈다
```

**역할이 갈려 있다. 이게 이 프로젝트의 핵심이다.**

| | 맡는 것 |
|---|---|
| LLM | 무엇을 고를지, 어떤 순서일지 — **판단이 필요한 것** |
| 코드 | 존재하나·겹치나·넘치나 — **계산으로 답이 나오는 것** |

"40+25가 65인가"를 모델에게 묻지 않는다. 판정이 흔들리고 토큰만 쓴다.

4번의 되돌아가는 부분이 **LangGraph** 로 묶여 있다. 화면 오른쪽에서 실제로 도는 게 보인다.

```text
✓ 목표를 읽었어요           강의 43개 중에서 골라요
✓ 강의를 고르는 중이에요
⚠ 시간이 넘어서 다시 골라요   40시간이라 20시간을 넘어요
✓ 다시 고르는 중이에요        2번째 시도예요
✓ 일정이 맞는지 확인했어요
✓ 주차별로 나눴어요           2주 계획
```

`2주 × 10h` 로 넣으면 예산이 빠듯해서 이게 잘 걸린다.

화면은 사용자가 읽을 말로 쓴다. `generate`·`verify` 같은 내부 이름과 서버가 보낸
원본 이벤트는 아래 **"서버가 보낸 원본 기록"** 을 펼치면 나온다.

---

## 파일 지도

코어가 630줄쯤이다. **전부 읽어도 30분이면 된다.**

```
curriculum/
  roadmap/            코어. CLI·평가·서비스가 전부 이걸 쓴다
    catalog.py    32  강의를 읽어온다
    prompt.py    100  프롬프트 문자열을 만든다
    llm.py       124  Gemini 를 부른다
    verify.py     65  코드 검사 5가지
    schedule.py   36  주차로 나눈다
    engine.py    252  LangGraph 그래프. 위 다섯을 엮는다
  service/
    app.py       243  HTTP 경계. 로직은 없다
    metrics.py    73  프로메테우스 지표
    static/           화면 (HTML 한 장, 빌드 도구 없음)
  scripts/
    roadmap.py    95  터미널에서 돌려보는 CLI
    evaluate.py  174  평가셋 8케이스 자동 채점
    seed.sh       46  카탈로그를 MongoDB 에 넣는다
  data/
    courses.json      강의 43개 · 762시간
    eval_roadmap.json 평가 케이스 8개
```

`service/app.py` 에는 판단 로직이 없다. 받아서 `roadmap` 패키지에 넘기고 결과를 JSON 으로
바꾸는 게 전부다. **로직을 고칠 일이면 `roadmap/` 안에 있다.**

---

## 뭘 바꾸려면 어디를 여나

| 하고 싶은 것 | 여는 파일 |
|---|---|
| 강의를 추가·수정한다 | `data/courses.json` |
| 모델이 고르는 기준을 바꾼다 | `roadmap/prompt.py` |
| 검사를 추가한다 (예: 최소 강의 수) | `roadmap/verify.py` |
| 다른 모델·유료 API 로 바꾼다 | `roadmap/llm.py` |
| 주차 나누는 방식을 바꾼다 | `roadmap/schedule.py` |
| 재시도 횟수·조건을 바꾼다 | `roadmap/engine.py` |
| 응답 JSON 모양을 바꾼다 | `service/app.py` |
| 화면을 고친다 | `service/static/index.html` |
| 평가 케이스를 늘린다 | `data/eval_roadmap.json` |

**강의를 나중에 `course-service` 에서 읽어올 때는** `roadmap/catalog.py` 의
`load_courses()` 하나만 바꾸면 된다. 나머지는 이 함수가 돌려주는 모양에만 의존한다.

---

## 개발할 때 쓰는 것

**파이썬 3.12 로 가상환경을 만든다.** 컨테이너도 `python:3.12-slim` 이라 맞춰두는 편이 낫다.
3.14 에서는 `pydantic-core` 휠이 없어서 설치가 중간에 깨진다 (직접 겪었다).

먼저 3.12 가 있는지 본다.

```bash
py --list
```

```
 -V:Astral/CPython3.14.5 * CPython 3.14.5 (64-bit)
 -V:Astral/CPython3.12.13 CPython 3.12.13 (64-bit)
```

**왼쪽 태그를 `-V:` 뒤에 통째로 붙인다.** `py -3.12` 나 `py -V:3.12` 로 줄이면
"No suitable Python runtime found" 가 난다. 태그는 환경마다 다르니 본인 것을 쓴다.

```bash
py -V:Astral/CPython3.12.13 -m venv curriculum/.venv
curriculum/.venv/Scripts/python.exe -m pip install -r curriculum/service/requirements.txt
```

아래 명령들은 `curriculum/.venv/Scripts/python.exe` 로 돌린다는 뜻이다.

터미널에서 한 번 돌려보기.

```bash
export GEMINI_API_KEY=...
python curriculum/scripts/roadmap.py --goal "백엔드 개발자가 되고 싶다" --weeks 8 --hours-per-week 15
```

프롬프트를 고쳤으면 **평가셋을 돌려서 나아졌는지 숫자로 본다.** 감으로 고치면 뭐가 좋아졌는지 모른다.

```bash
python curriculum/scripts/evaluate.py
```

```
8/8 통과 · 첫 시도 통과 7/8 · 호출 9회
```

**"첫 시도 통과"가 프롬프트 품질 지표다.** 재생성 루프가 있어서 결국은 통과하지만,
호출이 늘면 한도와 응답 시간을 먹는다. 이 숫자를 올리는 게 목표다.
케이스 수만큼 API 를 부르므로 하루 20건 한도에 금방 닿는다.

---

## 미리 알아두면 좋은 함정

**무료 한도가 모델별로 하루 20건이다.** 프로젝트 단위가 아니라 모델 단위라, 다 쓰면
`GEMINI_MODEL` 만 바꿔도 20건이 새로 생긴다. 블로그에 250~1500건이라고 쓰인 것들이 있는데
틀린 값이다. 실제 오류 응답에 `limit: 20` 이 찍힌다.

**한글을 `curl -d` 로 바로 넘기면 Windows 셸에서 깨져 422 가 난다.** 서비스 문제로 오해하기 쉽다.
파일로 두고 넘긴다.

```bash
curl -s -X POST localhost:8087/api/ai/curriculum/roadmap \
  -H 'Content-Type: application/json' --data-binary @req.json
```

**포트는 8087 이다.** 8086 은 `ai-service`(조직 규정 QA)가 쓴다.

**`compose.yaml` 도 같이 떠 있어야 한다.** 네트워크(`lxp-net`)를 새로 만들지 않고 붙는다.

**한 요청은 180초에서 끊긴다** (`ROADMAP_DEADLINE_SECONDS`). 안 걸어두면 재시도가 겹쳐서
최악 25분까지 간다. 그 사이 브라우저는 이미 끊겼는데 서버만 계속 모델을 부른다.

---

## 아직 안 된 것

| | 왜 |
|---|---|
| gateway 라우팅 | 라우트가 전부 `lb://` 라 Consul 등록이 먼저다. `ai-service` 가 같은 문제를 이미 풀어서 두 벌 만들지 않고 미뤘다 |
| LangSmith 트레이스 | 패키지와 환경변수는 있는데 **키가 없어서 꺼져 있다.** 키만 넣으면 코드 변경 없이 켜진다 |
| Jenkins | 파이프라인이 `./gradlew` 전용이라 파이썬 서비스를 넣으면 깨진다 |
| 화면을 gateway 뒤로 | 지금은 서비스가 직접 준다. CORS 를 피하려고 그랬다. gateway 라우팅이 붙으면 `frontend/client` 로 옮긴다 |
| `course-service` 연동 | 엔티티에 `estimatedHours`·`level`·`track` 이 없고 목록 API 도 없다. 지금은 JSON 을 직접 읽어 우회한다 |

**LangChain 은 안 쓴다.** `langchain-core` 가 깔려 있지만 `langgraph` 가 끌고 온 것이고
코드에서 임포트하지 않는다. 모델 호출은 `llm.py` 에서 표준 라이브러리로 직접 한다.

---

## 더 볼 것

- [README.md](README.md) — 왜 그렇게 만들었는지. 카탈로그 설계, 프롬프트를 고친 기록,
  무료 한도 실측, 평가 기준을 왜 바꿨는지
- `curriculum/roadmap/*.py` — 각 파일 맨 위 주석에 그 파일이 존재하는 이유가 적혀 있다
