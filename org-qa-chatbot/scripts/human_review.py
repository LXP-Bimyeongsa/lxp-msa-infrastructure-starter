"""judge를 사람 채점과 대조하기 위한 파일을 만들고, 채운 파일을 비교한다.

judge 프롬프트를 고쳐도 그 judge가 맞는지는 알 수 없다. 확인하는 방법은
사람 채점과 대조하는 것뿐이다. 이걸 하지 않으면 "judge 점수는 올랐는데 실제
품질은 나빠짐"을 영원히 잡을 수 없다.

채점 파일에는 judge 판정을 넣지 않는다. 보이면 사람이 거기에 끌려가고(앵커링),
그러면 대조의 의미가 없어진다.

사용법:
    uv run python scripts/human_review.py make eval_results/run_014.json
    # -> eval_results/human_review.md 생성. 각 문항의 `판정:` 뒤에 PASS/FAIL 기입

    uv run python scripts/human_review.py compare eval_results/run_014.json
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "eval_results"
REVIEW_PATH = RESULTS_DIR / "human_review.md"

ANSWERABLE_TYPES = {"normal", "multi_hop", "conflict"}
DEFAULT_N = 20


def load_run(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pick_sample(items, n):
    """judge가 FAIL을 낸 문항은 전부 넣고, 나머지는 고르게 훑어 채운다.

    FAIL을 전부 넣는 것은 의도적이다. judge의 오판은 FAIL 쪽에서 나오기 쉽고
    (실제로 E001이 그랬다), 그걸 놓치면 대조의 목적을 잃는다. 대신 표본이 FAIL을
    과대표집하므로, 여기서 나온 일치율은 실제보다 낮게 잡힌 보수적인 값이다.

    무작위 대신 일정 간격으로 뽑는다. 같은 회차에 대해 항상 같은 표본이 나와야
    사람 채점을 나중에 다시 대조할 수 있다.
    """
    ans = [r for r in items if r["type"] in ANSWERABLE_TYPES and "judge_pass" in r]
    fails = [r for r in ans if not r["judge_pass"]]
    passes = [r for r in ans if r["judge_pass"]]

    room = max(0, n - len(fails))
    if room >= len(passes):
        picked = passes
    else:
        step = len(passes) / room
        picked = [passes[int(i * step)] for i in range(room)]

    chosen = fails + picked
    order = {r["id"]: i for i, r in enumerate(ans)}
    return sorted(chosen, key=lambda r: order[r["id"]])


def make(run_path, n):
    run = load_run(run_path)
    eval_items = {json.loads(l)["id"]: json.loads(l)
                  for l in (ROOT / run["eval_file"]).open(encoding="utf-8") if l.strip()}
    sample = pick_sample(run["items"], n)

    out = [
        "# judge 대조용 사람 채점",
        "",
        f"- 대상 회차: `{Path(run_path).name}` (모델 {run['model']})",
        f"- 문항 수: {len(sample)}",
        "",
        "## 채점 방법",
        "",
        "각 문항의 `판정:` 뒤에 `PASS` 또는 `FAIL`을 적으세요. 기준은 두 개입니다.",
        "",
        "1. **정답 요지의 사실이 답변에 다 있는가** — 표현이 달라도 내용이 같으면 있는 것.",
        "   단, 수치·기준·조건은 값이 같아야 함",
        "2. **정답 요지와 어긋나는 서술이 있는가** — 정답 요지에 없는 내용을 덧붙인 것은",
        "   문제가 아닙니다. 같은 사항을 다르게 말한 경우만 어긋남입니다",
        "",
        "둘 다 만족하면 PASS입니다. judge 판정은 일부러 적지 않았습니다 — 보고 나서",
        "채점하면 그쪽에 끌려가서 대조의 의미가 없어집니다.",
        "",
        "다 채우면: `uv run python scripts/human_review.py compare "
        f"{Path(run_path).as_posix().split('org-qa-chatbot/')[-1]}`",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(sample, 1):
        gold = eval_items[r["id"]]["gold"]
        out += [
            f"## {i}. {r['id']} · {r['type']}",
            "",
            f"**질문** {r['q']}",
            "",
            f"**정답 요지** {gold}",
            "",
            "**챗봇 답변**",
            "",
            "```",
            r["body"].strip() or "(빈 응답)",
            "```",
            "",
            "판정: ",
            "",
            "---",
            "",
        ]

    RESULTS_DIR.mkdir(exist_ok=True)
    REVIEW_PATH.write_text("\n".join(out), encoding="utf-8")
    n_fail = sum(1 for r in sample if not r["judge_pass"])
    print(f"{len(sample)}문항 -> {REVIEW_PATH.relative_to(ROOT)}")
    print(f"  (judge가 FAIL을 낸 {n_fail}건을 모두 포함했습니다. "
          f"판정은 파일에 적지 않았습니다.)")


def parse_filled():
    if not REVIEW_PATH.exists():
        raise SystemExit(f"{REVIEW_PATH} 가 없습니다. 먼저 make 를 실행하세요.")
    text = REVIEW_PATH.read_text(encoding="utf-8")
    # "## 1. E001 · normal" ... "판정: PASS" 쌍을 순서대로 짝짓는다.
    blocks = re.split(r"^##\s+\d+\.\s+", text, flags=re.MULTILINE)[1:]
    out = {}
    for b in blocks:
        eid = b.split()[0].strip()
        m = re.search(r"^판정\s*[:：]\s*(\S+)?", b, re.MULTILINE)
        val = (m.group(1) or "").strip().upper() if m else ""
        if val in ("PASS", "FAIL"):
            out[eid] = val == "PASS"
        else:
            out[eid] = None
    return out


def compare(run_path):
    run = load_run(run_path)
    judge = {r["id"]: r["judge_pass"] for r in run["items"] if "judge_pass" in r}
    human = parse_filled()

    blank = [k for k, v in human.items() if v is None]
    scored = {k: v for k, v in human.items() if v is not None}

    if blank:
        print(f"아직 안 적은 문항 {len(blank)}건: {', '.join(blank)}\n")
    if not scored:
        raise SystemExit("채점된 문항이 없습니다.")

    agree = [k for k, v in scored.items() if judge.get(k) == v]
    disagree = [(k, judge.get(k), v) for k, v in scored.items() if judge.get(k) != v]

    print(f"대조 결과: {len(agree)}/{len(scored)} 일치 ({len(agree) / len(scored) * 100:.0f}%)")
    if disagree:
        print("\n어긋난 문항 (judge -> 사람):")
        for eid, j, h in disagree:
            kind = "judge가 잘못 통과시킴" if j else "judge가 잘못 실패시킴"
            print(f"  {eid}: {'PASS' if j else 'FAIL'} -> {'PASS' if h else 'FAIL'}  ({kind})")

    rate = len(agree) / len(scored)
    print()
    if rate >= 0.9:
        print("판정: judge를 신뢰할 수 있습니다. 정답률을 종료 조건에 쓸 수 있습니다.")
    elif rate >= 0.75:
        print("판정: judge 프롬프트를 더 손봐야 합니다. 위 어긋난 문항이 수정 단서입니다.")
    else:
        print("판정: judge를 이 상태로 쓰면 안 됩니다. 정답률은 사람이 재거나 지표에서 빼세요.")
    print("※ 표본에 judge FAIL을 모두 넣었으므로 이 일치율은 보수적(실제보다 낮게)입니다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["make", "compare"])
    ap.add_argument("run", help="대상 run_NNN.json")
    ap.add_argument("-n", type=int, default=DEFAULT_N, help=f"표본 수 (기본 {DEFAULT_N})")
    args = ap.parse_args()

    path = Path(args.run)
    if not path.is_absolute():
        path = ROOT / args.run
    if args.mode == "make":
        make(path, args.n)
    else:
        compare(path)


if __name__ == "__main__":
    main()
