"""
app/graph/edges.py: 분기 함수

이 파일의 역할: 그래프가 어느 갈래로 갈지 정한다.
→ app/graph/builder.py 가 add_conditional_edges 에 넘긴다
확인: 판정이 부족이면 no_evidence 를 돌려준다

반환 타입을 Literal 로 못박고 builder 의 매핑 키와 같은 값을 쓴다.
매핑에 없는 문자열을 돌려주면 그 노드는 영영 실행되지 않는다.
add_node 로 등록해 둬도 소용없다. 매핑이 갈 수 있는 길의 전부다
"""

from typing import Literal

from app.core.config import MAX_RETRY
from app.graph.state import TutorState


def route_grade(state: TutorState) -> Literal["generate", "rewrite", "no_evidence"]:
    if state.get("graded_ok"):
        return "generate"
    if state.get("retry", 0) < MAX_RETRY:
        return "rewrite"
    # 이 갈래가 없으면 루프가 끝나지 않는다
    return "no_evidence"
