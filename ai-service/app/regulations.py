"""규정 문서 로딩. docs/*.md -> 청크 -> 프롬프트에 주입할 단일 텍스트.

서비스가 이 코드를 소유하고 평가 스크립트가 같은 코드를 import한다. 복사본을
두면 평가와 운영의 청킹·조립이 갈라지고, 그 순간 평가 결과가 운영과 무관해진다.

청킹 규칙 (org-qa-chatbot/scripts/build_index.py 에서 옮겨왔다):
- 파일 상단 YAML front matter에서 doc_id, title, version, department, source를 읽는다
- '#', '##' 헤더는 breadcrumb으로 누적하고, 헤더를 만나면 새 청크를 시작한다
- 청크 텍스트 앞에 breadcrumb을 붙여 짧은 청크도 검색 문맥을 잃지 않게 한다
- MAX_CHUNK_CHARS를 넘으면 항(1. 2. 3. ...) 단위로 추가 분할한다

chunk_id는 {doc_id}-{문서 내 순번}이다. 문서 중간에 섹션을 하나 추가하면 뒤쪽
ID가 전부 밀리는데, 밀린 ID도 실존하는 ID라서 에러가 나지 않는다. 평가셋의
정답 키가 조용히 다른 곳을 가리키게 되므로, 규정을 고칠 때마다
org-qa-chatbot/scripts/check_eval_keys.py 를 돌려야 한다.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

MAX_CHUNK_CHARS = 1000  # 이보다 길면 항 단위로 추가 분할

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADER_RE = re.compile(r"^(#{1,3})\s+(.*)$")
SECTION_NO_RE = re.compile(r"^제\s*(\d+)\s*조")

CONTEXT_HEADER = """다음은 조직 규정 문서 전문이다.
각 항목은 [청크ID] 로 시작하며, 그 뒤에 문서 경로와 본문이 온다.
답변의 근거를 밝힐 때는 반드시 이 청크ID를 사용한다.
"""


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    return meta, text[m.end():]


def split_long_chunk(text: str, max_chars: int) -> list[str]:
    """항(숫자.) 단위로 텍스트를 나눈다. 못 나누면 원본 그대로 반환."""
    if len(text) <= max_chars:
        return [text]

    parts = re.split(r"\n(?=\d+\.\s)", text)
    if len(parts) <= 1:
        return [text]

    chunks: list[str] = []
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


def chunk_document(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)

    doc_id = str(meta.get("doc_id", path.stem))
    title = str(meta.get("title", path.stem))
    # YAML이 날짜로 파싱해도 문자열로 통일한다.
    version = str(meta.get("version", ""))
    department = str(meta.get("department", ""))
    source = str(meta.get("source", ""))

    breadcrumb = [title]
    current_section: str | None = None
    current_lines: list[str] = []
    records: list[dict] = []
    seq = 0

    def flush() -> None:
        nonlocal seq
        if current_section is None:
            return
        body_text = "\n".join(current_lines).strip()
        if not body_text:
            return
        path_str = " > ".join(breadcrumb)
        for piece in split_long_chunk(body_text, MAX_CHUNK_CHARS):
            seq += 1
            m = SECTION_NO_RE.match(current_section)
            records.append({
                "chunk_id": f"{doc_id}-{seq:03d}",
                "doc_id": doc_id,
                "title": title,
                "version": version,
                "department": department,
                "source": source,
                "section": current_section,
                "section_no": m.group(1) if m else None,
                "heading_path": path_str,
                "body": piece,
                # 하위 호환: chunks.jsonl을 읽던 코드가 기대하는 형태
                "text": f"[{path_str}]\n{piece}",
                "char_count": len(piece),
            })

    for line in body.split("\n"):
        m = HEADER_RE.match(line.strip())
        if m:
            flush()
            level, heading = len(m.group(1)), m.group(2).strip()
            # 헤더가 나오면 레벨에 관계없이 그 헤더를 현재 섹션으로 삼는다.
            # 이렇게 해야 ## 헤더 바로 아래에 ### 없이 본문/표가 오는 경우에도
            # 그 내용이 청크로 살아남는다.
            breadcrumb = breadcrumb[:level - 1] + [heading]
            current_section = heading
            current_lines = []
            continue
        if current_section is not None:
            current_lines.append(line)

    flush()
    return records


def chunk_all(docs_dir: Path) -> list[dict]:
    """파일명 순서로 청킹한다. 순서가 곧 캐싱 접두사라 바뀌면 안 된다."""
    records: list[dict] = []
    for path in sorted(docs_dir.glob("*.md")):
        records.extend(chunk_document(path))
    return records


def build_context(chunks: list[dict]) -> str:
    """청크 목록 -> 프롬프트에 통째로 주입할 단일 텍스트.

    각 청크 앞에 [chunk_id] 마커를 박아서 모델이 근거를 그 ID로 인용하게 하고,
    인용된 ID는 집합 조회만으로 실존 여부를 판정할 수 있게 한다.
    (평가셋의 answer_chunks와 바로 비교된다.)
    """
    parts = [CONTEXT_HEADER]

    # 문서 목록과 버전을 앞에 한 번 실어둔다. 개정 시점 확인용이고,
    # 모델이 "언제 기준 규정인지" 답할 수 있게 한다.
    docs_seen: dict[str, tuple[str, str]] = {}
    for c in chunks:
        docs_seen.setdefault(c["doc_id"], (c["title"], c["version"]))
    parts.append("## 수록 문서")
    for doc_id, (title, version) in docs_seen.items():
        parts.append(f"- {doc_id} · {title} (version: {version})")
    parts.append("")

    parts.append("## 규정 본문")
    for c in chunks:
        parts.append(f"\n[{c['chunk_id']}] {c['heading_path']}\n{c['body']}")

    return "\n".join(parts).strip() + "\n"


@dataclass(frozen=True)
class Regulations:
    """한 시점의 규정 스냅샷. 재로드(14번)는 이 객체를 통째로 교체한다."""

    chunks: list[dict]
    context: str
    chunk_ids: frozenset[str]
    # 규정 내용의 해시. 재로드 판단과 회차 형상 기록에 쓴다. mtime을 쓰면
    # 내용이 같은 touch에도 캐시 접두사가 무의미하게 무효화된다.
    context_sha: str = field(compare=False)

    @property
    def doc_count(self) -> int:
        return len({c["doc_id"] for c in self.chunks})


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load(docs_dir: Path | str) -> Regulations:
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"규정 문서 디렉터리가 없다: {docs_dir}")

    chunks = chunk_all(docs_dir)
    if not chunks:
        raise ValueError(f"{docs_dir} 안에서 청크를 만들 수 없었다 (.md 파일 확인)")

    context = build_context(chunks)
    return Regulations(
        chunks=chunks,
        context=context,
        chunk_ids=frozenset(c["chunk_id"] for c in chunks),
        context_sha=sha12(context),
    )
