"""
scripts/build_corpus.py — 학습 자료를 3단계 원본 규약으로 변환한다

이 파일의 역할: potenup 학습 자료(장/절/예제)를 courses/ 디렉터리 규약과 프론트매터로 옮긴다.
→ scripts/init_vectorstore.py 가 그 결과를 읽어 색인한다
확인: data/raw/courses/ 아래 lessons 와 missions 가 생기고, 판별 리포트에 기본값 파일이 없다

변환 규칙 (AI-06)
  장 디렉터리 NN_name        → courseId c-NN
  절의 readme.md             → lessons/MM-slug.md          공개
  절의 예제 *.py 의 docstring → missions/m-MM/description.md 공개
  절의 예제 *.py 의 코드      → missions/m-MM/solution.md    제한

제한 조각이 없으면 원칙 3(미션 정답을 흘리지 않는가)을 검증할 대상 자체가 없다.
그래서 코드 본문을 제한으로 갈라두는 것이 이 스크립트의 핵심이다.

실행 방법:
  uv run python scripts/build_corpus.py
  uv run python scripts/build_corpus.py --source <다른 경로>
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import RAW_DIR

DEFAULT_SOURCE = Path(__file__).resolve().parents[4] / "19_langchain"
COURSES_DIR = RAW_DIR / "courses"

# 장 디렉터리 이름이 이 꼴이어야 강의로 본다. 00_img 같은 자료 폴더를 걸러낸다
CHAPTER_RE = re.compile(r"^(\d{2})_(.+)$")


# 1. 언어 판별 — 자동 판별한 값은 반드시 리포트에 남긴다.
# 조용히 넘어가면 나중에 검색이 안 될 때 원인을 못 찾는다 (3단계 문서 5장)
def detect_lang(text: str) -> str:
    hangul = len(re.findall(r"[가-힣]", text))
    letters = len(re.findall(r"[A-Za-z가-힣]", text)) or 1
    return "ko" if hangul / letters > 0.15 else "en"


def slug(name: str) -> str:
    return name.replace("_", "-").lower()


# 코드 블록을 먼저 걷어내고 제목을 찾는다.
# 파이썬 주석 "# 출력: ..." 이 H1 으로 잡혀 title 에 들어간 적이 있다
def first_heading(text: str, fallback: str) -> str:
    stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    m = re.search(r"^#\s+(.+)$", stripped, re.MULTILINE)
    return m.group(1).strip() if m else fallback


# 프론트매터를 문자열 조립으로 만들지 않는다.
# title 에 콜론이나 따옴표가 들어가면 YAML 이 깨지는데, 읽는 쪽에서야 터진다
def write_doc(path: Path, meta: dict, body: str) -> None:
    head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    lines = ["---", head, "---", "", body.strip(), ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# 2. 예제 파일 가르기 — docstring 은 무엇을 만드는지, 코드는 어떻게 만드는지다
def split_example(text: str) -> tuple[str, str]:
    m = re.match(r'\s*"""(.*?)"""(.*)', text, re.DOTALL)
    if not m:
        return "", text
    return m.group(1).strip(), m.group(2).strip()


def build(source: Path) -> list[dict]:
    if COURSES_DIR.exists():
        # 규칙을 바꿔가며 여러 번 돌리게 된다. 지난 결과가 섞이면 판별 리포트를 믿을 수 없다
        shutil.rmtree(COURSES_DIR)

    report = []
    for chapter in sorted(p for p in source.iterdir() if p.is_dir()):
        m = CHAPTER_RE.match(chapter.name)
        if not m:
            continue
        course_id = f"c-{m.group(1)}"

        overview = chapter / "README.md"
        if overview.exists():
            text = overview.read_text(encoding="utf-8", errors="replace")
            lang = detect_lang(text)
            write_doc(
                COURSES_DIR / course_id / "lessons" / "00-overview.md",
                {
                    "courseId": course_id,
                    "visibility": "public",
                    "lang": lang,
                    "title": first_heading(text, slug(m.group(2))),
                    "version": 1,
                },
                text,
            )
            report.append({"file": f"{course_id}/lessons/00-overview.md", "vis": "public",
                           "why": "경로 규칙 lessons", "lang": lang, "chars": len(text)})

        for section in sorted(p for p in chapter.iterdir() if p.is_dir()):
            sm = CHAPTER_RE.match(section.name)
            if not sm:
                continue
            seq, sec_slug = sm.group(1), slug(sm.group(2))

            readme = next((f for f in section.glob("*.md") if f.name.lower() == "readme.md"), None)
            if readme:
                text = readme.read_text(encoding="utf-8", errors="replace")
                lang = detect_lang(text)
                write_doc(
                    COURSES_DIR / course_id / "lessons" / f"{seq}-{sec_slug}.md",
                    {
                        "courseId": course_id,
                        "visibility": "public",
                        "lang": lang,
                        "title": first_heading(text, sec_slug),
                        "version": 1,
                    },
                    text,
                )
                report.append({"file": f"{course_id}/lessons/{seq}-{sec_slug}.md", "vis": "public",
                               "why": "경로 규칙 lessons", "lang": lang, "chars": len(text)})

            examples = sorted(section.glob("*.py"))
            if not examples:
                continue
            mission_id = f"m-{seq}"
            descs, sols = [], []
            for ex in examples:
                text = ex.read_text(encoding="utf-8", errors="replace")
                doc, code = split_example(text)
                if doc:
                    descs.append(f"## {ex.name}\n\n{doc}")
                if code:
                    sols.append(f"## {ex.name}\n\n```python\n{code}\n```")

            base = COURSES_DIR / course_id / "missions" / mission_id
            meta = {"courseId": course_id, "missionId": mission_id, "lang": "ko", "version": 1}
            if descs:
                body = "\n\n".join(descs)
                write_doc(base / "description.md",
                          {**meta, "visibility": "public", "title": f"{sec_slug} 실습"}, body)
                report.append({"file": f"{course_id}/missions/{mission_id}/description.md",
                               "vis": "public", "why": "프론트매터", "lang": "ko", "chars": len(body)})
            if sols:
                body = "\n\n".join(sols)
                write_doc(base / "solution.md",
                          {**meta, "visibility": "restricted", "title": f"{sec_slug} 모범답안"}, body)
                report.append({"file": f"{course_id}/missions/{mission_id}/solution.md",
                               "vis": "restricted", "why": "경로 규칙 solution.md",
                               "lang": "ko", "chars": len(body)})
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"원본을 찾을 수 없다: {args.source}")

    report = build(args.source)
    pub = [r for r in report if r["vis"] == "public"]
    res = [r for r in report if r["vis"] == "restricted"]
    total = sum(r["chars"] for r in report)

    print(f"원본   : {args.source}")
    print(f"출력   : {COURSES_DIR}")
    print(f"파일   : {len(report)}개 (공개 {len(pub)} · 제한 {len(res)})")
    print(f"글자수 : {total:,} — 800자 기준 약 {total // 800}조각")
    print(f"언어   : ko {sum(1 for r in report if r['lang'] == 'ko')} · "
          f"en {sum(1 for r in report if r['lang'] == 'en')}")

    # 기본값(restricted)으로 떨어진 파일이 있으면 규약을 안 지킨 원본이 있다는 뜻이다
    fallback = [r for r in report if r["why"] == "기본값"]
    print(f"기본값 판정: {len(fallback)}개" + (" ← 확인 필요" if fallback else ""))

    if not res:
        raise SystemExit("제한 조각이 하나도 없다. 원칙 3을 검증할 대상이 없어진다")


if __name__ == "__main__":
    main()
