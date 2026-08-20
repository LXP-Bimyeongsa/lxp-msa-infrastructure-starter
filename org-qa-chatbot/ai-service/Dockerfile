# 빌드 컨텍스트는 저장소 루트다 (compose의 context: . 와 맞춘다).
# 다른 서비스와 같은 규칙이라 COPY 경로에 ai-service/ 가 붙는다.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 의존성만 먼저 넣어서 레이어를 재사용한다. 소스가 바뀌어도 lock이 그대로면
# 이 레이어는 캐시에서 나온다.
COPY ai-service/pyproject.toml ai-service/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY ai-service/app ./app

# 컨테이너 안에서는 .venv를 직접 쓴다. uv run은 매 실행마다 잠금을 확인하므로
# 기동 경로에서는 불필요한 일이다.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

EXPOSE 8086

# 워커는 1개다. 규정 전문을 메모리에 들고 있고 요청당 17k 토큰을 쓰는데,
# 무료 티어 상한이 분당 15요청이라 프로세스를 늘려도 처리량이 늘지 않는다.
# 늘리면 규정 전문만 워커 수만큼 중복 적재된다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8086", "--workers", "1"]
