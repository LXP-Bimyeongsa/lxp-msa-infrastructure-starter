"""
app/graph/state.py: 그래프가 들고 다니는 상태

이 파일의 역할: 노드들이 읽고 쓰는 필드를 한 곳에 선언한다.
→ app/graph/nodes.py 가 이 딕셔너리를 받아 일부 키만 돌려준다
→ app/graph/builder.py 가 StateGraph(TutorState) 로 넘긴다
확인: 노드가 돌려준 키만 갱신되고 나머지는 그대로 남는다

리듀서를 붙이지 않았다. LangGraph 는 리듀서가 없으면 뒤 노드가 앞 노드를
덮어쓰는데, 여기서는 그게 맞는 동작이다. 재검색하면 chunks 는 이전 결과를
버리고 새 결과로 갈아야 한다. 누적하면 버린 결과가 근거로 남는다.
누적이 필요한 필드가 생기면 그때 Annotated[list, add] 를 붙인다
"""

from typing import TypedDict


class TutorState(TypedDict, total=False):
    # 입력
    thread_id: str
    member_id: int
    course_id: str
    lang: str  # ko · en
    question: str  # 학습자 원문
    history_summary: str  # 앞 대화 요약

    # 처리 중
    intent: str  # CONCEPT · MISSION · SOLUTION_SEEKING · OUT_OF_SCOPE
    # 검색용으로 다시 쓴 질문. question 과 반드시 분리한다.
    # 재작성은 검색을 위한 것이고, 답변은 학습자가 실제로 한 질문에 해야 한다
    search_query: str
    chunks: list[dict]
    top_score: float
    retry: int  # 이 필드가 없으면 재검색 루프가 끝나지 않는다

    # 출력
    route: str  # ANSWER · HINT · NO_EVIDENCE · OUT_OF_SCOPE
    answer: str
    citations: list[dict]
