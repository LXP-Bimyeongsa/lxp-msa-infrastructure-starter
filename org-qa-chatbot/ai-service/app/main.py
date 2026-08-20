"""FastAPI 앱과 기동/종료 훅.

기동 순서가 중요하다. Consul 등록을 헬스체크가 통과할 수 있는 상태가 된 뒤에
해야 한다. 먼저 등록하면 Consul이 즉시 찌르고, 그 시점에 준비가 안 돼 있으면
critical로 잡혀 gateway가 한동안 이 인스턴스를 피한다.

종료는 반대다. Consul 등록을 먼저 해제하고 나서 프로세스를 내린다. 안 그러면
critical 판정이 나기까지 1분간 gateway가 죽은 인스턴스로 보낸다(P-19).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import config, logging_setup, regulations
from .consul import ConsulRegistrar
from .provider import GeminiProvider
from .routes import router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging_setup.setup(logging_setup.env_log_dir())

    settings = config.load()
    app.state.settings = settings
    log.info("설정 로딩 완료 (모델 %s, 질문 상한 %d자)",
             settings.model, settings.max_question_chars)

    # 모델 provider. 키가 없어도 기동은 시킨다. 헬스와 로그로 원인이 보이는 상태가
    # 낫고, 규정 적재 같은 나머지 문제를 같이 진단할 수 있다.
    if settings.gemini_api_key:
        app.state.provider = GeminiProvider(
            settings.gemini_api_key, settings.model, settings.request_timeout_seconds)
        log.info("모델 provider 준비: %s", settings.model)
    else:
        app.state.provider = None
        log.warning("GEMINI_API_KEY가 없다. 질문 요청은 503으로 실패한다.")

    # 규정을 메모리에 적재한다. 이게 실패하면 답변을 만들 수 없으므로 ready가 아니다.
    # 14번에서 여기에 재로드를 붙인다(내용 해시 비교 + 원자적 스왑).
    try:
        app.state.regulations = regulations.load(settings.docs_dir)
        regs = app.state.regulations
        log.info("규정 적재 완료: 문서 %d개 / 청크 %d개 / sha %s",
                 regs.doc_count, len(regs.chunks), regs.context_sha)
        app.state.ready = True
    except Exception as e:
        # 문서 마운트가 빠졌거나 경로가 틀린 경우다. 헬스에 DOWN으로 드러난다.
        app.state.regulations = None
        app.state.ready = False
        log.error("규정 적재 실패 (%s) — 질문 요청은 503으로 실패한다: %s",
                  settings.docs_dir, e)

    registrar = ConsulRegistrar(
        settings.consul_host, settings.consul_port, config.APP_NAME, config.PORT)
    app.state.registrar = registrar
    # 실패해도 기동을 막지 않는다. 대신 헬스에 상태가 드러나고 백그라운드로 재시도한다.
    await registrar.start()

    try:
        yield
    finally:
        # 순서: 등록 해제 -> 준비 상태 내림. 반대로 하면 해제되기 전에
        # 헬스체크가 실패해 critical로 먼저 잡힌다.
        await registrar.stop()
        app.state.ready = False
        log.info("종료 완료")


app = FastAPI(
    title="조직 규정 QA 챗봇",
    version="0.1.0",
    lifespan=lifespan,
    # gateway가 앞단에서 /api/ai/** 를 붙여 라우팅한다. 문서 경로는 내부용으로만 둔다.
    docs_url="/actuator/docs",
    redoc_url=None,
)
app.include_router(router)
