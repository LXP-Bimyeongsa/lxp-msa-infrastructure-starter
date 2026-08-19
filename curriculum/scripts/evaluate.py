#!/usr/bin/env python3
"""로드맵 평가 러너.

eval_roadmap.json 의 케이스를 전부 돌려 채점한다. 프롬프트를 고칠 때마다
나아졌는지 숫자로 확인하려고 만들었다. 감으로 고치면 뭐가 좋아졌는지 모른다.

채점은 두 층이다.
    공통  roadmap.verify() 가 보는 4가지 (번호 범위 · 중복 · 기간 · 난이도 역전)
    개별  케이스마다 적어둔 기대 (트랙 비율 · 필수 · 금지 · 수준 · 예산 활용)

전부 코드로 잰다. 사람이 읽고 판단하는 항목은 넣지 않았다. 자동으로 안 돌면
프롬프트를 고칠 때마다 쓰지 않게 되고, 그러면 있으나 마나다.

사용법
    export GEMINI_API_KEY=...
    python curriculum/scripts/evaluate.py
    python curriculum/scripts/evaluate.py --case R-04      한 건만
    python curriculum/scripts/evaluate.py --verbose        실패 상세

케이스 수만큼 API 를 호출한다. 무료 티어 RPM 을 넘지 않게 사이에 쉰다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap  # noqa: E402

EVAL = Path(__file__).resolve().parent.parent / "data" / "eval_roadmap.json"


def load_cases():
    with EVAL.open(encoding="utf-8") as f:
        return json.load(f)


def score(case, valid, total, problems, budget):
    """케이스별 기대를 채점한다. 반환은 (실패 사유 목록, 지표)."""
    exp = case.get("expect", {})
    fails = list(problems)
    titles = {c["title"] for c in valid}

    usage = total / budget if budget else 0
    tracks = exp.get("tracks")
    ratio = None
    if tracks and valid:
        hit = sum(1 for c in valid if c["track"] in tracks)
        ratio = hit / len(valid)
        floor = exp.get("trackRatioMin", 0)
        if ratio < floor:
            off = sorted({c["track"] for c in valid if c["track"] not in tracks})
            fails.append(
                f"트랙 비율 미달: {ratio:.0%} < {floor:.0%} (벗어난 트랙 {', '.join(off)})"
            )

    missing = [t for t in exp.get("mustInclude", []) if t not in titles]
    if missing:
        fails.append(f"필수 강의 누락: {', '.join(missing)}")

    banned = [t for t in exp.get("mustExclude", []) if t in titles]
    if banned:
        fails.append(f"들어가면 안 되는 강의 포함: {', '.join(banned)}")

    min_level = exp.get("minLevel")
    if min_level and valid:
        low = sorted({c["title"] for c in valid if c["level"] < min_level})
        if low:
            fails.append(f"수준 미달 강의(L{min_level} 미만): {', '.join(low)}")

    floor = exp.get("budgetUsageMin")
    if floor and usage < floor:
        fails.append(f"예산 활용 부족: {usage:.0%} < {floor:.0%}")

    cap = exp.get("maxSelected")
    if cap is not None and len(valid) > cap:
        fails.append(f"너무 많이 골랐다: {len(valid)}개 > {cap}개")

    return fails, {"usage": usage, "ratio": ratio}


def run_case(case, courses, model, api_key):
    budget = case["weeks"] * case["hoursPerWeek"]
    prompt = roadmap.build_prompt(
        courses, case["goal"], budget, case["weeks"],
        case["hoursPerWeek"], case["level"],
    )
    result, tokens = roadmap.call_gemini(prompt, model, api_key)
    selected = result.get("selected", [])
    valid, total, problems = roadmap.verify(courses, selected, budget)
    fails, metrics = score(case, valid, total, problems, budget)
    return {
        "case": case, "valid": valid, "total": total, "budget": budget,
        "fails": fails, "metrics": metrics, "tokens": tokens,
    }


def main():
    p = argparse.ArgumentParser(description="로드맵 평가 러너")
    p.add_argument("--case", help="케이스 id 하나만 (예: R-04)")
    p.add_argument("--model", default=roadmap.os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    p.add_argument("--verbose", action="store_true", help="선택된 강의까지 출력")
    p.add_argument("--sleep", type=float, default=7.0, help="케이스 사이 대기 초. RPM 회피")
    args = p.parse_args()

    api_key = roadmap.os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY 가 없다.", file=sys.stderr)
        sys.exit(1)

    courses = roadmap.load_catalog()
    cases = load_cases()
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"그런 케이스가 없다: {args.case}", file=sys.stderr)
            sys.exit(1)

    print(f"카탈로그 {len(courses)}개 · 케이스 {len(cases)}건 · 모델 {args.model}")
    print("=" * 78)

    results, tok_in, tok_out = [], 0, 0
    for i, case in enumerate(cases):
        if i:
            time.sleep(args.sleep)
        r = run_case(case, courses, args.model, api_key)
        results.append(r)
        tok_in += r["tokens"].get("promptTokenCount", 0)
        tok_out += r["tokens"].get("candidatesTokenCount", 0)

        mark = "통과" if not r["fails"] else "실패"
        ratio = r["metrics"]["ratio"]
        ratio_txt = f"트랙 {ratio:.0%} · " if ratio is not None else ""
        print(f"{r['case']['id']}  {mark}  {r['case']['goal'][:22]:<24} "
              f"{len(r['valid'])}개 · {r['total']}h/{r['budget']}h · "
              f"{ratio_txt}예산 {r['metrics']['usage']:.0%}")
        for msg in r["fails"]:
            print(f"        - {msg}")
        if args.verbose:
            for c in r["valid"]:
                print(f"        · L{c['level']} {c['track']:<6} {c['title']}")

    passed = sum(1 for r in results if not r["fails"])
    print("=" * 78)
    print(f"{passed}/{len(results)} 통과 · 토큰 입력 {tok_in:,} / 출력 {tok_out:,}")

    if passed < len(results):
        sys.exit(2)


if __name__ == "__main__":
    main()
