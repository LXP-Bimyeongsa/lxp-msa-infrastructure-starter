"""
app/main.py: FastAPI 진입점

이 파일의 역할: 앱을 만들고, 라우터를 붙이고, 기동 시 색인 상태를 알린다.
→ uv run uvicorn app.main:app --reload --port 8086
확인: /health 가 200 이고 index_ready 가 false (색인 전이므로 정상)

CORS 를 열지 않는다. 레퍼런스는 allow_origins=["*"] 였지만 학습용이라 그렇다.
5기에서는 게이트웨이가 이미 허용 출처를 지정하고 있고 이 서비스는 그 뒤에 있으므로
CORS 자체가 필요 없다. 지금 열어두면 나중에 닫는 것을 잊는다
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.endpoints import router as tutor_router
from app.core.config import INDEX_MARKER, settings
from app.schema.models import HealthResponse

# Windows 기본 stdout 인코딩은 cp949 다. 로그가 파일이나 파이프로 나가는 순간
# 한글이 깨진 바이트로 남고, 예외도 안 난다. 컨테이너(Linux)에서는 이미 utf-8 이라 무해하다
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 1. 수명주기: 색인이 없어도 서버는 뜬다
# 서버가 뜨는 것과 색인이 준비되는 것을 분리해야, 이후 문제가 어느 쪽인지 구분된다
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not INDEX_MARKER.exists():
        logger.warning(
            "벡터 색인이 없다. S1 에서 scripts/init_vectorstore.py 를 돌린다"
        )

    yield

    logger.info("서버를 종료한다")
    # 5기에 붙일 때 여기에 Consul 등록·해제가 들어간다.
    # 해제를 빠뜨리면 죽은 인스턴스 등록이 남아 그쪽으로 라우팅된다


app = FastAPI(
    title="LXP AI 튜터",
    description="강의·미션 질문에 근거를 인용해 답한다. 근거가 없으면 답하지 않는다",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tutor_router, prefix="/api/ai")


# 2. 상태 확인: 인증에서 빼는 경로다
# 나중에 붙일 Prometheus 스크레이프와 Consul 헬스체크가 이 경로를 쓴다
@app.get("/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        project=settings.PROJECT_NAME,
        index_ready=INDEX_MARKER.exists(),
    )
