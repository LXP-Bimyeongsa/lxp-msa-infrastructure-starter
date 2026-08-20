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
1) 첫 줄: `근거: <청크ID>` — 쉼표로 구분해 여러 개 가능

   `근거:` 에는 답변 본문에서 사용한 대목을 **빠짐없이** 적는다.
   질문에 답하는 값이 여러 문서에 서로 다르게 적혀 있으면 그 문서들을 **모두**
   `근거:` 에 넣는다. 한쪽만 근거로 삼지 않는다.

   질문에 답하는 내용이 규정 문서에 아예 없을 때만 `근거: 없음` 이라고 쓴다.
   이때 참고가 될 만한 다른 제도나 대목이 있으면 `참고:` 에 넣는다.
   `근거: 없음` 이라고 썼으면 `근거:` 칸에는 청크ID를 하나도 넣지 않는다.

     `근거: PAY-003-001, FAQ-010-017`      (값이 문서마다 달라 양쪽을 근거로)
     `근거: 없음 / 참고: FAQ-010-011`       (규정에 없고, 다른 제도를 안내)

2) 둘째 줄: `---`
3) 셋째 줄부터: 답변 본문

규칙:
- 규정 문서에 없는 내용은 추측하지 않는다. 질문에 해당하는 규정이 없으면
  `근거: 없음` 으로 시작하고, 본문 첫 문장에서 "규정에 없다"는 사실을 먼저
  분명히 밝힌 뒤 운영진 문의를 안내한다.
- 이름이 비슷한 다른 제도를 질문의 답인 것처럼 설명하지 않는다. 예를 들어
  '연차휴가'를 물었는데 규정에 없고 성격이 다른 '월 1회 휴가'만 있다면,
  먼저 연차휴가 규정이 없다고 밝히고 나서 다른 제도임을 명시해 안내한다.
- 문서마다 값이 서로 다르면 하나로 단정하지 않는다. 양쪽 값과 각 출처를
  함께 제시하고 운영진 확인을 안내한다.
- 청크ID는 `근거:` 와 `참고:` 양쪽 모두, 규정 본문의 대괄호에 있는 전체 형태를
  그대로 쓴다. 실제로 있는 것만 쓰고 지어내지 않으며, 문서 단위로 줄여 쓰지 않는다.
  (`SPACE-006` 처럼 쓰면 안 되고 `SPACE-006-004` 로 써야 한다.)
- 본문에서 문서를 가리킬 때는 청크ID가 아니라 사람이 읽는 문서명으로 쓴다.
"""

_ANSWER_HEADER = "근거:"
_REF_HEADER = "참고:"
_SEPARATOR = "---"
_NO_BASIS = "없음"


def _parse_ids(raw: str) -> list[str]:
    if raw.strip() in (_NO_BASIS, ""):
        return []
    return [c.strip() for c in raw.split(",") if c.strip()]


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


def split_answer(text: str) -> tuple[list[str], list[str], str]:
    """모델 응답을 (근거 청크ID, 참고 청크ID, 본문)으로 분리한다.

    `근거:` 는 질문에 직접 답하는 근거, `참고:` 는 관련은 있으나 질문의 답이
    아닌 대목이다. 둘을 나누는 이유는, 규정에 없는 질문에 "없다"고 밝히면서
    관련 제도를 안내하는 것이 정답 행동인데 채널이 하나면 그 둘을 구분할 수
    없기 때문이다. 관련 대목을 인용하는 순간 "규정에 있다"는 주장이 되어버린다.

    `근거: 없음` 이면 근거 목록이 빈다. 형식을 안 지킨 응답은 양쪽 목록을
    비우고 전체를 본문으로 본다.
    """
    lines = text.lstrip().split("\n")
    if not lines or not lines[0].startswith(_ANSWER_HEADER):
        return [], [], text.strip()

    head = lines[0][len(_ANSWER_HEADER):]
    basis_raw, _, ref_raw = head.partition(_REF_HEADER)
    basis_raw = basis_raw.strip().rstrip("/").strip()

    # 모델이 `근거:` 줄과 `---` 사이에 빈 줄을 넣는 경우가 흔하다. 다음 줄만 보고
    # 판단하면 구분선이 본문에 남아 사용자 화면에 `---` 가 그대로 보인다.
    body_start = 1
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    if body_start < len(lines) and lines[body_start].strip() == _SEPARATOR:
        body_start += 1
    return _parse_ids(basis_raw), _parse_ids(ref_raw), "\n".join(lines[body_start:]).strip()
