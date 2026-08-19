"""평가 스크립트가 ai-service의 코드를 import할 수 있게 경로를 잡는다.

프롬프트와 청킹은 ai-service가 소유한다. 평가 쪽에 복사본을 두면 둘이 갈라지고,
그 순간 평가 결과가 운영과 무관해진다. 그래서 여기서는 경로만 붙이고 코드는
가져다 쓴다.

사용:
    from _shared import DOCS_DIR, ROOT   # 이 import가 sys.path를 먼저 손댄다
    from app.prompt import SYSTEM_INSTRUCTION, build_prompt, split_answer
    from app.regulations import load as load_regulations
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # org-qa-chatbot/
REPO_ROOT = ROOT.parent
AI_SERVICE = REPO_ROOT / "ai-service"

DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"

if not AI_SERVICE.is_dir():
    raise SystemExit(
        f"ai-service를 찾을 수 없다: {AI_SERVICE}\n"
        "프롬프트와 청킹 코드는 ai-service/app 에 있다. 같은 저장소 안에서 실행해야 한다."
    )

if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))
