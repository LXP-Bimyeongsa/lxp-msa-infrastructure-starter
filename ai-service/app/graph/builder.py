"""
app/graph/builder.py: 그래프 조립

이 파일의 역할: 노드와 엣지를 붙여 실행 가능한 그래프를 만든다.
→ scripts/ask.py 가 부른다. 나중에 app/api/endpoints.py 도 부른다
확인: 질문 하나를 넣으면 answer 와 citations 가 채워져 나온다

지금은 분기 하나까지다. 재검색 루프(S4)는 route_grade 에 갈래를 하나 더해서 붙인다.
한 번에 붙이지 않는 이유는 답이 이상할 때 분기 탓인지 루프 탓인지 가리기 위해서다.

generate 와 no_evidence 는 END 로 곧장 닫는다. 판정 노드로 되돌아가게 두면
같은 조건이 다시 참이 되어 같은 일을 반복한다
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.edges import route_grade
from app.graph.nodes import generate, grade, no_evidence, retrieve
from app.graph.state import TutorState


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(TutorState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("generate", generate)
    g.add_node("no_evidence", no_evidence)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    # 매핑 키는 route_grade 의 Literal 과 같은 값이어야 한다.
    # 매핑에 없는 값을 돌려주면 그 노드로 갈 길이 없다
    g.add_conditional_edges(
        "grade",
        route_grade,
        {"generate": "generate", "no_evidence": "no_evidence"},
    )
    g.add_edge("generate", END)
    g.add_edge("no_evidence", END)
    return g.compile()
