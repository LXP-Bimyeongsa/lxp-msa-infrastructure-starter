"""
app/graph/state.py: 그래프가 들고 다니는 상태

이 파일의 역할: 노드들이 읽고 쓰는 필드를 한 곳에 선언한다.
→ app/graph/nodes.py 가 이 딕셔너리를 받아 일부 키만 돌려준다
→ app/graph/builder.py 가 StateGraph(TutorState) 로 넘긴다
확인: 노드가 돌려준 키만 갱신되고 나머지는 그대로 남는다

messages 만 리듀서를 붙였다. 나머지는 덮어쓰기가 맞다. 재검색하면 chunks 는
이전 결과를 버리고 갈아야 하고, 누적하면 버린 결과가 근거로 남는다.

messages 는 반대다. 체크포인터가 thread_id 별로 상태를 이어주는데, 여기에
리듀서가 없으면 이번 턴 메시지가 앞 대화를 통째로 덮어쓴다
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class TutorState(TypedDict, total=False):
    # 입력
    thread_id: str
    member_id: int
    course_id: str
    lang: str  # ko · en
    question: str  # 학습자 원문
    messages: Annotated[list[AnyMessage], add_messages]  # 스레드 안에서 누적된다

    # 처리 중
    intent: str  # CONCEPT · MISSION · SOLUTION_SEEKING · OUT_OF_SCOPE
    # 검색용으로 다시 쓴 질문. question 과 반드시 분리한다.
    # 재작성은 검색을 위한 것이고, 답변은 학습자가 실제로 한 질문에 해야 한다
    search_query: str
    # 앞 대화를 반영해 혼자서도 뜻이 통하게 고친 질문. "그거 왜 필요해" 같은 것을 푼다
    standalone_question: str
    chunks: list[dict]
    top_score: float
    graded_ok: bool  # grade 판정 결과. route_grade 가 이것만 본다
    retry: int  # 이 필드가 없으면 재검색 루프가 끝나지 않는다

    # 출력
    route: str  # ANSWER · HINT · NO_EVIDENCE · OUT_OF_SCOPE
    answer: str
    citations: list[dict]
    blocked: list[str]  # 가드레일이 걸러낸 사유. 비어 있으면 통과
