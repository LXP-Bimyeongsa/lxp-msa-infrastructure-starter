"""커리큘럼 로드맵 서비스.

로직은 curriculum/roadmap 패키지에 있다. 여기는 HTTP 경계만 담당한다.
CLI(`scripts/roadmap.py`)와 평가 러너가 같은 패키지를 쓰므로 동작이 갈리지 않는다.

엔드포인트
    GET  /actuator/health   Prometheus 스크레이프와 compose healthcheck 용
    GET  /api/ai/curriculum/catalog
    POST /api/ai/curriculum/roadmap

gateway 를 거쳐 들어오는 것을 전제한다. 서비스 토큰 검증(D-33)은 아직 없다.
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from curriculum import roadmap  # noqa: E402

app = FastAPI(title="curriculum-roadmap", version="0.1.0")

# 카탈로그는 기동할 때 한 번 읽는다. 43개 2,600자라 메모리에 들고 있어도 무리가 없다.
# 나중에 course-service 목록 API 로 바꾸면 load_courses() 만 갈아끼운다.
COURSES = roadmap.load_courses()

MAX_ATTEMPTS = int(os.environ.get("ROADMAP_MAX_ATTEMPTS", "3"))


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


@app.get("/actuator/health")
def health():
    return {"status": "UP", "courses": len(COURSES)}


@app.get("/api/ai/curriculum/catalog")
def catalog():
    """로드맵이 고를 수 있는 강의 목록. 화면에서 트랙·난이도를 보여줄 때 쓴다."""
    return {"count": len(COURSES), "courses": COURSES}


@app.post("/api/ai/curriculum/roadmap", response_model=RoadmapResponse)
def create_roadmap(req: RoadmapRequest):
    try:
        llm = roadmap.Gemini()
    except roadmap.LLMError as e:
        raise HTTPException(status_code=503, detail=f"모델을 부를 수 없다: {e.detail}")

    try:
        r = roadmap.build(COURSES, llm, req.goal, req.weeks,
                          req.hoursPerWeek, req.level, MAX_ATTEMPTS)
    except roadmap.LLMError as e:
        # 429 는 무료 티어 한도라 잠시 뒤 다시 부르면 된다. 그대로 내려보낸다.
        status = 429 if e.status == 429 else 502
        raise HTTPException(status_code=status, detail=e.detail[:500])

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
