"""
scripts/score_dist.py: 평가셋의 검색 점수 분포를 본다

이 파일의 역할: MIN_SCORE 를 정하려면 실제 분포가 있어야 한다. 검색만 하고 판정은 안 한다.
→ data/eval/golden.jsonl 을 읽는다
확인: normal 과 out_of_scope 의 점수 구간이 갈리는지 본다

LLM 을 부르지 않으므로 값을 바꿔가며 여러 번 돌려도 싸다.

실행 방법:
  uv run python scripts/score_dist.py
"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import BASE_DIR
from app.tools.rag import is_ready, search

GOLDEN = BASE_DIR / "data" / "eval" / "golden.jsonl"


def main() -> None:
    if not is_ready():
        raise SystemExit("색인이 없다")

    rows = [json.loads(x) for x in GOLDEN.read_text(encoding="utf-8").splitlines() if x.strip()]
    scored = []
    for row in rows:
        hits = search(row["question"], row.get("courseId"))
        top = hits[0]["score"] if hits else 0.0
        scored.append((row["type"], row["id"], top))
        print(f"{row['id']:7} {row['type']:13} {top:.3f}")

    print()
    for t in ("normal", "out_of_scope", "leak"):
        vals = sorted(s for ty, _, s in scored if ty == t)
        if vals:
            print(f"{t:13} 최소 {vals[0]:.3f}  중앙 {vals[len(vals) // 2]:.3f}  최대 {vals[-1]:.3f}")

    # 두 구간이 겹치면 점수만으로는 가를 수 없다는 뜻이다
    n = [s for ty, _, s in scored if ty == "normal"]
    o = [s for ty, _, s in scored if ty == "out_of_scope"]
    if n and o:
        print()
        print(f"normal 최소 {min(n):.3f} vs out_of_scope 최대 {max(o):.3f}")
        if min(n) > max(o):
            print(f"→ 겹치지 않는다. 그 사이 값을 MIN_SCORE 로 쓸 수 있다: {(min(n) + max(o)) / 2:.3f}")
        else:
            print("→ 겹친다. 점수만으로는 가를 수 없다")


if __name__ == "__main__":
    main()
