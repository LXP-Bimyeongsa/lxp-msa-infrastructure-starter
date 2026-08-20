"""로드맵 생성 그래프.

생성 -> 검증 -> 실패면 되돌아가 재생성. LangGraph 로 묶었다.

    START -> generate -> verify -+-(통과/횟수소진)-> schedule -> END
                  ^              |
                  +--(실패)------+

for 문으로도 같은 흐름이 돈다. 묶은 이유는 사이클 자체가 아니라 트레이스다.
재생성이 "왜" 일어났는지는 지역변수 problems 안에 있어서, 데코레이터만 달면
같은 호출이 3번 찍히고 이유는 안 남는다. 노드로 쪼개면 verify 가 남긴 실패
사유가 그대로 LangSmith 에 올라간다. "첫 시도 통과율"이 프롬프트 품질 지표라
그게 보여야 한다.

역할을 나눈 기준
    LLM   어떤 강의를 어떤 순서로 들을지 고른다
    코드  존재 여부·기간·순서를 검증하고 주차를 배분한다

상태에 llm 과 on_retry 를 넣지 않고 config 로 넘긴다. 체크포인터를 붙이는
날 상태는 직렬화 대상이 되는데, 소켓을 쥔 객체와 콜백은 직렬화가 안 된다.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

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


class State(TypedDict, total=False):
    # 입력
    courses: list
    goal: str
    budget_hours: int
    weeks: int
    hours_per_week: int
    level: int
    max_attempts: int
    deadline: float | None
    # 돌면서 쌓이는 것
    feedback: str | None
    attempts: int
    tok_in: int
    tok_out: int
    # 노드가 채우는 것
    goal_summary: str
    selected: list
    valid: list
    total_hours: int
    problems: list
    packed: list


def _deps(config):
    """runtime 의존성. 상태가 아니라 config 에 둔다."""
    c = (config or {}).get("configurable", {})
    return c.get("llm"), c.get("on_retry")


def generate(state: State, config) -> dict:
    """프롬프트를 조립해 모델에게 고르게 한다. 재생성이면 피드백이 붙는다."""
    llm, _ = _deps(config)
    text = prompt_mod.build(
        state["courses"], state["goal"], state["budget_hours"],
        state["weeks"], state["hours_per_week"], state["level"],
        state.get("feedback"),
    )
    payload, usage = llm.generate(text, deadline=state.get("deadline"))
    return {
        "goal_summary": payload.get("goal_summary", ""),
        "selected": payload.get("selected", []),
        "attempts": state.get("attempts", 0) + 1,
        "tok_in": state.get("tok_in", 0) + usage.get("promptTokenCount", 0),
        "tok_out": state.get("tok_out", 0) + usage.get("candidatesTokenCount", 0),
    }


def check(state: State, config) -> dict:
    """계산으로 판정되는 것을 코드가 본다. 모델에게 되묻지 않는다."""
    _, on_retry = _deps(config)
    valid, total, problems = verify.check(
        state["courses"], state["selected"], state["budget_hours"])

    out = {"valid": valid, "total_hours": total, "problems": problems}
    if problems and state["attempts"] < state["max_attempts"]:
        if on_retry:
            on_retry(state["attempts"], problems)
        # 무엇이 틀렸는지 적어 다음 프롬프트에 붙인다.
        out["feedback"] = prompt_mod.build_feedback(
            valid, total, problems, state["budget_hours"])
    return out


def schedule(state: State, config) -> dict:
    """고른 순서를 주당 시간에 맞춰 주차로 나눈다. 긴 강의는 여러 주에 걸친다."""
    pairs = verify.pick(state["courses"], state["selected"])
    return {"packed": pack_weeks(pairs, state["hours_per_week"])}


def route(state: State) -> str:
    """검증 뒤 갈림길. 통과했거나 횟수를 다 썼으면 나간다."""
    if not state["problems"]:
        return "schedule"
    if state["attempts"] >= state["max_attempts"]:
        return "schedule"
    if state.get("deadline") and time.monotonic() >= state["deadline"]:
        # 재생성할 시간이 없다. 지금까지 고른 것으로 내보낸다.
        return "schedule"
    return "generate"


def _compile():
    g = StateGraph(State)
    g.add_node("generate", generate)
    g.add_node("verify", check)
    g.add_node("schedule", schedule)
    g.add_edge(START, "generate")
    g.add_edge("generate", "verify")
    g.add_conditional_edges("verify", route, ["generate", "schedule"])
    g.add_edge("schedule", END)
    return g.compile()


# 기동할 때 한 번 컴파일한다. 요청마다 다시 만들 이유가 없다.
GRAPH = _compile()


def _inputs(courses, goal, weeks, hours_per_week, level, max_attempts,
            deadline_seconds=None):
    # 서비스는 pydantic 이 막지만 CLI 와 평가 러너는 안 막는다.
    # hours_per_week 가 0 이면 pack_weeks 가 한 주에 0시간씩 담아 무한루프가 된다.
    for name, v in (("weeks", weeks), ("hours_per_week", hours_per_week),
                    ("max_attempts", max_attempts)):
        if not isinstance(v, int) or v < 1:
            raise ValueError(f"{name} 는 1 이상의 정수여야 한다: {v!r}")
    budget = weeks * hours_per_week
    return budget, {
        "courses": courses, "goal": goal, "budget_hours": budget,
        "weeks": weeks, "hours_per_week": hours_per_week, "level": level,
        "max_attempts": max_attempts,
        "feedback": None, "attempts": 0, "tok_in": 0, "tok_out": 0,
        # 요청 하나가 쓸 수 있는 전체 시간. 안 주면 제한이 없다.
        "deadline": (time.monotonic() + deadline_seconds) if deadline_seconds else None,
    }


def _config(llm, on_retry, max_attempts):
    return {
        "configurable": {"llm": llm, "on_retry": on_retry},
        # generate+verify 가 한 번에 2 스텝이다. 여유를 두고 잡는다.
        "recursion_limit": max_attempts * 2 + 5,
    }


def _result(final, courses, budget) -> Result:
    # 거르는 규칙은 verify.pick 하나만 쓴다. 여기서 따로 거르면 강의와 이유의
    # 짝이 밀릴 수 있다.
    pairs = verify.pick(courses, final["selected"])
    packed = final["packed"]
    return Result(
        goal_summary=final["goal_summary"],
        courses=pairs,
        weeks=packed,
        total_hours=final["total_hours"],
        budget_hours=budget,
        week_count=len(packed),
        attempts=final["attempts"],
        problems=final["problems"],
        tokens={"input": final["tok_in"], "output": final["tok_out"]},
    )


def build(courses, llm, goal, weeks, hours_per_week, level,
          max_attempts=3, on_retry=None, deadline_seconds=None) -> Result:
    """검증이 통과할 때까지 재생성한다.

    attempts 가 1 이면 첫 시도에 통과했다는 뜻이고, 이 값이 프롬프트 품질 지표다.
    루프가 있으면 결국 통과하지만 호출이 늘면 쿼터와 지연을 먹는다.
    """
    budget, state = _inputs(courses, goal, weeks, hours_per_week, level,
                            max_attempts, deadline_seconds)
    final = GRAPH.invoke(state, config=_config(llm, on_retry, max_attempts))
    return _result(final, courses, budget)


def stream(courses, llm, goal, weeks, hours_per_week, level, max_attempts=3,
           deadline_seconds=None):
    """build() 와 같은 일을 하되 노드가 끝날 때마다 진행 상황을 내보낸다.

    yield 는 (종류, 내용) 이다. 마지막 한 번만 종류가 "result" 이고 Result 가 온다.

        ("generate", {"attempt": 1, ...})
        ("verify",   {"ok": False, "problems": [...]})
        ("generate", {"attempt": 2, ...})
        ("verify",   {"ok": True, ...})
        ("schedule", {"week_count": 4})
        ("result",   Result(...))

    모델이 JSON 한 덩어리를 뱉으므로 토큰 단위로 흘려보낼 것이 없다.
    반쯤 온 JSON 으로는 화면에 그릴 게 없다. 그래서 단계만 내보낸다.
    쓸모는 재생성이 도는 동안 화면이 멈춰 보이지 않게 하는 것이다.
    """
    budget, state = _inputs(courses, goal, weeks, hours_per_week, level,
                            max_attempts, deadline_seconds)
    final = None

    for mode, chunk in GRAPH.stream(
        state, config=_config(llm, None, max_attempts),
        stream_mode=["updates", "values"],
    ):
        if mode == "values":
            final = chunk          # 마지막 것이 최종 상태다
            continue
        for node, upd in chunk.items():
            if node == "generate":
                yield node, {
                    "attempt": upd["attempts"],
                    "selected": len(upd["selected"]),
                    "tokens": {"input": upd["tok_in"], "output": upd["tok_out"]},
                }
            elif node == "verify":
                yield node, {
                    "ok": not upd["problems"],
                    "problems": upd["problems"],
                    "selected": len(upd["valid"]),
                    "total_hours": upd["total_hours"],
                }
            elif node == "schedule":
                yield node, {"week_count": len(upd["packed"])}

    yield "result", _result(final, courses, budget)
