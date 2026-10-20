# history-research-harness — Codex 등 Claude 밖 에이전트 진입 지침

학술적 규범과 현행 버전의 정본은 `CLAUDE.md`다. 사료·인용·문체 규범이 충돌하면 CLAUDE.md가 우선한다. 필요한 절과 요청에 해당하는 모듈만 읽는다. 모든 수정 전에 전체 헌장·모듈 지도·시작 안내를 차례로 읽을 필요는 없다. 연구 분야·시대·지역 설정은 `research-profile.md`에 있다 — 작업 전에 읽는다.

## 사료와 저자 판단

- 없는 원문·서지·권면·좌표·외국어 전사·연대 환산을 만들지 않는다. 미확인은 `[GAP:원문]`, `[GAP:면수]`, `[GAP:전거]`, `[GAP:좌표]`, `[GAP:연대]`로 남긴다.
- AI가 만든 번역·요약·추출·초안은 `[AI잠정]` 또는 파일 머리 배너 `> ⚠ AI 작성 초안 — 저자 검토 전`으로 표시하고 원문과 섞지 않는다.
- 4단계 이후 사료 인용은 논문별 `02_sources_whitelist.md`와 `passages/P-*.md`에 연결한다. 1차 사료 原文은 사용자가 비판정본에서 옮긴 것만 카드에 등록한다. 2차문헌 각주도 `03_biblio_whitelist.md`의 tier와 프로젝트 근거가 필요하다.
- 좌표는 `corpus/gazetteer-master.csv`, 표기는 `references/glossary-master.md`, 인식범주는 `references/perception-categories.md`를 따른다. 새 정준 항목 승급은 저자 판단을 받는다. 외부 검색 결과는 발견·제안으로 남기고 확인 없이 승급하지 않는다. 관찰의 quote_ref는 해당 카드 原文/코딩과 verbatim 일치해야 한다.
- 집필·윤문 중에는 승인된 증거층으로 작업한다. 웹·외부 DB 검색은 사료 검증과 DB 작업에서 수행한다.
- 논문의 연구 질문·구조·사료 승급·배열 확정 등 저자의 실질적 결정을 보존한다. 논문 단계 승인 규칙을 코드 수정·설정 정리·검증의 매 단계 승인으로 확대하지 않는다. 사용자가 여러 단계의 수행을 이미 허용했다면 그 범위의 완료까지 진행하고, 새로운 저자 판단이 필요한 지점만 묻는다.

## 요청별 자료

| 작업 | 필요한 자료 |
|---|---|
| 연구 분야 설정 | `research-profile.md` |
| 자료 검색·등록·조회 | `.claude/skills/DB/SKILL.md`; 도서관 검색은 `tools/library_search.py` |
| 연구 질문·사료 검증·집필 단계 | `.claude/skills/집필/SKILL.md`와 `CLAUDE.md`의 해당 단계, `.claude/agents/`의 단계 에이전트 정의 |
| 지도·표·네트워크·통시 | `.claude/skills/시각화/SKILL.md`; 이미 지정된 유형과 도구는 다시 묻지 않는다 |
| 윤문·문장 교정 | `.claude/skills/윤문/SKILL.md` |
| 모의 심사·답변·재심 | `.claude/skills/심사/SKILL.md`, `corpus/_review-template.md` |
| 사료 비판·연대 검증 | `references/source-criticism.md` |
| 완성 원고 재구조 | `references/re-architecture-loop.md` |
| 문제화 요청 | `references/problematization.md` |
| 로컬 자료층·새 clone 문제 | `references/local-data-layer.md` |
| 하네스 규칙·도구 개조 | 관련 도구의 실코드, `tools/check_harness_hierarchy.py`; 규칙 정본·전파 대상·기계 검증 한계를 짧게 정리한 뒤 요청 범위 안에서 수정 |

일반 안내가 필요할 때 `시작하기.md`, 모듈 관계가 필요할 때 `Claude-History.md`, 도구 목록이 필요할 때 `references/도구-지도.md`를 읽는다.

## Codex 구성 — 스킬과 단계 에이전트

정본은 `.claude/` 아래 파일 하나씩이다. Codex용 파일은 그 정본을 가리키는 얇은 어댑터이며, 어긋나면 정본이 우선한다.

| Codex | 위치 | 정본 |
|---|---|---|
| 스킬 `$history-draft` | `.agents/skills/history-draft/` | `.claude/skills/집필/SKILL.md` |
| 스킬 `$history-db` | `.agents/skills/history-db/` | `.claude/skills/DB/SKILL.md` |
| 스킬 `$history-visualize` | `.agents/skills/history-visualize/` | `.claude/skills/시각화/SKILL.md` |
| 스킬 `$history-polish` | `.agents/skills/history-polish/` | `.claude/skills/윤문/SKILL.md` |
| 스킬 `$history-review` | `.agents/skills/history-review/` | `.claude/skills/심사/SKILL.md` |
| 에이전트 `question_sharpener` 외 6종 | `.codex/agents/*.toml` | `.claude/agents/*.md` |

- 단계 위임은 `.codex/agents/`의 같은 역할 에이전트를 이름으로 부른다(`question_sharpener`, `source_verifier`, `structure_architect`, `prose_writer`, `intro_reconciler`, `citation_auditor`, `peer_reviewer`).
- 프로젝트 에이전트를 쓸 수 없는 환경이면 `.claude/agents/<역할>.md`를 역할 지침으로 읽고 한 세션 안에서 차례로 수행한다. 단계 산출물 파일명과 게이트(사용자 승인)는 그대로 지킨다.
- 시각화 위저드의 `AskUserQuestion`은 일반 텍스트 질문으로 바꿔 순서대로 묻는다.
- 정본 스킬·에이전트를 고치면 Codex 어댑터의 설명(description)과 역할 이름이 여전히 맞는지 확인한다(`tools/check_harness_hierarchy.py`).

## 원고 생성과 심사

새 글쓰기 단계에서 논문별 `_authorial_foundation.md`와 `glossary.md`를 확인한다. 3.5단계 카드 배열은 서술이 아닌 배치이며 저자의 「배열 굳음」 선언이 4단계 착수 조건이다. 배열판은 인용 원천이나 블라인드 심사 입력이 아니다.

한국어 산문 생성·재수정에는 `references/style-profile-ko.md`와 `references/style-exemplars-ko.md`를 읽는다(저자가 채우는 양식 — 비어 있으면 그 사실을 보고한다). 예문은 문체 참조이며 사료·서지를 새 원고에 가져오지 않는다. `tools/voice_match.py`는 문체 이탈 후보 보고용이고 하드 게이트가 아니다.

심사에는 최신 원고·화이트리스트·카드·CSV·매니페스트·검증 결과와 재심 시 직전 답변서만 제공한다. 저자 의도·확신·집필 이력은 제외한다. 역할 검토와 실제 독립·블라인드 심사를 구별하며, 존재하지 않는 도구 격리를 가정하지 않는다.

## 검증과 실행 환경

원고·증거층·관련 검증 로직을 변경했으면 `run_verify.cmd`(또는 `python tools/verify.py`)를 사용한다. 하네스 지침을 변경했으면 `python tools/check_harness_hierarchy.py`를 실행한다. 하드 FAIL은 수정하고, GC는 미확인 근거와 게재 전 소진 계획으로 보고한다. 사소한 안내문 변경 때문에 전체 원고 검증을 반복하지 않는다.

Claude 전용 도구 제한은 실제 도구에 맞춰 해석한다. 집필·심사·사료 검증 모델의 평가 절차는 `tools/regression_traps.md`와 `references/이행-훈련.md`에 있으며, 모델 이름만으로 통과했다고 가정하지 않는다.
