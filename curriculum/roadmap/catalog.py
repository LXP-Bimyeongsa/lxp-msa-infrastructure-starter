"""강의 카탈로그 로드.

지금은 JSON 파일에서 읽는다. course-service 에 목록 조회 API 가 생기면
load_courses() 구현만 바꾸면 된다. 나머지는 이 함수가 돌려주는 모양에만
의존한다.
"""

import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "data" / "courses.json"

LEVEL_LABEL = {
    1: "완전 입문", 2: "기초", 3: "중급", 4: "중상급", 5: "고급",
}


def load_courses(path=None):
    with (path or CATALOG).open(encoding="utf-8") as f:
        return json.load(f)


def available_hours(courses, tracks, level_floor=1):
    """주어진 트랙에서 수준 조건을 만족하는 강의의 총 시간.

    채움 정도를 예산 대비로 재면 안 된다. 카탈로그가 그 트랙에 그만큼 없으면
    "예산을 채워라"가 곧 "관계없는 강의를 넣어라"가 된다.
    """
    if not tracks:
        return None
    return sum(c["estimatedHours"] for c in courses
               if c["track"] in tracks and c["level"] >= level_floor)
