"""프로메테우스 지표.

무엇을 재는가 — 이 서비스에서 흥미로운 것은 응답 시간이 아니라
**첫 시도에 통과했는가**다. 검증에 걸려 재생성하면 결국 통과는 하지만
호출이 늘어 쿼터와 지연을 먹는다. 프롬프트를 고칠 때 그 비율이 올라가는지를
봐야 하는데, 지금은 평가 러너를 손으로 돌려야만 보인다.

    첫 시도 통과율 = first_try_total / requests_total{outcome="ok"}

`ai-service` 와 같은 경로(`/actuator/prometheus`)와 같은 라이브러리를 쓴다.
Consul 헬스체크 경로와 prometheus 잡 설정이 전역이라 서비스마다 다르게 두면
두 곳을 다 고쳐야 한다.
"""

from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter(
    "curriculum_roadmap_requests_total",
    "로드맵 생성 요청 수",
    ["outcome"],          # ok / quota / model_error / unavailable
)

LLM_CALLS = Counter(
    "curriculum_roadmap_llm_calls_total",
    "모델 호출 수. 재생성이 돌면 요청 하나에 여러 번 는다",
)

FIRST_TRY = Counter(
    "curriculum_roadmap_first_try_total",
    "재생성 없이 첫 시도에 검증을 통과한 요청 수",
)

UNRESOLVED = Counter(
    "curriculum_roadmap_unresolved_total",
    "재생성을 다 쓰고도 검증 문제가 남은 요청 수",
)

DURATION = Histogram(
    "curriculum_roadmap_duration_seconds",
    "로드맵 생성에 걸린 시간",
    # 모델 호출 한 번이 10~20초다. 기본 버킷(0.005~10)은 전부 +Inf 로 몰린다.
    buckets=(1, 5, 10, 20, 30, 45, 60, 90, 120),
)

TOKENS = Counter(
    "curriculum_llm_tokens_total",
    "모델에 오간 토큰",
    ["direction"],        # input / output
)

CATALOG = Gauge(
    "curriculum_catalog_courses",
    "기동할 때 읽은 강의 수",
)


def record(result, seconds):
    """성공한 요청 하나를 기록한다."""
    REQUESTS.labels(outcome="ok").inc()
    LLM_CALLS.inc(result.attempts)
    DURATION.observe(seconds)
    TOKENS.labels(direction="input").inc(result.tokens.get("input", 0))
    TOKENS.labels(direction="output").inc(result.tokens.get("output", 0))
    if result.attempts == 1:
        FIRST_TRY.inc()
    if result.problems:
        # 재생성을 다 쓰고도 안 풀렸다. 프롬프트를 봐야 한다는 신호다.
        UNRESOLVED.inc()


def record_error(status):
    # 429 는 무료 티어 한도라 서버 잘못이 아니다. 따로 센다.
    REQUESTS.labels(outcome="quota" if status == 429 else "model_error").inc()
