"""
app/api/endpoints.py: 튜터 API

이 파일의 역할: 게이트웨이가 /api/ai/** 로 보낸 요청을 받는다.
→ app/main.py 가 prefix="/api/ai" 로 등록한다
확인: X-Member-Id 를 넣은 GET /api/ai/ping 이 200, 없으면 401

스트리밍은 아직 없다. 동기 응답 하나다. SSE 는 나중 작업이다
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.core.config import RECURSION_LIMIT
from app.core.security import require_member_id
from app.graph.builder import build_graph, new_turn
from app.schema.models import ChatRequest, ChatResponse, PingResponse
from app.tools.rag import is_ready

logger = logging.getLogger(__name__)

router = APIRouter()


# 1. 연결 확인: 뼈대 단계의 유일한 엔드포인트
@router.get("/ping", response_model=PingResponse, tags=["Tutor"])
def ping(member_id: int = Depends(require_member_id)) -> PingResponse:
    return PingResponse(message="pong", member_id=member_id)


# 2. 질문
@router.post("/chat", response_model=ChatResponse, tags=["Tutor"])
def chat(request: ChatRequest, member_id: int = Depends(require_member_id)) -> ChatResponse:
    # 색인이 없는 것은 오류가 아니라 모름 응답이다. 준비 안 된 강의라고 안내하는 게 맞다
    if not is_ready():
        logger.warning("색인이 준비되지 않았다. 모름 응답으로 답한다")
        return ChatResponse(
            thread_id=request.thread_id or "",
            route="NO_EVIDENCE",
            answer="아직 이 강의의 학습 자료가 준비되지 않았다. 강사에게 문의하는 것을 권한다.",
            citations=[],
            intent="",
            top_score=0.0,
        )

    thread_id = request.thread_id or uuid4().hex
    state = build_graph().invoke(
        new_turn(request.question, request.course_id, request.lang, member_id=member_id),
        {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT},
    )

    # 가드레일에 걸린 것은 응답에 싣지 않는다. 왜 막혔는지 알려주면 우회 방법을 알려주는 셈이다
    if state.get("blocked"):
        logger.warning("가드레일 차단: %s", state["blocked"])

    return ChatResponse(
        thread_id=thread_id,
        route=state["route"],
        answer=state["answer"],
        citations=[
            {k: c[k] for k in ("course_id", "seq", "source_path", "score")}
            for c in state.get("citations", [])
        ],
        intent=state.get("intent", ""),
        top_score=state.get("top_score", 0.0),
    )
