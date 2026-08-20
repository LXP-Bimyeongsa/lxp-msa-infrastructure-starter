"""12번 429 재시도 테스트.

실제 Gemini API를 부르지 않는다 — GeminiProvider를 서브클래싱해서 한 번의
호출(_attempt)만 바꿔치기하고, generate_stream의 재시도 루프(지수 백오프,
스트림 시작 후에는 재시도 안 함)만 검증한다.
"""

import pytest

from app.provider import RETRIES, GeminiProvider, ProviderError

# 재시도 사이 실제로 기다리면 테스트가 느려진다 — 초 단위 대신 아주 짧게 준다.
FAST_DELAY = 0.001


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FlakyProvider(GeminiProvider):
    """처음 fail_times번은 429, 그 다음은 성공."""

    def __init__(self, fail_times: int, **kwargs):
        super().__init__(api_key="test-key", model="test-model", **kwargs)
        self._fail_times = fail_times
        self.calls = 0

    async def _attempt(self, system, prompt):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderError("모델 호출량 한도에 걸렸다", status=429, retryable=True)
        yield "ok"


class _MidStreamFailProvider(GeminiProvider):
    """한 조각을 이미 내보낸 뒤 429가 나는 경우 — 재시도하면 안 된다."""

    def __init__(self, **kwargs):
        super().__init__(api_key="test-key", model="test-model", **kwargs)
        self.calls = 0

    async def _attempt(self, system, prompt):
        self.calls += 1
        yield "부분 응답"
        raise ProviderError("모델 호출량 한도에 걸렸다", status=429, retryable=True)


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


@pytest.mark.anyio
async def test_retry_recovers_within_attempts():
    before = _counter_value(RETRIES, outcome="recovered")
    provider = _FlakyProvider(
        fail_times=1, retry_max_attempts=2, retry_initial_delay_seconds=FAST_DELAY)

    pieces = [p async for p in provider.generate_stream("sys", "prompt")]

    assert pieces == ["ok"]
    assert provider.calls == 2
    assert _counter_value(RETRIES, outcome="recovered") == before + 1


@pytest.mark.anyio
async def test_retry_exhausted_raises_provider_error():
    before = _counter_value(RETRIES, outcome="exhausted")
    # max_attempts=2 -> 총 3회 시도. 계속 실패하게 fail_times를 넉넉히 둔다.
    provider = _FlakyProvider(
        fail_times=10, retry_max_attempts=2, retry_initial_delay_seconds=FAST_DELAY)

    with pytest.raises(ProviderError) as exc_info:
        async for _ in provider.generate_stream("sys", "prompt"):
            pass

    assert exc_info.value.status == 429
    assert provider.calls == 3  # 최초 1회 + 재시도 2회
    assert _counter_value(RETRIES, outcome="exhausted") == before + 1


@pytest.mark.anyio
async def test_no_retry_once_stream_has_started():
    provider = _MidStreamFailProvider(
        retry_max_attempts=3, retry_initial_delay_seconds=FAST_DELAY)

    pieces = []
    with pytest.raises(ProviderError):
        async for piece in provider.generate_stream("sys", "prompt"):
            pieces.append(piece)

    assert pieces == ["부분 응답"]
    assert provider.calls == 1  # 재시도하지 않았다
