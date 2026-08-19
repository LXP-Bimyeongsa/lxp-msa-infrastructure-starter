"""docker compose healthcheck용. 종료 코드만 쓴다.

python:slim 이미지에는 curl이 없다. 의존성을 하나 더 넣는 대신 표준 라이브러리로
확인한다. compose에 한 줄로 밀어 넣을 수도 있지만, 503일 때 urlopen이 예외를
던져 컨테이너 로그에 트레이스백이 남는다. 헬스체크는 10초마다 도므로 그 노이즈가
쌓인다.

사용: python -m app.healthcheck
"""

import sys
import urllib.error
import urllib.request

URL = "http://localhost:8086/actuator/health"
TIMEOUT = 3.0


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as resp:
            return 0 if resp.status == 200 else 1
    except urllib.error.HTTPError as e:
        # 503은 정상적인 응답이다(미등록 등). 실패로 세되 조용히 끝낸다.
        print(f"health {e.code}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"health unreachable: {type(e).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
