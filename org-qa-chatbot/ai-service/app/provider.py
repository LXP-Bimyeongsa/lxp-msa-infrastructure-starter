"""모델 호출을 인터페이스 뒤에 둔다.

시그니처를 처음부터 스트리밍으로 만든 이유 — 동기 generate()로 만들면 13번(SSE)에서
반환 타입을 바꿔야 하고, 그러면 호출자(라우터, 11번 검증 가드)를 전부 고쳐야 한다.
스트리밍으로 시작하면 "전체를 모아서 반환"은 join 한 줄이다. 역방향은 재작성이다.

추상화하는 지점은 셋이다.
  - 모델 교체 (lite -> flash, 무료 -> 유료)
  - 테스트에서 가짜 provider 주입. API 호출 없이 라우터와 검증 가드를 시험할 수 있고,
    무료 티어 하루 500요청을 테스트로 태우지 않는다.
  - 12번 429 재시도를 한 곳에 넣을 수 있다.

얇게 유지한다. Gemini SDK 타입이 이 인터페이스로 새어나오면 추상화한 의미가 없다.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from prometheus_client import Counter

log = logging.getLogger(__name__)

# 12번 429 재시도 결과. recovered=재시도 끝에 성공, exhausted=재시도를 다 썼는데도 429.
# RPD(일일 한도)와 RPM(분당 한도)을 구분하지 않는다 — 실제 429 응답의 정확한
# 형태를 검증하지 못한 채로 구분 로직을 넣으면 오히려 잘못 분류할 위험이 크다.
# 지금은 run_eval.py와 같은 지수 백오프만 적용하고, 운영 로그에서 실제 형태를
# 본 뒤 필요하면 구분을 추가한다.
RETRIES = Counter("ai_provider_retry_total", "429 재시도 결과", ["outcome"])

# 회차 재현성을 위해 고정한다. 평가 스크립트와 같은 값이어야 운영과 측정이 일치한다.
TEMPERATURE = 0
# flash-lite는 thinking_budget=0을 거부한다(400 INVALID_ARGUMENT).
# 허용되는 최소값이 1이고, 이 값이면 사고 토큰이 실제로 잡히지 않는다.
THINKING_BUDGET = 1


class ProviderError(RuntimeError):
    """모델 호출 실패. status로 상위에서 응답 코드를 정한다."""

    def __init__(self, message: str, *, status: int = 502, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@runtime_checkable
class LLMProvider(Protocol):
    def generate_stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        """응답을 조각 단위로 흘려보낸다. 조각 경계는 보장하지 않는다."""
        ...


async def collect(provider: LLMProvider, system: str, prompt: str) -> str:
    """스트림을 다 모아 문자열로 만든다. 13번 이전까지 라우터가 쓰는 경로."""
    parts: list[str] = []
    async for piece in provider.generate_stream(system, prompt):
        parts.append(piece)
    return "".join(parts).strip()


class GeminiProvider:
    """google-genai 구현체."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        retry_max_attempts: int = 3,
        retry_initial_delay_seconds: float = 2.0,
    ):
        from google import genai
        from google.genai import types

        self._types = types
        self._model = model
        self._retry_max_attempts = retry_max_attempts
        self._retry_initial_delay = retry_initial_delay_seconds
        # SDK가 타임아웃을 밀리초로 받는다.
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    @property
    def model(self) -> str:
        return self._model

    def _config(self, system: str):
        t = self._types
        return t.GenerateContentConfig(
            temperature=TEMPERATURE,
            thinking_config=t.ThinkingConfig(thinking_budget=THINKING_BUDGET),
            system_instruction=system,
        )

    async def _attempt(self, system: str, prompt: str) -> AsyncIterator[str]:
        """한 번의 호출. 재시도는 generate_stream이 감싼다.

        테스트에서 이 메서드만 오버라이드하면 실제 API 없이 재시도 루프를
        시험할 수 있다.
        """
        from google.genai import errors

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self._model, contents=prompt, config=self._config(system))
            async for chunk in stream:
                if text := (chunk.text or ""):
                    yield text
        except errors.ClientError as e:
            code = getattr(e, "code", None)
            if code == 429:
                raise ProviderError("모델 호출량 한도에 걸렸다", status=429,
                                    retryable=True) from e
            raise ProviderError(f"모델 호출이 거부됐다 (code {code})", status=502) from e
        except errors.APIError as e:
            raise ProviderError(f"모델 API 오류: {e}", status=502) from e

    async def generate_stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        """429는 지수 백오프로 재시도한다(계획서 12번, run_eval.py와 같은 정책).

        스트림이 이미 한 조각이라도 내보낸 뒤에 429가 나면 재시도하지 않는다.
        사용자 화면에 이미 나간 내용이 있어 다시 부르면 중복·불일치가 생긴다.
        """
        delay = self._retry_initial_delay
        for attempt in range(self._retry_max_attempts + 1):
            yielded_any = False
            try:
                async for piece in self._attempt(system, prompt):
                    yielded_any = True
                    yield piece
                if attempt > 0:
                    RETRIES.labels(outcome="recovered").inc()
                return
            except ProviderError as e:
                if e.status == 429 and not yielded_any and attempt < self._retry_max_attempts:
                    log.warning(
                        "모델 호출량 한도(429), %.0f초 후 재시도 (%d/%d)",
                        delay, attempt + 1, self._retry_max_attempts)
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                if e.status == 429 and attempt > 0:
                    RETRIES.labels(outcome="exhausted").inc()
                raise


class StubProvider:
    """테스트와 로컬 확인용. API를 부르지 않는다.

    형식을 지킨 응답을 흘려보내서 라우터와 11번 검증 가드의 경로를 시험할 수 있다.
    조각을 여러 개로 쪼개는 것은 의도다 — 가드가 첫 줄만 버퍼링하는 동작을
    확인하려면 한 덩어리로 오면 안 된다.

    call_citations을 주면 호출 순서대로 다른 청크ID 목록을 돌려준다 — 11번
    재생성 가드가 "1차는 유령 청크ID, 2차는 정상"처럼 호출별로 다른 응답을
    받는 상황을 재현하기 위해서다. 목록보다 호출이 많아지면 마지막 값을
    반복한다. 안 주면 매번 citations(또는 기본값)를 그대로 돌려준다.
    """

    def __init__(
        self,
        citations: list[str] | None = None,
        body: str = "테스트 응답입니다.",
        call_citations: list[list[str]] | None = None,
    ):
        self._citations = citations if citations is not None else ["RULES-002-001"]
        self._body = body
        self._call_citations = call_citations
        self._call_count = 0

    @property
    def model(self) -> str:
        return "stub"

    async def generate_stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        if self._call_citations is not None:
            idx = min(self._call_count, len(self._call_citations) - 1)
            citations = self._call_citations[idx]
        else:
            citations = self._citations
        self._call_count += 1

        head = ", ".join(citations) if citations else "없음"
        for piece in (f"근거: {head}\n", "---\n", self._body):
            yield piece
