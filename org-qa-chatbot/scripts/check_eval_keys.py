"""eval_qa.jsonl의 정답 키가 현재 docs/와 정합한지 검사한다.

chunk_id는 `{doc_id}-{문서 내 순번}` 이라 문서 중간에 섹션을 하나만 추가해도
그 뒤 청크 ID가 전부 밀린다. 밀린 ID도 '존재하는' ID이므로 에러 없이
평가셋이 엉뚱한 청크를 가리키게 되고, 채점 점수만 조용히 무너진다.
docs/를 고칠 때마다 이 스크립트를 돌려서 그 사고를 잡는다.

사용법:
    uv run python scripts/check_eval_keys.py

정상이면 exit 0, 문제가 있으면 exit 1.
"""

import json
import sys
from collections import Counter

from _shared import DATA_DIR, DOCS_DIR, ROOT

# 서비스가 쓰는 청킹 로직 그대로. 평가와 운영의 chunk_id가 어긋나면 안 된다.
from app.regulations import chunk_document  # noqa: E402

EVAL_PATH = DATA_DIR / "eval_qa.jsonl"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"

REQUIRED_FIELDS = ("id", "q", "category", "type", "answer_doc", "answer_chunks", "gold")
VALID_TYPES = {"normal", "multi_hop", "conflict", "unanswerable"}

errors: list[str] = []
warnings: list[str] = []


def load_fresh_chunks():
    """docs/를 지금 청킹한 결과. chunks.jsonl이 아니라 이쪽을 정답으로 본다."""
    records = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        records.extend(chunk_document(path))
    return records


def main():
    if not EVAL_PATH.exists():
        raise SystemExit(f"평가셋을 찾을 수 없습니다: {EVAL_PATH}")

    chunks = load_fresh_chunks()
    chunk_ids = {c["chunk_id"] for c in chunks}
    # doc_id -> 그 문서의 청크 ID 집합 (answer_doc 정합성 확인용)
    doc_to_chunks: dict[str, set[str]] = {}
    for c in chunks:
        doc_to_chunks.setdefault(c["doc_id"], set()).add(c["chunk_id"])

    dup = [cid for cid, n in Counter(c["chunk_id"] for c in chunks).items() if n > 1]
    if dup:
        errors.append(f"chunk_id 중복: {dup}")

    # docs/*.md 파일명 -> doc_id
    file_to_doc_id = {}
    for path in sorted(DOCS_DIR.glob("*.md")):
        recs = chunk_document(path)
        if recs:
            file_to_doc_id[path.name] = recs[0]["doc_id"]

    items = []
    with EVAL_PATH.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append((lineno, json.loads(line)))
            except json.JSONDecodeError as e:
                errors.append(f"{EVAL_PATH.name}:{lineno} JSON 파싱 실패 - {e}")

    seen_ids = set()
    for lineno, it in items:
        eid = it.get("id", f"<line {lineno}>")

        missing_fields = [k for k in REQUIRED_FIELDS if k not in it]
        if missing_fields:
            errors.append(f"{eid}: 필드 누락 {missing_fields}")
            continue

        if eid in seen_ids:
            errors.append(f"{eid}: id 중복")
        seen_ids.add(eid)

        qtype = it["type"]
        if qtype not in VALID_TYPES:
            errors.append(f"{eid}: 알 수 없는 type '{qtype}' (허용: {sorted(VALID_TYPES)})")
            continue

        answer_chunks = it["answer_chunks"]
        answer_doc = it["answer_doc"]

        if qtype == "unanswerable":
            # 규정에 없는 질문은 정답 청크가 있으면 안 된다.
            if answer_chunks:
                errors.append(f"{eid}: unanswerable인데 answer_chunks가 비어 있지 않음 {answer_chunks}")
            if answer_doc is not None:
                errors.append(f"{eid}: unanswerable인데 answer_doc이 '{answer_doc}'")
            continue

        # 답변 가능 문항: 정답 청크가 반드시 있어야 채점이 성립한다.
        if not answer_chunks:
            errors.append(f"{eid}: type={qtype}인데 answer_chunks가 비어 있음")
            continue

        unknown = [c for c in answer_chunks if c not in chunk_ids]
        if unknown:
            errors.append(f"{eid}: 존재하지 않는 chunk_id {unknown}")

        if len(set(answer_chunks)) != len(answer_chunks):
            warnings.append(f"{eid}: answer_chunks에 중복 있음 {answer_chunks}")

        # answer_doc은 '주 근거 문서'다. 청크가 여러 문서에 걸쳐도,
        # 최소 하나는 answer_doc에서 나와야 한다.
        if answer_doc not in file_to_doc_id:
            errors.append(f"{eid}: answer_doc '{answer_doc}'가 docs/에 없음")
        else:
            owned = doc_to_chunks.get(file_to_doc_id[answer_doc], set())
            if not (set(answer_chunks) & owned):
                errors.append(
                    f"{eid}: answer_chunks 중 answer_doc('{answer_doc}')에 속한 것이 하나도 없음"
                )

        if qtype == "multi_hop" and len(answer_chunks) < 2:
            warnings.append(f"{eid}: multi_hop인데 answer_chunks가 1개뿐")
        if qtype == "conflict" and len(answer_chunks) < 2:
            warnings.append(f"{eid}: conflict인데 answer_chunks가 1개뿐 (불일치는 2곳 이상이어야 성립)")

    # chunks.jsonl이 docs/보다 오래됐는지 확인
    if CHUNKS_PATH.exists():
        stale = {json.loads(l)["chunk_id"] for l in CHUNKS_PATH.open(encoding="utf-8") if l.strip()}
        if stale != chunk_ids:
            warnings.append(
                f"chunks.jsonl이 docs/와 다릅니다 (파일 {len(stale)}개 vs 현재 {len(chunk_ids)}개). "
                "build_index.py를 다시 실행하세요."
            )
    else:
        warnings.append("chunks.jsonl이 아직 없습니다. build_index.py를 실행하세요.")

    # ── 리포트 ────────────────────────────────────────────
    type_counts = Counter(it["type"] for _, it in items if "type" in it)
    used = {c for _, it in items for c in it.get("answer_chunks", [])}

    print(f"문서 {len(file_to_doc_id)}개 → 청크 {len(chunk_ids)}개 "
          f"/ 본문 {sum(c['char_count'] for c in chunks):,}자")
    print(f"평가셋 {len(items)}문항: " + " · ".join(f"{t} {n}" for t, n in sorted(type_counts.items())))
    print(f"정답 키가 참조하는 고유 청크: {len(used)}/{len(chunk_ids)} "
          f"({len(used) / len(chunk_ids) * 100:.0f}% 커버)")

    for w in warnings:
        print(f"  [경고] {w}")
    for e in errors:
        print(f"  [오류] {e}")

    if errors:
        print(f"\n실패: 오류 {len(errors)}건")
        return 1
    print(f"\n통과{f' (경고 {len(warnings)}건)' if warnings else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
