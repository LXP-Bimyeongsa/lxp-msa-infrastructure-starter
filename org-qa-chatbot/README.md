# 조직 규정 QA 챗봇

사내 규정(인사, 복무, 경비처리, 보안 등)에 대해 직원이 자연어로 질문하면
근거 조항을 인용해 답변하는 RAG(Retrieval-Augmented Generation) 챗봇 프로젝트입니다.

## 폴더 구조

```
org-qa-chatbot/
├── docs/                   # 규정 원문 (Markdown, 조 단위로 정리)
│   ├── 01_인사규정.md
│   └── 03_경비처리규정.md
├── data/
│   ├── chunks.jsonl        # build_index.py 실행 결과 (전처리된 청크)
│   ├── eval_qa.jsonl       # 평가용 질문-정답 셋
│   └── synonyms.json       # 사내 용어 동의어 사전
├── scripts/
│   └── build_index.py      # docs/*.md -> data/chunks.jsonl 청킹 스크립트
├── .gitignore
└── README.md
```

## 진행 순서 (3. 데이터 준비 단계)

1. **원본 확보**: PDF/HWP 등 원본 규정을 확보한다.
2. **Markdown 변환**: `docs/` 아래에 규정별로 `.md` 파일을 만들고,
   조(제N조) 단위로 `###` 헤더를 사용해 옮겨 적는다. 표는 Markdown 표로 옮긴다.
3. **메타데이터 작성**: 각 파일 상단에 YAML front matter로
   `doc_id`, `version`, `department`, `source`를 기록한다.
4. **동의어 사전 보강**: 직원들이 실제로 쓰는 표현(예: "연차" ↔ "연차유급휴가")을
   `data/synonyms.json`에 추가한다.
5. **평가 질문셋 작성**: `data/eval_qa.jsonl`에 실제로 나올 법한 질문 20~30개와
   근거 조항, "규정에 없는 질문" 몇 개를 함께 넣는다.
6. **청킹 실행**: `python scripts/build_index.py` 실행 → `data/chunks.jsonl` 생성 확인.
7. 이후 단계(임베딩/인덱싱/검색/응답 생성)는 사용할 프레임워크(LangChain,
   LlamaIndex, 직접 구현 등)를 정한 뒤 이어서 진행한다.

## 문서 작성 규칙

- 조(제N조) = `###` 헤더 하나. 조가 1000자를 넘으면 항 단위로 더 쪼갠다.
- 짧은 조(2~3줄)는 검색이 잘 안 될 수 있으니, 필요하면 헤더 경로를
  청크 앞에 붙인다 (예: "인사규정 > 제3장 휴가 > 제12조").
- 표/서식은 이미지로 캡처하지 말고 반드시 Markdown 표로 옮긴다.
- 개정 시 파일 상단 front matter의 `version`을 갱신하고 Git 커밋으로 이력을 남긴다.

## 실행 방법

```bash
pip install pyyaml
python scripts/build_index.py
```
