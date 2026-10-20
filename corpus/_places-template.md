# places.csv 템플릿 (Places 테이블 — 표준 노드의 승급판)

> `_workspace/{논문}/places.csv`로 쓴다. **장소 테이블은 좌표 화이트리스트의 표준 노드 파일을 승급한 것**이다(place_id·level·status·게이지티어 필드를 얹음). 스키마 정의서: `_relational-schema.md`.
>
> 절대 원칙(상속): **좌표·지명 비정을 지어내지 않는다.** 모든 좌표는 사료 P-키 / 고증·역주 면수 / 역사 게이지티어 / 현대 실측에 정박한다. 찾지 못하면 `[GAP:좌표]`로 비우고 지도에서 뺀다. **`source` 공란 = 하드 FAIL.**

---

## 1. 열 정의

UTF-8 CSV. 헤더 1행 + 장소당 1행.

| 열 | 뜻 | 필수 | 예 |
|---|---|---|---|
| `place_id` | `PL-0NN`(불변 ID) | ✔ | `PL-001` |
| `name` | 표기(glossary 고정) | ✔ | {표기} |
| `name_zh` | 원어 표기(열 이름은 도구 호환용 — 한자 외 문자도 여기) | | {원어 표기} |
| `aliases` | 이표기·별칭(세미콜론 구분 권장) | | {이표기1}; {이표기2} |
| `lon` | 경도 (CRS84 / EPSG:4326) | ✔ | {경도} |
| `lat` | 위도 | ✔ | {위도} |
| `type` | 유형 | ✔ | 도시 · 관문 · 호수 · 수도 · 경계 · 사원 |
| `level` | 위계 **1(점 지점)~4(광역)** | ✔ | 2 |
| `source` | **출처(공란 금지)** — 사료 P-키 / 고증서·역주 면수 / 게이지티어 ID | ✔ | {P-0nn / 고증서 약칭+면수} |
| `certainty` | `high` · `medium` · `low` | ✔ | high |
| `modern_name` | 현대 지명·실측 지점 | | {현대 지명} |
| `note` | 비고(기각 사유·비정 근거·id_basis·게이지티어 ID 등) | | {체계:ID} |
| `status` | **상태 3분법** — `confirmed`(좌표·출처 확정) · `unresolved`(미해결: 성급히 확정하지도 버리지도 않음) · `rejected`(검토 후 기각된 비정 — 기록은 남긴다) | ✔ | unresolved |
| `gm_id` | 마스터 게이지티어(`corpus/gazetteer-master.csv`) 연결 ID(선택) | | `G-001` |
| `source_db` | 외부 DB·어댑터 이름(선택 확장) | | {DB 이름} |
| `source_id` | 외부 DB의 안정 ID(선택 확장) | | {외부 ID} |
| `loc_basis` | 위치 비정 근거 전문 또는 요약(선택 확장) | | {근거 요약} |
| `loc_rank` | 원천 DB의 위치 비정 등급(선택 확장) | | {등급} |
| `contents` | 원천 DB 상세 설명·본문·URI 보존용 확장 열 | | {URI} |

- `status`는 `certainty`와 **별개 축**이다(처리 상태 vs 확신도). `rejected` 장소를 관찰이 인용하면 verify.py 하드 FAIL — 기각된 비정을 근거로 쓰는 것을 기계가 막는다. 배제할 때는 `note`에 기각 사유를 적는다.
- `gm_id`를 채우면 verify.py가 이 행의 좌표를 마스터 게이지티어와 반올림 없이 대조한다(마스터에 없는 ID·좌표 불일치 = FAIL). 좌표는 있으나 `gm_id`가 없는 행은 승급 후보로 집계된다.
- `source_db`·`source_id`·`loc_basis`·`loc_rank`·`contents`는 외부 게이지티어·역사 GIS 커넥터가 원천 정보를 잃지 않게 하는 확장 열이다. 없으면 비워도 되지만, 있으면 지도 매니페스트와 승급 검토에 그대로 남긴다. 게이지티어 ID 연결 열(`whg_id` 등)과 매칭 상태 열은 `references/gazetteer-linking.md`를 따른다.
- 외부 원천이 위치 비정 불가로 표시한 경우(예: 최하위 등급, 결측 좌표 코드) `lon`·`lat`은 비우고 `status=unresolved`, `note=[GAP:좌표] …`로 둔다. 화면용 임시 중심좌표는 쓰지 않는다.

### level 위계 정의 (1~4)
- **1** = 점 지점(촌락·성채·역·관문·사원 등)
- **2** = 거점(도시 등)
- **3** = 지역(유역·산맥·노선 구간·행정구역)
- **4** = 광역(대지역·생태권 등 최광역)

---

## 2. 승급 규칙 (표준 노드 파일 → places.csv)

좌표 화이트리스트의 표준 노드 파일(`name·name_zh·lon·lat·type·segment·id_basis·source·certainty`)에서:

1. **`place_id`(PL-0NN) 부여** — 노드 순서대로 채번한다.
2. **`level` 부여** — 위 1~4 위계로 저자가 판정한다.
3. `id_basis`·`segment`·게이지티어 ID는 `note` 또는 별도 열로 넘긴다(비정 근거 보존).
4. `source`·`certainty`는 **그대로 계승**한다(무결성 유지). `status`는 저자가 판정한다.

> 승급은 노드의 출처·확신도를 **손실 없이** 옮긴다. 좌표·출처를 새로 창작하지 않는다.

---

## 3. 예시 행 (형식 예시 — 값은 자리표시)

```csv
place_id,name,name_zh,aliases,lon,lat,type,level,source,certainty,modern_name,note,status,gm_id,source_db,source_id,loc_basis,loc_rank,contents
PL-001,{장소A},{원어 표기},,{경도},{위도},도시,2,{P-0nn},high,{현대 지명},{비정 근거},confirmed,{G-0nn},,,,,
PL-002,{장소B},{원어 표기},{이표기},,,관문,1,{고증서 약칭+면수},low,,[GAP:좌표] {비정 미확정 사유},unresolved,,,,,,
PL-003,{장소C},{원어 표기},,{경도},{위도},경계,3,{외부 DB 이름}:{외부 ID},medium,,{외부 DB 제안 좌표 — 마스터 승급은 저자 확인 필요},unresolved,,{외부 DB 이름},{외부 ID},{근거 요약},{등급},{URI}
```

---

## 4. 무결성 (verify.py)

- **`source` 공란 = 하드 FAIL.** 미상이면 그 행을 `[GAP:좌표]`로 두고 지도·관계형에서 뺀다.
- `observations.place_id`가 이 파일의 `place_id`에 실재해야 한다(외래키, `relational_scan`).
- GC: 관찰 없는 place / `certainty: low` / `[GAP:좌표]` → 인용(지도 게재) 전에 확인하거나 강등한다.
- 표기는 `glossary.md`를 따른다(라벨도 같은 표기로 고정).

---

> 관련: `_relational-schema.md`(스키마 정의) · `_geo-whitelist-template.md`(좌표 화이트리스트) · `_observations-template.md`(place_id를 참조) · `corpus/gazetteer-master.csv`(gm_id 원천).
