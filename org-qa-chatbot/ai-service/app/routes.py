"""엔드포인트.

경로를 Spring Actuator와 똑같이 둔 것은 의도다. Consul의 health-check-path와
Prometheus의 metrics_path가 서비스 단위가 아니라 전역/잡 단위 설정이라,
경로를 다르게 하면 두 곳을 다 고쳐야 한다. 같은 경로를 쓰면 prometheus 잡에
타겟 한 줄만 추가하면 된다.

/api/ai/chat 은 13번부터 SSE(text/event-stream)로 응답한다. 이벤트 3종:
  meta  {"citations": [...], "references": [...], "warning": str|None} — 1회
  chunk "본문 조각"                                                    — 여러 번
  done  {}                                                             — 1회, 정상 종료
  error {"status": int, "detail": str}                                 — 실패 시 meta 대신

SSE는 상태 코드를 스트림 시작 후에 못 바꾼다. 그래서 입력 검증(413)과 서비스
미준비(503)만 스트림을 시작하기 전에 일반 HTTP 오류로 raise하고, 모델 호출
실패(429·502 등)는 스트림이 이미 200으로 시작된 뒤라 error 이벤트로 알린다.
"""

import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from .prompt import SYSTEM_INSTRUCTION, build_prompt, header_complete, split_answer
from .provider import LLMProvider, ProviderError
from .regulations import Regulations

log = logging.getLogger(__name__)
router = APIRouter()

# 계획서 16번이 요구하는 최소 지표.
# outcome 라벨로 429 발생률을 뽑을 수 있다: ai_chat_requests_total{outcome="error_429"}
REQUESTS = Counter("ai_chat_requests_total", "챗봇 요청 수", ["outcome"])
LATENCY = Histogram(
    "ai_chat_duration_seconds", "챗봇 요청 처리 시간",
    buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0, 10.0, 30.0),
)
# 첫 토큰까지 걸린 시간. 11번 가드가 헤더를 버퍼링하는 비용이 여기 섞여 들어간다
# — 가드가 켜져 있으면 이 값이 재생성 가능성만큼 올라가는 게 정상이다.
FIRST_TOKEN_LATENCY = Histogram(
    "ai_chat_first_token_seconds", "첫 토큰까지 걸린 시간",
    buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0, 10.0),
)
# 실존하지 않는 청크ID 인용 횟수. 11번 검증 가드의 실패율 지표가 된다.
GHOST_CITATIONS = Counter("ai_ghost_citations_total", "규정에 없는 청크ID를 인용한 횟수")
# 11번 재생성 가드가 실제로 문제를 고치는지 관측한다. recovered=재생성 후 정상,
# exhausted=재생성 시도를 다 썼는데도 유령 청크ID가 남음.
REGENERATE = Counter(
    "ai_chat_regenerate_total", "유령 청크ID로 인한 재생성 시도 결과", ["outcome"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


def _sse(event: str, data: object) -> str:
    """SSE 한 이벤트를 만든다. data는 항상 JSON으로 인코딩한다 — 본문 조각에
    개행이 섞여 있어서 raw 문자열로 내보내면 SSE 필드 구분이 깨진다."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/actuator/health")
def health(request: Request, response: Response) -> dict:
    """Consul이 10초마다 찌른다. 여기서 무거운 확인을 하면 안 된다.

    모델 API 도달 가능성을 여기서 검사하고 싶은 유혹이 있는데, 그러면 무료 티어
    할당량을 헬스체크로 태우게 된다(10초마다면 하루 8,640회로 상한 500을 한참
    넘는다). 외부 의존성 상태는 별도 엔드포인트나 메트릭으로 본다.

    Consul 미등록을 DOWN으로 보는 이유 — 등록되지 않은 인스턴스는 gateway를 통해
    도달할 수 없으므로 트래픽을 처리하지 못한다. 그런데도 UP을 보고하면 거짓이고,
    나중에 502만 보고 원인을 엉뚱한 데서 찾게 된다. 미등록 상태에서는 Consul이
    이 엔드포인트를 찌르지도 않으므로, DOWN을 내보내도 트래픽에 영향이 없다.
    docker compose 헬스체크에서만 unhealthy로 보이고, 그게 문제를 드러내는 자리다.
    """
    ready = getattr(request.app.state, "ready", False)
    registrar = getattr(request.app.state, "registrar", None)
    registered = bool(registrar and registrar.registered)
    regs = getattr(request.app.state, "regulations", None)

    reg_component: dict[str, object] = {"status": "UP" if regs else "DOWN"}
    if regs:
        reg_component["details"] = {
            "documents": regs.doc_count,
            "chunks": len(regs.chunks),
            # 회차 형상 기록의 context_sha와 같은 값이다. 운영에서 품질 이상이
            # 보고될 때 어느 규정 스냅샷이었는지 평가 회차와 대조할 수 있다.
            "contextSha": regs.context_sha,
        }

    consul: dict[str, object] = {"status": "UP" if registered else "DOWN"}
    if registrar:
        details: dict[str, object] = {"instanceId": registrar.instance_id}
        if not registered and registrar.last_error:
            details["error"] = registrar.last_error
            details["retrying"] = True
        consul["details"] = details

    up = ready and registered
    if not up:
        # 200으로 UP이 아닌 상태를 돌려주면 Consul과 docker 양쪽이 통과로 읽는다.
        response.status_code = 503
    return {
        "status": "UP" if up else "OUT_OF_SERVICE",
        "components": {
            "regulations": reg_component,
            "consul": consul,
        },
    }


@router.get("/actuator/prometheus")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def _stream_answer(
    provider: LLMProvider, regs: Regulations, prompt: str, max_attempts: int,
    question_for_log: str,
) -> AsyncIterator[str]:
    """모델 응답을 SSE로 흘려보낸다. 11번 재생성 가드가 여기 들어간다.

    헤더(첫 줄 `근거:` + 구분선)가 끝날 때까지는 조각을 버퍼링만 하고 아무 것도
    내보내지 않는다 — 그래야 유령 청크ID를 발견했을 때 사용자 화면에 아무 것도
    보여주지 않은 채로 처음부터 다시 부를 수 있다. 헤더가 통과(또는 재생성 소진)
    하면 그때부터 남은 조각을 그대로 흘려보낸다.
    """
    started = time.perf_counter()
    first_token_recorded = False
    try:
        for attempt in range(1, max_attempts + 1):
            stream = provider.generate_stream(SYSTEM_INSTRUCTION, prompt).__aiter__()
            buffered = ""
            async for piece in stream:
                if not first_token_recorded:
                    FIRST_TOKEN_LATENCY.observe(time.perf_counter() - started)
                    first_token_recorded = True
                buffered += piece
                if header_complete(buffered):
                    break

            citations, references, body_from_header = split_answer(buffered)
            unknown = [c for c in citations + references if c not in regs.chunk_ids]

            if unknown and attempt < max_attempts:
                log.warning(
                    "실존하지 않는 청크ID 인용, 재생성 시도 %d/%d: %s (질문: %s)",
                    attempt, max_attempts - 1, unknown, question_for_log)
                await stream.aclose()
                continue

            # 60문항 실측에서 인용 102건 중 1건이 존재하지 않는 ID였다(E025가
            # PAY-003-012를 인용, PAY-003은 청크 9개).
            warning = None
            if unknown:
                GHOST_CITATIONS.inc(len(unknown))
                warning = "일부 근거를 규정에서 확인하지 못했습니다. 운영진에게 확인해주세요."
                log.warning("실존하지 않는 청크ID 인용 (재생성 소진): %s (질문: %s)",
                            unknown, question_for_log)
                if max_attempts > 1:
                    REGENERATE.labels(outcome="exhausted").inc()
            elif max_attempts > 1 and attempt > 1:
                REGENERATE.labels(outcome="recovered").inc()

            yield _sse("meta", {"citations": citations, "references": references,
                                "warning": warning})
            if body_from_header:
                yield _sse("chunk", body_from_header)
            async for piece in stream:
                yield _sse("chunk", piece)
            yield _sse("done", {})
            REQUESTS.labels(outcome="ok").inc()
            return
    except ProviderError as e:
        REQUESTS.labels(outcome=f"error_{e.status}").inc()
        # 429는 12번에서 이미 provider 안에서 재시도를 다 쓴 뒤다.
        detail = ("현재 이용량이 많습니다. 잠시 후 다시 시도해주세요."
                  if e.status == 429 else "답변을 생성하지 못했습니다.")
        log.warning("모델 호출 실패 (%s): %s", e.status, e)
        yield _sse("error", {"status": e.status, "detail": detail})
    finally:
        LATENCY.observe(time.perf_counter() - started)


@router.post("/api/ai/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    state = request.app.state
    settings = state.settings

    # 입력 길이 상한. 프롬프트 인젝션 완화와 토큰 예산 보호를 겸한다.
    # 무료 티어는 하루 500요청이라 긴 입력을 반복하면 그날 할당량이 소진된다.
    # 스트림이 시작되기 전이라 여기까지는 평범한 HTTP 오류로 처리한다.
    limit = settings.max_question_chars
    if len(req.question) > limit:
        REQUESTS.labels(outcome="rejected").inc()
        raise HTTPException(
            status_code=413,
            detail=f"질문이 너무 깁니다. {limit}자 이내로 입력해주세요.",
        )

    regs = getattr(state, "regulations", None)
    provider = getattr(state, "provider", None)
    if regs is None or provider is None:
        # 규정 적재 실패 또는 API 키 없음. 헬스에 원인이 드러나 있다.
        REQUESTS.labels(outcome="unavailable").inc()
        raise HTTPException(
            status_code=503,
            detail="답변 준비가 되지 않았습니다. 잠시 후 다시 시도해주세요.",
        )

    prompt = build_prompt(req.question, regs.context)
    # 가드가 꺼져 있으면 그냥 1회 호출이다(9·10번 단계와 동일 동작).
    max_attempts = 1 + settings.guard_regenerate_attempts if settings.guard_enabled else 1

    return StreamingResponse(
        _stream_answer(provider, regs, prompt, max_attempts, req.question[:40]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
