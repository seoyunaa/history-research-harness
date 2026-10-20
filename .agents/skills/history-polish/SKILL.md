---
name: history-polish
description: 윤문 모듈 — 저자의 출판 문체에 정박해 문장만 다듬는다. 논증·내용·사료 인용·면수·고유명사는 건드리지 않고, 원본을 덮어쓰지 않으며 대조 리포트를 남긴다. "윤문해줘", "문장 다듬어", "번역투 고쳐", "매끄럽게" 요청에 쓴다. Sentence-level copyediting anchored to the author's published style.
---

# history-polish — 윤문 모듈 (Codex 어댑터)

**정본은 `.claude/skills/윤문/SKILL.md`** 이다. 이 파일은 Codex에서 쓰는 방법만 적는다. 어긋나면 정본과 `CLAUDE.md`가 우선한다.

## 시작하기 전에 읽을 것

1. `.claude/skills/윤문/SKILL.md` — 정박 문서 순서·철칙·절차 전문.
2. `references/register-rules-ko.md`(영어는 `-en.md`), `references/style-profile-ko.md`, `references/style-exemplars-ko.md`. 문체 양식이 비어 있으면 그 사실을 알리고 register-rules만으로 진행한다.

## Codex에서의 번역 규칙

- 결과는 `{파일}_윤문.md`와 `{파일}_윤문리포트.md`로 옆에 쓴다. 원본은 고치지 않는다.
- 의미가 흔들리는 자리는 고치지 말고 `[윤문 보류: 사유]`로 표시한다.
- 전후 비교는 `python tools/voice_match.py <원본.md> <윤문본.md>`, 마지막에 `python tools/verify.py`.
