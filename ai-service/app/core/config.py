"""
app/core/config.py — 설정과 경로 상수

이 파일의 역할: .env 를 읽어 타입 검증된 설정 하나를 만들고, 데이터 경로를 한 곳에 고정한다.
→ app/main.py 가 /health 에서 CHROMA_DIR 를 본다
→ S1 이후 scripts/init_vectorstore.py 와 app/tools/rag.py 가 같은 상수를 참조한다
확인: uv run uvicorn app.main:app 이 .env 없이도 뜬다
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# LangChain 계열은 BaseSettings 가 아니라 os.environ 을 직접 읽는다.
# 그래서 둘 다 필요하다. load_dotenv() 가 없으면 트레이싱이 조용히 안 켜진다
load_dotenv()


# 1. 경로 상수 — 색인을 만드는 쪽과 읽는 쪽이 같은 경로를 봐야 한다
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # lxp-fifth/
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # 강의 교안 원본 마크다운
CHROMA_DIR = DATA_DIR / "chroma"  # 색인. S1 에서 생성된다

# 강의별로 컬렉션을 나누지 않는다. 강의가 늘 때마다 컬렉션이 늘면 관리가 안 되고,
# course_id 메타 필터로 같은 효과가 나온다 (2단계 문서 3.1)
COLLECTION_NAME = "lxp_knowledge"


# 2. 환경 설정
class Settings(BaseSettings):
    PROJECT_NAME: str = "lxp-ai-tutor"
    PORT: int = 8086  # 5기 compose 에서 8080·8082~8085 가 쓰이고 있어 비어 있는 번호

    # 모델 — 4단계에서는 호출하지 않으므로 기본값을 준다.
    # 필수로 두면 키 없이는 서버가 아예 안 떠서 "뼈대가 도는가"를 확인할 수 없다.
    # 빈 값 검사는 실제로 모델을 부르는 S1 의 팩토리에서 한다
    GEMINI_API_KEY: str = ""

    # 트레이싱 — 기본값을 반드시 준다.
    # 레퍼런스(11_serving_ops)는 LANGSMITH_API_KEY 에 기본값이 없어서,
    # .env 에 키가 빠지면 모듈 임포트 시점에 예외가 나고 서버가 안 뜬다
    LANGSMITH_TRACING: str = "false"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "lxp-ai-tutor"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# 3. 전역 인스턴스 — 다른 모듈은 이것을 import 한다
settings = Settings()
