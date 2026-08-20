"""chunks.jsonl -> 프롬프트에 통째로 주입할 단일 텍스트(data/context.txt)를 만든다.

RAG(검색) 대신 규정 전문을 매 요청에 주입하는 방식이라, 이 파일이 프롬프트의
고정 접두사가 된다. 각 청크 앞에 [chunk_id] 마커를 박아서 모델이 근거를
그 ID로 인용하게 하고, 인용된 ID는 chunks.jsonl의 ID 집합 조회만으로
실존 여부를 판정할 수 있게 한다. (평가셋의 answer_chunks와 바로 비교된다.)

출력 순서는 chunks.jsonl 순서를 그대로 따른다. implicit caching의 접두사
히트를 위해 이 순서는 바뀌면 안 된다.

사용법:
    uv run python scripts/build_prompt_context.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = ROOT / "data" / "chunks.jsonl"
OUT_PATH = ROOT / "data" / "context.txt"

HEADER = """다음은 조직 규정 문서 전문이다.
각 항목은 [청크ID] 로 시작하며, 그 뒤에 문서 경로와 본문이 온다.
답변의 근거를 밝힐 때는 반드시 이 청크ID를 사용한다.
"""


def load_chunks():
    if not CHUNKS_PATH.exists():
        raise SystemExit(
            f"{CHUNKS_PATH} 가 없습니다. 먼저 `uv run python scripts/build_index.py` 를 실행하세요."
        )
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def chunk_body(rec):
    """chunks.jsonl의 text는 '[heading_path]\\n본문' 형태다. 본문만 떼어낸다."""
    text = rec["text"]
    first, _, rest = text.partition("\n")
    if first.strip() == f"[{rec['heading_path']}]":
        return rest.strip()
    return text.strip()


def main():
    chunks = load_chunks()

    parts = [HEADER]

    # 문서 목록과 버전을 앞에 한 번 실어둔다. 개정 시점 확인용이고,
    # 모델이 "언제 기준 규정인지" 답할 수 있게 한다.
    docs_seen = {}
    for c in chunks:
        docs_seen.setdefault(c["doc_id"], (c["title"], c["version"]))
    parts.append("## 수록 문서")
    for doc_id, (title, version) in docs_seen.items():
        parts.append(f"- {doc_id} · {title} (version: {version})")
    parts.append("")

    parts.append("## 규정 본문")
    for c in chunks:
        parts.append(f"\n[{c['chunk_id']}] {c['heading_path']}\n{chunk_body(c)}")

    text = "\n".join(parts).strip() + "\n"
    OUT_PATH.write_text(text, encoding="utf-8")

    print(f"청크 {len(chunks)}개 / 문서 {len(docs_seen)}개")
    print(f"{OUT_PATH} 저장 ({len(text):,}자)")
    print("\n--- 앞부분 미리보기 ---")
    preview = text.split("\n")
    for line in preview[:14]:
        print(line)
    print("...")


if __name__ == "__main__":
    main()
