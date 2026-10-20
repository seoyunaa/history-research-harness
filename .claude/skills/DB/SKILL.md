---
name: DB
description: (Claude History 모듈 1) 연구 데이터베이스 — 사료·연구논문·좌표·인물의 수집과 검색, 카드·화이트리스트 정박. "이 자료 있나", "사료 찾아", "DB에서 검색", "좌표/인물 조회", "카드 만들자", "화이트리스트에 올려", "PDF 변환" 같은 요청, 또는 "DB" 호출에 쓴다. 검색 위계(등록부→로컬 폴더→보유원장→웹)와 외부 데이터베이스 조회의 진입점.
---

# DB 모듈 — 연구 데이터베이스 (수집·검색·정박)

절대 원칙(`CLAUDE.md`) 상속: 없는 사료·서지·좌표·연대를 만들지 않는다. 외부에서 얻은 것은 전부 "발견"이며, 척추 진입(카드·화이트리스트·마스터)은 저자 확인 + 비판정본 정박을 통과해야 한다. 분야·시대·지역에 맞는 데이터베이스와 게이지티어는 `research-profile.md` §5와 `references/connectors.md`에서 고른다.

## 무엇을 하나

1. **보유 검색 (등록부 + 3층 위계)** — 질문이 "이 자료 있나/찾아줘"면:
   ```
   python tools/library_search.py "질의"        # 등록부 → 1차 로컬 → 2차 보유원장 순
   python tools/library_search.py "질의" --docs # 문서 단위
   python tools/refresh.py                      # 새 파일 넣은 직후 색인 갱신
   ```
   핵심 1차 사료는 사료 등록부(`core-library/catalog.yml`, 있으면)가 먼저 답한다 — 판본·소재·상태를 안내한다(규약 `core-library/SCHEMA.md`). 등록부·검색층은 발견 계급 — 인용 정박은 카드·비판정본 경유. 등록부·색인은 선택적 로컬 데이터층이라 처음 받은 저장소에는 없다. 설정은 `references/library/sources.txt`(양식 `sources.example.txt`), 배경은 `references/local-data-layer.md`. 1·2차에 없으면 3차 웹 — 외부 데이터베이스와 게이트는 `references/connectors.md`.
2. **자료 변환** — 새 자료(.pdf/.docx/.hwp/.pptx …)를 페이지 앵커·provenance 프런트매터가 붙은 md로:
   ```
   python tools/ingest.py <파일|폴더> [--out DIR] [--recursive]
   ```
   스캔본(텍스트층 없음)은 변환하지 않고 `_ingest_report.md`의 `[GAP: OCR필요]` 대기열로 — 선별 OCR은 저자 게이트. 산출 md는 파생물이며 인용 원천이 아니다(인용은 카드·비판정본 정박 경유).
3. **좌표·인물 조회** — `research-profile.md` §5에 적힌 역사 게이지티어·인물 데이터베이스를 조회한다(웹 또는 사용자가 따로 갖춘 조회 도구). 결과는 **제안** — 마스터(`corpus/gazetteer-master.csv`) 기입은 저자 게이트. 좌표계가 다른 자료(예: 국가별 변환 좌표)는 변환 과정을 매니페스트에 적는다.
4. **카드·화이트리스트 구축 (2단계 절차)** — source-verifier 에이전트에 위임. 읽기 프로토콜(통독/대조)은 저자가 사료별로 지정. 양식: `corpus/_passage-template.md` · `_whitelist-template.md`. 카드에는 사료 구분(1차/2차/이론)·연대 표기와 환산 근거·certainty·status·AI 초벌 표시를 함께 적는다.
5. **관계형·마스터** — 관찰-사건 데이터(`corpus/_relational-schema.md`), 마스터 게이지티어·인식범주 상속과 승급. 파생 뷰는 `python tools/build_db.py`.
6. **검증** — 어떤 작업 후든 `python tools/verify.py`.

## 다른 모듈과의 계약

DB의 산출(카드·화이트리스트·places/observations·마스터)은 **집필 모듈의 유일한 인용 원천**이고, 시각화 모듈의 좌표 원천이다. 여러 연구 저장소를 운용한다면 구조는 공유하되 데이터는 각자 둔다.
