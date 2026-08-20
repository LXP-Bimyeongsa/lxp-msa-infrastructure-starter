"""설정 로딩. config-server에서 받아오고, 없으면 환경변수와 기본값으로 돈다.

다른 서비스는 Spring Cloud Config 클라이언트가 이 일을 해준다. 이 서비스는
JVM이 아니라서 config-server의 REST API를 직접 호출한다.

  GET http://config-server:8888/{application}/{profile}

응답의 propertySources는 우선순위가 높은 것이 앞에 온다. Spring과 같은 순서로
합쳐야 config-repo/ai-service.yml 이 application.yml 을 덮어쓴다.

비밀은 config-server를 통해 오지 않는다. config-repo는 평문 git이고 이 저장소는
공개다. GEMINI_API_KEY 같은 값은 compose 환경변수로만 받는다.
"""

import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

APP_NAME = "ai-service"
PORT = 8086

# 로컬 실행 편의. 컨테이너에서는 compose가 환경변수를 주입하고 .env 파일이 없으므로
# 아무 일도 하지 않는다. 저장소에 커밋되지 않는 파일이라(gitignore) 운영 경로에
# 영향을 주지 않는다.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.is_file():
    from dotenv import load_dotenv

    load_dotenv(_ENV_FILE)

# config-server가 늦게 뜨거나 죽어 있어도 서비스는 떠야 한다. compose의
# depends_on(service_healthy)이 순서를 보장하지만, 운영 중 config-server가
# 재기동할 때 이 서비스가 같이 죽으면 안 된다.
_FETCH_TIMEOUT = 5.0


class Settings:
    """config-server 값 + 환경변수 + 기본값을 한 곳에서 읽는다.

    조회 우선순위는 환경변수 -> config-server -> 기본값이다. 환경변수를 가장
    위에 두는 것은 compose에서 값을 덮어써 디버깅할 수 있게 하기 위해서다.
    """

    def __init__(self, remote: dict[str, object] | None = None):
        self._remote = remote or {}

    def get(self, key: str, default=None, env: str | None = None):
        if env and (v := os.environ.get(env)) is not None:
            return v
        if key in self._remote:
            return self._remote[key]
        return default

    def get_int(self, key: str, default: int, env: str | None = None) -> int:
        v = self.get(key, default, env)
        try:
            return int(v)
        except (TypeError, ValueError):
            log.warning("설정 %s 값이 정수가 아니라 기본값 %s를 쓴다: %r", key, default, v)
            return default

    # ── 서비스 자신에 대한 것 ──────────────────────────────
    @property
    def consul_host(self) -> str:
        return os.environ.get("CONSUL_HOST", "localhost")

    @property
    def consul_port(self) -> int:
        return int(os.environ.get("CONSUL_PORT", "8500"))

    @property
    def log_dir(self) -> str:
        return os.environ.get("LOG_DIR", "./logs")

    @property
    def docs_dir(self) -> Path:
        """규정 문서 디렉터리.

        컨테이너에서는 org-qa-chatbot/docs 를 읽기 전용으로 마운트해 받는다.
        문서를 이미지에 굽지 않는 이유는 14번 규정 재로드다. 런타임에 다시 읽을 수
        있어야 재배포 없이 개정을 반영할 수 있다.
        """
        if v := os.environ.get("AI_DOCS_DIR"):
            return Path(v)
        # 로컬 실행 기본값. 저장소 안에서 그대로 돌 수 있게 한다.
        return Path(__file__).resolve().parents[2] / "org-qa-chatbot" / "docs"

    # ── 모델 호출 (10번에서 사용) ──────────────────────────
    @property
    def gemini_api_key(self) -> str | None:
        # 비밀이라 config-server 경로를 두지 않는다. 환경변수만 본다.
        return os.environ.get("GEMINI_API_KEY")

    @property
    def model(self) -> str:
        return str(self.get("ai.model", "gemini-3.5-flash-lite", env="GEMINI_MODEL"))

    @property
    def max_question_chars(self) -> int:
        # 프롬프트 인젝션 완화와 토큰 예산 보호를 겸한다. 무료 티어는 하루 500요청이라
        # 긴 입력을 반복하면 그날 할당량이 소진된다.
        return self.get_int("ai.max-question-chars", 500, env="AI_MAX_QUESTION_CHARS")

    @property
    def request_timeout_seconds(self) -> float:
        return float(self.get("ai.request-timeout-seconds", 30, env="AI_REQUEST_TIMEOUT"))

    # ── 11번 런타임 청크ID 검증 가드 ──────────────────────
    @property
    def guard_enabled(self) -> bool:
        return str(self.get("ai.guard.enabled", True)).strip().lower() not in ("false", "0")

    @property
    def guard_regenerate_attempts(self) -> int:
        # 재생성도 실 API 호출이라 무료 티어 하루 500요청을 태운다. 값을 늘릴수록
        # 유령 청크ID 한 건이 여러 요청을 잡아먹으므로 기본값을 낮게 둔다.
        return self.get_int(
            "ai.guard.regenerate-attempts", 1, env="AI_GUARD_REGENERATE_ATTEMPTS")


def fetch_remote(profile: str = "default") -> dict[str, object]:
    """config-server에서 설정을 읽어 평평한 dict로 만든다. 실패하면 빈 dict."""
    url = os.environ.get("CONFIG_SERVER_URL")
    if not url:
        log.info("CONFIG_SERVER_URL이 없어 config-server 조회를 건너뛴다")
        return {}

    try:
        resp = httpx.get(f"{url.rstrip('/')}/{APP_NAME}/{profile}", timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        # 설정이 없어도 기본값으로 돌 수 있게 만들었으므로 기동을 막지 않는다.
        log.warning("config-server 조회 실패 — 환경변수와 기본값으로 계속한다: %s", e)
        return {}

    merged: dict[str, object] = {}
    # propertySources는 우선순위 높은 것이 앞에 온다. 뒤에서부터 넣어야
    # 앞쪽(우선순위 높은 쪽)이 마지막에 덮어쓴다.
    for src in reversed(body.get("propertySources", [])):
        merged.update(src.get("source", {}))

    log.info("config-server에서 설정 %d개를 읽었다", len(merged))
    return merged


def load() -> Settings:
    return Settings(fetch_remote())
