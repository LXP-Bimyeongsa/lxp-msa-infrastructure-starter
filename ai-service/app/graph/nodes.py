"""
app/graph/nodes.py: 그래프 노드

이 파일의 역할: 상태를 받아 일부 키만 갱신해 돌려준다.
→ app/graph/builder.py 가 add_node 로 등록한다
확인: retrieve 가 chunks 와 top_score 를 채우고, generate 가 answer 를 만든다
"""

from app.graph.state import TutorState
from app.tools.rag import search


# 1. 검색
def retrieve(state: TutorState) -> dict:
    # 재작성(S4)이 돌기 전에는 search_query 가 비어 있다. 그때는 원문으로 찾는다
    query = state.get("search_query") or state["question"]
    chunks = search(query, state.get("course_id"))
    return {
        "search_query": query,
        "chunks": chunks,
        "top_score": chunks[0]["score"] if chunks else 0.0,
    }


# 2. 답변 생성
def generate(state: TutorState) -> dict:
    # S2 에서는 모델을 부르지 않고 조각을 그대로 잇는다.
    # 여기에 제대로 된 생성을 먼저 붙이면 검색이 빗나가도 답이 그럴듯해서
    # 무엇이 잘못됐는지 눈치채지 못한다. 프롬프트는 S5 이후에 손본다
    chunks = state.get("chunks", [])
    return {
        "answer": "\n\n".join(c["text"] for c in chunks),
        "citations": [
            {k: c[k] for k in ("course_id", "seq", "source_path", "score")} for c in chunks
        ],
        "route": "ANSWER",
    }
