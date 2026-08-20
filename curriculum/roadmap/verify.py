"""LLM 이 고른 것을 코드로 검증한다.

계산으로 판정되는 것은 전부 여기서 본다. 모델에게 "기간 안에 들어가나"를 되묻지
않는다. 판정이 흔들리고 토큰만 쓴다.
"""


def pick(courses, selected):
    """쓸 수 있는 (강의, 이유) 만 골라낸다.

    번호를 고르는 것은 모델이라 없거나·정수가 아니거나·범위 밖일 수 있다.
    거르는 자리를 여기 하나로 둔다. 두 군데서 각자 거르면 강의 목록과 이유
    목록의 길이가 어긋나 짝이 밀린다.
    """
    out = []
    for s in selected:
        i = s.get("index") if isinstance(s, dict) else None
        # bool 은 int 의 하위형이라 따로 막는다. True 가 1번 강의가 되면 안 된다.
        if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(courses):
            out.append((courses[i], s.get("reason", "")))
    return out


def check(courses, selected, budget_hours):
    """반환: (유효한 강의 목록, 총 시간, 문제 목록)"""
    problems = []

    bad = [s for s in selected
           if not isinstance(s, dict)
           or not isinstance(s.get("index"), int)
           or isinstance(s.get("index"), bool)]
    if bad:
        problems.append(f"번호가 없거나 정수가 아닌 항목: {len(bad)}개")

    indices = [s["index"] for s in selected
               if isinstance(s, dict) and isinstance(s.get("index"), int)
               and not isinstance(s["index"], bool)]

    out_of_range = [i for i in indices if not (0 <= i < len(courses))]
    if out_of_range:
        problems.append(f"존재하지 않는 번호를 골랐다: {out_of_range}")

    dupes = {i for i in indices if indices.count(i) > 1}
    if dupes:
        problems.append(f"같은 강의를 여러 번 골랐다: {sorted(dupes)}")

    valid = [c for c, _ in pick(courses, selected)]
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
