"""
docs/*.md 규정 파일을 조(제N조) 단위로 청킹해서 data/chunks.jsonl로 저장한다.

규칙:
- 파일 상단 YAML front matter(---)에서 doc_id, title, version, department, source를 읽는다.
- '#', '##' 헤더는 breadcrumb(제목 경로)로 누적하고, '###' 헤더가 나오면 새 청크를 시작한다.
  (### 보다 깊은 헤더가 없다는 전제. 필요하면 MAX_CHUNK_CHARS 초과 시 항 단위로 추가 분할한다.)
- 청크 텍스트 맨 앞에 breadcrumb를 붙여서, 짧은 조항도 검색 컨텍스트를 잃지 않게 한다.

사용법:
    python scripts/build_index.py
"""

import json
import re
from pathlib import Path

import yaml

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "chunks.jsonl"

MAX_CHUNK_CHARS = 1000  # 이보다 길면 항(1. 2. 3. ...) 단위로 추가 분할

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADER_RE = re.compile(r"^(#{1,3})\s+(.*)$")
SECTION_NO_RE = re.compile(r"^제\s*(\d+)\s*조")


def parse_front_matter(text):
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():]
    return meta, body


def split_long_chunk(text, max_chars):
    """항(숫자.) 단위로 텍스트를 나눈다. 못 나누면 원본 그대로 반환."""
    if len(text) <= max_chars:
        return [text]

    parts = re.split(r"\n(?=\d+\.\s)", text)
    if len(parts) <= 1:
        return [text]

    chunks = []
    buf = ""
    for part in parts:
        if buf and len(buf) + len(part) > max_chars:
            chunks.append(buf.strip())
            buf = part
        else:
            buf += ("\n" if buf else "") + part
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def chunk_document(path):
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)

    doc_id = str(meta.get("doc_id", path.stem))
    title = str(meta.get("title", path.stem))
    version = str(meta.get("version", ""))  # YAML이 날짜로 파싱해도 문자열로 통일
    department = str(meta.get("department", ""))
    source = str(meta.get("source", ""))

    breadcrumb = [title]  # breadcrumb[i] = (i+1)레벨 헤더의 텍스트
    current_section = None  # 가장 마지막에 만난 헤더 텍스트 (레벨 무관, 1~3 모두 포함)
    current_lines = []
    records = []
    seq = 0

    def flush():
        nonlocal seq, current_section, current_lines
        if current_section is None:
            return
        body_text = "\n".join(current_lines).strip()
        if not body_text:
            return
        path_str = " > ".join(breadcrumb)
        for piece in split_long_chunk(body_text, MAX_CHUNK_CHARS):
            seq += 1
            section_no_m = SECTION_NO_RE.match(current_section)
            records.append({
                "chunk_id": f"{doc_id}-{seq:03d}",
                "doc_id": doc_id,
                "title": title,
                "version": version,
                "department": department,
                "source": source,
                "section": current_section,
                "section_no": section_no_m.group(1) if section_no_m else None,
                "heading_path": path_str,
                "text": f"[{path_str}]\n{piece}",
                "char_count": len(piece),
            })

    for line in body.split("\n"):
        m = HEADER_RE.match(line.strip())
        if m:
            flush()
            level, heading = len(m.group(1)), m.group(2).strip()
            # 헤더가 나오면 레벨에 관계없이 그 헤더를 현재 섹션으로 삼는다.
            # 이렇게 해야 ##(레벨2) 헤더 바로 아래에 ### 없이 본문/표가 오는
            # 경우에도 그 내용이 청크로 살아남는다.
            idx = level - 1
            breadcrumb = breadcrumb[:idx] + [heading]
            current_section = heading
            current_lines = []
            continue
        if current_section is not None:
            current_lines.append(line)

    flush()
    return records


def main():
    if not DOCS_DIR.exists():
        raise SystemExit(f"docs 폴더를 찾을 수 없습니다: {DOCS_DIR}")

    md_files = sorted(DOCS_DIR.glob("*.md"))
    if not md_files:
        raise SystemExit(f"{DOCS_DIR} 안에 .md 파일이 없습니다.")

    all_records = []
    for path in md_files:
        records = chunk_document(path)
        print(f"  {path.name}: {len(records)}개 청크")
        all_records.extend(records)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n총 {len(all_records)}개 청크를 {OUT_PATH} 에 저장했습니다.")


if __name__ == "__main__":
    main()
