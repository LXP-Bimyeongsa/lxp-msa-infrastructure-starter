"""규정 전문을 프롬프트 주입용 단일 텍스트로 만들어 data/context.txt 에 저장한다.

조립 로직은 ai-service/app/regulations.py 에 있다. 서비스는 이 파일을 거치지 않고
기동 시 메모리에 직접 만든다. 이 스크립트는 사람이 주입 텍스트를 눈으로 확인하거나
countTokens로 토큰 수를 재기 위한 CLI다.

사용법:
    uv run python scripts/build_prompt_context.py
"""

from _shared import DATA_DIR, DOCS_DIR, ROOT

from app.regulations import load  # noqa: E402  (_shared 가 경로를 먼저 잡는다)

OUT_PATH = DATA_DIR / "context.txt"


def main() -> None:
    regs = load(DOCS_DIR)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(regs.context, encoding="utf-8")

    print(f"문서 {regs.doc_count}개 / 청크 {len(regs.chunks)}개")
    print(f"{OUT_PATH.relative_to(ROOT)} 저장 ({len(regs.context):,}자, "
          f"sha {regs.context_sha})")
    print("\n--- 앞부분 미리보기 ---")
    for line in regs.context.split("\n")[:14]:
        print(line)
    print("...")


if __name__ == "__main__":
    main()
