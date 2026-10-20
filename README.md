# history-research-harness — 역사학 연구 하네스

역사학 학술 논문을 **0~10단계 인간 게이트**로 집필·정리하는 다중 에이전트 하네스입니다. **Claude Code와 OpenAI Codex 양쪽에서** 쓸 수 있습니다. 시대·지역은 가리지 않습니다. 연구 분야·시대·지역·사료 언어·역법·권위 판본은 `research-profile.md` 한 파일에서 설정합니다.

> ⚠ **AI 작성 고지.** 이 공개판은 한 연구자가 비공개로 쓰던 원대사(元代史)·고려몽골관계사 전용 하네스를 AI(Claude Code)가 시대·지역 중립으로 일반화한 것입니다. 일반화 과정에서 원대사 전용 사료 목록·용어집·개인 문체 자료·연구 데이터는 모두 뺐고, 그 자리는 사용자가 채우는 양식으로 바꿨습니다.

*English summary below.*

---

## 설계의 척추 — 날조 차단

LLM 학술 글쓰기에서 가장 위험한 실패는 두 가지입니다. 이 하네스는 둘을 구조로 막습니다.

1. **날조** — 없는 사료·전거·연대를 지어내기. → 2단계가 만든 **인용 화이트리스트**만이 이후 모든 인용의 원천입니다. 정체성이 등록되고 발췌 카드에 原文이 실재하는 사료만 화이트리스트에 오릅니다. 原文은 사용자가 판본에서 옮기며, 모델은 생성하지 않습니다.
2. **오귀속** — 실재하는 사료에 틀린 주장 붙이기. → 화이트리스트와 카드가 각 사료가 *지지하는 주장*을 함께 적고(주장-사료 결속), 9단계 감사가 이를 역점검합니다.

채울 수 없는 자리는 비워 표시합니다: `[GAP:원문]` `[GAP:면수]` `[GAP:전거]` `[GAP:좌표]` `[GAP:연대]`. AI가 만든 번역·요약·초안은 `[AI잠정]`으로 표시합니다. `tools/verify.py`가 이 규칙을 기계로 강제합니다(위반 시 exit 1).

역사학 공통의 작업 원칙도 규칙으로 들어 있습니다: 사료 비판(외적·내적), 1차·2차·이론 구분, 전거 표기, 연대 검증(연호·간지·역법 환산), 불확실성 표시(certainty와 status 분리), AI 생성물 표시, 처리 이력(`_provenance.md`) 기록.

## 구성

| 층 | 내용 |
|---|---|
| `CLAUDE.md` | 헌장 — 절대 원칙, 0~10단계, 현행 규범 |
| `research-profile.md` | **분야 설정** — 시대·지역·사료 언어·역법·판본·게이지티어·표기법 |
| `.claude/skills/` | 모듈 5종: `DB`(자료 검색·카드) · `집필`(0~10단계 오케스트레이터) · `시각화`(지도·네트워크·통시) · `윤문`(문장) · `심사`(모의 피어리뷰) |
| `.claude/agents/` | 단계 에이전트 7종: question-sharpener · source-verifier · structure-architect · prose-writer · intro-reconciler · citation-auditor · peer-reviewer |
| `references/` | 사료 비판, 레지스터(ko/en), 표기법(ko/en), 질문 설계, 재구조, 문제화 렌즈, 글쓰기 원리, 지리·시각화 참조, 저자가 채우는 양식(문체·입장·표기) |
| `corpus/` | 카드·화이트리스트·수집 풀·처리 이력·도표 매니페스트·관계형 스키마·심사표 템플릿 |
| `tools/` | `verify.py`(가드레일) · `check_harness_hierarchy.py` · `library_search.py` · `ingest.py` · `voice_match.py` · `suggest_visual.py` · `georef.py` · `build_network.py` · `build_diachronic.py` · `md2hwpx.py` 등 |
| `AGENTS.md` | Codex 등 Claude 밖 에이전트용 진입 지침(Codex가 자동으로 읽음) |
| `.agents/skills/` | Codex 스킬 5종: `$history-draft` · `$history-db` · `$history-visualize` · `$history-polish` · `$history-review` |
| `.codex/agents/` | Codex 단계 에이전트 7종(`question_sharpener` 외) |

Claude Code용 파일(`.claude/`)이 정본입니다. Codex용 스킬·에이전트는 같은 정본을 읽게 하는 얇은 어댑터라서, 두 도구가 같은 규칙으로 움직입니다.

## 0~10단계

0 투고 맥락 → 1 연구 질문 → 2 사료·선행연구 검증(화이트리스트) → 3 거시구조 → 3.5 카드 배열 → 4 서론 초고 → 5 본론(장별) → 6 결론 → 7 서론 재수정 → 8 초록·주제어 → 9 각주·참고문헌 감사 → 10 모의 심사 루프(선택·반복).

한 번에 한 단계만 진행하고, 사용자가 승인해야 다음으로 넘어갑니다.

## 설치

필요한 것: [Claude Code](https://claude.com/claude-code) 또는 [OpenAI Codex](https://developers.openai.com/codex)(CLI·IDE 확장·앱), Python 3.10 이상(핵심 도구는 표준 라이브러리만 사용). 지도·네트워크 같은 선택 기능은 `environment.yml`의 패키지가 필요합니다.

```bash
git clone https://github.com/<계정>/history-research-harness.git
cd history-research-harness
python tools/verify.py
```

`python tools/verify.py`가 "하드 FAIL 없음"으로 끝나면 준비가 된 것입니다. Windows에서는 `run_verify.cmd`를 더블클릭해도 됩니다.

## 사용법

### Claude Code에서 쓰기

1. **Claude Code로 이 폴더를 엽니다.** 폴더 자체가 프로젝트입니다 — `CLAUDE.md`와 `.claude/`의 스킬·에이전트가 자동으로 로드됩니다.
2. **`research-profile.md`를 채웁니다.** 분야·시대·지역·사료 언어·연대 표기와 환산 근거·권위 판본·게이지티어·투고지 표기법. 모르는 칸은 비워 둡니다.
3. **(선택) 저자 양식을 채웁니다:** `references/authorial-stance.md`(입장·논저), `references/style-profile-ko.md`·`style-exemplars-ko.md`(본인 게재 논문의 문체 실측), `references/glossary-master.md`(확정 표기), `corpus/registry.md`(자주 쓰는 사료).
4. **(선택) 로컬 자료 폴더를 연결합니다:** `references/library/sources.example.txt`를 `sources.txt`로 복사해 `tier1:`에 PDF·텍스트 폴더를 적고 `python tools/refresh.py`를 실행합니다.
5. **시작합니다.** Claude Code에서 "논문 쓰자, 질문은 ○○○이야"라고 말하면 `집필` 스킬이 `_workspace/{논문}/`을 만들고 1단계부터 진행합니다. 모듈만 쓰려면 "이 자료 있나"(`DB`), "지도 만들어"(`시각화`), "윤문해줘"(`윤문`), "심사해줘"(`심사`)처럼 부릅니다.

자세한 안내는 [`시작하기.md`](시작하기.md), 모듈 지도는 [`Claude-History.md`](Claude-History.md), 전체 규칙은 [`CLAUDE.md`](CLAUDE.md)에 있습니다.

### Codex에서 쓰기

1. **저장소 폴더에서 Codex를 엽니다.** CLI라면 폴더로 이동해 `codex`를 실행합니다. IDE 확장·앱이라면 이 폴더를 작업 폴더로 엽니다. Codex가 루트의 `AGENTS.md`를 자동으로 읽습니다. 폴더 신뢰 여부를 물으면 허용해야 프로젝트 설정(`.codex/`)이 적용됩니다.
2. **`research-profile.md`를 채웁니다**(위 2~4단계와 같음).
3. **스킬을 부릅니다.** `/skills`로 목록을 보거나 `$`로 직접 부릅니다.
   - `$history-draft 논문 쓰자, 질문은 ○○○이야` — 0~10단계 집필
   - `$history-db 이 주제 자료 있나` — 자료 검색·카드
   - `$history-visualize` — 지도·네트워크·통시
   - `$history-polish` — 윤문
   - `$history-review` — 모의 심사
   스킬 설명이 요청과 맞으면 Codex가 알아서 고르기도 합니다.
4. **단계 에이전트**: `$history-draft`가 단계마다 `.codex/agents/`의 역할 에이전트(`question_sharpener`, `source_verifier`, `structure_architect`, `prose_writer`, `intro_reconciler`, `citation_auditor`, `peer_reviewer`)에 일을 맡깁니다. 프로젝트 에이전트를 쓸 수 없는 환경에서는 같은 역할 지침(`.claude/agents/*.md`)을 읽고 한 세션 안에서 차례로 수행합니다.
5. **검증**은 Claude Code와 같습니다: `python tools/verify.py`.

Codex의 파일 위치 규칙은 OpenAI 공식 문서를 따랐습니다: [Skills](https://developers.openai.com/codex/skills) · [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Subagents](https://developers.openai.com/codex/subagents).

### 작업물은 저장소에 올라가지 않습니다

`.gitignore`가 `_workspace/`(논문 초고·카드), `core-library/` 데이터, `references/library/`(로컬 자료 설정·색인), PDF·HWP·DOCX·DB 파일을 제외합니다. 이 저장소를 fork해 쓰더라도 연구 데이터는 각자의 컴퓨터에만 남습니다. 공개 저장소에 push하기 전에는 `git status`로 한 번 더 확인하세요.

## 한계

- 이 하네스는 날조를 **줄이는** 장치이지 없애는 장치가 아닙니다. verify.py는 화이트리스트·카드·서지 등록부와의 *결속*을 검사할 뿐, 사용자가 카드에 옮긴 原文이 판본과 일치하는지는 검사하지 못합니다.
- 모의 심사는 실제 동료 심사를 대신하지 않습니다.
- 문체 실측(`voice_match.py`)은 진단용이며, 저자가 문체 양식을 채우지 않으면 일반 규칙만으로 작동합니다.

## 라이선스

[미정 — 공개 전 결정]

---

## English summary

**history-research-harness** is a multi-agent harness for Claude Code and OpenAI Codex that helps historians draft and revise journal articles through an 11-step, human-gated pipeline (research question → source verification → structure → card montage → drafting → citation audit → mock peer review). It is period- and region-agnostic: field, period, region, source languages, calendar conversion rules, critical editions, and gazetteers are configured in `research-profile.md`.

Its core is **anti-fabrication by construction**: only sources on the stage-2 citation whitelist may be cited; primary-source text is entered by the researcher from critical editions, never generated by the model; every source is bound to the claim it supports; unfillable slots are marked (`[GAP:원문]`, `[GAP:면수]`, `[GAP:연대]`, …); AI-generated material is labelled (`[AI잠정]`). `tools/verify.py` (stdlib-only Python) enforces these rules and exits non-zero on violations.

**Claude Code:** open the folder; `CLAUDE.md` and the skills/agents in `.claude/` load automatically. Say "논문 쓰자" (let's write a paper) to start. **Codex:** open the folder; `AGENTS.md` loads automatically, skills live in `.agents/skills/` (`$history-draft`, `$history-db`, `$history-visualize`, `$history-polish`, `$history-review`) and stage agents in `.codex/agents/`. The Codex files are thin adapters pointing at the canonical `.claude/` files, so both tools follow the same rules.

The rule files are written in Korean. The pipeline supports both Korean and English manuscripts (`lang: ko | en`).

*This public edition was generalized by an AI assistant (Claude Code) from a private, Yuan-dynasty–specific harness. Field-specific source lists, glossaries, personal style data, and research data were removed and replaced with fill-in templates.*
