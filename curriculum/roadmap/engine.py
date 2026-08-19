"""로드맵 생성 엔진.

생성 → 검증 → 실패면 재생성. 지금은 순수 파이썬 루프다.
LangGraph 로 감싸도 이 모양은 그대로다.

역할을 나눈 기준
    LLM   어떤 강의를 어떤 순서로 들을지 고른다
    코드  존재 여부·기간·순서를 검증하고 주차를 배분한다
"""

from dataclasses import dataclass, field

from . import prompt as prompt_mod
from . import verify
from .schedule import pack_weeks


@dataclass
class Result:
    goal_summary: str = ""
    courses: list = field(default_factory=list)      # [(course, reason)]
    weeks: list = field(default_factory=list)
    total_hours: int = 0
    budget_hours: int = 0
    week_count: int = 0
    attempts: int = 0
    problems: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.problems


def build(courses, llm, goal, weeks, hours_per_week, level,
          max_attempts=3, on_retry=None):
    """검증이 통과할 때까지 재생성한다.

    attempts 가 1 이면 첫 시도에 통과했다는 뜻이고, 이 값이 프롬프트 품질 지표다.
    루프가 있으면 결국 통과하지만 호출이 늘면 쿼터와 지연을 먹는다.
    """
    budget = weeks * hours_per_week
    feedback = None
    tok_in = tok_out = 0

    for attempt in range(1, max_attempts + 1):
        text = prompt_mod.build(courses, goal, budget, weeks,
                                hours_per_week, level, feedback)
        payload, usage = llm.generate(text)
        tok_in += usage.get("promptTokenCount", 0)
        tok_out += usage.get("candidatesTokenCount", 0)

        selected = payload.get("selected", [])
        valid, total, problems = verify.check(courses, selected, budget)

        if not problems or attempt == max_attempts:
            reasons = [s.get("reason", "") for s in selected
                       if 0 <= s["index"] < len(courses)]
            pairs = list(zip(valid, reasons))
            packed = pack_weeks(pairs, hours_per_week)
            return Result(
                goal_summary=payload.get("goal_summary", ""),
                courses=pairs,
                weeks=packed,
                total_hours=total,
                budget_hours=budget,
                week_count=len(packed),
                attempts=attempt,
                problems=problems,
                tokens={"input": tok_in, "output": tok_out},
            )

        if on_retry:
            on_retry(attempt, problems)
        feedback = prompt_mod.build_feedback(valid, total, problems, budget)
