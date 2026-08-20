"""커리큘럼 로드맵 코어.

CLI(`scripts/`), 평가 러너, FastAPI 서비스(`service/`)가 전부 이 패키지를 쓴다.
로직을 한 곳에 두려고 뺐다.

    catalog   강의 목록 로드
    prompt    프롬프트 조립
    verify    코드 검증
    schedule  주차 배분
    llm       모델 호출 지점 (여기만 갈아끼우면 모델을 바꾼다)
    engine    생성 → 검증 → 재생성 루프
"""

from .catalog import LEVEL_LABEL, available_hours, load_courses
from .engine import Result, build, stream
from .llm import Gemini, LLMError
from .schedule import pack_weeks
from .verify import check

__all__ = [
    "LEVEL_LABEL", "available_hours", "load_courses",
    "Result", "build", "stream", "Gemini", "LLMError", "pack_weeks", "check",
]
