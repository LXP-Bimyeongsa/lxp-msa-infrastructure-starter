"""
scripts/search_check.py — 색인이 쓸 만한지 눈으로 본다

이 파일의 역할: 질의 하나를 넣어 조각이 돌아오는지, 제한 조각이 새지 않는지 본다.
→ scripts/init_vectorstore.py 가 만든 색인을 읽는다
→ 앞으로 app/tools/rag.py 가 여기서 확인한 질의 형태를 그대로 쓴다
확인: 학습자 검색에 restricted 가 0건이고, 필터를 뗀 검색에는 나온다

실행 방법:
  uv run python scripts/search_check.py "청킹할 때 겹침을 왜 두나요"
  uv run python scripts/search_check.py "질문" --course c-04
"""

import argparse
import sys

from langchain_chroma import Chroma

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    INDEX_MARKER,
    TOP_K,
    get_embeddings,
)


def open_store() -> Chroma:
    if not INDEX_MARKER.exists():
        raise SystemExit("색인이 끝까지 만들어지지 않았다. init_vectorstore.py 를 돌린다")
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


# 1. 학습자 검색 — 제한 조각을 질의 조건으로 뺀다.
# 가져온 뒤 걸러내지 않는다. 한 곳만 빠뜨려도 뚫리기 때문이다
def learner_filter(course_id: str | None) -> dict:
    conds = [{"visibility": {"$eq": "public"}}]
    if course_id:
        conds.append({"course_id": {"$eq": course_id}})
    return conds[0] if len(conds) == 1 else {"$and": conds}


def show(title: str, hits) -> None:
    print(f"\n[{title}] {len(hits)}건")
    for doc, score in hits:
        m = doc.metadata
        head = doc.page_content.split("\n", 1)[0][:60]
        print(f"  {score:.3f}  {m['visibility']:<10} {m['source_path']}#{m['seq']}")
        print(f"         {head}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--course", default=None)
    ap.add_argument("--k", type=int, default=TOP_K)
    args = ap.parse_args()

    store = open_store()

    learner = store.similarity_search_with_relevance_scores(
        args.question, k=args.k, filter=learner_filter(args.course)
    )
    show("학습자 검색 (제한 제외)", learner)

    leaked = [d for d, _ in learner if d.metadata["visibility"] != "public"]
    print(f"\n제한 조각 유출: {len(leaked)}건" + ("" if not leaked else "  ← 필터가 안 걸렸다"))

    # 필터를 떼면 제한 조각이 실제로 색인에 있다는 것을 보인다.
    # 이게 0건이면 필터가 잘 도는 게 아니라 막을 것이 애초에 없었던 것이다
    raw = store.similarity_search_with_relevance_scores(args.question, k=args.k)
    show("필터 없음 (대조군)", raw)
    restricted = sum(1 for d, _ in raw if d.metadata["visibility"] == "restricted")
    print(f"\n대조군의 제한 조각: {restricted}건")
    if not leaked and restricted:
        print("→ 막을 것이 있었고 실제로 막혔다")


if __name__ == "__main__":
    main()
