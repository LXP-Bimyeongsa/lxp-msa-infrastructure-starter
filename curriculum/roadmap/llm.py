"""모델 호출 지점.

여기만 갈아끼우면 유료 전환·다른 모델·로컬 모델로 옮길 수 있다. 나머지 코드는
generate(prompt) -> (dict, usage) 라는 모양에만 의존한다.

    무료 → 유료        API 키만 교체. 코드는 그대로
    Gemini → 다른 API  Backend 구현을 하나 더 만든다
    API → 로컬          같음
"""

import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 무료 티어에서 흔히 만난다. 429 는 한도, 5xx 는 일시적 과부하다.
# 둘 다 잠깐 뒤에 다시 부르면 되는 종류라 실패로 끝내지 않는다.
RETRIABLE = {429, 500, 502, 503, 504}

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


class LLMError(RuntimeError):
    def __init__(self, status, detail):
        super().__init__(f"{status} {detail}")
        self.status = status
        self.detail = detail


class Gemini:
    """Gemini REST 호출. 의존성을 늘리지 않으려고 SDK 대신 표준 라이브러리를 쓴다."""

    def __init__(self, api_key=None, model=None, max_attempts=4, temperature=0.2):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or DEFAULT_MODEL
        self.max_attempts = max_attempts
        self.temperature = temperature
        if not self.api_key:
            raise LLMError(0, "GEMINI_API_KEY 가 없다")

    def generate(self, prompt):
        """반환: (파싱된 JSON, usage 딕셔너리)"""
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": self.temperature,
            },
        }).encode("utf-8")
        url = ENDPOINT.format(model=self.model) + f"?key={self.api_key}"

        last = None
        for attempt in range(1, self.max_attempts + 1):
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    payload = json.loads(resp.read())
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text), payload.get("usageMetadata", {})
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")
                last = LLMError(e.code, detail)
                if e.code not in RETRIABLE or attempt == self.max_attempts:
                    raise last
            except urllib.error.URLError as e:
                last = LLMError(0, str(e.reason))
                if attempt == self.max_attempts:
                    raise last
            time.sleep(2 ** attempt)

        raise last
