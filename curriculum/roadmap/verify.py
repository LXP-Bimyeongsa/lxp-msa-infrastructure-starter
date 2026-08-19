"""LLM 이 고른 것을 코드로 검증한다.

계산으로 판정되는 것은 전부 여기서 본다. 모델에게 "기간 안에 들어가나"를 되묻지
않는다. 판정이 흔들리고 토큰만 쓴다.
"""


def check(courses, selected, budget_hours):
    """반환: (유효한 강의 목록, 총 시간, 문제 목록)"""
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
