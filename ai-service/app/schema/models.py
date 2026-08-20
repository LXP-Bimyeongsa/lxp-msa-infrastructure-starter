"""
app/schema/models.py: API 요청·응답 모델

이 파일의 역할: 엔드포인트가 주고받는 형태를 선언한다.
→ app/api/endpoints.py · app/main.py 가 response_model 로 쓴다
확인: /docs 에서 각 응답의 필드가 보인다

그래프 상태(TutorState)는 여기 없다. S2 에서 app/graph/state.py 에 만든다.
API 계약과 그래프 내부 상태는 수명이 다르고, 같이 두면 한쪽을 고칠 때 다른 쪽이 딸려 온다
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    project: str
    index_ready: bool  # 색인이 없어도 서버는 뜬다. 사람이 볼 때 쓰는 값이다


class PingResponse(BaseModel):
    message: str
    member_id: int  # 게이트웨이가 넣은 값이 여기까지 도달했는지 확인하는 용도


class Citation(BaseModel):
    course_id: str
    seq: int
    source_path: str
    score: float


class ChatRequest(BaseModel):
    # 길이 상한은 비용 통제와 프롬프트 조작 방지 둘 다에 필요하다
    question: str = Field(min_length=1, max_length=2000)
    course_id: str | None = None
    lang: str = "ko"


class ChatResponse(BaseModel):
    # route 를 먼저 둔다. 클라이언트가 모름 응답과 힌트 응답일 때 화면을 다르게 그린다
    route: str  # ANSWER · HINT · NO_EVIDENCE · OUT_OF_SCOPE
    answer: str
    citations: list[Citation]
    # 아래 둘은 사후 분석용이다. 답변 본문만 남기면 왜 그렇게 답했는지 못 되짚는다
    intent: str
    top_score: float
