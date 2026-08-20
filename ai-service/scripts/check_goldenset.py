"""
scripts/check_goldenset.py: 평가셋 자체를 검사한다

이 파일의 역할: 문항이 지표를 부풀리거나 무의미해지는 경우를 기계로 잡는다.
→ data/eval/golden.jsonl 과 data/raw/courses 를 읽는다
확인: 오류 0건. 경고는 사람이 판단한다

사람 교차 검수를 대신하지 못한다. 여기서 잡는 것은 규칙으로 판정되는 것뿐이고,
질문이 학습자가 실제로 물을 법한지는 사람이 봐야 한다.

LLM 도 임베딩도 부르지 않는다. 몇 번이고 돌려도 싸다.

실행 방법:
  uv run python scripts/check_goldenset.py
"""

import json
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import BASE_DIR, RAW_DIR

GOLDEN = BASE_DIR / "data" / "eval" / "golden.jsonl"
COURSES = RAW_DIR / "courses"
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[가-힣]{3,}")

# 3단계 문서 7.4 의 배분
TARGET = {"normal": 20, "out_of_scope": 10, "leak": 15}

errors: list[str] = []
warnings: list[str] = []


def load_corpus() -> tuple[dict[str, str], dict[str, str]]:
    public, restricted = {}, {}
    for path in COURSES.rglob("*.md"):
        course = path.relative_to(COURSES).parts[0]
        text = path.read_text(encoding="utf-8", errors="replace")
        bucket = restricted if path.name == "solution.md" else public
        bucket[course] = bucket.get(course, "") + "\n" + text
    return public, restricted


def eojeol_ngrams(text: str, n: int = 4) -> set[str]:
    words = text.split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def main() -> None:
    rows = [json.loads(x) for x in GOLDEN.read_text(encoding="utf-8").splitlines() if x.strip()]
    public, restricted = load_corpus()

    # 1. id 와 질문 중복
    for key in ("id", "question"):
        dup = [v for v, c in Counter(r[key] for r in rows).items() if c > 1]
        if dup:
            errors.append(f"{key} 중복: {dup}")

    for r in rows:
        rid, q, course = r["id"], r["question"], r.get("courseId", "")
        pub = public.get(course, "")

        # 2. normal: 기대 문서가 실제로 있는가
        if r["type"] == "normal":
            for src in r.get("expectedSources", []):
                if not (COURSES / src).exists():
                    errors.append(f"{rid} expectedSources 가 없는 파일: {src}")
            if not r.get("expectedSources"):
                errors.append(f"{rid} normal 인데 expectedSources 가 없다")

            # 3. 교안 문장을 그대로 베꼈는가.
            # 베끼면 검색이 너무 쉬워져 근거 적중률이 실력보다 높게 나온다
            copied = eojeol_ngrams(q) & eojeol_ngrams(pub)
            if copied:
                warnings.append(f"{rid} 교안 문구를 그대로 씀: {sorted(copied)[:2]}")

        # 4. out_of_scope: 정말 강의에 없는 것을 묻는가.
        # 질문의 모든 용어가 교안에 있으면 사실은 범위 안일 수 있다
        if r["type"] == "out_of_scope":
            toks = set(TOKEN.findall(q))
            absent = [t for t in toks if t.lower() not in pub.lower()]
            if not absent:
                warnings.append(f"{rid} 질문의 모든 용어가 {course} 교안에 있다. 범위 안일 수 있다")

        # 5. leak: 금지 문자열이 쓸모 있는가
        if r["type"] == "leak":
            terms = r.get("forbiddenTerms", [])
            for t in terms:
                if t in pub:
                    errors.append(f"{rid} 금지 문자열이 공개 문서에도 있다: {t!r}. 정상 답변이 유출로 잡힌다")
                if t not in restricted.get(course, ""):
                    errors.append(f"{rid} 금지 문자열이 제한 문서에 없다: {t!r}. 검사가 무의미하다")
            if not terms:
                warnings.append(f"{rid} 금지 문자열이 없다. route 만 본다")

    # 6. 배분
    counts = Counter(r["type"] for r in rows)
    print(f"문항 {len(rows)}개")
    for t, target in TARGET.items():
        got = counts.get(t, 0)
        mark = "" if got >= target else f"  ← {target - got}개 모자람"
        print(f"  {t:13} {got:2} / {target}{mark}")

    print(f"\n오류 {len(errors)}건")
    for e in errors:
        print(f"  {e}")
    print(f"경고 {len(warnings)}건  (사람이 판단한다)")
    for w in warnings:
        print(f"  {w}")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
