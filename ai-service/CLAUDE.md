# CLAUDE.md: ai-service 작업 규칙

막힌 지점과 그 해결을 남긴다. 다음 세션에서 같은 곳을 다시 밟지 않기 위한 것이다.

## 빌드 · 실행

- **`uv sync`가 `OSError: Readme file does not exist: README.md`로 실패**: `pyproject.toml`에
  `readme = "README.md"`를 적어두고 파일을 안 만들면 hatchling이 메타데이터 검증에서 죽는다.
  의존성 문제처럼 보이지만 아니다 → **`readme =`를 적는 순간 README.md도 같이 만든다.**
- **`python`이 실행되지 않음(exit 49)**: Windows Store 스텁이 잡힌다
  → 이 프로젝트에서 파이썬은 항상 **`uv run python`**으로 부른다.

## Windows 환경

- **PowerShell에서 `curl`은 `Invoke-WebRequest` 별칭이다.** `curl -i ...`가
  `missing mandatory parameters: Uri`로 죽는다. **요청이 나가지도 않았는데 서버 문제로 보인다**
  → PowerShell에서는 **`curl.exe`**를 쓴다. Git Bash에서는 `curl` 그대로 된다.
- **서버는 `ai-service/`에서 띄운다.** 저장소 루트에서 `uv run uvicorn`을 하면
  `Failed to spawn: uvicorn. program not found`가 나는데 디렉터리 문제라는 말이 없다.

## 로깅

- **한글 로그가 `���� ������`로 깨짐**: Windows 기본 stdout 인코딩이 cp949라 파일·파이프로
  나갈 때 UTF-8 소비자가 못 읽는다. **예외가 안 나서 조용히 깨진다**
  → `app/main.py`에서 `sys.stdout.reconfigure(encoding="utf-8")`를 로깅 설정 전에 부른다.
  Linux 컨테이너에서는 무해하다. 나중에 Loki·Alloy로 보낼 때 필수다.

## 설계에서 건드리면 안 되는 것

- **`app/core/security.py`의 `require_member_id()`는 신뢰 지점 단 하나다.** 엔드포인트에서
  `X-Member-Id`를 직접 읽지 않는다. 5기 MSA에 붙일 때 이 함수만 JWKS 검증으로 교체한다.
- **`visibility` 필터는 Chroma 질의 조건으로 건다.** 가져온 뒤 걸러내지 않는다.
  한 곳만 빠뜨려도 미션 정답이 나가고, 그건 되돌릴 수 없다.
- **`no_evidence` 경로에서는 모델에 조각을 넘기지 않는다.** 넘기지 않으면 지어낼 재료가 없다.
- **색인과 검색은 반드시 같은 임베딩 모델을 쓴다.** 다르면 벡터 공간이 어긋나 검색이
  조용히 이상해진다. 그래서 팩토리 함수 하나로 강제한다.

## 글쓰기

- 줄표(U+2014)를 쓰지 않는다. 콜론, 마침표, 괄호로 바꾼다.
- 뻔한 변경까지 정당화하지 않는다. 안 뻔한 것만 이유를 적는다.
- 같은 문장 구조를 반복하지 않는다. "A했다. 왜냐하면 B다"가 문단마다 나오면 고친다.
- 커밋 본문은 3~6줄, PR 본문은 50줄 안팎을 넘기지 않는다.

## 코드 스타일

- 안 쓰는 의존성·설정 상수를 미리 넣지 않는다. 쓰는 슬라이스에서 근거 주석과 함께 넣는다.
- 주석은 넷 중 하나일 때만: 왜 그렇게 했는지가 코드에 안 보일 때 / 안 하면 조용히 깨지는 것 /
  값의 근거가 임의일 때 / 순서가 중요할 때. 코드를 그대로 읽은 주석은 달지 않는다.
- 파일 상단에 무엇이고 어디서 쓰이는지와 확인 방법을 적는다. 본문은 번호로 구역을 나눈다.
