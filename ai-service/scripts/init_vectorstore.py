"""
scripts/init_vectorstore.py: 교안을 조각내어 Chroma 에 적재한다

이 파일의 역할: data/raw/courses 의 마크다운을 분할·메타 부착·임베딩해서 색인을 만든다.
→ scripts/build_corpus.py 가 만든 결과를 읽는다
→ 앞으로 app/tools/rag.py 가 이 색인을 검색한다
확인: --dry-run 으로 조각 분포를 보고, 상한 초과 조각이 코드 블록뿐인지 본다

실행 방법:
  uv run python scripts/init_vectorstore.py --dry-run     # 임베딩 없이 분할만
  uv run python scripts/init_vectorstore.py --limit 5     # 5개 파일만 실제 적재
  uv run python scripts/init_vectorstore.py               # 전체 적재 (REBUILD)
"""

import argparse
import hashlib
import re
import shutil
import sys
import time
from pathlib import Path

import frontmatter
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import (
    CHROMA_DIR,
    CHUNK_MAX,
    CHUNK_MIN,
    CHUNK_OVERLAP,
    CHUNK_TARGET,
    COLLECTION_NAME,
    INDEX_MARKER,
    RAW_DIR,
    get_embeddings,
)

COURSES_DIR = RAW_DIR / "courses"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


# 1. 블록 나누기: 코드 펜스 안에서는 제목도 문단도 인식하지 않는다.
# 파이썬 주석 "# 출력" 이 제목으로 잡히는 문제를 build_corpus 에서 이미 겪었다
def parse_blocks(text: str) -> list[tuple[tuple[str, ...], str, str]]:
    blocks: list[tuple[tuple[str, ...], str, str]] = []
    path: list[tuple[int, str]] = []
    buf: list[str] = []
    fence = None

    def flush(kind: str) -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if body:
            blocks.append((tuple(t for _, t in path), kind, body))

    for line in text.split("\n"):
        if fence:
            buf.append(line)
            if FENCE_RE.match(line) and line.strip().startswith(fence):
                flush("code")
                fence = None
            continue
        m = FENCE_RE.match(line)
        if m:
            flush("prose")
            fence = m.group(1)
            buf.append(line)
            continue
        h = HEADING_RE.match(line)
        if h:
            flush("prose")
            level = len(h.group(1))
            path = [(lv, t) for lv, t in path if lv < level]
            path.append((level, h.group(2).strip()))
            continue
        buf.append(line)
    flush("code" if fence else "prose")
    return blocks


# 2. 조각으로 묶기
# 의미 경계를 우선하고 길이는 나중에 본다. 반대로 하면 문장 중간에서 잘려
# 조각 하나만으로 뜻이 안 통한다
def pack(blocks, doc_title: str) -> list[str]:
    # 제목 경로는 조각 앞에 붙는다. 붙인 뒤에 길이를 재면 이미 늦어서,
    # 접두사 길이를 미리 빼둔 예산으로 묶는다
    def crumb(path: tuple[str, ...]) -> str:
        head = " > ".join((doc_title, *path)) if path else doc_title
        return "[" + head + "]\n\n"

    chunks: list[tuple[tuple[str, ...], str]] = []
    cur_path: tuple[str, ...] | None = None
    cur = ""
    lim = CHUNK_MAX

    def close() -> None:
        nonlocal cur
        if cur.strip():
            chunks.append((cur_path or (), cur.strip()))
        cur = ""

    for path, kind, body in blocks:
        if cur_path is not None and path != cur_path:
            close()
        cur_path = path
        lim = CHUNK_MAX - len(crumb(path))

        # 코드 블록은 상한을 넘어도 자르지 않는다. 반쪽 코드가 근거로 인용되면
        # 학습자는 동작하지 않는 코드를 보게 된다. 길이 규칙보다 우선한다
        if kind == "code" and len(body) > lim:
            close()
            chunks.append((path, body))
            continue

        if kind == "prose" and len(body) > lim:
            close()
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=lim, chunk_overlap=CHUNK_OVERLAP
            )
            for piece in splitter.split_text(body):
                chunks.append((path, piece))
            continue

        if cur and len(cur) + len(body) + 2 > lim:
            tail = cur[-CHUNK_OVERLAP:]
            close()
            cur = tail + "\n\n"
        cur += body + "\n\n"
        if len(cur) >= CHUNK_TARGET:
            close()
    close()

    # 하한 미만은 앞 조각에 병합한다. 같은 제목 경로일 때만 붙인다
    merged: list[tuple[tuple[str, ...], str]] = []
    for path, body in chunks:
        fits = merged and len(merged[-1][1]) + len(body) + 2 <= CHUNK_MAX - len(crumb(path))
        if fits and len(body) < CHUNK_MIN and merged[-1][0] == path:
            merged[-1] = (path, merged[-1][1] + "\n\n" + body)
        else:
            merged.append((path, body))

    # 제목 경로를 붙인다. 이게 없으면 "격리 수준을 낮추면 처리량은 늘지만..." 같은
    # 문장이 어느 강의의 무슨 이야기인지 알 수 없어 다른 강의와 구분되지 않는다
    out = []
    for path, body in merged:
        crumb = " > ".join((doc_title, *path)) if path else doc_title
        out.append(f"[{crumb}]\n\n{body}")
    return out


# 3. 파일 하나를 조각과 메타데이터로 바꾼다
def load_file(path: Path) -> tuple[list[str], list[dict], list[str]]:
    doc = frontmatter.load(path)
    meta = doc.metadata
    course_id = meta.get("courseId", "")
    if not course_id:
        raise SystemExit(f"courseId 가 없다: {path}")

    version = int(meta.get("version", 1))
    source_path = path.relative_to(COURSES_DIR).as_posix()
    source_id = source_path.replace("/", "-").removesuffix(".md")
    title = str(meta.get("title") or source_id)
    texts = pack(parse_blocks(doc.content), title)

    metas, ids = [], []
    for seq, body in enumerate(texts):
        metas.append(
            {
                "course_id": course_id,
                # 목차를 만들 때 쓴다. 경로만으로는 한국어 질문과 영문 슬러그가
                # 이어지지 않아 정상 질문이 범위 밖으로 밀렸다 (AI-07)
                "title": title,
                "mission_id": meta.get("missionId", ""),
                # 판별이 애매하면 막는 쪽으로 기운다. 공개해야 할 걸 제한하면 답을
                # 못 하고 끝나지만, 제한해야 할 걸 공개하면 되돌릴 수 없다
                "visibility": meta.get("visibility", "restricted"),
                "seq": seq,
                "source_path": source_path,
                "source_hash": hashlib.sha256(body.encode()).hexdigest()[:16],
                "version": version,
                "lang": meta.get("lang", "ko"),
                "char_len": len(body),
            }
        )
        # id 에 버전을 넣는다. 나중에 갱신할 때 새 버전을 다 넣은 뒤 옛 버전을
        # 지워야, 지우고 넣는 사이에 들어온 검색이 빈 결과를 받지 않는다
        ids.append(f"{course_id}:{source_id}:{seq}:{version}")
    return texts, metas, ids


def report(texts: list[str], metas: list[dict]) -> None:
    lens = sorted(len(t) for t in texts)
    over = [(t, m) for t, m in zip(texts, metas) if len(t) > CHUNK_MAX]
    over_code = sum(1 for t, _ in over if "```" in t)
    pub = sum(1 for m in metas if m["visibility"] == "public")

    print(f"조각    : {len(texts)}개 (공개 {pub} · 제한 {len(texts) - pub})")
    if lens:
        mid = lens[len(lens) // 2]
        print(f"길이    : 최소 {lens[0]} · 중앙 {mid} · 최대 {lens[-1]}")
    print(f"상한 초과: {len(over)}개 (그중 코드 블록 포함 {over_code})")
    if len(over) != over_code:
        print("  ← 코드 블록이 아닌데 상한을 넘은 조각이 있다. 분할 규칙을 본다")


# 한도 초과만 잡다가 DNS 실패(getaddrinfo)로 275/633 에서 통째로 죽은 적이 있다.
# REBUILD 는 시작할 때 기존 색인을 지우므로, 죽으면 쓸 수 있는 색인이 아예 없어진다
TRANSIENT = ("RESOURCE_EXHAUSTED", "getaddrinfo", "Connection", "timed out", "UNAVAILABLE", "503")


# 4. 적재: 한도에 걸리면 기다렸다 같은 배치를 다시 넣는다.
# 여기서 포기하면 앞서 넣은 것만 남아 반쪽 색인이 된다
def add_with_retry(store, texts, metas, ids, tries: int = 5) -> None:
    for attempt in range(tries):
        try:
            store.add_texts(texts, metadatas=metas, ids=ids)
            return
        except Exception as e:
            if not any(t in str(e) for t in TRANSIENT) or attempt == tries - 1:
                raise
            wait = 65 * (attempt + 1)
            print(f"  실패. {wait}초 기다린다 ({attempt + 1}/{tries - 1}): {str(e)[:60]}", flush=True)
            time.sleep(wait)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="임베딩 없이 분할 결과만 본다")
    ap.add_argument("--limit", type=int, default=0, help="처리할 파일 수 상한")
    # 임베딩은 하루 한도가 있고, REBUILD 는 실패하면 처음부터다. 실제로 두 번 죽었다.
    # 이어서 넣으면 이미 값을 치른 조각을 다시 임베딩하지 않는다
    ap.add_argument("--resume", action="store_true", help="이미 들어간 조각은 건너뛴다")
    ap.add_argument("--batch", type=int, default=25)
    # 무료 등급은 분당 한도를 조각 수로 센다. 배치 50 두 번에 100 을 채우고 429 가 났다.
    # 요청 수가 아니라 조각 수라는 걸 모르면 배치만 줄이다가 계속 막힌다
    ap.add_argument("--rpm", type=int, default=90, help="분당 임베딩할 조각 수 상한")
    args = ap.parse_args()

    files = sorted(COURSES_DIR.rglob("*.md"))
    if not files:
        raise SystemExit(f"원본이 없다. build_corpus.py 를 먼저 돌린다: {COURSES_DIR}")
    if args.limit:
        files = files[: args.limit]

    texts, metas, ids = [], [], []
    for f in files:
        t, m, i = load_file(f)
        texts += t
        metas += m
        ids += i

    print(f"파일    : {len(files)}개")
    report(texts, metas)

    if args.dry_run:
        print("dry-run 이라 적재하지 않는다")
        return

    # 표시를 먼저 지워야, 다시 만드는 도중에 뜬 서버가 준비됐다고 하지 않는다
    INDEX_MARKER.unlink(missing_ok=True)
    if not args.resume and CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)

    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )
    if args.resume:
        have = set(store.get(include=[])["ids"])
        keep = [i for i, cid in enumerate(ids) if cid not in have]
        print(f"이어서: 이미 {len(have)}개, 넣을 것 {len(keep)}개")
        texts = [texts[i] for i in keep]
        metas = [metas[i] for i in keep]
        ids = [ids[i] for i in keep]
        if not texts:
            INDEX_MARKER.write_text(str(len(have)), encoding="utf-8")
            print(f"완료    : 더 넣을 것이 없다. 조각 {len(have)}")
            return

    pause = 60.0 * args.batch / args.rpm
    for start in range(0, len(texts), args.batch):
        end = min(start + args.batch, len(texts))
        add_with_retry(store, texts[start:end], metas[start:end], ids[start:end])
        print(f"  적재 {end}/{len(texts)}", flush=True)
        if end < len(texts):
            time.sleep(pause)

    # 마지막에 표시를 남긴다. 중간에 죽으면 표시가 없어서 /health 가 준비됐다고
    # 하지 않는다. 순서를 바꾸면 반쪽 색인이 준비된 것으로 보인다
    total = len(store.get(include=[])["ids"])
    INDEX_MARKER.write_text(str(total), encoding="utf-8")
    print(f"완료    : {CHROMA_DIR} · 조각 {total}")


if __name__ == "__main__":
    main()
