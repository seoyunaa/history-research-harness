# 관계형 스키마 정의서 (Places / Observation / Category / Sources)

> 관계형 데이터층의 **단일 스키마 정의서**다. TYDA(Tracks of Yu Digital Atlas, Mostern & Horne 2021)의 event↔place↔type↔source 다대다 모델을 빌리되, **뼈대(구조·통제어휘·검증)만 빌리고 "많이 넣을수록 좋다"는 볼륨 인식론은 받아들이지 않는다**.
>
> 절대 원칙(상속, 불가침): 이 데이터층의 모든 행은 사료 P-키·권위 판본·게이지티어에 정박한다. 관계형화가 날조의 우회로가 되지 않는다. 미확정은 `[GAP:...]`로 비운다.
>
> 관계형층은 선택이다. 장소·관찰·범주를 구조화할 필요가 있는 연구에서만 쓴다.

---

## 0. 최상위 원칙 — 카드가 진실, 관계형은 파생 뷰

- **단일 원천(single source of truth)은 markdown 발췌 카드(`passages/P-00n_*.md`)와 화이트리스트(`02_sources_whitelist.md`)다.** CSV·DB는 카드에서 파생·재생성할 수 있는 *뷰*다.
- **원천으로 관리하는 것은 CSV·카드뿐이다.** SQLite 등 DB는 빌드 산출물이다(`tools/build_db.py`로 재생성 — 원천 아님).
- **이중 원천 위험**: 카드와 CSV가 어긋나면 **카드 우선**. CSV는 카드에서 파생·검증되는 뷰다.
- 이 정의서는 **논문과 무관한 표준**이다. 분과의 *내용*이 아니라 *구조·ID 규칙·검증 방법*만 하네스에 고정한다(특정 논문에 과적합하지 않는다).

---

## 1. 4개 테이블 개요

카드에서 파생하는 4개 테이블과 관계. 모든 파일은 `_workspace/{논문}/` 안의 **UTF-8 CSV**다.

| 테이블 | 파일 | 역할 | ID 규칙 |
|---|---|---|---|
| **Places** | `places.csv` | 장소(좌표 화이트리스트 표준 노드의 승급판) | `PL-0NN` |
| **Observation** | `observations.csv` | 관찰-사건(기록자가 장소를 어떤 범주로 인식했나) | `OB-0NN` |
| **Category** | `categories.csv` | 인식 범주 통제어휘 | `CAT-0NN` |
| **Sources** | (기존 화이트리스트·발췌 카드) | 원천 사료 — **신규 파일 없음** | `P-00N` |

- **Places** 열 정의 → `_places-template.md`
- **Observation** 열 정의(+ 다대다 결속표 `obs_categories.csv`) → `_observations-template.md`
- **Category** 열 정의 → 아래 3절 + `references/perception-categories.md`(공통 시드)

---

## 2. ID 규칙 (불변 — 처음부터 구속력 있게 정한다)

네 접두사는 **불변**이다(스키마 필드는 추가할 수 있으나 ID 규칙은 고정).

| 접두사 | 대상 | 형식 | 예 |
|---|---|---|---|
| `PL-` | Place | `PL-` + 3자리 0채움 | `PL-001`, `PL-020` |
| `OB-` | Observation | `OB-` + 3자리 0채움 | `OB-001`, `OB-047` |
| `CAT-` | Category | `CAT-` + 2~3자리 0채움 | `CAT-01`, `CAT-012` |
| `P-` | Source(발췌 카드) | `P-` + 3자리 0채움 (발췌 카드 규칙 그대로) | `P-001`, `P-031` |

- 번호는 **재사용하지 않는다**(삭제해도 결번 유지). 삭제 대신 `note`에 폐기 사유를 적거나 `status=rejected`로 둔다.

---

## 3. Category 테이블 (통제어휘) — 열 정의

`categories.csv`(인식 범주 통제어휘). 언어 중립 공통 시드는 `references/perception-categories.md`.

| 열 | 뜻 | 필수 |
|---|---|---|
| `cat_id` | `CAT-0NN` | ✔ |
| `name` | 범주명(glossary 표기 고정) | ✔ |
| `definition` | 정의(한 문장) | ✔ |
| `source_terms` | 이 범주에 묶인 사료 원어(세미콜론 구분: `{원어 어구1};{원어 어구2}`) — 카드 原文에서 옮긴 것만 | ✔ |
| `scope` | 재사용 구분: `common`(여러 논문에서 재사용 가능) / `paper`(이 논문 특수) | ✔ |
| `note` | 비고 | |

- **재사용 구분 의무**(과적합 방지): 이 논문 특수 범주와 공통 범주를 반드시 나눈다.
- verify.py는 `scope=common`인데 `references/perception-categories.md` 1절에 없는 범주를 **승급 후보**로 집계한다. 승급은 저자 승인 뒤에만 한다.

---

## 4. Sources 테이블 (신규 파일 없음)

- 기존 **화이트리스트(`02_sources_whitelist.md`)·발췌 카드(`passages/P-00n_*.md`)가 그대로 Sources 역할**을 한다.
- `observations.p_key`가 이 `P-00N` 키를 참조한다. 새 sources 파일을 만들지 않는다.
- 카드의 사료 구분(1차/2차/이론)·연대·certainty·status는 카드에 있다. 관계형층은 이를 복제하지 않고 P-키로 참조한다.

---

## 5. 외래키 관계 (다대다)

```
Places (PL) ──1──< Observation (OB) >──M── Category (CAT)
                        │
                        └──> Source (P-키, 발췌 카드)
```

| 관계 | 카디널리티 | 구현 |
|---|---|---|
| Place ↔ Observation | 1 : N (한 장소에 여러 관찰이 모임) | `observations.place_id → places.place_id` |
| Observation ↔ Category | **M : N** (한 관찰이 여러 범주를 가질 수 있음) | 결속표 `obs_categories.csv`(obs_id, cat_id) |
| Observation ↔ Source | N : 1 (모든 관찰은 한 P-키에 결속) | `observations.p_key → 발췌 카드 P-00N` |

- **질의 예**: "여러 기록자가 같은 장소를 각기 다른 범주로 인식했다" = `GROUP BY place_id`로 산출한다(`tools/build_db.py`가 만든 DB에서).

---

## 6. 무결성 규칙 (verify.py `relational_scan`)

**하드 FAIL** (날조 금지 원칙의 관계형 확장):

| 검사 | 실패 조건 |
|---|---|
| 관찰↔사료 결속 | `observations.p_key`가 발췌 카드에 **없음** 또는 공란 (미결속 = 날조 위험) |
| 인용문 실재 | `observations.quote_ref`가 해당 카드 본문에 **없음** |
| 관찰↔장소 | `observations.place_id`가 `places.csv`에 **없음** |
| 기각 비정 인용 | `observations.place_id`가 `status=rejected`인 장소 |
| 관찰↔범주 | `obs_categories.cat_id`가 `categories.csv`에 **없음**, 또는 `obs_id`가 `observations.csv`에 **없음** |

**GC(정보)**: 관찰 없는 place / 좌표 없는 place(`[GAP:좌표]`) / 쓰이지 않은 범주 / 장소 상태(confirmed·unresolved·rejected) 분포 / `_provenance.md` 부재.

- 좌표 화이트리스트 검사(geo_scan)와 같은 패턴이다. TYDA 외래키 무결성의 학술판.

---

## 7. 경계·리스크

- **과잉공학 금지**: 핵심은 스키마·어휘·데이터·검증이다. SQLite·노트북·LOD(연결 데이터)는 선택이다. 논문 완성이 목적이지 DB 구축이 목적이 아니다.
- **볼륨 유혹 경계**: 관계형화는 "더 넣고 싶은" 유혹을 부른다. 발췌는 넓게 모으되(`_library`) 결속은 엄격히 한다. 소수를 깊게.
- **스키마 경직 회피**: ID 규칙만 불변이고, 필드 추가는 열어 둔다.
- **AI 추출 표시**: AI가 카드에서 관찰·범주를 추출했으면 저자 확인 전까지 `[AI잠정]`으로 표시하고 `_provenance.md`에 처리 이력을 남긴다.

---

> 관련: `_places-template.md`(Places 열) · `_observations-template.md`(Observation 열 + obs_categories) · `references/perception-categories.md`(Category 공통 시드) · `tools/verify.py`(`relational_scan`) · `tools/build_db.py`(DB 재생성).
