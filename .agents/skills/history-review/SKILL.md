---
name: history-review
description: 심사 모듈 — 학술지 심사표 8항목으로 모의 피어리뷰를 돌리고 답변서·수정·재심 루프로 원고를 발전시킨다. 모든 지적은 본문 구절에 정박하고 문헌 제안은 서지를 단정하지 않는다. 자기 논문(A)·타인 원고 심사 보조(B)·외부 초고 발전(C) 세 모드. "심사해줘", "리뷰 돌려", "피어리뷰", "퇴고" 요청에 쓴다. Mock peer review loop for history manuscripts.
---

# history-review — 심사 모듈 (Codex 어댑터)

**정본은 `.claude/skills/심사/SKILL.md`** 이다. 이 파일은 Codex에서 쓰는 방법만 적는다. 어긋나면 정본과 `CLAUDE.md`가 우선한다.

## 시작하기 전에 읽을 것

1. `.claude/skills/심사/SKILL.md` — 모드·절차 전문.
2. `corpus/_review-template.md` — 심사표 양식과 규율.

## Codex에서의 번역 규칙

- 먼저 모드(A/B/C)와 시점(draft/final)을 사용자에게 묻는다. 모드 B는 학술지 AI 사용 규정과 비밀유지 의무를 먼저 확인한다.
- 심사자 3관점(전공 사료·고증 / 방법론·이론 / 편집위원)은 `.codex/agents/`의 `peer_reviewer`를 관점별로 세 번 부른다. 서브에이전트를 쓸 수 없으면 `.claude/agents/peer-reviewer.md`를 지침으로 관점마다 따로 수행한다.
- **블라인드 경계**: 심사자에게는 원고·화이트리스트·카드·CSV·매니페스트·verify 출력(재심이면 직전 답변서)만 준다. `_authorial_foundation.md`·`_problematization.md`·배열판·집필 대화는 주지 않는다. 같은 세션 안에서 역할만 바꾼 심사는 실제 독립 심사가 아니라는 점을 결과에 밝힌다.
- 결과 머리에 `> ⚠ AI 모의 심사 — 실제 심사가 아님`을 단다.
