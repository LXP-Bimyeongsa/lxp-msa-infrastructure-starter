"""
app/graph/builder.py: 그래프 조립

이 파일의 역할: 노드와 엣지를 붙여 실행 가능한 그래프를 만든다.
→ scripts/ask.py 가 부른다. 나중에 app/api/endpoints.py 도 부른다
확인: 질문 하나를 넣으면 answer 와 citations 가 채워져 나온다

체크포인터가 thread_id 별로 상태를 저장한다. 같은 스레드로 다시 물으면 앞 대화가
messages 에 남아 있어서 "그거 왜 필요해" 같은 질문을 풀 수 있다.
다만 이번 턴에만 쓰는 필드(retry, chunks 등)는 호출하는 쪽에서 초기화해 넘겨야 한다.
안 하면 지난 턴의 retry 가 남아 재검색이 한 번도 안 돈다.

rewrite 가 retrieve 로 되돌아가는 순환이 하나 있다. 끝나는 조건은 route_grade 의
retry 상한이고, recursion_limit 은 그것이 안 먹었을 때를 위한 안전장치다.

generate 와 no_evidence 는 END 로 곧장 닫는다. 판정 노드로 되돌아가게 두면
같은 조건이 다시 참이 되어 같은 일을 반복한다
"""

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import CHECKPOINT_DB
from app.graph.edges import route_grade, route_intent
from app.graph.nodes import (
    classify,
    generate,
    grade,
    guard,
    hint,
    no_evidence,
    retrieve,
    rewrite,
)
from app.graph.state import TutorState


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(TutorState)
    g.add_node("classify", classify)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("generate", generate)
    g.add_node("rewrite", rewrite)
    g.add_node("hint", hint)
    g.add_node("no_evidence", no_evidence)
    g.add_node("guard", guard)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        route_intent,
        {"hint": "hint", "no_evidence": "no_evidence", "retrieve": "retrieve"},
    )
    g.add_edge("retrieve", "grade")
    # 매핑 키는 route_grade 의 Literal 과 같은 값이어야 한다.
    # 매핑에 없는 값을 돌려주면 그 노드로 갈 길이 없다
    g.add_conditional_edges(
        "grade",
        route_grade,
        {"generate": "generate", "rewrite": "rewrite", "no_evidence": "no_evidence"},
    )
    g.add_edge("rewrite", "retrieve")
    # 모델이 만든 답변만 검사한다. no_evidence 는 고정 문구라 볼 것이 없다
    g.add_edge("hint", "guard")
    g.add_edge("generate", "guard")
    g.add_edge("guard", END)
    g.add_edge("no_evidence", END)

    # check_same_thread=False: uvicorn 이 요청을 여러 스레드에서 처리한다
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))


# 턴마다 비워야 하는 필드. 체크포인터가 지난 턴 값을 그대로 들고 오기 때문이다.
# retry 가 남으면 재검색이 한 번도 안 돌고, chunks 가 남으면 버린 근거가 인용된다
def new_turn(question: str, course_id: str | None, lang: str = "ko", **extra) -> dict:
    return {
        "question": question,
        "course_id": course_id,
        "lang": lang,
        "search_query": "",
        "standalone_question": "",
        "chunks": [],
        "top_score": 0.0,
        "retry": 0,
        "graded_ok": False,
        "citations": [],
        "blocked": [],
        **extra,
    }
