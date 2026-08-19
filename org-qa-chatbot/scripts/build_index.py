"""docs/*.md 를 청킹해서 data/chunks.jsonl 로 저장한다.

청킹 로직 자체는 ai-service/app/regulations.py 에 있다. 서비스가 런타임에 규정을
읽어야 하고(14번 재로드), 평가와 운영이 같은 청킹을 써야 chunk_id가 일치한다.
이 스크립트는 그 결과를 파일로 떨어뜨리는 CLI일 뿐이다.

chunks.jsonl 은 사람이 청크 경계를 눈으로 확인하거나 특정 chunk_id의 내용을
찾아볼 때 쓴다. 평가 스크립트는 이 파일이 아니라 regulations.load() 를 직접 쓴다.
파일을 거치면 오래된 chunks.jsonl 로 채점하는 사고가 생긴다.

사용법:
    uv run python scripts/build_index.py
"""

import json

from _shared import DATA_DIR, DOCS_DIR, ROOT

from app.regulations import chunk_all  # noqa: E402  (_shared 가 경로를 먼저 잡는다)

OUT_PATH = DATA_DIR / "chunks.jsonl"


def main() -> None:
    if not DOCS_DIR.is_dir():
        raise SystemExit(f"docs 폴더를 찾을 수 없습니다: {DOCS_DIR}")

    records = chunk_all(DOCS_DIR)
    if not records:
        raise SystemExit(f"{DOCS_DIR} 안에 .md 파일이 없습니다.")

    by_doc: dict[str, int] = {}
    for r in records:
        by_doc[r["doc_id"]] = by_doc.get(r["doc_id"], 0) + 1
    for doc_id, n in by_doc.items():
        print(f"  {doc_id}: {n}개 청크")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total_chars = sum(r["char_count"] for r in records)
    print(f"\n총 {len(records)}개 청크 / 본문 {total_chars:,}자 "
          f"→ {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
