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

log = logging.getLogger(__name__)
router = APIRouter()

# 계획서 16번이 요구하는 최소 지표 중 이 단계에서 낼 수 있는 것들.
# 429 발생률, 첫 토큰 지연, 조항 검증 실패율, 일일 토큰 누적은 10~13번에서 붙인다.
REQUESTS = Counter("ai_chat_requests_total", "챗봇 요청 수", ["outcome"])
LATENCY = Histogram(
    "ai_chat_duration_seconds", "챗봇 요청 처리 시간",
    buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0, 10.0, 30.0),
)


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
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    settings = request.app.state.settings

    # 입력 길이 상한. 프롬프트 인젝션 완화와 토큰 예산 보호를 겸한다.
    # 무료 티어는 하루 500요청이라 긴 입력을 반복하면 그날 할당량이 소진된다.
    limit = settings.max_question_chars
    if len(req.question) > limit:
        REQUESTS.labels(outcome="rejected").inc()
        raise HTTPException(
            status_code=413,
            detail=f"질문이 너무 깁니다. {limit}자 이내로 입력해주세요.",
        )

    started = time.perf_counter()
    try:
        # 10번에서 LLMProvider 호출로 교체한다.
        answer = (
            "아직 모델이 연결되지 않았습니다. "
            f"(질문 {len(req.question)}자를 받았습니다, 모델 {settings.model})"
        )
        REQUESTS.labels(outcome="stub").inc()
        return ChatResponse(answer=answer, warning="모델 미연결 상태의 임시 응답입니다.")
    finally:
        LATENCY.observe(time.perf_counter() - started)
