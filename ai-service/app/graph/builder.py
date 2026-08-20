"""
app/graph/builder.py: 그래프 조립

이 파일의 역할: 노드와 엣지를 붙여 실행 가능한 그래프를 만든다.
→ scripts/ask.py 가 부른다. 나중에 app/api/endpoints.py 도 부른다
확인: 질문 하나를 넣으면 answer 와 citations 가 채워져 나온다

지금은 직선이다. 분기(S3)와 루프(S4)는 여기에 add_conditional_edges 로 붙는다.
한 번에 붙이지 않는 이유는 답이 이상할 때 분기 탓인지 루프 탓인지 가리기 위해서다
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import generate, retrieve
from app.graph.state import TutorState


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(TutorState)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()
