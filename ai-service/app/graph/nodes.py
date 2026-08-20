"""
app/graph/nodes.py: 그래프 노드

이 파일의 역할: 상태를 받아 일부 키만 갱신해 돌려준다.
→ app/graph/builder.py 가 add_node 로 등록한다
확인: retrieve 가 chunks 와 top_score 를 채우고, generate 가 answer 를 만든다
"""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.core.config import MIN_SCORE, get_llm
from app.core.guardrails import check_output
from app.graph.state import TutorState
from app.tools.rag import course_outline, search


# 1. 의도 분류
class Intent(BaseModel):
    intent: Literal["CONCEPT", "MISSION", "SOLUTION_SEEKING", "OUT_OF_SCOPE"]
    # 앞 대화를 반영해 혼자서도 뜻이 통하게 고친 질문.
    # 분류가 이미 LLM 호출이라 여기서 같이 받는다. 따로 노드를 두면 호출이 하나 는다
    standalone_question: str = Field(description="앞 대화 없이도 뜻이 통하는 질문")
    reason: str = Field(description="한 문장 근거")


CLASSIFY = """학습자 질문의 의도를 하나로 분류한다.

이 강의가 다루는 자료 목록이다. 파일 이름이 곧 주제다.
{outline}

CONCEPT          위 목록에 있는 주제를 묻는다
MISSION          미션에 대해 묻지만 정답을 요구하지는 않는다
SOLUTION_SEEKING 미션의 정답, 완성 코드, 풀이를 요구한다. 우회 표현도 여기다
                 (남들은 어떻게 짰나, 예시 코드 좀, 답만 보고 이해할게)
OUT_OF_SCOPE     위 목록에 없는 주제다. 기술 질문이어도, 인접한 주제여도 목록에
                 없으면 여기다. 목록에 있는 파일이 그 질문에 답할 내용을 담고
                 있을지를 기준으로 판단한다

standalone_question 은 앞 대화를 모르는 사람도 이해할 수 있게 고쳐 쓴다.
지시대명사와 생략된 주어를 앞 대화에서 찾아 채운다. 앞 대화가 없으면 원문 그대로 둔다.

앞 대화:
{history}

질문: {question}"""


def _history(state: TutorState, limit: int = 6) -> str:
    msgs = state.get("messages", [])[-limit:]
    if not msgs:
        return "(없음)"
    role = {"human": "학습자", "ai": "튜터"}
    return "\n".join(f"{role.get(m.type, m.type)}: {m.text[:200]}" for m in msgs)


def classify(state: TutorState) -> dict:
    try:
        out = get_llm().with_structured_output(Intent).invoke(
            CLASSIFY.format(
                question=state["question"],
                history=_history(state),
                outline=course_outline(state.get("course_id")),
            )
        )
    except Exception:
        # 실패하면 CONCEPT 으로 두고 진행한다. SOLUTION_SEEKING 을 놓치는 셈이지만
        # 둘째 겹인 visibility 필터가 그대로 살아 있어 제한 조각은 여전히 안 나온다.
        # 두 겹으로 만든 이유가 이것이다
        return {"intent": "CONCEPT", "messages": [HumanMessage(state["question"])]}
    return {
        "intent": out.intent,
        "standalone_question": out.standalone_question or state["question"],
        # 이번 턴 질문을 여기서 한 번만 넣는다. 여러 노드에서 넣으면 중복된다
        "messages": [HumanMessage(state["question"])],
    }


# 2. 검색
def retrieve(state: TutorState) -> dict:
    # 재작성(S4)이 돌기 전에는 search_query 가 비어 있다. 그때는 원문으로 찾는다
    # 재작성이 있으면 그것을, 없으면 앞 대화를 푼 질문을, 그것도 없으면 원문을 쓴다
    query = state.get("search_query") or state.get("standalone_question") or state["question"]
    chunks = search(query, state.get("course_id"))
    return {
        "search_query": query,
        "chunks": chunks,
        "top_score": chunks[0]["score"] if chunks else 0.0,
    }


# 3. 품질 판정
class Verdict(BaseModel):
    enough: bool = Field(description="주어진 자료만으로 질문에 답할 수 있으면 true")
    reason: str = Field(description="한 문장 근거")


JUDGE = """너는 검색 결과가 질문에 답할 내용을 담고 있는지만 판정한다.
답을 만들지 말고 자료에 답이 들어 있는지만 본다.
질문이 다루는 주제를 언급만 하고 설명하지 않는 자료는 부족으로 본다.

질문: {question}

자료:
{context}"""


def grade(state: TutorState) -> dict:
    chunks = state.get("chunks", [])

    # 1단계는 점수다. 계산만 하니 비용이 없다.
    # 여기서 걸리면 2단계를 안 돌린다. 반대로 하면 명백히 실패한 검색에도 판정 비용이 나간다
    if not chunks or state.get("top_score", 0.0) < MIN_SCORE:
        return {"graded_ok": False}

    # 2단계는 내용이다. 점수는 넘었지만 실제로 답할 내용이 있는지 본다.
    # 같은 용어를 많이 쓰지만 다른 이야기를 하는 조각이 상위에 오는 경우가 여기서 걸린다
    context = "\n\n".join(c["text"][:600] for c in chunks)
    judge = get_llm().with_structured_output(Verdict)
    try:
        verdict = judge.invoke(JUDGE.format(question=state["question"], context=context))
    except Exception:
        # 판정에 실패하면 충분하다고 보지 않는다. 모름 응답이 반쪽 답변보다 낫다
        return {"graded_ok": False}
    return {"graded_ok": verdict.enough}


# 4. 질문 재작성
REWRITE = """학습자 질문을 강의 교안에서 검색하기 좋은 형태로 바꿔라.
교안에 쓰일 법한 용어와 명사구로 쓰고, 인사말과 군더더기를 뺀다.
질문의 의도를 바꾸지 말고 답을 짐작해 넣지도 마라.
바꾼 질의 한 줄만 출력한다.

원래 질문: {question}
이미 써 본 질의: {tried}"""


def rewrite(state: TutorState) -> dict:
    retry = state.get("retry", 0) + 1
    try:
        out = get_llm(temperature=0.3).invoke(
            REWRITE.format(question=state["question"], tried=state.get("search_query", ""))
        )
        # .text 는 속성이다. 메서드로 부르면 지금은 경고만 나지만 곧 깨진다
        query = out.text.strip()
    except Exception:
        # 재작성이 실패해도 retry 는 올린다. 안 올리면 같은 질의로 영원히 돈다
        return {"retry": retry}
    # 재작성 결과만 search_query 에 넣는다. question 은 건드리지 않는다.
    # 답변은 학습자가 실제로 한 질문에 해야 한다
    return {"search_query": query or state["question"], "retry": retry}


# 5. 근거 부족
def no_evidence(state: TutorState) -> dict:
    # 이 경로에서는 조각을 모델에 넘기지 않는다. 넘기지 않으면 지어낼 재료가 없다.
    # 프롬프트로 "모르면 모른다고 하라"고 부탁하는 것과 다른 지점이 여기다
    course = state.get("course_id") or "이 강의"
    # 두 경우를 route 로 구분한다. 검색이 실패한 것과 애초에 범위 밖인 것은 원인이
    # 다르다. 전자가 많으면 검색을 고치고 후자가 많으면 안내 문구를 고친다
    out_of_scope = state.get("intent") == "OUT_OF_SCOPE"
    return {
        "answer": (
            f"{course} 내용에서는 이 질문에 답할 근거를 찾지 못했다. "
            "강의에서 다루지 않는 내용일 수 있다. 강사에게 문의하는 것을 권한다."
        ),
        "citations": [],
        "route": "OUT_OF_SCOPE" if out_of_scope else "NO_EVIDENCE",
        "messages": [AIMessage("근거를 찾지 못해 답하지 못했다")],
    }


# 6. 힌트
HINT = """학습자가 미션의 정답을 요구했다. 정답을 주지 않는다.

지켜야 할 것
- 완성 코드, 정답 코드 조각, 최종 답을 쓰지 않는다
- 의사코드나 거의 완성된 형태로 우회하지 않는다
- 대신 무엇을 알아야 풀리는지 개념 이름으로 알려준다
- 강의의 특정 장, 절, 섹션 이름을 말하지 않는다. 검색을 하지 않았으므로
  강의에 무엇이 있는지 모른다. 이름을 대면 지어내는 것이 된다
- 질문에 드러난 것만 근거로 삼는다. 미션 내용을 짐작해 단정하지 않는다
- 막힌 지점을 되물어 다음 질문으로 이어지게 한다
- 설명하는 어조로 세 문장 안에 쓴다

질문: {question}"""


def hint(state: TutorState) -> dict:
    # 검색을 하지 않는다. 검색 후에 막으면 정답 문서가 이미 손에 있고,
    # 그때부터는 참고하지 않았다고 보장할 방법이 없다
    try:
        out = get_llm(temperature=0.3).invoke(HINT.format(question=state["question"]))
        answer = out.text.strip()
    except Exception:
        answer = "미션 정답은 알려줄 수 없다. 어느 개념이 막히는지 알려주면 그 부분을 설명하겠다."
    return {"answer": answer, "citations": [], "route": "HINT"}


# 7. 답변 생성
def generate(state: TutorState) -> dict:
    # S2 에서는 모델을 부르지 않고 조각을 그대로 잇는다.
    # 여기에 제대로 된 생성을 먼저 붙이면 검색이 빗나가도 답이 그럴듯해서
    # 무엇이 잘못됐는지 눈치채지 못한다. 프롬프트는 S5 이후에 손본다
    chunks = state.get("chunks", [])
    return {
        "answer": "\n\n".join(c["text"] for c in chunks),
        "citations": [
            {k: c[k] for k in ("course_id", "seq", "source_path", "score", "visibility")}
            for c in chunks
        ],
        "route": "ANSWER",
    }


# 8. 출력 검사
def guard(state: TutorState) -> dict:
    route = state.get("route", "")
    answer = state.get("answer", "")
    citations = state.get("citations", [])

    reasons = check_output(route, answer, citations)
    # 대화 이력에는 검사를 통과한 최종본만 남긴다. 여기서 남겨야 가드가 갈아끼운
    # 답변이 반영된다. generate 나 hint 에서 남기면 막힌 답이 이력에 들어간다
    if not reasons:
        return {"blocked": [], "messages": [AIMessage(answer)]}

    # 걸리면 답변을 버린다. 부분만 지우면 무엇이 남았는지 보장할 수 없다
    if route == "HINT":
        safe = "미션 정답은 알려줄 수 없다. 어느 개념이 막히는지 알려주면 그 부분을 설명하겠다."
        return {"blocked": reasons, "answer": safe, "citations": [], "messages": [AIMessage(safe)]}
    course = state.get("course_id") or "이 강의"
    return {
        "blocked": reasons,
        "answer": (
            f"{course} 내용에서는 이 질문에 답할 근거를 찾지 못했다. "
            "강의에서 다루지 않는 내용일 수 있다. 강사에게 문의하는 것을 권한다."
        ),
        "citations": [],
        "route": "NO_EVIDENCE",
        "messages": [AIMessage("근거를 찾지 못해 답하지 못했다")],
    }
