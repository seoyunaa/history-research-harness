# observations.csv 템플릿 (Observation 테이블 — 관찰-사건)

> `_workspace/{논문}/observations.csv` + 결속표 `obs_categories.csv`로 쓴다. **관찰-사건**은 "기록자 X가 장소 Y를 범주 Z로 인식·기록했다"는 사건이다. 스키마 정의서: `_relational-schema.md`.
>
> 절대 원칙(상속, 불가침): **모든 행은 `p_key` 결속 필수.** 미결속 = 하드 FAIL(날조 차단). 새 사료·좌표·관찰을 창작하지 않는다 — 각 관찰은 기존 발췌 카드(`passages/P-00n_*.md`)에 정박한다.

---

## 1. observations.csv — 열 정의

UTF-8 CSV. 헤더 1행 + 관찰당 1행.

| 열 | 뜻 | 필수 | 예 |
|---|---|---|---|
| `obs_id` | `OB-0NN`(불변 ID) | ✔ | `OB-001` |
| `observer` | 관찰자(사료의 저자·화자, glossary 표기) | ✔ | {기록자 A} |
| `place_id` | → `places.place_id`(외래키) | ✔ | `PL-001` |
| `place_name` | 장소 표기(가독성용 비정규화 사본 — place_id가 진실) | ✔ | {장소A} |
| `p_key` | → 발췌 카드 `P-00N`(외래키, **공란 금지**) | ✔ | `P-001` |
| `year` | 관찰 연도(또는 범위) — 사료 표기를 환산한 서력. 환산 근거는 카드의 「연대」 칸. 미검증이면 `[GAP:연대]` | | {서력 연도} |
| `quote_ref` | 원어 표지(관찰을 짚는 原文 어구) — **해당 카드 본문에 글자 그대로 있어야 한다** | | {原文 어구} |
| `note` | 비고(관찰 요지·편향 메모) | | {요지} |

- **`place_name`은 비정규화 사본**(사람이 읽기 쉽게)이다. 어긋나면 `place_id`가 진실이다(카드·places.csv 우선).
- **`quote_ref`는 카드 原文에서 옮긴 것만** 적는다. verify.py가 `p_key` 카드 본문과 대조해, 카드에 없는 어구면 FAIL을 낸다(인용문 날조 차단). 모델이 原文 어구를 지어 넣지 않는다.
- 범주(category)는 이 표에 두지 않는다 — **다대다이므로 아래 결속표**로 분리한다.

---

## 2. obs_categories.csv — 관찰↔범주 결속표 (다대다)

한 관찰이 여러 인식 범주를 가질 수 있으므로 별도 결속표로 M:N을 구현한다.

| 열 | 뜻 | 필수 |
|---|---|---|
| `obs_id` | → `observations.obs_id`(외래키) | ✔ |
| `cat_id` | → `categories.cat_id`(외래키) | ✔ |

- (obs_id, cat_id) 쌍은 유일하다. 한 obs_id가 여러 행으로 여러 범주에 결속될 수 있다.
- **각 관찰은 최소 1개 범주에 결속**한다(범주 없는 관찰은 점검 대상).

---

## 3. 예시 (형식 예시 — 값은 자리표시)

`observations.csv`:
```csv
obs_id,observer,place_id,place_name,p_key,year,quote_ref,note
OB-001,{기록자 A},PL-001,{장소A},P-001,{연도},,{관찰 요지}
OB-002,{기록자 B},PL-001,{장소A},P-002,{연도},,{같은 장소를 다른 범주로 인식}
OB-003,{기록자 C},PL-002,{장소B},P-003,[GAP:연대],{카드 原文의 어구},{요지}
```

`obs_categories.csv`:
```csv
obs_id,cat_id
OB-001,CAT-01
OB-001,CAT-03
OB-002,CAT-01
OB-003,CAT-02
```
(OB-001이 두 범주에 결속 = 다대다 예시.)

---

## 4. 무결성 (verify.py `relational_scan`)

**하드 FAIL**:
- `p_key`가 발췌 카드에 **없음** 또는 공란 → 미결속(날조 위험).
- `quote_ref`가 해당 카드 본문에 **없음** → 인용문 날조 위험.
- `place_id`가 `places.csv`에 **없음**, 또는 `status=rejected`인 장소를 인용.
- `obs_categories`의 `obs_id`·`cat_id`가 각 테이블에 **없음**.

**GC(정보)**: 좌표 없는 장소(`[GAP:좌표]`) / 관찰 없는 place / 쓰이지 않은 범주 / 장소 상태 분포 / `_provenance.md` 부재. 범주 없는 관찰은 사람이 점검한다.

- 표기(observer·place_name)는 `glossary.md`를 따른다.
- **결속 원칙**: 관찰을 옮길 때 반드시 기존 P-키·place_id에 매핑한다. 없는 관찰을 만들지 않는다(표 → csv는 *옮김*이지 *창작*이 아니다). AI가 카드에서 관찰을 추출했으면 저자 확인 전까지 `note`에 `[AI잠정]`을 달고 `_provenance.md`에 기록한다.

---

> 관련: `_relational-schema.md`(스키마 정의) · `_places-template.md`(place_id 원천) · `references/perception-categories.md`(cat_id 공통 시드) · 발췌 카드 `passages/P-00n_*.md`(p_key 원천).
