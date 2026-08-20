#!/usr/bin/env python3
"""커리큘럼 로드맵 CLI.

로직은 curriculum/roadmap 패키지에 있다. 여기는 인자를 받아 출력만 한다.

사용법
    export GEMINI_API_KEY=...
    python curriculum/scripts/roadmap.py --goal "백엔드 개발자가 되고 싶다" --weeks 26

    python curriculum/scripts/roadmap.py \
        --goal "프론트엔드로 취업" --weeks 12 --hours-per-week 15 --level 2

난이도는 트랙과 무관한 전역 척도다.
    L1 완전 입문 · L2 기초 · L3 중급 · L4 중상급 · L5 고급
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from curriculum import roadmap  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="커리큘럼 로드맵 CLI")
    p.add_argument("--goal", required=True, help='예: "백엔드 개발자가 되고 싶다"')
    def positive(v):
        n = int(v)
        if n < 1:
            raise argparse.ArgumentTypeError(f"1 이상이어야 한다: {v}")
        return n

    p.add_argument("--weeks", type=positive, default=26)
    p.add_argument("--hours-per-week", type=positive, default=20)
    p.add_argument("--level", type=int, default=1, choices=[1, 2, 3, 4, 5],
                   help="현재 수준. 1 완전입문 · 2 기초 · 3 중급 · 4 중상급 · 5 고급")
    p.add_argument("--model", default=None)
    p.add_argument("--max-attempts", type=positive, default=3,
                   help="검증 실패 시 재생성 포함 최대 호출 횟수")
    args = p.parse_args()

    try:
        llm = roadmap.Gemini(model=args.model)
    except roadmap.LLMError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    courses = roadmap.load_courses()
    budget = args.weeks * args.hours_per_week

    print(f"카탈로그 {len(courses)}개 / 모델 {llm.model}")
    print(f"목표: {args.goal}")
    print(f"예산: {args.weeks}주 × {args.hours_per_week}h = {budget}h · "
          f"수준 L{args.level} ({roadmap.LEVEL_LABEL[args.level]})")
    print("=" * 70)

    def on_retry(attempt, problems):
        print(f"[재생성 {attempt}] " + " · ".join(problems), file=sys.stderr)

    try:
        r = roadmap.build(courses, llm, args.goal, args.weeks,
                          args.hours_per_week, args.level,
                          args.max_attempts, on_retry)
    except roadmap.LLMError as e:
        print(f"[API 오류] {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{r.goal_summary}\n")
    shown = set()  # 여러 주에 걸친 강의는 첫 주에만 이유를 적는다
    for week_no, week in enumerate(r.weeks, start=1):
        print(f"[{week_no}주차] {sum(t for _, t, _, _ in week)}h")
        for course, take, whole, reason in week:
            span = f"{take}h" if take == whole else f"{take}h / 전체 {whole}h"
            print(f"    {course['title']} ({span}, L{course['level']}, {course['track']})")
            if reason and course["title"] not in shown:
                print(f"      → {reason}")
                shown.add(course["title"])

    print("=" * 70)
    print(f"선택 {len(r.courses)}개 · 총 {r.total_hours}h / 예산 {r.budget_hours}h · "
          f"{r.week_count}주 / 예산 {args.weeks}주")
    print(f"호출 {r.attempts}회 · 토큰 입력 {r.tokens['input']} / 출력 {r.tokens['output']}")

    if r.problems:
        print(f"\n검증 실패 {len(r.problems)}건")
        for msg in r.problems:
            print(f"  - {msg}")
        sys.exit(2)

    print("\n검증 통과")


if __name__ == "__main__":
    main()
