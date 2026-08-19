"""계획서 4단계 '무료 처리량 표'를 채운다. 생성 호출 없이 countTokens만 쓴다.

사용법:
    uv run python scripts/measure_tokens.py --list      # 쓸 수 있는 모델 ID 확인 (버전 핀 고정용)
    uv run python scripts/measure_tokens.py             # 토큰 실측
    uv run python scripts/measure_tokens.py --model gemini-2.5-flash

TPM/RPD는 계정마다 다르고 문서에 티어별 고정 수치가 공개돼 있지 않다.
AI Studio의 rate limit 페이지에서 본인 계정 값을 확인해 --tpm / --rpd 로 넣으면
분당/하루 처리 가능 요청 수까지 계산한다.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt import SYSTEM_INSTRUCTION, build_prompt, load_context  # noqa: E402

# gemini-2.5-* 는 신규 사용자에게 더 이상 제공되지 않는다(404). 3.x 계열을 쓴다.
# `-latest` 별칭은 뒤에서 모델이 바뀌어 회차 간 지표 비교가 무효가 되므로 쓰지 않는다.
#
# lite를 쓰는 이유는 무료 티어 RPD다. 3.6/3.5 Flash는 RPD 20이라 평가 60문항
# 한 회차에 3일이 걸려 튜닝 루프가 성립하지 않는다. lite는 RPD 500이라
# judge 채점까지 포함해도(120요청) 하루 안에 돈다.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
# 실측용 대표 질문. 평가셋에서 길이가 평균적인 것으로 골랐다.
SAMPLE_QUESTION = "면접 때문에 조퇴하면 출석 인정도 받고 조퇴 카운트도 안 되나요?"
# 응답 길이 가정. 실제 측정 전까지 쓰는 값이고, 8단계 이후 실측치로 바꾼다.
ASSUMED_OUTPUT_TOKENS = 400


def get_client():
    try:
        from google import genai
    except ImportError:
        raise SystemExit("google-genai가 없습니다. `uv add google-genai` 를 실행하세요.")

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit(
            "GEMINI_API_KEY가 없습니다. org-qa-chatbot/.env 에 아래 한 줄을 넣으세요.\n"
            "  GEMINI_API_KEY=<발급받은 키>"
        )
    return genai.Client(api_key=key)


def list_models(client):
    print("generateContent 지원 모델 (버전 접미사가 붙은 것을 골라 고정하세요):\n")
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if actions and "generateContent" not in actions:
            continue
        name = m.name.removeprefix("models/")
        limit = getattr(m, "input_token_limit", None)
        print(f"  {name:45s} in={limit:>9,}" if limit else f"  {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--list", action="store_true", help="사용 가능한 모델 ID 나열")
    ap.add_argument("--rpm", type=int, help="계정 실제 RPM (AI Studio rate limit 페이지 확인)")
    ap.add_argument("--tpm", type=int, help="계정 실제 TPM — '분당 최대 입력 토큰 수'라 입력분만 센다")
    ap.add_argument("--rpd", type=int, help="계정 실제 RPD")
    ap.add_argument("--question", default=SAMPLE_QUESTION)
    args = ap.parse_args()

    client = get_client()
    if args.list:
        list_models(client)
        return

    context = load_context()
    prompt = build_prompt(args.question, context)

    def count(text):
        return client.models.count_tokens(model=args.model, contents=text).total_tokens

    sys_tokens = count(SYSTEM_INSTRUCTION)
    ctx_tokens = count(context)
    q_tokens = count(args.question)
    prompt_tokens = count(prompt)
    input_total = sys_tokens + prompt_tokens
    per_request = input_total + ASSUMED_OUTPUT_TOKENS

    print(f"모델: {args.model}")
    print(f"질문: {args.question}\n")
    print(f"| {'항목':<34} | {'값':>12} |")
    print(f"| {'-' * 34} | {'-' * 12} |")
    print(f"| {'규정 전문 (context.txt)':<32} | {ctx_tokens:>12,} |")
    print(f"| {'시스템 지시':<33} | {sys_tokens:>12,} |")
    print(f"| {'사용자 질문 (예시 1건)':<31} | {q_tokens:>12,} |")
    print(f"| {'입력 합계':<34} | {input_total:>12,} |")
    print(f"| {f'응답 가정 ({ASSUMED_OUTPUT_TOKENS}토큰)':<32} | {ASSUMED_OUTPUT_TOKENS:>12,} |")
    print(f"| {'요청당 총 토큰':<32} | {per_request:>12,} |")

    if not (args.rpm or args.tpm or args.rpd):
        print("\n※ RPM/TPM/RPD는 계정·모델마다 다릅니다. AI Studio rate limit 페이지에서")
        print("   확인 후 --rpm / --tpm / --rpd 로 넣으면 처리량까지 계산합니다.")
        return

    print()
    # TPM은 '분당 최대 입력 토큰 수'다. 응답 토큰은 여기 안 들어가므로
    # per_request가 아니라 input_total로 나눈다.
    by_tpm = args.tpm // input_total if args.tpm else None
    if args.rpm:
        print(f"| {'계정 RPM':<35} | {args.rpm:>12,} |")
    if args.tpm:
        print(f"| {'계정 TPM (입력)':<33} | {args.tpm:>12,} |")
        print(f"| {'  TPM으로 가능한 분당 요청':<29} | {by_tpm:>12,} |")
    if args.rpd:
        print(f"| {'계정 RPD':<35} | {args.rpd:>12,} |")

    per_min = min(x for x in (args.rpm, by_tpm) if x is not None) if (args.rpm or by_tpm) else None
    if per_min is not None:
        binding = "RPM" if args.rpm == per_min else "TPM"
        print(f"| {'→ 분당 처리 가능 요청':<31} | {per_min:>12,} |  ← {binding} 제약")
    if args.rpd:
        print(f"| {'→ 하루 처리 가능 요청':<31} | {args.rpd:>12,} |  ← RPD 제약")

        # 평가 1회차를 무료 티어로 돌릴 수 있는지가 8단계 루프의 전제다.
        eval_n = 60
        print(f"\n평가 {eval_n}문항 1회차 기준:")
        if per_min:
            print(f"  - 소요 시간: 최소 {eval_n / per_min:.1f}분 (분당 {per_min}요청)")
        days = -(-eval_n // args.rpd)  # 올림
        verdict = "가능" if args.rpd >= eval_n else f"불가 — {days}일에 걸쳐야 함"
        print(f"  - 하루 한도 {args.rpd}요청 대비: {verdict}")
        if args.rpd >= eval_n:
            print(f"  - judge 채점까지 포함(요청 2배): "
                  f"{'가능' if args.rpd >= eval_n * 2 else '하루 한도 초과'}")


if __name__ == "__main__":
    main()
