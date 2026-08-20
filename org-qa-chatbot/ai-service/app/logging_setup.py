"""로그 설정. 콘솔은 평문, 파일은 ECS JSON.

config-repo/application.yml 의 D-64 결정을 그대로 따른다. 파일 로그만 JSON으로
바꾸는 이유는 Alloy가 level·service·traceId를 라벨로 올릴 수 있어야 하기
때문이고, 콘솔을 평문으로 남기는 이유는 docker logs 로 JSON 한 줄씩 읽는 것이
사람에게 더 나쁘기 때문이다.

Spring Boot 3.4는 structured.format.file=ecs 한 줄로 되지만 여기서는 포매터를
직접 쓴다. 의존성을 하나 더 두는 것보다 20줄 쓰는 편이 낫다.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SERVICE = "ai-service"

# ECS 필드명과 맞춘다. 기존 서비스의 파일 로그와 같은 스키마여야 Alloy 파이프라인이
# 서비스별로 갈라지지 않는다.
_LEVEL_MAP = {
    "DEBUG": "debug", "INFO": "info", "WARNING": "warn",
    "ERROR": "error", "CRITICAL": "critical",
}


class EcsFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "@timestamp": datetime.fromtimestamp(record.created, timezone.utc)
                          .isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "log.level": _LEVEL_MAP.get(record.levelname, record.levelname.lower()),
            "message": record.getMessage(),
            "service.name": _SERVICE,
            "log.logger": record.name,
            "process.thread.name": record.threadName,
        }
        # 요청 상관관계 필드. application.yml의 correlation fields와 맞춘다.
        for attr in ("request_id", "trace_id", "span_id"):
            if (v := getattr(record, attr, None)) is not None:
                doc[attr.replace("_", ".")] = v
        if record.exc_info:
            doc["error.stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)


def setup(log_dir: str, level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    # uvicorn이 자기 핸들러를 붙여두므로 중복 출력을 막으려면 비우고 시작한다.
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"))
    root.addHandler(console)

    try:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path / f"{_SERVICE}.json", encoding="utf-8")
        file_handler.setFormatter(EcsFormatter())
        root.addHandler(file_handler)
    except OSError as e:
        # 로그 디렉터리가 없어도 서비스는 떠야 한다. 콘솔 로그는 남는다.
        root.warning("파일 로그를 열 수 없어 콘솔만 쓴다 (%s): %s", log_dir, e)

    # uvicorn 로거들이 자기 핸들러로 따로 찍는 것을 막고 루트로 모은다.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    # 헬스체크가 10초마다 들어와 액세스 로그를 가득 채운다. Consul 체크와
    # Prometheus 스크레이프는 정상 트래픽이 아니므로 액세스 로그에서 뺀다.
    logging.getLogger("uvicorn.access").addFilter(_drop_probe_paths)


_PROBE_PATHS = ("/actuator/health", "/actuator/prometheus")


def _drop_probe_paths(record: logging.LogRecord) -> bool:
    msg = record.getMessage()
    return not any(p in msg for p in _PROBE_PATHS)


def env_log_dir() -> str:
    return os.environ.get("LOG_DIR", "./logs")
