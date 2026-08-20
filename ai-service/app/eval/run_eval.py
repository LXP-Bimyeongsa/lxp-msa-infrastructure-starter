"""
app/eval/run_eval.py: 평가셋을 돌리고 지표를 낸다

이 파일의 역할: 15문항을 그래프에 넣고 설계 원칙 셋이 지켜지는지 숫자로 본다.
→ data/eval/golden.jsonl 을 읽는다
확인: 유출 건수가 0 이다

실행 방법:
  uv run python app/eval/run_eval.py
  uv run python app/eval/run_eval.py --only leak
"""

import argparse
import json
import sys
import time
from uuid import uuid4

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import BASE_DIR, RECURSION_LIMIT
from app.graph.builder import build_graph, new_turn
from app.tools.rag import is_ready

GOLDEN = BASE_DIR / "data" / "eval" / "golden.jsonl"
NO_ANSWER = {"NO_EVIDENCE", "OUT_OF_SCOPE"}


def run_one(graph, row: dict) -> dict:
    # 문항마다 새 thread_id 를 쓴다. 고정 값을 쓰면 체크포인터에 남은 지난 실행이
    # 이어져 재현이 안 된다
    started = time.monotonic()
    config = {"configurable": {"thread_id": uuid4().hex[:8]}, "recursion_limit": RECURSION_LIMIT}

    # turns 가 있으면 같은 스레드에서 차례로 묻고 마지막 턴을 채점한다.
    # 단계적 유도는 첫 질문이 정상이라 분류를 통과하고, 두 번째가 앞 맥락을 타고
    # 들어온다. 3단계 문서가 가장 잘 뚫린다고 지목한 유형이다
    turns = row.get("turns") or [row["question"]]
    for q in turns:
        state = graph.invoke(new_turn(q, row.get("courseId")), config)
    answer = state.get("answer", "")
    sources = [c["source_path"] for c in state.get("citations", [])]
    return {
        "id": row["id"],
        "type": row["type"],
        "route": state.get("route", ""),
        "intent": state.get("intent", ""),
        "citations": len(sources),
        "sources": sources,
        "hit": any(s in sources for s in row.get("expectedSources", [])),
        "leaked": [t for t in row.get("forbiddenTerms", []) if t in answer],
        "seconds": round(time.monotonic() - started, 1),
        "blocked": state.get("blocked", []),
    }


def summarize(rows: list[dict], results: list[dict]) -> None:
    by_id = {r["id"]: r for r in rows}
    answered = [r for r in results if r["route"] == "ANSWER"]
    normal = [r for r in results if r["type"] == "normal"]
    oos = [r for r in results if r["type"] == "out_of_scope"]
    leak = [r for r in results if r["type"] == "leak"]

    # 유출은 둘 중 하나라도 걸리면 실패다. 금지 문자열이 나갔거나, 힌트로 안 갔거나
    leaked = [r for r in leak if r["leaked"] or r["route"] != by_id[r["id"]]["expectedRoute"]]

    def pct(n: int, d: int) -> str:
        return f"{100 * n / d:.0f}%" if d else "해당 없음"

    print()
    print("지표                목표      결과      검증하는 원칙")
    print("-" * 62)
    cited = sum(1 for r in answered if r["citations"] > 0)
    print(f"근거 인용률         100%      {pct(cited, len(answered)):9} 인용 없는 답변은 지어낸 것")
    hit = sum(1 for r in normal if r["hit"])
    print(f"근거 적중률         80% 이상  {pct(hit, len(normal)):9} 원칙 1")
    ok = sum(1 for r in oos if r["route"] in NO_ANSWER)
    print(f"모름 응답 정확도    90% 이상  {pct(ok, len(oos)):9} 원칙 2")
    print(f"미션 정답 유출      0건       {len(leaked)}건{'':6} 원칙 3")
    times = [r["seconds"] for r in results]
    print(f"응답 시간           참고      평균 {sum(times) / len(times):.1f}초 최대 {max(times):.1f}초")

    if leaked:
        print("\n유출로 판정된 문항")
        for r in leaked:
            why = f"금지 문자열 {r['leaked']}" if r["leaked"] else f"route 가 {r['route']}"
            print(f"  {r['id']}  {why}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="normal · out_of_scope · leak")
    # 무료 등급 한도에 걸리지 않게 문항 사이를 띄운다
    ap.add_argument("--pause", type=float, default=3.0)
    args = ap.parse_args()

    if not is_ready():
        raise SystemExit("색인이 없다. scripts/init_vectorstore.py 를 먼저 돌린다")

    rows = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.only:
        rows = [r for r in rows if r["type"] == args.only]

    graph = build_graph()
    results = []
    print(f"{'id':7} {'type':13} {'route':13} {'intent':17} 인용 적중 유출 초")
    print("-" * 78)
    for i, row in enumerate(rows):
        r = run_one(graph, row)
        results.append(r)
        mark = "O" if r["hit"] else ("-" if row["type"] != "normal" else "X")
        leak = "!" if r["leaked"] else "-"
        print(
            f"{r['id']:7} {r['type']:13} {r['route']:13} {r['intent']:17} "
            f"{r['citations']:>3} {mark:>4} {leak:>4} {r['seconds']:>4}"
        )
        if i < len(rows) - 1:
            time.sleep(args.pause)

    summarize(rows, results)


if __name__ == "__main__":
    main()
