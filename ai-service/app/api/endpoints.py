"""
app/api/endpoints.py — 튜터 API

이 파일의 역할: 게이트웨이가 /api/ai/** 로 보낸 요청을 받는다.
→ app/main.py 가 prefix="/api/ai" 로 등록한다
확인: X-Member-Id 를 넣은 GET /api/ai/ping 이 200, 없으면 401

지금은 ping 하나뿐이다. 질문·응답 엔드포인트는 S7 에서 붙인다 —
그래프가 먼저 돌아야 한다. API 부터 만들면 껍데기만 있고 확인할 게 없다
"""

from fastapi import APIRouter, Depends

from app.core.security import require_member_id
from app.schema.models import PingResponse

router = APIRouter()


# 1. 연결 확인 — 뼈대 단계의 유일한 엔드포인트
@router.get("/ping", response_model=PingResponse, tags=["Tutor"])
def ping(member_id: int = Depends(require_member_id)) -> PingResponse:
    return PingResponse(message="pong", member_id=member_id)
