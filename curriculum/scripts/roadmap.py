#!/usr/bin/env python3
"""커리큘럼 로드맵 1단계 스크립트.

강의 카탈로그를 통째로 프롬프트에 넣고 LLM에게 학습 경로를 짜게 한 뒤,
결과를 코드로 검증한다. 서비스도 LangGraph도 아직 없다. 되는지부터 본다.

역할을 나눈 기준
    LLM   어떤 강의를 어떤 순서로 들을지 고른다
    코드  고른 것이 실제로 존재하는지, 기간에 맞는지, 순서가 뒤집히지 않았는지 검증한다
          주차별 배분도 코드가 한다 (시간 합산이라 LLM에게 맡길 이유가 없다)

사용법
    export GEMINI_API_KEY=...
    python curriculum/scripts/roadmap.py --goal "백엔드 개발자가 되고 싶다" --weeks 26

    python curriculum/scripts/roadmap.py \
        --goal "프론트엔드로 취업" --weeks 12 --hours-per-week 15 --level 2

난이도는 트랙과 무관한 전역 척도다.
    L1 완전 입문 · L2 기초 · L3 중급 · L4 중상급 · L5 고급
트랙 안에서만 의미를 갖게 두면 "스프링 입문(L1)"이 "자바 객체지향(L2)"보다
앞이라는 판정이 나온다. 전역으로 두면 트랙을 넘어 비교할 수 있다.

의존성 없음. 표준 라이브러리만 쓴다.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "data" / "courses.json"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 무료 티어에서 흔히 만난다. 429 는 한도, 5xx 는 일시적 과부하다.
# 둘 다 잠깐 뒤에 다시 부르면 되는 종류라 실패로 끝내지 않는다.
RETRIABLE = {429, 500, 502, 503, 504}

LEVEL_LABEL = {
    1: "완전 입문", 2: "기초", 3: "중급", 4: "중상급", 5: "고급",
}


def load_catalog():
    with CATALOG.open(encoding="utf-8") as f:
        return json.load(f)


def build_prompt(courses, goal, budget_hours, weeks, hours_per_week, level,
                 feedback=None):
    """강의 목록을 통째로 넣는다.

    필드를 전부 넣지 않고 제목·시간·난이도·트랙·태그만 넣는다. description 은 빼도
    순서를 짜는 데 지장이 없고 토큰만 늘린다.

    feedback 이 있으면 직전 시도의 문제를 뒤에 붙인다. 재생성용이다.
    """
    level_label = LEVEL_LABEL[level]
    lines = [
        f"{i} | {c['title']} | {c['estimatedHours']}h | L{c['level']} | "
        f"{c['track']} | {','.join(c['topics'])}"
        for i, c in enumerate(courses)
    ]
    catalog_block = "\n".join(lines)
    tail = f"\n\n{feedback}" if feedback else ""

    return f"""너는 학습 경로를 설계한다.

[강의 목록]
번호 | 제목 | 예상 학습시간 | 난이도 | 트랙 | 태그
{catalog_block}

난이도는 트랙과 무관한 전역 척도다. L1 완전 입문 · L2 기초 · L3 중급 · L4 중상급 · L5 고급.
다른 트랙끼리도 그대로 비교할 수 있다.

[요청]
목표: {goal}
기간: {weeks}주, 주 {hours_per_week}시간
쓸 수 있는 총 학습시간: {budget_hours}시간
현재 수준: L{level} ({level_label})

[따를 순서]
1. 목표에 직접 필요한 트랙이 무엇인지 먼저 정한다.
2. 그 트랙에서 현재 수준부터 시작해 난이도가 낮은 것부터 고른다.
3. 예산이 남으면 목표를 뒷받침하는 인접 트랙을 더한다.
4. 그래도 남으면 그냥 남긴다. 채우려고 목표와 무관한 강의를 넣지 않는다.

[절대 지켜야 하는 것]
고른 강의의 예상 학습시간 합계는 {budget_hours}시간을 절대 넘지 않는다.
이건 타협하지 않는다. 넘을 것 같으면 뒤쪽 강의를 뺀다.
예산에 들어가는 조합이 강의 하나뿐이면 그 하나만 고른다.

[그다음 우선순위]
목표 적합성 > 난이도 순서 > 예산 활용
셋이 부딪히면 위쪽을 지킨다. {budget_hours}시간은 상한이지 채워야 할 목표가 아니다.
예산을 절반만 쓰고 목표에 맞는 편이, 예산을 다 쓰고 엉뚱한 강의를 넣는 것보다 낫다.

[아무것도 고르지 않아야 하는 경우]
카탈로그에 목표와 관련된 강의가 없으면 selected 를 빈 배열로 둔다.
비슷해 보이는 것을 억지로 고르지 않는다. 이 카탈로그는 소프트웨어 개발 강의만 담고 있다.

[규칙]
- 위 목록에 있는 강의만 고른다. 목록에 없는 강의를 만들어내지 않는다.
- 고른 강의의 예상 학습시간 합계가 {budget_hours}시간을 넘지 않는다.
- 같은 트랙 안에서는 난이도가 낮은 것부터 배열한다. L3 이 L2 보다 앞에 오면 안 된다.
- 트랙이 다르면 순서를 섞어도 된다. 인프라와 백엔드를 번갈아 배치해도 무방하다.
- 현재 수준(L{level})보다 2단계 이상 낮은 강의는 넣지 않는다. 이미 아는 것을 다시 듣게 하지 않는다.
- 예산이 빠듯하면 짧은 강의 여러 개로 채우지 말고, 목표의 핵심 강의를 먼저 넣는다.
- 각 강의를 그 자리에 둔 이유를 한 줄로 적는다.

[출력 형식]
아래 JSON 만 출력한다. 설명을 덧붙이지 않는다.

{{
  "goal_summary": "목표를 한 줄로 정리",
  "selected": [
    {{"index": 0, "reason": "이 자리에 둔 이유"}}
  ]
}}{tail}
"""


def build_feedback(valid, total, problems, budget_hours):
    """직전 시도의 문제를 다음 프롬프트에 붙일 형태로 만든다.

    검증이 잡은 것을 그대로 돌려준다. 산술 제약은 프롬프트로 보장되지 않아서
    (40시간 예산에 65시간을 고른다) 검증에서 잡아 다시 부르는 편이 확실하다.
    """
    picked = ", ".join(f"{c['title']}({c['estimatedHours']}h)" for c in valid) or "없음"
    lines = [
        "[직전 시도의 문제]",
        "아래처럼 짰는데 문제가 있었다. 고쳐서 다시 짜라.",
        "",
        f"직전 선택: {picked}",
        f"합계 {total}h / 예산 {budget_hours}h",
        "",
        "문제:",
    ]
    lines += [f"  - {p}" for p in problems]
    lines.append("")
    if total > budget_hours:
        lines.append(
            f"{total - budget_hours}시간을 줄여야 한다. 목표에서 먼 강의부터 뺀다. "
            "강의 하나만 남아도 괜찮다."
        )
    lines.append("목표 적합성은 유지한다. 관계없는 강의로 바꿔치지 않는다.")
    return "\n".join(lines)


def generate(courses, goal, budget_hours, weeks, hours_per_week, level,
             model, api_key, max_attempts=3, on_retry=None):
    """검증이 통과할 때까지 재생성한다.

    반환: (result, selected, valid, total, problems, attempts, tokens)
    attempts 는 실제로 부른 횟수다. 1 이면 첫 시도에 통과했다는 뜻이고,
    이 값이 프롬프트 품질 지표가 된다.
    """
    feedback = None
    tok_in = tok_out = 0

    for attempt in range(1, max_attempts + 1):
        prompt = build_prompt(courses, goal, budget_hours, weeks,
                              hours_per_week, level, feedback)
        result, usage = call_gemini(prompt, model, api_key)
        tok_in += usage.get("promptTokenCount", 0)
        tok_out += usage.get("candidatesTokenCount", 0)

        selected = result.get("selected", [])
        valid, total, problems = verify(courses, selected, budget_hours)

        if not problems or attempt == max_attempts:
            tokens = {"promptTokenCount": tok_in, "candidatesTokenCount": tok_out}
            return result, selected, valid, total, problems, attempt, tokens

        if on_retry:
            on_retry(attempt, problems)
        feedback = build_feedback(valid, total, problems, budget_hours)


def call_gemini(prompt, model, api_key, max_attempts=4):
    """재시도를 붙인다. 무료 티어에서 429 와 503 을 실제로 만난다.

    지수 백오프로 2초, 4초, 8초를 기다린다. 429 는 분당 한도라 몇 초면 풀리고,
    503 은 일시적 과부하라 대개 한 번 더 부르면 된다.
    """
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }).encode("utf-8")

    url = ENDPOINT.format(model=model) + f"?key={api_key}"

    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code in RETRIABLE and attempt < max_attempts:
                wait = 2 ** attempt
                print(f"[{e.code}] {wait}초 후 재시도 ({attempt}/{max_attempts - 1})",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"[API 오류] {e.code}\n{detail}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            if attempt < max_attempts:
                wait = 2 ** attempt
                print(f"[네트워크 오류] {e.reason} · {wait}초 후 재시도", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"[네트워크 오류] {e.reason}", file=sys.stderr)
            sys.exit(1)

    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    usage = payload.get("usageMetadata", {})
    return json.loads(text), usage


def verify(courses, selected, budget_hours):
    """LLM 이 고른 것을 코드로 검증한다. 이게 나중에 평가 하네스의 씨앗이 된다."""
    problems = []

    indices = [s["index"] for s in selected]

    out_of_range = [i for i in indices if not (0 <= i < len(courses))]
    if out_of_range:
        problems.append(f"존재하지 않는 번호를 골랐다: {out_of_range}")

    dupes = {i for i in indices if indices.count(i) > 1}
    if dupes:
        problems.append(f"같은 강의를 여러 번 골랐다: {sorted(dupes)}")

    valid = [courses[i] for i in indices if 0 <= i < len(courses)]
    total = sum(c["estimatedHours"] for c in valid)
    if total > budget_hours:
        problems.append(f"기간 초과: {total}h > {budget_hours}h")

    # 같은 트랙 안에서만 난이도 단조성을 본다.
    # 트랙이 다르면 순서가 자유로워야 한다. 인프라를 백엔드 중간에 끼워도 문제가 아니다.
    seen = {}
    for c in valid:
        prev = seen.get(c["track"])
        if prev and prev["level"] > c["level"]:
            problems.append(
                f"난이도 역전 [{c['track']}]: "
                f"'{prev['title']}'(L{prev['level']})가 "
                f"'{c['title']}'(L{c['level']})보다 앞"
            )
        seen[c["track"]] = c

    return valid, total, problems


def pack_weeks(pairs, hours_per_week):
    """강의를 시간축에 늘어놓고 주 단위로 자른다.

    강의 하나가 여러 주에 걸칠 수 있다. 40시간짜리를 주 20시간으로 들으면 두 주가
    걸린다. 강의를 통째로 한 주에 몰아넣으면 40시간 강의 하나가 한 주를 통째로
    먹고 그 주가 40시간이 되어버린다. 주차 수도 예산을 넘긴다.

    쪼개면 총 주차가 ceil(총시간 / 주당시간) 로 딱 떨어진다. 총시간이 예산 안이면
    주차도 자동으로 예산 안이라 따로 검증할 필요가 없다.

    반환: [[(course, 이번주에 들을 시간, 전체 시간, reason), ...], ...]
    """
    weeks, current, used = [], [], 0
    for course, reason in pairs:
        remaining = course["estimatedHours"]
        while remaining > 0:
            take = min(remaining, hours_per_week - used)
            current.append((course, take, course["estimatedHours"], reason))
            used += take
            remaining -= take
            if used >= hours_per_week:
                weeks.append(current)
                current, used = [], 0
    if current:
        weeks.append(current)
    return weeks


def main():
    p = argparse.ArgumentParser(description="커리큘럼 로드맵 1단계 스크립트")
    p.add_argument("--goal", required=True, help='예: "백엔드 개발자가 되고 싶다"')
    p.add_argument("--weeks", type=int, default=26)
    p.add_argument("--hours-per-week", type=int, default=20)
    p.add_argument("--level", type=int, default=1, choices=[1, 2, 3, 4, 5],
                   help="현재 수준. 1 완전입문 · 2 기초 · 3 중급 · 4 중상급 · 5 고급")
    p.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    p.add_argument("--max-attempts", type=int, default=3,
                   help="검증 실패 시 재생성 포함 최대 호출 횟수")
    p.add_argument("--show-prompt", action="store_true", help="보낸 프롬프트를 함께 출력")
    args = p.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY 가 없다.", file=sys.stderr)
        sys.exit(1)

    courses = load_catalog()
    budget = args.weeks * args.hours_per_week

    if args.show_prompt:
        print(build_prompt(courses, args.goal, budget, args.weeks,
                           args.hours_per_week, args.level))
        print("=" * 70)

    print(f"카탈로그 {len(courses)}개 / 모델 {args.model}")
    print(f"목표: {args.goal}")
    print(f"예산: {args.weeks}주 × {args.hours_per_week}h = {budget}h · 수준 L{args.level} ({LEVEL_LABEL[args.level]})")
    print("=" * 70)

    def on_retry(attempt, problems):
        print(f"[재생성 {attempt}] " + " · ".join(problems), file=sys.stderr)

    result, selected, valid, total, problems, attempts, usage = generate(
        courses, args.goal, budget, args.weeks, args.hours_per_week,
        args.level, args.model, api_key, args.max_attempts, on_retry,
    )

    # valid 와 같은 조건으로 걸러서 순서를 맞춘다.
    reasons = [s.get("reason", "") for s in selected
               if 0 <= s["index"] < len(courses)]
    weeks = pack_weeks(list(zip(valid, reasons)), args.hours_per_week)

    print(f"\n{result.get('goal_summary', '')}\n")
    shown = set()  # 여러 주에 걸친 강의는 첫 주에만 이유를 적는다
    for week_no, week in enumerate(weeks, start=1):
        print(f"[{week_no}주차] {sum(t for _, t, _, _ in week)}h")
        for course, take, whole, reason in week:
            span = f"{take}h" if take == whole else f"{take}h / 전체 {whole}h"
            print(f"    {course['title']} ({span}, L{course['level']}, {course['track']})")
            if reason and course["title"] not in shown:
                print(f"      → {reason}")
                shown.add(course["title"])

    print("=" * 70)
    print(f"선택 {len(valid)}개 · 총 {total}h / 예산 {budget}h · "
          f"{len(weeks)}주 / 예산 {args.weeks}주")
    print(f"호출 {attempts}회 · 토큰 입력 {usage.get('promptTokenCount', '?')} / "
          f"출력 {usage.get('candidatesTokenCount', '?')}")

    if problems:
        print(f"\n검증 실패 {len(problems)}건")
        for msg in problems:
            print(f"  - {msg}")
        sys.exit(2)

    print("\n검증 통과")


if __name__ == "__main__":
    main()
