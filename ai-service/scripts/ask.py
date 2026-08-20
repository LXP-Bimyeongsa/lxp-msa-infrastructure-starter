"""
scripts/ask.py: 그래프를 한 번 돌려본다

이 파일의 역할: 질문 하나를 그래프에 넣고 어느 경로로 갔는지와 근거를 본다.
→ app/graph/builder.py 의 그래프를 부른다
확인: route 가 ANSWER 이고 citations 가 비어 있지 않다

실행 방법:
  uv run python scripts/ask.py "청킹할 때 겹침을 왜 두나요"
  uv run python scripts/ask.py "질문" --course c-04
"""

import argparse
import sys
from uuid import uuid4

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import RECURSION_LIMIT
from app.graph.builder import build_graph, new_turn
from app.tools.rag import is_ready


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--course", default=None)
    ap.add_argument("--thread", default=None, help="같은 값을 주면 앞 대화를 이어간다")
    args = ap.parse_args()

    if not is_ready():
        raise SystemExit("색인이 없다. init_vectorstore.py 를 먼저 돌린다")

    # thread_id 를 안 주면 매번 새 실행이다. 고정 값을 쓰면 지난 실행이 이어져
    # 재현이 안 되므로, 이어가려는 의도가 있을 때만 준다
    thread = args.thread or uuid4().hex[:8]
    state = build_graph().invoke(
        new_turn(args.question, args.course),
        {"configurable": {"thread_id": thread}, "recursion_limit": RECURSION_LIMIT},
    )
    print(f"thread     : {thread}")

    print(f"route      : {state['route']}")
    print(f"intent     : {state.get('intent', '-')}")
    print(f"top_score  : {state.get('top_score', 0.0):.3f}")
    print(f"검색 질의  : {state.get('search_query', '(검색 안 함)')}")
    if "graded_ok" in state:
        print(f"판정       : {'충분' if state['graded_ok'] else '부족'}")
        print(f"재검색     : {state.get('retry', 0)}회")
    blocked = state.get("blocked") or []
    print(f"가드레일   : {'통과' if not blocked else ' / '.join(blocked)}")
    print(f"인용 조각  : {len(state['citations'])}개")
    for c in state["citations"]:
        print(f"  {c['score']:.3f}  {c['source_path']}#{c['seq']}")
    print(f"\n답변 {len(state['answer'])}자 중 앞 300자")
    print(state["answer"][:300])


if __name__ == "__main__":
    main()
