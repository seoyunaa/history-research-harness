---
name: history-draft
description: 역사학 학술 논문을 0~10단계 인간 게이트로 집필한다(연구 질문 → 사료 검증·화이트리스트 → 거시구조 → 카드 배열 → 서론·본론·결론 → 서론 재수정 → 초록 → 각주 감사 → 모의 심사). "논문 쓰자", "이 질문으로 논문", "사료 검증", "다음 단계", "집필" 요청에 쓴다. Drafts a history journal article through the harness's human-gated 0-10 stage pipeline.
---

# history-draft — 집필 모듈 (Codex 어댑터)

이 스킬은 Codex용 진입점이다. **정본은 `.claude/skills/집필/SKILL.md`** 이며, 이 파일은 그것을 Codex에서 쓰는 방법만 적는다. 두 파일이 어긋나면 정본과 `CLAUDE.md`가 우선한다.

## 시작하기 전에 읽을 것

1. `CLAUDE.md` — 절대 원칙(원문·서지·면수·좌표·연대 창작 금지, 비워 표시, AI 산출물 표시)과 단계 체계.
2. `research-profile.md` — 분야·시대·지역·사료 언어·역법·권위 판본. 빈칸은 추측하지 말고 사용자에게 묻는다.
3. `.claude/skills/집필/SKILL.md` — 오케스트레이터 절차 전문. 그대로 따른다.

## Codex에서의 번역 규칙

- **단계 에이전트**: 정본이 서브에이전트에 위임하라고 하면, 이 저장소의 `.codex/agents/`에 정의된 같은 역할의 에이전트(`question_sharpener`, `source_verifier`, `structure_architect`, `prose_writer`, `intro_reconciler`, `citation_auditor`, `peer_reviewer`)를 이름으로 불러 맡긴다. 서브에이전트를 쓸 수 없는 환경이면 `.claude/agents/<역할>.md`를 역할 지침으로 읽고 한 세션 안에서 직접 수행한다.
- **게이트**: 한 번에 한 단계만 진행하고, 단계가 끝나면 무엇을 했고 무엇을 확인해야 하는지 밝힌 뒤 사용자 승인을 기다린다. 자동으로 다음 단계로 넘어가지 않는다.
- **질문 도구**: 정본의 `AskUserQuestion`은 일반 텍스트 질문으로 바꿔 순서대로 묻는다.
- **검증**: 4~10단계 게이트마다 `python tools/verify.py`를 실행해 결과를 보고한다. 하드 FAIL이 있으면 게이트를 통과시키지 않는다.
- **산출물 표시**: 초안 파일 머리에 `> ⚠ AI 작성 초안 — 저자 검토 전`을 단다.
