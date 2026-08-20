"""엔드포인트.

경로를 Spring Actuator와 똑같이 둔 것은 의도다. Consul의 health-check-path와
Prometheus의 metrics_path가 서비스 단위가 아니라 전역/잡 단위 설정이라,
경로를 다르게 하면 두 곳을 다 고쳐야 한다. 같은 경로를 쓰면 prometheus 잡에
타겟 한 줄만 추가하면 된다.

이 단계(계획서 9번)에서 /api/ai/chat 은 고정 응답을 돌려준다. 모델 호출은
10번에서 붙인다. 뼈대와 LLM 코드를 한꺼번에 넣으면 Consul·config-server 연동에서
막힐 때 원인이 섞인다.
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from .prompt import SYSTEM_INSTRUCTION, build_prompt, split_answer
from .provider import ProviderError, collect

log = logging.getLogger(__name__)
router = APIRouter()

# 계획서 16번이 요구하는 최소 지표. 첫 토큰 지연은 13번(SSE)에서 붙인다.
# outcome 라벨로 429 발생률을 뽑을 수 있다: ai_chat_requests_total{outcome="error_429"}
REQUESTS = Counter("ai_chat_requests_total", "챗봇 요청 수", ["outcome"])
LATENCY = Histogram(
    "ai_chat_duration_seconds", "챗봇 요청 처리 시간",
    buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0, 10.0, 30.0),
)
# 실존하지 않는 청크ID 인용 횟수. 11번 검증 가드의 실패율 지표가 된다.
GHOST_CITATIONS = Counter("ai_ghost_citations_total", "규정에 없는 청크ID를 인용한 횟수")
# 11번 재생성 가드가 실제로 문제를 고치는지 관측한다. recovered=재생성 후 정상,
# exhausted=재생성 시도를 다 썼는데도 유령 청크ID가 남음.
REGENERATE = Counter(
    "ai_chat_regenerate_total", "유령 청크ID로 인한 재생성 시도 결과", ["outcome"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    # 근거로 인용된 청크ID. 11번 검증 가드가 이 값을 검사한다.
    citations: list[str] = []
    # 참고로 제시한 청크ID. 질문에 대한 답은 아니지만 관련이 있는 것.
    references: list[str] = []
    # 근거가 없거나 검증에 실패했을 때 사용자에게 붙일 경고.
    warning: str | None = None


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


@router.post("/api/ai/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    state = request.app.state
    settings = state.settings

    # 입력 길이 상한. 프롬프트 인젝션 완화와 토큰 예산 보호를 겸한다.
    # 무료 티어는 하루 500요청이라 긴 입력을 반복하면 그날 할당량이 소진된다.
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

    started = time.perf_counter()
    try:
        # 13번에서 이 자리를 SSE 스트리밍으로 바꾼다. provider 시그니처는 이미
        # 스트리밍이므로 라우터만 고치면 되고 인터페이스는 그대로다. 재생성도
        # 같은 자리에서 반복 호출로 처리한다.
        #
        # 동일 프롬프트로 그대로 재시도한다. 힌트를 덧붙이면 매 시도마다 프롬프트가
        # 달라져 고정 접두사 캐싱 전제가 깨진다.
        for attempt in range(1, max_attempts + 1):
            raw = await collect(provider, SYSTEM_INSTRUCTION, prompt)
            citations, references, body = split_answer(raw)
            unknown = [c for c in citations + references if c not in regs.chunk_ids]
            if not unknown or attempt == max_attempts:
                break
            log.warning(
                "실존하지 않는 청크ID 인용, 재생성 시도 %d/%d: %s (질문: %s)",
                attempt, max_attempts - 1, unknown, req.question[:40])
    except ProviderError as e:
        REQUESTS.labels(outcome=f"error_{e.status}").inc()
        # 429는 12번에서 재시도와 폴백 문구를 붙인다.
        detail = ("현재 이용량이 많습니다. 잠시 후 다시 시도해주세요."
                  if e.status == 429 else "답변을 생성하지 못했습니다.")
        log.warning("모델 호출 실패 (%s): %s", e.status, e)
        raise HTTPException(status_code=e.status, detail=detail) from e
    finally:
        LATENCY.observe(time.perf_counter() - started)

    # 60문항 실측에서 인용 102건 중 1건이 존재하지 않는 ID였다(E025가
    # PAY-003-012를 인용, PAY-003은 청크 9개).
    warning = None
    if unknown:
        GHOST_CITATIONS.inc(len(unknown))
        warning = "일부 근거를 규정에서 확인하지 못했습니다. 운영진에게 확인해주세요."
        log.warning("실존하지 않는 청크ID 인용 (재생성 소진): %s (질문: %s)",
                    unknown, req.question[:40])
        if max_attempts > 1:
            REGENERATE.labels(outcome="exhausted").inc()
    elif max_attempts > 1 and attempt > 1:
        REGENERATE.labels(outcome="recovered").inc()

    REQUESTS.labels(outcome="ok").inc()
    return ChatResponse(answer=body or raw, citations=citations,
                        references=references, warning=warning)
