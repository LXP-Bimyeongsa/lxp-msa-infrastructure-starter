"""프롬프트 조립. 평가 스크립트와 런타임(ai-service)이 같은 걸 쓴다.

블록 순서는 캐싱 때문에 고정이다. 크고 안 바뀌는 규정 전문을 앞에,
매 요청 달라지는 사용자 질문을 맨 뒤에 둔다. 순서를 바꾸면 그때까지
측정한 지연·비용 수치가 전부 무효가 된다.

출력 형식도 고정이다. 첫 줄에 근거 청크ID를 강제하는 이유는,
스트리밍 중에 앞부분만 버퍼링해서 청크ID 실존 여부를 검증한 뒤
본문을 흘려보내기 위해서다. 근거가 본문 뒤에 나오면 이미 사용자
화면에 출력된 다음에야 검증 결과를 알게 된다.
"""

from pathlib import Path

CONTEXT_PATH = Path(__file__).resolve().parent.parent / "data" / "context.txt"

SYSTEM_INSTRUCTION = """너는 조직 규정 안내 챗봇이다. 아래 규정 문서만을 근거로 답한다.

출력 형식 (반드시 지킬 것):
1) 첫 줄: `근거: <청크ID>` — 쉼표로 구분해 여러 개 가능. 근거가 없으면 `근거: 없음`
2) 둘째 줄: `---`
3) 셋째 줄부터: 답변 본문

규칙:
- 규정 문서에 없는 내용은 추측하지 않는다. `근거: 없음` 으로 시작하고,
  규정에 해당 내용이 없다고 answer한 뒤 운영진 문의를 안내한다.
- 문서마다 값이 서로 다르면 하나로 단정하지 않는다. 양쪽 값과 각 출처를
  함께 제시하고 운영진 확인을 안내한다.
- 첫 줄의 청크ID는 규정 본문에 실제로 있는 것만 쓴다. 지어내지 않는다.
- 본문에서 문서를 가리킬 때는 청크ID가 아니라 사람이 읽는 문서명으로 쓴다.
"""

_ANSWER_HEADER = "근거:"
_SEPARATOR = "---"


def load_context() -> str:
    if not CONTEXT_PATH.exists():
        raise SystemExit(
            f"{CONTEXT_PATH} 가 없습니다. "
            "`uv run python scripts/build_prompt_context.py` 를 먼저 실행하세요."
        )
    return CONTEXT_PATH.read_text(encoding="utf-8")


def build_prompt(question: str, context: str | None = None) -> str:
    """규정 전문 -> 구분선 -> 질문 순서. 이 순서는 캐싱 접두사라 바뀌면 안 된다."""
    if context is None:
        context = load_context()
    return f"{context}\n\n========\n\n[사용자 질문]\n{question}\n"


def split_answer(text: str) -> tuple[list[str], str]:
    """모델 응답을 (청크ID 목록, 본문)으로 분리한다.

    `근거: 없음` 이면 빈 목록을 돌려준다. 형식을 안 지킨 응답은
    청크ID 목록을 None이 아니라 빈 목록으로 두고 전체를 본문으로 본다.
    """
    lines = text.lstrip().split("\n")
    if not lines or not lines[0].startswith(_ANSWER_HEADER):
        return [], text.strip()

    raw = lines[0][len(_ANSWER_HEADER):].strip()
    ids = [] if raw in ("없음", "") else [c.strip() for c in raw.split(",") if c.strip()]

    body_start = 1
    if len(lines) > 1 and lines[1].strip() == _SEPARATOR:
        body_start = 2
    return ids, "\n".join(lines[body_start:]).strip()
