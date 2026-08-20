"""
app/core/guardrails.py: 출력 검사

이 파일의 역할: 밖으로 나가기 직전의 답변을 보고 나가면 안 되는 것을 잡는다.
→ app/graph/nodes.py 의 guard 노드가 부른다
확인: 인용 없는 ANSWER 와 코드가 든 HINT 가 걸린다

앞 단계가 다 통과했는데도 여기를 두는 이유. 검색 필터는 질의 조건이고 의도 분류는
LLM 판단이다. 둘 다 틀릴 수 있고, 틀렸을 때 알아챌 방법이 결과물을 보는 것뿐이다
"""

import re

# 힌트에 코드 블록이 있으면 정답을 준 것으로 본다
CODE_FENCE = re.compile(r"```")


def check_output(route: str, answer: str, citations: list[dict]) -> list[str]:
    reasons = []

    # 1. 인용 없는 답변은 지어낸 것이다. 목표 지표가 인용률 100% 라 예외를 두지 않는다
    if route == "ANSWER" and not citations:
        reasons.append("근거 없이 답변했다")

    # 2. 제한 조각이 인용에 섞였다면 검색 필터가 뚫린 것이다.
    # 여기서 잡히면 답변을 막는 것보다 필터를 고치는 게 먼저다
    leaked = [c["source_path"] for c in citations if c.get("visibility") != "public"]
    if leaked:
        reasons.append(f"제한 조각이 인용됐다: {', '.join(leaked)}")

    # 3. 힌트에 코드 블록이 있으면 정답을 준 것이다
    if route == "HINT" and CODE_FENCE.search(answer):
        reasons.append("힌트에 코드 블록이 들어갔다")

    return reasons
