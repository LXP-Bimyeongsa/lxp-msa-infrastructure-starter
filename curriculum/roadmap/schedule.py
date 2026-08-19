"""주차 배분.

시간 합산이라 계산이지 판단이 아니다. LLM 에게 맡기지 않는다.
"""


def pack_weeks(pairs, hours_per_week):
    """강의를 시간축에 늘어놓고 주 단위로 자른다.

    강의 하나가 여러 주에 걸칠 수 있다. 40시간짜리를 주 20시간으로 들으면 두 주가
    걸린다. 강의를 통째로 한 주에 몰아넣으면 그 주가 40시간이 되고 주차 수도 예산을
    넘긴다.

    쪼개면 총 주차가 ceil(총시간 / 주당시간) 으로 떨어진다. 총시간이 예산 안이면
    주차도 자동으로 예산 안이라 따로 검증할 필요가 없다.

    입력:  [(course, reason), ...]
    반환:  [[(course, 이번주에 들을 시간, 전체 시간, reason), ...], ...]
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
