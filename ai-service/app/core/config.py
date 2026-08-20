"""
app/core/config.py: 설정과 경로 상수

이 파일의 역할: .env 를 읽어 타입 검증된 설정 하나를 만들고, 데이터 경로를 한 곳에 고정한다.
→ app/main.py 가 /health 에서 CHROMA_DIR 를 본다
→ S1 이후 scripts/init_vectorstore.py 와 app/tools/rag.py 가 같은 상수를 참조한다
확인: uv run uvicorn app.main:app 이 .env 없이도 뜬다
"""

from pathlib import Path

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic_settings import BaseSettings, SettingsConfigDict

# LangChain 계열은 BaseSettings 가 아니라 os.environ 을 직접 읽는다.
# 그래서 둘 다 필요하다. load_dotenv() 가 없으면 트레이싱이 조용히 안 켜진다
load_dotenv()


# 1. 경로 상수: 색인을 만드는 쪽과 읽는 쪽이 같은 경로를 봐야 한다
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # ai-service/
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # 강의 교안 원본 마크다운
CHROMA_DIR = DATA_DIR / "chroma"  # 색인. S1 에서 생성된다

# 색인이 끝까지 갔다는 표시. 디렉터리 존재만 보면 중간에 죽은 반쪽 색인도
# 준비된 것으로 보인다. 실제로 429 로 50/633 에서 끊겼을 때 그렇게 보였다
INDEX_MARKER = CHROMA_DIR / ".complete"

# 그래프 재개용 저장소. 대화 이력 조회는 나중에 관계형 테이블로 따로 만든다
CHECKPOINT_DB = DATA_DIR / "checkpoints.sqlite"

# 강의별로 컬렉션을 나누지 않는다. 강의가 늘 때마다 컬렉션이 늘면 관리가 안 되고,
# course_id 메타 필터로 같은 효과가 나온다 (2단계 문서 3.1)
COLLECTION_NAME = "lxp_knowledge"

# 2. 분할 파라미터: 전부 임의값이다. 6단계에서 조각 길이 분포를 보고 조정한다
CHUNK_TARGET = 800  # 목표 길이
CHUNK_MAX = 1200  # 상한. 코드 블록 하나가 이걸 넘으면 예외로 둔다
CHUNK_MIN = 200  # 하한. 미만이면 앞 조각에 병합한다
CHUNK_OVERLAP = 120  # 겹침. 경계에 걸친 설명이 양쪽 어디에도 안 들어가는 것을 막는다

TOP_K = 5  # 가져올 조각 수. 임의값

# 1단계 판정 기준. 최고 유사도가 이 값 미만이면 내용 판정을 돌리지 않고 부족으로 본다.
# 임의값이고 6단계에서 실제 점수 분포를 보고 조정한다
MIN_SCORE = 0.35

# 재검색 상한. 이 값이 없으면 루프가 끝나지 않는다
MAX_RETRY = 2

# 한 실행에서 밟을 수 있는 최대 단계. 루프가 잘못 돌아도 호출만 쌓이는 것을 막는다
RECURSION_LIMIT = 12


# 3. 환경 설정
class Settings(BaseSettings):
    PROJECT_NAME: str = "lxp-ai-tutor"
    PORT: int = 8086  # 5기 compose 에서 8080·8082~8085 가 쓰이고 있어 비어 있는 번호

    # 모델: 4단계에서는 호출하지 않으므로 기본값을 준다.
    # 필수로 두면 키 없이는 서버가 아예 안 떠서 "뼈대가 도는가"를 확인할 수 없다.
    # 빈 값 검사는 실제로 모델을 부르는 S1 의 팩토리에서 한다
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = "gemini-3.1-flash-lite"
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"  # 한국어·영어를 함께 처리한다

    # 트레이싱: 기본값을 반드시 준다.
    # 레퍼런스(11_serving_ops)는 LANGSMITH_API_KEY 에 기본값이 없어서,
    # .env 에 키가 빠지면 모듈 임포트 시점에 예외가 나고 서버가 안 뜬다
    LANGSMITH_TRACING: str = "false"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "lxp-ai-tutor"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# 4. 전역 인스턴스: 다른 모듈은 이것을 import 한다
settings = Settings()


# 5. 임베딩 팩토리
# 색인하는 쪽과 검색하는 쪽이 반드시 같은 인스턴스 설정을 쓰게 강제한다.
# 다른 모델로 색인하고 검색하면 벡터 공간이 어긋나는데, 오류가 나지 않고
# 그냥 엉뚱한 조각이 상위에 온다. 원인을 찾기 가장 어려운 형태다
def get_embeddings() -> Embeddings:
    # 빈 키 검사를 여기서 한다. 설정 클래스에서 필수로 두면 키 없이는 서버가
    # 아예 안 떠서, 모델을 안 쓰는 단계까지 막힌다 (AI-05)
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 가 비어 있다. .env 에 넣는다")
    return GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL)


# 6. LLM 팩토리
def get_llm(temperature: float = 0.0):
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 가 비어 있다. .env 에 넣는다")
    # 판정과 답변 모두 지어내면 안 되는 작업이라 기본 온도를 0 으로 둔다
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, temperature=temperature)
