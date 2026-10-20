# core-library 스키마 규약 (정본)

이 문서가 core-library의 파일 구조·필드·상태 어휘의 정본이다. README·catalog.yml과 어긋나면 이 문서가 우선한다.

## 0. 성격 — 선택적 로컬 데이터층

- core-library는 **핵심 1차 사료의 소재·판본·파일 상태**를 등록하는 사료 등록부다. 검색 위계의 0차(등록부 표제 조회)에 해당한다.
- **선택층이다.** 없어도 하네스는 돌아간다. 데이터층이 없으면 0차 조회는 조용히 0건이며, 등록부 선조회 절차는 건너뛴다(`references/local-data-layer.md`).
- **git에는 이 규약(`SCHEMA.md`)만 올린다.** `catalog.yml`·각 `source.yml`·텍스트층·PDF 등 데이터는 로컬 전용이다. 사료 원본은 저작권·용량 문제가 있으므로 공개 저장소에 올리지 않는다(저장소의 `.gitignore`로 제외).
- `corpus/registry.md`와 나눠 맡는다. registry = 사료의 *정체성·편향*(서지·권위 정본·전승·성격), core-library = 실물 파일의 *소재·판본 계보·검색층 상태*. registry 항목의 「core-library source_id」 칸이 둘을 잇는다.
- 발췌·인용 정박은 여전히 발췌 카드(P-키)와 권위 판본을 거친다. core-library의 `search_only` 파생 텍스트는 발견용이지 인용 원천이 아니다.

## 1. 정본 선언 — 무엇이 어디서 생성되는가

- **각 자료의 `source.yml`이 유일한 정본**이다. 자료의 상태·파일 목록·불확실성은 여기에만 손으로 적는다.
- `catalog.yml`의 `sources:` 블록과 `README.md`의 등록 자료 표는 source.yml들에서 옮겨 만든 **파생물**이다. 둘이 어긋나면 source.yml이 우선한다.
- `catalog.yml`의 머리(`purpose`·`citation_policy`·`collections`)는 손으로 유지한다.
- **재생성**: 공개본에는 catalog 재생성 스크립트가 들어 있지 않다. 자료가 적으면 손으로 유지하고, 많아지면 source.yml들을 읽어 `sources:` 블록과 README 표를 다시 쓰는 스크립트를 직접 두어도 된다. 어느 쪽이든 파생물을 고칠 때는 source.yml을 먼저 고친다.

### catalog.yml 최소 형식 (도구 호환)

`tools/library_search.py`가 `catalog.yml`을 0차 등록부로 읽는다. 도구가 읽는 키는 다음과 같다.

```yaml
purpose: "…"            # 수동 — 이 등록부의 목적
citation_policy: "…"    # 수동 — 예: search_only 텍스트는 인용 원천이 아니다
collections: []          # 수동·선택 — 혼합 컬렉션(아래 참고)
sources:                 # 파생 — 각 source.yml에서 옮김
  - source_id: example-chronicle
    title_ko: "{한국어 표기명}"
    title_original: "{원어 서명}"
    status: registered            # §4 자료 수준 통제어휘
    category: "{§8 통제어휘}"
    directory: "example-chronicle"   # core-library 기준 폴더
    current_stage: "…"
    files_summary: "…"            # 선택 — 파일 상태 한 줄 요약
```

- 혼합 컬렉션(개별 source.yml 대신 매니페스트 JSON 하나로 관리하는 묶음)은 `collections:` 항목에 `directory`·`registry`·`manifest`를 둔다. 매니페스트의 각 항목은 `title`·`sha256`·`markdown`·`status`·`has_search_text`·`reason`을 갖는다.

## 2. 폴더 구조

```
core-library/
├── SCHEMA.md            ← 이 문서(정본, git 추적)
├── README.md            ← 원칙 + [파생 표]          (로컬 전용)
├── catalog.yml          ← 머리(수동) + sources(파생)  (로컬 전용)
├── <source-id>/                                       (로컬 전용)
│   ├── source.yml       ← 정본
│   ├── sources/         ← 원본 사본(선택, 아래 참고)
│   ├── texts/           ← 파생 검색층(원본 아님)
│   ├── references/      ← 참고 판본·색인 사본
│   └── indexes/, crawl/, mappings/ 등 자료별 하위층
└── <group>/<source-id>/ ← 묶음 자료(예: 같은 장르의 여러 소품, 공구서 묶음)
```

원본 파일은 원 위치에서 **옮기거나 삭제하지 않는다**. `source.yml`에 경로 + SHA-256으로 등록한다.
(예외: 외부에서 새로 내려받은 참고 사본은 `references/`에 둘 수 있되 `source_url`을 적는다.)

**원본 사본 보유(선택).** 핵심 원본 PDF는 등록부가 직접 사본을 보유할 수 있다 — 각 자료 폴더의 `sources/`에 **복사**하고(원 위치 파일은 그대로 둔다), 등록 path는 내부 사본을 가리키며, 원 위치 파일과 해시가 같음을 확인한 사실을 `stage_note`에 남긴다. 대형 전집이나 다른 프로젝트가 관리하는 자료는 외부 경로 + SHA-256 등록만 한다.

## 3. source.yml 필수 필드

```yaml
schema_version: 1        # 단순형=1, 다판본형(위성 editions.yml 사용)=2
source_id: example-chronicle   # 폴더명과 일치, kebab-case
title_ko: "{한국어 표기명}"     # 필수(도구가 조회하는 키 이름)
title_original: "{원어 서명}"   # 없으면 생략 가능
path_base: "{로컬 연구 폴더 경로}"   # 필수. 모든 상대경로의 기준(로컬 값 — 공개 저장소에 올리지 않는다)
status: registered       # §4 통제어휘만
category: "{§8 통제어휘}"  # 재분류 1차 축(장르). 없으면 README에서 '미분류'로 묶인다
current_stage: "…"       # 자유 서술(한 줄)
files:                   # 컨테이너는 files 하나로 통일
  - file_id: critical-edition-pdf   # 필수, kebab-case
    kind: full_primary_text         # §5 참고
    path: "{path_base 기준 상대경로}"
    sha256: "{64자리 16진수}"        # 실물 파일이면 필수(폴더·URL 제외)
    status: verified_source         # §4 통제어휘만
    stage_note: "…"                 # 선택. 상태어로 담기지 않는 사정의 보존처
    language: "{언어}"               # 선택. 언어·문화권은 2차 축(§8)
uncertainties:           # 키 이름은 uncertainties로 통일(pending 금지)
  - "[VERIFY:판본·누락 확인 필요]"
```

다판본형(`schema_version: 2`)은 위 구조에 더해 위성 `editions.yml`(판본 계보)과 `alignment.csv`(판본 간 위치 대응)를 둘 수 있다. 판본을 하위 폴더로 나누는 경우에도 각 하위 폴더의 source.yml은 이 규약을 따른다.

**source_id와 폴더명.** 묶음 폴더 하위 자료와 다판본 하위 폴더에서는 source_id가 바로 위 폴더명과 다를 수 있다(예: `{group}/{작품}/` 폴더의 source_id가 `{작품}-{역자}`). 이때 source_id는 자료·판본 수준 식별자이고, 실제 위치는 catalog의 `directory` 필드가 가리킨다. 최상위 단독 폴더는 폴더명 = source_id 규칙을 그대로 따른다.

## 4. 상태 통제어휘 (이 목록 밖 값 금지)

**자료 수준(source status, 6종)**

| 값 | 뜻 |
|---|---|
| `acquisition_pending` | 실물 미보유, 수집 대기 |
| `registered` | 원본 등록 완료, 검색층 미비 |
| `building` | 등록·검색층 구축 진행 중 |
| `search_ready` | 핵심 검색층 사용 가능 |
| `citation_ready` | 저자 최종 대조까지 완료 |
| `deferred` | 저자 결정으로 보류(사유를 current_stage에) |

**파일 수준(file status, 8종)**

| 값 | 뜻 |
|---|---|
| `verified_source` | 원본 실재·서지·역할 확인됨 |
| `direct_compare` | 텍스트층 없이 원본을 직접 대조하는 자료 |
| `search_only` | 검색용 파생 텍스트. 원문 인용 불가 |
| `provisional_alignment` | 둘 이상 판본의 위치가 잠정 대응됨 |
| `citation_ready` | 저자가 원본과 최종 대조함 |
| `pending` | 획득·변환·OCR 대기(내용은 stage_note에) |
| `superseded` | 폐기 판정. 이력 보존을 위해 삭제하지 않음 |
| `generated` | 기계 생성 리포트·색인·매니페스트(인용 원천 아님) |

옛 복합 상태(예: `search_ready_encoding_needs_conversion`)를 옮길 때는 가장 가까운 통제어휘로 바꾸고 **잃는 정보는 `stage_note`로 옮긴다. 삭제 금지.**

AI가 만든 파생물(OCR 교정·자동 정렬·요약 등)은 `generated` 또는 `search_only`로 두고, 저자 대조 전에는 `citation_ready`로 올리지 않는다.

## 5. kind 관례 (열린 목록, 새 값 허용)

`full_primary_text` 원문 전문 / `translation_pdf` 역주·번역본 / `facsimile_pdf` 영인·사본 이미지 /
`derived_search_text` 파생 검색 텍스트 / `derived_ocr_markdown` OCR 파생 / `scholarly_index_pdf` 색인·공구 /
`reference_dictionary` 사전·어원 공구서 / `crawl_manifest_tsv`·`derived_crawl_report`·`ocr_quality_report` 기계 산출.

## 6. 파생물 이력(provenance) 규약

| 상황 | 방식 |
|---|---|
| 텍스트 변환(인코딩·포맷) | `<산출파일>.provenance.json` 사이드카 (입출력 SHA-256·문자 수·대체 문자 수) |
| OCR·크롤 등 일괄 산출 | 산출 폴더에 `*_report.json` + source.yml에 `kind: *_report, status: generated`로 등록 |
| 소규모 수동 교정 | source.yml 안 `corrections:` 블록에 인라인 |

세 방식 중 하나를 반드시 쓴다. 검색층 파일인데 셋 다 없으면 등록 불완전으로 본다. (`tools/ingest.py`로 변환한 Markdown은 앞머리 provenance 프런트매터가 이 역할을 한다.)

**generated 산출물의 sha256.** `status: generated`인 기계 산출 리포트·크롤 매니페스트·자리표시 문서는 재생성물이므로 sha256을 권장하되 생략할 수 있다. 원문·검색층 실물 파일(`search_only` 포함)의 sha256 필수 규정은 그대로다.

## 7. 불확실성 마커

- 형식은 `[GAP:무엇]` / `[VERIFY:무엇]` — **콜론 뒤 공백 없음**(하네스 갭 마커 표준과 같다). 연대·역법 환산 미검증은 `[GAP:연대]`.
- 기존 파일의 `[GAP: 무엇]`(공백 변형)은 그 파일을 수정할 때에만 함께 통일한다(일괄 치환 금지 — 동시 작업 충돌 방지).
- 마커는 근거 없이 지우지 않는다. 해소할 때는 근거(무엇으로 확인했는지)를 `stage_note`나 커밋 메시지에 남긴다.

## 8. category 통제어휘 (재분류 1차 축 — 장르)

`category:`는 자료를 연구자가 찾기 쉬운 성격별로 묶는 **1차 축(장르)**이다. 언어·문화권은 2차 축이며 파일별 `language:`나 표의 열로 남긴다(장르가 언어를 가로지르기 때문이다 — 예: 견문 기록은 여러 언어로 쓰이고, 공구서도 여러 언어를 아우른다).

**기본 목록(분야에 맞게 고쳐 쓴다):**

| category | 뜻 |
|---|---|
| `연대기·편찬 사서` | 왕조·국가·교회 등이 편찬한 연대기·정사·관찬 기록 |
| `행정·법제 문서` | 법령·판례·행정 문서·재판 기록·회계 장부 |
| `서신·일기·회고` | 개인이 남긴 서신·일기·회고록·필기 |
| `견문·여행기` | 외부 사절·여행자·관찰자의 견문 기록(언어 불문) |
| `문집·총집` | 개인 문집과 여러 저자의 총집·선집 |
| `금석·물질 자료` | 비문·인장·화폐·출토 문서·고고 자료 |
| `도상·지도` | 회화·지도·도판 |
| `후대 편찬 사서` | 후대의 재편찬·발췌·기사본말·신편 사서 |
| `공구서·사전` | 사전·색인·연표·대역 사전 |

- 분야에 맞게 이 표를 처음 한 번 정하고(값 추가·삭제·개명), 정한 뒤에는 **목록 밖 값을 쓰지 않는다.** 정말 맞지 않는 자료가 나오면 표에 값을 추가한다. catalog·README를 스크립트로 재생성한다면 그 정렬 순서도 함께 고친다.
- 컬렉션(개별 자료의 묶음)은 category를 두지 않는다. 컬렉션에서 개별 자료로 승급한 항목은 자기 category를 갖는다.
