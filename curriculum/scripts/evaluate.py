#!/usr/bin/env python3
"""로드맵 평가 러너.

eval_roadmap.json 의 케이스를 전부 돌려 채점한다. 프롬프트를 고칠 때마다
나아졌는지 숫자로 확인하려고 만들었다. 감으로 고치면 뭐가 좋아졌는지 모른다.

채점은 두 층이다.
    공통  verify.check() 4가지 (번호 범위 · 중복 · 기간 · 트랙 내 난이도 역전)
    개별  케이스마다 적어둔 기대

전부 코드로 잰다. 사람이 읽고 판단하는 항목은 넣지 않았다. 자동으로 안 돌면
프롬프트를 고칠 때마다 쓰지 않게 되고, 그러면 있으나 마나다.

사용법
    export GEMINI_API_KEY=...
    python curriculum/scripts/evaluate.py
    python curriculum/scripts/evaluate.py --case R-04 --verbose
    python curriculum/scripts/evaluate.py --max-attempts 1   루프 없이 프롬프트만

케이스 수만큼 API 를 호출한다. 무료 티어 한도가 하루 20건이라 금방 닿는다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from curriculum import roadmap  # noqa: E402

EVAL = Path(__file__).resolve().parent.parent / "data" / "eval_roadmap.json"


def load_cases():
    with EVAL.open(encoding="utf-8") as f:
        return json.load(f)


def score(case, result, courses):
    """케이스별 기대를 채점한다. 반환은 (실패 사유 목록, 지표)."""
    exp = case.get("expect", {})
    fails = list(result.problems)
    valid = [c for c, _ in result.courses]
    titles = {c["title"] for c in valid}

    # 채울 수 있는 상한은 예산과 가용 중 작은 쪽이다. 예산 대비로 재면
    # 카탈로그에 없는 만큼을 관계없는 강의로 채우라는 요구가 된다.
    floor_level = max(exp.get("minLevel", 1), case["level"] - 1)
    avail = roadmap.available_hours(courses, exp.get("tracks"), floor_level)
    ceiling = min(result.budget_hours, avail) if avail else result.budget_hours
    usage = result.total_hours / ceiling if ceiling else 0

    ratio = None
    tracks = exp.get("tracks")
    if tracks and valid:
        ratio = sum(1 for c in valid if c["track"] in tracks) / len(valid)
        floor = exp.get("trackRatioMin", 0)
        if ratio < floor:
            off = sorted({c["track"] for c in valid if c["track"] not in tracks})
            fails.append(
                f"트랙 비율 미달: {ratio:.0%} < {floor:.0%} (벗어난 트랙 {', '.join(off)})")

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

    floor = exp.get("fillRateMin")
    if floor and usage < floor:
        cap = f"{ceiling}h" + (" (가용 상한)" if avail and avail < result.budget_hours else "")
        fails.append(f"채움 부족: {result.total_hours}h / {cap} = {usage:.0%} < {floor:.0%}")

    cap = exp.get("maxSelected")
    if cap is not None and len(valid) > cap:
        fails.append(f"너무 많이 골랐다: {len(valid)}개 > {cap}개")

    least = exp.get("minSelected")
    if least is not None and len(valid) < least:
        fails.append(f"너무 적게 골랐다: {len(valid)}개 < {least}개")

    return fails, {"usage": usage, "ratio": ratio}


def main():
    p = argparse.ArgumentParser(description="로드맵 평가 러너")
    p.add_argument("--case", help="케이스 id 하나만 (예: R-04)")
    p.add_argument("--model", default=None)
    p.add_argument("--verbose", action="store_true", help="선택된 강의까지 출력")
    p.add_argument("--sleep", type=float, default=7.0, help="케이스 사이 대기 초")
    p.add_argument("--max-attempts", type=int, default=3,
                   help="검증 실패 시 재생성 포함 최대 호출 횟수. 1 이면 루프 없음")
    args = p.parse_args()

    try:
        llm = roadmap.Gemini(model=args.model)
    except roadmap.LLMError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    courses = roadmap.load_courses()
    cases = load_cases()
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"그런 케이스가 없다: {args.case}", file=sys.stderr)
            sys.exit(1)

    print(f"카탈로그 {len(courses)}개 · 케이스 {len(cases)}건 · 모델 {llm.model}")
    print("=" * 78)

    results, tok_in, tok_out = [], 0, 0
    for i, case in enumerate(cases):
        if i:
            time.sleep(args.sleep)
        r = roadmap.build(courses, llm, case["goal"], case["weeks"],
                          case["hoursPerWeek"], case["level"], args.max_attempts)
        fails, metrics = score(case, r, courses)
        results.append((case, r, fails))
        tok_in += r.tokens["input"]
        tok_out += r.tokens["output"]

        mark = "통과" if not fails else "실패"
        ratio_txt = f"트랙 {metrics['ratio']:.0%} · " if metrics["ratio"] is not None else ""
        retry = "" if r.attempts == 1 else f" · 재생성 {r.attempts - 1}회"
        print(f"{case['id']}  {mark}  {case['goal'][:22]:<24} "
              f"{len(r.courses)}개 · {r.total_hours}h/{r.budget_hours}h · "
              f"{ratio_txt}채움 {metrics['usage']:.0%}{retry}")
        for msg in fails:
            print(f"        - {msg}")
        if args.verbose:
            for c, _ in r.courses:
                print(f"        · L{c['level']} {c['track']:<6} {c['title']}")

    passed = sum(1 for _, _, f in results if not f)
    first_try = sum(1 for _, r, _ in results if r.attempts == 1)
    calls = sum(r.attempts for _, r, _ in results)
    print("=" * 78)
    print(f"{passed}/{len(results)} 통과 · 첫 시도 통과 {first_try}/{len(results)} · 호출 {calls}회")
    print(f"토큰 입력 {tok_in:,} / 출력 {tok_out:,}")

    if passed < len(results):
        sys.exit(2)


if __name__ == "__main__":
    main()
