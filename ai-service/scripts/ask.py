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

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import RECURSION_LIMIT
from app.graph.builder import build_graph
from app.tools.rag import is_ready


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--course", default=None)
    args = ap.parse_args()

    if not is_ready():
        raise SystemExit("색인이 없다. init_vectorstore.py 를 먼저 돌린다")

    state = build_graph().invoke(
        {"question": args.question, "course_id": args.course, "lang": "ko"},
        {"recursion_limit": RECURSION_LIMIT},
    )

    print(f"route      : {state['route']}")
    print(f"top_score  : {state['top_score']:.3f}")
    print(f"검색 질의  : {state['search_query']}")
    print(f"판정       : {'충분' if state.get('graded_ok') else '부족'}")
    print(f"재검색     : {state.get('retry', 0)}회")
    print(f"인용 조각  : {len(state['citations'])}개")
    for c in state["citations"]:
        print(f"  {c['score']:.3f}  {c['source_path']}#{c['seq']}")
    print(f"\n답변 {len(state['answer'])}자 중 앞 300자")
    print(state["answer"][:300])


if __name__ == "__main__":
    main()
