"""커리큘럼 로드맵 서비스.

로직은 curriculum/roadmap 패키지에 있다. 여기는 HTTP 경계만 담당한다.
CLI(`scripts/roadmap.py`)와 평가 러너가 같은 패키지를 쓰므로 동작이 갈리지 않는다.

엔드포인트
    GET  /                      데모 콘솔 (static/index.html)
    GET  /actuator/health       compose healthcheck 와 Consul
    GET  /actuator/prometheus   지표 스크레이프 (D-62)
    GET  /api/ai/curriculum/catalog
    POST /api/ai/curriculum/roadmap
    POST /api/ai/curriculum/roadmap/stream   같은 일을 SSE 로 흘려보낸다

gateway 를 거쳐 들어오는 것을 전제한다. 서비스 토큰 검증(D-33)은 아직 없다.

콘솔을 이 서비스가 직접 준다. gateway 라우팅이 없어서 브라우저가 8087 을 직접
부르는데, 페이지를 다른 포트에 두면 CORS 를 열어야 한다. 같은 오리진에서 주면
그 문제가 없고 촬영할 때 컨테이너 하나만 띄우면 된다.
실제 사용자 화면은 나중에 frontend/client 에 붙인다. 이건 개발용 콘솔이다.
"""

import json
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from curriculum import roadmap  # noqa: E402
from curriculum.service import metrics  # noqa: E402

app = FastAPI(title="curriculum-roadmap", version="0.1.0")

CONSOLE = Path(__file__).resolve().parent / "static" / "index.html"

# 카탈로그는 기동할 때 한 번 읽는다. 43개 2,600자라 메모리에 들고 있어도 무리가 없다.
# 나중에 course-service 목록 API 로 바꾸면 load_courses() 만 갈아끼운다.
COURSES = roadmap.load_courses()

def _max_attempts():
    """잘못된 값이면 기동 자체를 막는다.

    int() 가 그냥 터지면 트레이스백만 남아 무엇이 잘못됐는지 안 보이고,
    0 이나 음수를 통과시키면 요청이 올 때까지 멀쩡해 보인다.
    """
    raw = os.environ.get("ROADMAP_MAX_ATTEMPTS", "3")
    try:
        n = int(raw)
    except ValueError:
        raise RuntimeError(f"ROADMAP_MAX_ATTEMPTS 가 정수가 아니다: {raw!r}")
    if n < 1:
        raise RuntimeError(f"ROADMAP_MAX_ATTEMPTS 는 1 이상이어야 한다: {n}")
    return n


MAX_ATTEMPTS = _max_attempts()

# 요청 하나가 쓸 수 있는 전체 시간. 안 걸면 재생성 3회 x 재시도 4회 x 대기라
# 한 요청이 25분까지 갈 수 있다. gateway 와 브라우저는 그 전에 끊는데,
# 서버는 그것도 모르고 계속 모델을 부른다 — 쿼터만 태운다.
DEADLINE_SECONDS = int(os.environ.get("ROADMAP_DEADLINE_SECONDS", "180"))

metrics.CATALOG.set(len(COURSES))


class RoadmapRequest(BaseModel):
    goal: str = Field(..., min_length=2, max_length=200,
                      examples=["백엔드 개발자가 되고 싶다"])
    weeks: int = Field(26, ge=1, le=104)
    hoursPerWeek: int = Field(20, ge=1, le=80)
    level: int = Field(1, ge=1, le=5)


class CourseOut(BaseModel):
    title: str
    track: str
    level: int
    estimatedHours: int
    reason: str


class WeekSlot(BaseModel):
    title: str
    hours: int
    totalHours: int


class WeekOut(BaseModel):
    week: int
    hours: int
    slots: list[WeekSlot]


class RoadmapResponse(BaseModel):
    goalSummary: str
    courses: list[CourseOut]
    weeks: list[WeekOut]
    totalHours: int
    budgetHours: int
    weekCount: int
    attempts: int
    problems: list[str]


@app.get("/", include_in_schema=False)
def console():
    """촬영용 데모 콘솔. 정적 파일 한 장이라 빌드 도구가 없다."""
    return FileResponse(CONSOLE)


@app.get("/actuator/health")
def health():
    return {"status": "UP", "courses": len(COURSES)}


@app.get("/actuator/prometheus")
def prometheus():
    """ai-service 와 같은 경로를 쓴다. prometheus 잡 설정이 전역이라 다르게 두면
    스크레이프 설정을 서비스마다 나눠야 한다."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/ai/curriculum/catalog")
def catalog():
    """로드맵이 고를 수 있는 강의 목록. 화면에서 트랙·난이도를 보여줄 때 쓴다."""
    return {"count": len(COURSES), "courses": COURSES}


@app.post("/api/ai/curriculum/roadmap", response_model=RoadmapResponse)
def create_roadmap(req: RoadmapRequest):
    try:
        llm = roadmap.Gemini()
    except roadmap.LLMError as e:
        metrics.REQUESTS.labels(outcome="unavailable").inc()
        raise HTTPException(status_code=503, detail=f"모델을 부를 수 없다: {e.detail}")

    started = time.perf_counter()
    try:
        r = roadmap.build(COURSES, llm, req.goal, req.weeks,
                          req.hoursPerWeek, req.level, MAX_ATTEMPTS,
                          deadline_seconds=DEADLINE_SECONDS)
    except roadmap.LLMError as e:
        metrics.record_error(e.status)
        # 429 는 무료 티어 한도라 잠시 뒤 다시 부르면 된다. 그대로 내려보낸다.
        status = 429 if e.status == 429 else 502
        raise HTTPException(status_code=status, detail=e.detail[:500])

    metrics.record(r, time.perf_counter() - started)
    return to_response(r)


def to_response(r) -> RoadmapResponse:
    return RoadmapResponse(
        goalSummary=r.goal_summary,
        courses=[
            CourseOut(title=c["title"], track=c["track"], level=c["level"],
                      estimatedHours=c["estimatedHours"], reason=reason)
            for c, reason in r.courses
        ],
        weeks=[
            WeekOut(
                week=i,
                hours=sum(t for _, t, _, _ in week),
                slots=[WeekSlot(title=c["title"], hours=t, totalHours=whole)
                       for c, t, whole, _ in week],
            )
            for i, week in enumerate(r.weeks, start=1)
        ],
        totalHours=r.total_hours,
        budgetHours=r.budget_hours,
        weekCount=r.week_count,
        attempts=r.attempts,
        problems=r.problems,
    )


def sse(event, data):
    """SSE 한 덩어리. 빈 줄 하나로 끝난다."""
    body = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n"


@app.post("/api/ai/curriculum/roadmap/stream")
def stream_roadmap(req: RoadmapRequest):
    """로드맵을 만들면서 단계마다 흘려보낸다.

    토큰 단위가 아니라 단계 단위다. 모델이 JSON 한 덩어리를 뱉으므로
    반쯤 온 JSON 으로는 화면에 그릴 것이 없다. 쓸모는 재생성이 도는 동안
    화면이 멈춰 보이지 않게 하는 것이다. 재생성까지 가면 30초를 넘긴다.

    이벤트는 start / generate / verify / schedule / result / error 여섯이다.
    result 나 error 가 오면 끝이다.

    한 번 흘려보내기 시작하면 상태 코드를 바꿀 수 없다. 이미 200 이 나갔다.
    그래서 모델 오류는 error 이벤트로 간다. 상태 코드로 받고 싶으면
    스트리밍 아닌 쪽(POST .../roadmap)을 쓴다.
    """
    # 키가 없는 것은 흘려보내기 전에 걸린다. 여기까지는 상태 코드가 먹는다.
    try:
        llm = roadmap.Gemini()
    except roadmap.LLMError as e:
        metrics.REQUESTS.labels(outcome="unavailable").inc()
        raise HTTPException(status_code=503, detail=f"모델을 부를 수 없다: {e.detail}")

    def events():
        started = time.perf_counter()
        yield sse("start", {
            "goal": req.goal,
            "budgetHours": req.weeks * req.hoursPerWeek,
            "weeks": req.weeks,
            "catalog": len(COURSES),
            "maxAttempts": MAX_ATTEMPTS,
        })
        try:
            for kind, data in roadmap.stream(
                COURSES, llm, req.goal, req.weeks,
                req.hoursPerWeek, req.level, MAX_ATTEMPTS,
                deadline_seconds=DEADLINE_SECONDS,
            ):
                if kind == "result":
                    metrics.record(data, time.perf_counter() - started)
                    yield sse("result", to_response(data).model_dump())
                else:
                    yield sse(kind, data)
        except roadmap.LLMError as e:
            metrics.record_error(e.status)
            # 429 는 무료 티어 한도라 잠시 뒤 다시 부르면 된다.
            yield sse("error", {"status": e.status, "detail": e.detail[:500]})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # nginx 가 앞에 있으면 버퍼링 때문에 한꺼번에 몰려 나온다.
            "X-Accel-Buffering": "no",
        },
    )
