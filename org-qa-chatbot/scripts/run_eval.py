"""평가셋을 돌려 지표를 찍고 회차별 결과를 eval_results/run_NNN.json 에 남긴다.

계획서 7번. 지표를 한 번에 같이 찍는 이유는, "근거를 반드시 인용하라"는 제약이
정답률과 트레이드오프가 나기 때문이다. 출처·회피만 보고 튜닝한 뒤 마지막에
정답률을 재면, 튜닝이 정답률을 깎았어도 어느 수정 때문인지 알 수 없다.

집계 지표만 남기면 회귀를 못 잡는다(3개 고치고 3개 깨져도 동률). 그래서
문항 단위 결과를 저장하고, 직전 회차와 비교해 pass -> fail 로 바뀐 문항을 따로 찍는다.

사용법:
    uv run python scripts/run_eval.py                 # 전체
    uv run python scripts/run_eval.py --limit 10      # 앞 10문항만
    uv run python scripts/run_eval.py --judge         # 정답률(judge)까지
    uv run python scripts/run_eval.py --tag "회피 문구 완화"
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt import SYSTEM_INSTRUCTION, build_prompt, load_context, split_answer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = ROOT / "data" / "chunks.jsonl"
RESULTS_DIR = ROOT / "eval_results"

DEFAULT_MODEL = "gemini-3.5-flash-lite"
# 무료 티어 실측: RPM 15 / TPM 250,000. 요청당 입력이 약 17k라 TPM 쪽이 먼저 걸려
# 분당 14요청이 상한이다. 여유를 두고 13으로 잡는다.
DEFAULT_RPM = 13
MAX_RETRIES = 3
# flash-lite는 0을 거부하므로 허용 최소값. 자세한 이유는 gen_config() 주석 참고.
THINKING_BUDGET = 1

ANSWERABLE_TYPES = {"normal", "multi_hop", "conflict"}

# 규정에 없는 질문에서 "없다"고 밝혔는지 판정하는 표현들.
#
# 인용 유무로 판정하면 안 된다. unanswerable 문항의 gold를 보면 대부분이 단순
# 거부가 아니라 "지어내지 말고 ~로 안내해야 함"을 정답 행동으로 적어놨다.
# (E029 그룹웨어 확인 / E041 슬랙 채널 / E058 운영진 문의 / E060 장려금과 구분)
# 관련 제도를 짚어주려면 그 근거를 인용하게 되므로, 인용했다는 이유로 환각으로
# 세면 정답 행동이 실패로 찍힌다.
#
# 실제로 막아야 할 것은 "규정에 없는 내용을 있는 것처럼 단정하는 것"이므로
# 부재를 명시했는지로 판정한다.
# 부재를 밝히는 표현은 어미 변화가 많아서 문자열 목록만으로는 새는 게 생긴다.
# ("기재되어 있지 않습니다"를 놓쳐 정답 행동을 환각으로 잘못 센 적이 있다.)
# 그래서 '규정/문서/내용' 류 명사 뒤 일정 거리 안에 부정 표현이 오는 패턴으로 잡고,
# 목록은 그 패턴에 안 걸리는 관용 표현만 남긴다.
DENIAL_RE = re.compile(
    r"(규정|문서|자료|지침|안내|기준|항목|내용|정보|사항)"
    r"[^.!?\n]{0,60}?"
    r"(없습니다|없음|없으며|없고|있지\s*않|되지\s*않|되어\s*있지\s*않)"
)
DENIAL_MARKERS = (
    "확인할 수 없", "찾을 수 없", "확인되지 않", "알 수 없",
    "규정하고 있지 않", "다루고 있지 않", "나와 있지 않",
)


def states_absence(body: str) -> bool:
    return bool(DENIAL_RE.search(body)) or any(m in body for m in DENIAL_MARKERS)

# 정답 키(answer_chunks)는 '반드시 포함해야 할 최소 근거'다. 그래서 pass 판정은
# 누락(recall)만 본다. 초과 인용은 실패로 세지 않고 따로 관측만 한다.
# 초과분이 대개 정당한 관련 근거이기 때문이다.
# (E001은 지각 기준·점심시간 FAQ, E018은 conflict 짝인 FAQ와 법령 근거를 더 인용했다.)
# 다만 남발은 봐야 하므로 이 값을 넘으면 따로 센다.
OVER_CITE_WATCH = 3

JUDGE_PROMPT = """다음은 조직 규정 QA 챗봇의 답변을 채점하는 작업이다.

[질문]
{question}

[정답 요지]
{gold}

[챗봇 답변]
{answer}

챗봇 답변이 정답 요지와 사실관계가 일치하는지 판정하라.
표현이 달라도 내용이 맞으면 통과다. 정답 요지에 없는 내용을 덧붙였더라도
그것이 틀리지 않았다면 통과로 본다. 수치·기준·조건이 틀렸으면 실패다.

첫 줄에 PASS 또는 FAIL 만 쓰고, 둘째 줄에 한 문장으로 이유를 쓴다.
"""


def get_client():
    from google import genai
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY가 없습니다. org-qa-chatbot/.env 를 확인하세요.")
    return genai.Client(api_key=key)


def gen_config(system_instruction=None):
    from google.genai import types

    return types.GenerateContentConfig(
        temperature=0,
        # 규정 조회는 추론 난이도가 낮으므로 thinking을 최소로 둔다. 응답 토큰과
        # 첫 토큰 지연이 줄어든다. 정답률이 목표에 못 미치면 이 값만 올려 한 회차
        # 더 돌려서 개선폭을 따로 확인한다.
        #
        # flash-lite는 thinking_budget=0을 거부한다(400 INVALID_ARGUMENT).
        # 허용되는 최소값이 1이고, 이 값이면 사고 토큰이 실제로 잡히지 않는다.
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
        system_instruction=system_instruction,
    )


def generate(client, model, contents, system_instruction=None):
    """429는 지수 백오프로 재시도한다(계획서 12번). 끝내 실패하면 None."""
    from google.genai import errors

    delay = 2.0
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model, contents=contents, config=gen_config(system_instruction)
            )
            return (resp.text or "").strip()
        except errors.ClientError as e:
            if getattr(e, "code", None) != 429 or attempt == MAX_RETRIES:
                print(f"    [실패] {str(e)[:140]}")
                return None
            print(f"    [429] {delay:.0f}초 후 재시도 ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(delay)
            delay *= 2
    return None


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def git_sha():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def provenance(model, context):
    """이 회차가 '무엇으로' 만들어졌는지. 없으면 지표를 나중에 해석할 수 없다.

    tag는 사람이 손으로 쓰는 메모라 신뢰할 수 없다. 프롬프트 해시가 있으면 회차
    비교에서 "프롬프트가 같으므로 이 차이는 노이즈"를 자동으로 판정할 수 있다.
    temperature=0도 완전 결정적이지 않아서 이 구분이 실제로 필요하다.
    """
    return {
        "model": model,
        "temperature": 0,
        "thinking_budget": THINKING_BUDGET,
        "prompt_sha": sha(SYSTEM_INSTRUCTION),
        "context_sha": sha(context),
        "git_sha": git_sha(),
        "system_instruction": SYSTEM_INSTRUCTION,
    }


def load_chunk_ids():
    if not CHUNKS_PATH.exists():
        raise SystemExit("chunks.jsonl이 없습니다. build_index.py를 먼저 실행하세요.")
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        return {json.loads(line)["chunk_id"] for line in f if line.strip()}


def score_item(item, raw_answer, chunk_ids):
    """문항 하나를 채점한다. 판정은 전부 pass/fail 로 떨어뜨린다."""
    cited, refs, body = split_answer(raw_answer)
    truth = set(item["answer_chunks"])
    cited_set = set(cited)
    qtype = item["type"]

    r = {
        "id": item["id"],
        "type": qtype,
        "q": item["q"],
        "cited": cited,
        "refs": refs,
        "truth": sorted(truth),
        "answer": raw_answer,
        "body": body,
    }

    # 형식 준수: 첫 줄이 `근거:` 로 시작했는가.
    r["format_ok"] = raw_answer.lstrip().startswith("근거:")

    # 청크ID 실존: 인용한 ID가 실제 규정에 있는가. 11번 런타임 가드와 같은 판정.
    # 참고로 단 것도 사용자에게 보이므로 같이 검증한다.
    ghost = [c for c in cited + refs if c not in chunk_ids]
    r["ghost_ids"] = ghost
    r["exists_ok"] = not ghost

    if qtype == "unanswerable":
        # 환각 판정은 두 조건을 같이 본다.
        #  - 본문에서 부재를 밝혔는가
        #  - 질문에 직접 답하는 근거가 있다고 주장하지 않았는가(`근거:`가 비었는가)
        # 관련 제도는 `참고:`로 안내할 수 있게 됐으므로, 규정에 없는 질문에
        # `근거:`를 채우는 것은 "규정에 있다"는 주장이 된다.
        r["denial_stated"] = states_absence(body)
        r["direct_claim"] = bool(cited_set)
        r["guided"] = bool(refs)  # 부재를 밝히면서 관련 대목까지 짚었는가
        r["hallucinated"] = not r["denial_stated"] or r["direct_claim"]
        r["pass"] = not r["hallucinated"] and r["exists_ok"]
    else:
        # 부당 회피: 답할 수 있는데 모른다고 했는가.
        r["evaded"] = not cited_set
        # 출처 일치는 누락(recall)만 본다. 정답 키가 최소 근거라서
        # 초과 인용은 대개 정당한 관련 근거다. 따로 관측만 한다.
        extra = cited_set - truth
        r["extra_chunks"] = sorted(extra)
        r["over_cited"] = len(extra)
        # 누락은 `근거`와 `참고`를 합쳐서 본다. 근거를 실제로 짚었는지가 요점이고,
        # 어느 칸에 넣었는지는 아니다. conflict 문항에서 모델이 한쪽 문서를 주 근거로,
        # 상대 문서를 참고로 나눠 적었는데(E054·E055) 답변 자체는 양쪽 값과 출처를
        # 모두 제시한 정답 행동이었다. 칸 배치를 이유로 누락으로 세면 오판이다.
        # 다만 배치 자체는 관측해야 하므로 따로 기록한다.
        surfaced = cited_set | set(refs)
        r["truth_in_refs"] = sorted(truth & set(refs) - cited_set)
        r["missing_chunks"] = sorted(truth - surfaced)
        r["source_ok"] = truth.issubset(surfaced)
        r["pass"] = r["source_ok"] and r["exists_ok"] and not r["evaded"]

    return r


def blank_result(item):
    """응답 자체를 못 받은 문항. 통과로 세면 안 되므로 전부 실패로 둔다."""
    return {
        "id": item["id"], "type": item["type"], "q": item["q"],
        "cited": [], "truth": sorted(item["answer_chunks"]),
        "answer": "", "body": "", "format_ok": False,
        "ghost_ids": [], "exists_ok": False, "pass": False, "error": True, "refs": [],
        **({"hallucinated": True, "denial_stated": False,
            "direct_claim": False, "guided": False}
           if item["type"] == "unanswerable"
           else {"evaded": True, "source_ok": False, "over_cited": 0,
                 "missing_chunks": sorted(item["answer_chunks"]),
                 "extra_chunks": [], "truth_in_refs": []}),
    }


def aggregate(results):
    ans = [r for r in results if r["type"] in ANSWERABLE_TYPES]
    una = [r for r in results if r["type"] == "unanswerable"]

    return {
        "문항 수": len(results),
        "응답 실패": sum(1 for r in results if r.get("error")),
        "형식 위반": sum(1 for r in results if not r["format_ok"]),
        "인용 청크 총계": sum(len(r["cited"]) for r in results),
        "실존하지 않는 청크ID": sum(len(r["ghost_ids"]) for r in results),
        "근거 누락": sum(1 for r in ans if not r["source_ok"]),
        "부당 회피": sum(1 for r in ans if r["evaded"]),
        "답변가능 분모": len(ans),
        "환각": sum(1 for r in una if r["hallucinated"]),
        "규정외 분모": len(una),
        # 아래 둘은 실패가 아니라 관측치다.
        "과잉 인용 총계": sum(r.get("over_cited", 0) for r in ans),
        f"과잉 {OVER_CITE_WATCH}개 초과 문항": sum(
            1 for r in ans if r.get("over_cited", 0) > OVER_CITE_WATCH),
        "부재 명시 + 관련 안내": sum(1 for r in una if r.get("guided") and not r["hallucinated"]),
        "정답 근거를 참고로 배치": sum(1 for r in ans if r.get("truth_in_refs")),
    }


def next_run_path():
    RESULTS_DIR.mkdir(exist_ok=True)
    existing = sorted(RESULTS_DIR.glob("run_*.json"))
    nums = []
    for p in existing:
        m = re.match(r"run_(\d+)\.json$", p.name)
        if m:
            nums.append(int(m.group(1)))
    n = max(nums) + 1 if nums else 1
    return RESULTS_DIR / f"run_{n:03d}.json", n, (existing[-1] if existing else None)


def print_regressions(results, prev_path, prov=None):
    """직전 회차 대비 pass -> fail 로 바뀐 문항. 집계만 보면 안 보이는 것."""
    if not prev_path:
        return
    prev = json.loads(prev_path.read_text(encoding="utf-8"))
    prev_pass = {r["id"]: r["pass"] for r in prev["items"]}
    regressed = [r["id"] for r in results
                 if prev_pass.get(r["id"]) is True and not r["pass"]]
    fixed = [r["id"] for r in results
             if prev_pass.get(r["id"]) is False and r["pass"]]

    print(f"\n직전 회차({prev_path.name}) 대비")
    print(f"  고쳐짐: {len(fixed)}건 {fixed if fixed else ''}")
    print(f"  깨짐  : {len(regressed)}건 {regressed if regressed else ''}")
    if regressed:
        print("  ※ 집계가 좋아졌어도 깨진 문항이 있으면 그 수정은 재검토 대상이다.")

    # 프롬프트가 그대로인데 판정이 바뀌었다면 모델 비결정성이다. 개선/악화로 읽으면 안 된다.
    prev_prov = prev.get("provenance") or {}
    if prov and prev_prov.get("prompt_sha") == prov["prompt_sha"] and (fixed or regressed):
        print("  ※ 프롬프트 해시가 직전 회차와 같다. 위 변화는 모델 비결정성으로 봐야 한다.")
    if prev_prov.get("context_sha") and prev_prov["context_sha"] != (prov or {}).get("context_sha"):
        print("  ※ 규정 전문이 바뀌었다(context_sha 불일치). 프롬프트 효과와 섞여 있다.")


def report(results, agg, judge=False):
    """집계표 출력. 실행 경로와 재채점 경로가 같은 표를 쓴다."""
    print("\n" + "=" * 46)
    print(f"{'지표':<20}{'실패':>8}{'분모':>8}")
    print("-" * 46)
    rows = [
        ("형식 위반", agg["형식 위반"], agg["문항 수"]),
        ("없는 청크ID", agg["실존하지 않는 청크ID"], agg["인용 청크 총계"]),
        ("근거 누락", agg["근거 누락"], agg["답변가능 분모"]),
        ("부당 회피", agg["부당 회피"], agg["답변가능 분모"]),
        ("환각", agg["환각"], agg["규정외 분모"]),
    ]
    if judge:
        judged = [r for r in results if "judge_pass" in r]
        rows.append(("정답률 실패",
                     len(judged) - sum(1 for r in judged if r["judge_pass"]), len(judged)))
    for name, fail, denom in rows:
        pad = 20 - (len(name) - len(name.encode("ascii", "ignore").decode()))
        print(f"{name:<{pad}}{fail:>8}{denom:>8}")
    print("=" * 46)
    print(f"관측: 과잉 인용 {agg['과잉 인용 총계']}개"
          f" ({OVER_CITE_WATCH}개 초과 문항 {agg[f'과잉 {OVER_CITE_WATCH}개 초과 문항']}건)"
          f" · 부재 명시 + 관련 안내 {agg['부재 명시 + 관련 안내']}/{agg['규정외 분모']}"
          f" · 정답 근거를 참고로 배치 {agg['정답 근거를 참고로 배치']}건")


def rescore(path, tag):
    """저장된 응답을 새 채점 기준으로 다시 채점한다. API 호출 없음."""
    if not path.exists():
        raise SystemExit(f"파일이 없습니다: {path}")
    prev = json.loads(path.read_text(encoding="utf-8"))
    chunk_ids = load_chunk_ids()

    eval_items = {json.loads(l)["id"]: json.loads(l)
                  for l in (ROOT / prev["eval_file"]).open(encoding="utf-8") if l.strip()}

    results = []
    for old in prev["items"]:
        item = eval_items[old["id"]]
        if old.get("error"):
            results.append(blank_result(item))
            continue
        r = score_item(item, old["answer"], chunk_ids)
        for k in ("judge_pass", "judge_reason"):
            if k in old:
                r[k] = old[k]
        results.append(r)

    old_pass = {r["id"]: r["pass"] for r in prev["items"]}
    changed = [(r["id"], old_pass[r["id"]], r["pass"])
               for r in results if old_pass.get(r["id"]) != r["pass"]]

    print(f"재채점: {path.name} (모델 {prev['model']}, {len(results)}문항) — API 호출 없음")
    old_prov = prev.get("provenance") or {}
    if old_prov:
        print(f"원본 프롬프트 {old_prov.get('prompt_sha', '-')}"
              f" · 규정 {old_prov.get('context_sha', '-')}"
              f" · git {old_prov.get('git_sha') or '-'}")
    if tag:
        print(f"태그: {tag}")
    agg = aggregate(results)
    report(results, agg, prev.get("judge", False))

    print(f"\n기준 변경으로 판정이 바뀐 문항: {len(changed)}건")
    for eid, was, now in changed:
        print(f"  {eid}: {'통과' if was else '실패'} -> {'통과' if now else '실패'}")

    out_path, n, _ = next_run_path()
    out_path.write_text(json.dumps({
        "run": n, "model": prev["model"], "eval_file": prev["eval_file"],
        "tag": tag or f"rescore of {path.name}", "judge": prev.get("judge", False),
        # 응답은 원본 회차의 것이므로 생성 조건도 원본을 그대로 물려준다.
        # 재채점으로 바뀐 것은 채점 기준(현재 코드)뿐이다.
        "provenance": old_prov, "scored_by_git_sha": git_sha(),
        "rescored_from": path.name, "summary": agg, "items": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out_path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--eval-file", default="data/eval_qa.jsonl")
    ap.add_argument("--limit", type=int, help="앞에서 N문항만")
    # --limit은 앞에서부터 자르므로 앞쪽에 몰린 normal만 뽑힌다. 유형을 고루
    # 보려면 --ids로 직접 고른다. (예: 스모크 확인용 10문항 세트)
    ap.add_argument("--ids", help="쉼표로 구분한 문항 id만 (예: E001,E050,E054)")
    ap.add_argument("--rpm", type=int, default=DEFAULT_RPM, help="분당 요청 상한")
    ap.add_argument("--judge", action="store_true", help="정답률까지 채점 (요청 2배)")
    ap.add_argument("--tag", default="", help="이 회차에서 무엇을 바꿨는지 (기록용)")
    # 채점 기준만 바꿨을 때 쓴다. 저장된 응답을 그대로 다시 채점하므로 API를 부르지
    # 않는다. 재생성하면 응답이 함께 달라져서 기준 변경의 효과만 따로 볼 수 없다.
    ap.add_argument("--rescore", help="저장된 run_NNN.json을 새 기준으로 재채점")
    args = ap.parse_args()

    if args.rescore:
        rescore(Path(args.rescore), args.tag)
        return

    eval_path = ROOT / args.eval_file
    if not eval_path.exists():
        raise SystemExit(f"평가셋이 없습니다: {eval_path}")

    items = [json.loads(l) for l in eval_path.open(encoding="utf-8") if l.strip()]
    if args.ids:
        want = [s.strip() for s in args.ids.split(",") if s.strip()]
        by_id = {it["id"]: it for it in items}
        unknown = [w for w in want if w not in by_id]
        if unknown:
            raise SystemExit(f"평가셋에 없는 id: {unknown}")
        items = [by_id[w] for w in want]
    if args.limit:
        items = items[:args.limit]

    chunk_ids = load_chunk_ids()
    context = load_context()
    client = get_client()
    interval = 60.0 / args.rpm
    est = len(items) * interval / 60 * (2 if args.judge else 1)

    prov = provenance(args.model, context)
    print(f"모델 {args.model} · {len(items)}문항 · 분당 {args.rpm}요청 (예상 {est:.1f}분)")
    print(f"프롬프트 {prov['prompt_sha']} · 규정 {prov['context_sha']}"
          f" · git {prov['git_sha'] or '-'} · thinking {prov['thinking_budget']}")
    if args.tag:
        print(f"태그: {args.tag}")
    print()

    results = []
    for i, item in enumerate(items, 1):
        raw = generate(client, args.model, build_prompt(item["q"], context), SYSTEM_INSTRUCTION)
        if raw is None:
            print(f"  {i:>3}/{len(items)} {item['id']} [{item['type']:<12}] -  응답 없음")
            results.append(blank_result(item))
            time.sleep(interval)
            continue

        r = score_item(item, raw, chunk_ids)

        if args.judge and r["type"] in ANSWERABLE_TYPES:
            time.sleep(interval)
            verdict = generate(client, args.model, JUDGE_PROMPT.format(
                question=item["q"], gold=item["gold"], answer=r["body"]))
            r["judge_pass"] = bool(verdict) and verdict.lstrip().upper().startswith("PASS")
            r["judge_reason"] = (verdict or "").strip()

        results.append(r)

        detail = ""
        if not r["pass"]:
            if r.get("hallucinated"):
                detail = "환각 (규정에 없다고 밝히지 않음)"
            elif r.get("evaded"):
                detail = "부당 회피"
            elif r["ghost_ids"]:
                detail = f"없는 청크ID {r['ghost_ids']}"
            elif r.get("missing_chunks"):
                detail = f"근거 누락 {r['missing_chunks']}"
        elif r.get("over_cited"):
            detail = f"(과잉 {r['over_cited']}개)"
        elif r.get("guided"):
            detail = "(부재 명시 + 관련 안내)"
        if not r["format_ok"]:
            detail = (detail + " / 형식 위반").lstrip(" /")
        print(f"  {i:>3}/{len(items)} {item['id']} [{r['type']:<12}] "
              f"{'O' if r['pass'] else 'X'}  {detail}")

        if i < len(items):
            time.sleep(interval)

    # ── 집계 ──────────────────────────────────────────────
    agg = aggregate(results)
    if args.judge:
        judged = [r for r in results if "judge_pass" in r]
        agg["정답률 통과"] = sum(1 for r in judged if r["judge_pass"])
        agg["정답률 분모"] = len(judged)
    report(results, agg, args.judge)

    if agg["응답 실패"]:
        print(f"※ 응답을 못 받은 문항 {agg['응답 실패']}건은 전부 실패로 셌다.")
    by_type = Counter(r["type"] for r in results if not r["pass"])
    if by_type:
        print("실패 문항 유형별:", dict(by_type))

    out_path, n, prev_path = next_run_path()
    out_path.write_text(json.dumps({
        "run": n,
        "model": args.model,
        "eval_file": args.eval_file,
        "tag": args.tag,
        "judge": args.judge,
        "provenance": prov,
        "summary": agg,
        "items": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print_regressions(results, prev_path, prov)
    print(f"\n저장: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
