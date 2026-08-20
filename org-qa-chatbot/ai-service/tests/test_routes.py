"""11번 런타임 청크ID 검증 가드 테스트.

실제 Gemini API를 부르지 않는다 — StubProvider로 응답을 고정하고, 호출
순서별로 다른 청크ID를 돌려주게 해서 "1차 유령ID -> 2차 정상"과 "계속
유령ID" 두 경로를 재현한다. lifespan(Consul 등록, config-server 조회, 규정
파일 로딩)은 거치지 않는다 — 여기서 보는 건 라우터의 재생성 루프뿐이다.
"""

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


def test_chat_ok_without_ghost_citation():
    client = make_client(StubProvider(citations=[VALID_CHUNK_ID]))
    resp = client.post("/api/ai/chat", json={"question": "연차는 며칠인가요?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"] == [VALID_CHUNK_ID]
    assert body["warning"] is None


def test_chat_regenerates_and_recovers():
    before = _counter_value(REGENERATE, outcome="recovered")
    provider = StubProvider(call_citations=[["GHOST-999-999"], [VALID_CHUNK_ID]])

    client = make_client(provider, regenerate_attempts=1)
    resp = client.post("/api/ai/chat", json={"question": "연차는 며칠인가요?"})

    assert resp.status_code == 200
    body = resp.json()
    # 최종적으로 2차(정상) 응답이 사용자에게 나간다.
    assert body["citations"] == [VALID_CHUNK_ID]
    assert body["warning"] is None
    assert _counter_value(REGENERATE, outcome="recovered") == before + 1


def test_chat_regeneration_exhausted_keeps_warning():
    ghost_before = _counter_value(GHOST_CITATIONS)
    exhausted_before = _counter_value(REGENERATE, outcome="exhausted")
    provider = StubProvider(call_citations=[["GHOST-1"], ["GHOST-2"]])

    client = make_client(provider, regenerate_attempts=1)
    resp = client.post("/api/ai/chat", json={"question": "연차는 며칠인가요?"})

    assert resp.status_code == 200
    body = resp.json()
    # 재생성 시도를 다 썼으므로 마지막(2차) 응답을 그대로 돌려주되 경고를 붙인다.
    assert body["citations"] == ["GHOST-2"]
    assert body["warning"] is not None
    assert _counter_value(GHOST_CITATIONS) == ghost_before + 1
    assert _counter_value(REGENERATE, outcome="exhausted") == exhausted_before + 1


def test_chat_guard_disabled_skips_regeneration_but_still_warns():
    provider = StubProvider(call_citations=[["GHOST-1"], [VALID_CHUNK_ID]])
    exhausted_before = _counter_value(REGENERATE, outcome="exhausted")
    recovered_before = _counter_value(REGENERATE, outcome="recovered")

    client = make_client(provider, guard_enabled=False)
    resp = client.post("/api/ai/chat", json={"question": "연차는 며칠인가요?"})

    assert resp.status_code == 200
    body = resp.json()
    # 가드가 꺼져 있으니 1차 응답(유령ID)을 재시도 없이 그대로 반환한다.
    assert body["citations"] == ["GHOST-1"]
    assert body["warning"] is not None
    # 재생성 자체가 없었으니 recovered/exhausted 어느 쪽도 늘지 않는다.
    assert _counter_value(REGENERATE, outcome="exhausted") == exhausted_before
    assert _counter_value(REGENERATE, outcome="recovered") == recovered_before
