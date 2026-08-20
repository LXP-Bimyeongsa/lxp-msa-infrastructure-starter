"""
app/schema/models.py: API 요청·응답 모델

이 파일의 역할: 엔드포인트가 주고받는 형태를 선언한다.
→ app/api/endpoints.py · app/main.py 가 response_model 로 쓴다
확인: /docs 에서 각 응답의 필드가 보인다

그래프 상태(TutorState)는 여기 없다. S2 에서 app/graph/state.py 에 만든다.
API 계약과 그래프 내부 상태는 수명이 다르고, 같이 두면 한쪽을 고칠 때 다른 쪽이 딸려 온다
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    project: str
    index_ready: bool  # 색인이 없어도 서버는 뜬다. 사람이 볼 때 쓰는 값이다


class PingResponse(BaseModel):
    message: str
    member_id: int  # 게이트웨이가 넣은 값이 여기까지 도달했는지 확인하는 용도
