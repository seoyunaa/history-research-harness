---
name: history-db
description: 연구 데이터베이스 모듈 — 사료·연구논문·좌표·인물의 수집과 검색, 자료 변환, 발췌 카드·화이트리스트 정박. "이 자료 있나", "사료 찾아", "DB에서 검색", "좌표/인물 조회", "카드 만들자", "PDF 변환" 요청에 쓴다. Searches and registers sources through the harness search hierarchy (registry, local folders, reference manager, web).
---

# history-db — DB 모듈 (Codex 어댑터)

**정본은 `.claude/skills/DB/SKILL.md`** 이다. 이 파일은 Codex에서 쓰는 방법만 적는다. 어긋나면 정본과 `CLAUDE.md`가 우선한다.

## 시작하기 전에 읽을 것

1. `CLAUDE.md`의 절대 원칙과 「B. 수집·도서관·변환」.
2. `research-profile.md` §4~§7 — 사료 유형·권위 판본·게이지티어·로컬 자료층.
3. `.claude/skills/DB/SKILL.md` — 절차 전문.

## Codex에서의 번역 규칙

- 검색은 위계순으로: `python tools/library_search.py "질의"` → 없으면 웹. 로컬 자료층(`references/library/sources.txt`)이 없으면 도구가 0건으로 답한다 — 그 사실을 보고하고 웹 결과는 더 보수적으로 다룬다.
- 외부 데이터베이스·웹에서 얻은 원문·좌표·인물 정보는 **발견/제안**이다. 판본 검증과 저자 확인 없이 카드·화이트리스트·마스터에 넣지 않는다.
- 原文은 사용자가 판본에서 옮긴다. 모델은 原文을 생성하지 않고 `[GAP:원문]`으로 비운다.
- 카드·화이트리스트 구축(2단계)은 `.codex/agents/`의 `source_verifier`에 맡기거나, 없으면 `.claude/agents/source-verifier.md`를 지침으로 읽고 직접 수행한다.
- 작업 뒤에는 `python tools/verify.py`.
