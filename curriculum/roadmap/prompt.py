"""프롬프트 조립.

강의 카탈로그를 통째로 넣는다. 43개에 2,600자 남짓이라 청킹이나 검색이 필요 없다.
description 은 빼도 순서를 짜는 데 지장이 없고 토큰만 늘린다.
"""

from .catalog import LEVEL_LABEL


def build(courses, goal, budget_hours, weeks, hours_per_week, level, feedback=None):
    lines = [
        f"{i} | {c['title']} | {c['estimatedHours']}h | L{c['level']} | "
        f"{c['track']} | {','.join(c['topics'])}"
        for i, c in enumerate(courses)
    ]
    catalog_block = "\n".join(lines)
    level_label = LEVEL_LABEL[level]
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

    산술 제약은 프롬프트로 보장되지 않는다. 40시간 예산에 65시간을 고르는 일이
    실제로 일어난다. 검증에서 잡아 다시 부르는 편이 확실하다.
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
