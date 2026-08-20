"""11번 런타임 청크ID 검증 가드 + 13번 SSE 라우팅 테스트.

실제 Gemini API를 부르지 않는다 — StubProvider로 응답을 고정하고, 호출
순서별로 다른 청크ID를 돌려주게 해서 "1차 유령ID -> 2차 정상"과 "계속
유령ID" 두 경로를 재현한다. lifespan(Consul 등록, config-server 조회, 규정
파일 로딩)은 거치지 않는다 — 여기서 보는 건 라우터의 재생성 루프와 SSE
프레이밍뿐이다.

/api/ai/chat이 13번부터 SSE라 응답 본문을 JSON으로 바로 못 읽는다. TestClient는
스트림을 동기적으로 다 소진해 resp.text에 담아주므로, 이벤트 블록만 파싱한다.
"""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, regulations
from app.provider import StubProvider
from app.routes import GHOST_CITATIONS, REGENERATE, router

VALID_CHUNK_ID = "RULES-002-001"


def make_client(provider, *, guard_enabled: bool = True, regenerate_attempts: int = 1) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.settings = config.Settings(remote={
        "ai.guard.enabled": guard_enabled,
        "ai.guard.regenerate-attempts": regenerate_attempts,
    })
    app.state.regulations = regulations.Regulations(
        chunks=[],
        context="(테스트 규정 전문)",
        chunk_ids=frozenset({VALID_CHUNK_ID}),
        context_sha="test-sha",
    )
    app.state.provider = provider
    return TestClient(app)


def _counter_value(counter, **labels) -> float:
    target = counter.labels(**labels) if labels else counter
    return target._value.get()


def parse_sse(text: str) -> list[tuple[str, object]]:
    """`event: x\\ndata: y\\n\\n` 블록들을 (이벤트명, 파싱된 data) 목록으로 만든다."""
    events = []
    for block in text.strip("\n").split("\n\n"):
        if not block.strip():
            continue
        event_type, data = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        assert event_type is not None, f"이벤트 이름 없는 블록: {block!r}"
        events.append((event_type, data))
    return events


def chat_events(client: TestClient, question: str = "연차는 며칠인가요?") -> list[tuple[str, object]]:
    resp = client.post("/api/ai/chat", json={"question": question})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    return parse_sse(resp.text)


def test_chat_ok_without_ghost_citation():
    client = make_client(StubProvider(citations=[VALID_CHUNK_ID]))
    events = chat_events(client)

    kind, meta = events[0]
    assert kind == "meta"
    assert meta["citations"] == [VALID_CHUNK_ID]
    assert meta["warning"] is None
    assert events[-1] == ("done", {})
    # 본문이 최소 한 조각은 나온다.
    assert any(k == "chunk" for k, _ in events)


def test_chat_regenerates_and_recovers():
    before = _counter_value(REGENERATE, outcome="recovered")
    provider = StubProvider(call_citations=[["GHOST-999-999"], [VALID_CHUNK_ID]])

    client = make_client(provider, regenerate_attempts=1)
    events = chat_events(client)

    kind, meta = events[0]
    assert kind == "meta"
    # 최종적으로 2차(정상) 응답이 사용자에게 나간다. 1차 시도는 화면에 전혀
    # 노출되지 않는다 — meta 이벤트가 딱 하나만 있어야 한다.
    assert meta["citations"] == [VALID_CHUNK_ID]
    assert meta["warning"] is None
    assert sum(1 for k, _ in events if k == "meta") == 1
    assert _counter_value(REGENERATE, outcome="recovered") == before + 1


def test_chat_regeneration_exhausted_keeps_warning():
    ghost_before = _counter_value(GHOST_CITATIONS)
    exhausted_before = _counter_value(REGENERATE, outcome="exhausted")
    provider = StubProvider(call_citations=[["GHOST-1"], ["GHOST-2"]])

    client = make_client(provider, regenerate_attempts=1)
    events = chat_events(client)

    kind, meta = events[0]
    # 재생성 시도를 다 썼으므로 마지막(2차) 응답을 그대로 돌려주되 경고를 붙인다.
    assert kind == "meta"
    assert meta["citations"] == ["GHOST-2"]
    assert meta["warning"] is not None
    assert _counter_value(GHOST_CITATIONS) == ghost_before + 1
    assert _counter_value(REGENERATE, outcome="exhausted") == exhausted_before + 1


def test_chat_guard_disabled_skips_regeneration_but_still_warns():
    provider = StubProvider(call_citations=[["GHOST-1"], [VALID_CHUNK_ID]])
    exhausted_before = _counter_value(REGENERATE, outcome="exhausted")
    recovered_before = _counter_value(REGENERATE, outcome="recovered")

    client = make_client(provider, guard_enabled=False)
    events = chat_events(client)

    kind, meta = events[0]
    # 가드가 꺼져 있으니 1차 응답(유령ID)을 재시도 없이 그대로 반환한다.
    assert kind == "meta"
    assert meta["citations"] == ["GHOST-1"]
    assert meta["warning"] is not None
    # 재생성 자체가 없었으니 recovered/exhausted 어느 쪽도 늘지 않는다.
    assert _counter_value(REGENERATE, outcome="exhausted") == exhausted_before
    assert _counter_value(REGENERATE, outcome="recovered") == recovered_before


def test_chat_provider_error_becomes_sse_error_event():
    """429 등 provider 오류는 스트림이 이미 시작된 뒤라 HTTP 상태가 아니라
    error 이벤트로 나간다."""
    from app.provider import ProviderError

    class _FailingProvider:
        model = "failing"

        async def generate_stream(self, system, prompt):
            raise ProviderError("모델 호출량 한도에 걸렸다", status=429, retryable=True)
            yield ""  # pragma: no cover - AsyncIterator 타입을 맞추기 위한 미도달 yield

    client = make_client(_FailingProvider())
    events = chat_events(client)

    assert events == [("error", {"status": 429, "detail": "현재 이용량이 많습니다. 잠시 후 다시 시도해주세요."})]
