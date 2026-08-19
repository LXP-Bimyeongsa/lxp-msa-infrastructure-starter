"""
app/tools/rag.py: 검색 계층

이 파일의 역할: Chroma 에 질의하고 조각을 돌려준다. 제한 조각을 거르는 유일한 자리다.
→ app/graph/nodes.py 의 retrieve 가 부른다
→ scripts/search_check.py 가 같은 필터를 쓴다
확인: learner_filter 를 건 검색 결과에 visibility=restricted 가 없다
"""

from functools import lru_cache

from langchain_chroma import Chroma

from app.core.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    INDEX_MARKER,
    TOP_K,
    get_embeddings,
)


# 1. 저장소: 요청마다 다시 열지 않는다
@lru_cache(maxsize=1)
def get_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def is_ready() -> bool:
    return INDEX_MARKER.exists()


# 2. 학습자 검색 필터: 제한 조각을 질의 조건으로 뺀다.
# 가져온 뒤 걸러내지 않는다. 거르는 자리가 여러 곳이면 한 곳만 빠뜨려도 뚫리고,
# 그때는 미션 정답이 나간 뒤라 되돌릴 수 없다
def learner_filter(course_id: str | None = None) -> dict:
    conds: list[dict] = [{"visibility": {"$eq": "public"}}]
    if course_id:
        conds.append({"course_id": {"$eq": course_id}})
    return conds[0] if len(conds) == 1 else {"$and": conds}


# 3. 검색: 점수를 함께 돌려준다. 품질 판정(S3)이 점수를 봐야 한다
def search(query: str, course_id: str | None = None, k: int = TOP_K) -> list[dict]:
    hits = get_store().similarity_search_with_relevance_scores(
        query, k=k, filter=learner_filter(course_id)
    )
    return [
        {
            "text": doc.page_content,
            "score": score,
            "course_id": doc.metadata["course_id"],
            "seq": doc.metadata["seq"],
            "source_path": doc.metadata["source_path"],
        }
        for doc, score in hits
    ]
