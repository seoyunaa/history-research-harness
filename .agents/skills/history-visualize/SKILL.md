---
name: history-visualize
description: 연구 시각화 모듈 — 표·지도·네트워크·통시 그림을 데이터 기반 추천과 순차 질문으로 고르고, 좌표 출처·도표 매니페스트를 갖춰 재현 가능하게 만든다. "지도 만들어", "노선도", "네트워크 그려", "도표/표 만들어", "고지도 정합", "시각화" 요청에 쓴다. Builds reproducible maps, networks, timelines and tables for history research.
---

# history-visualize — 시각화 모듈 (Codex 어댑터)

**정본은 `.claude/skills/시각화/SKILL.md`** 이다. 이 파일은 Codex에서 쓰는 방법만 적는다. 어긋나면 정본과 `CLAUDE.md`가 우선한다.

## 시작하기 전에 읽을 것

1. `CLAUDE.md`의 절대 원칙과 「D. 지리·좌표·지도」「E. 관계형 데이터·시각화」.
2. `.claude/skills/시각화/SKILL.md` — 위저드 절차 전문.

## Codex에서의 번역 규칙

- 바로 그리지 않는다. 먼저 `python tools/suggest_visual.py <데이터파일>`로 신호를 세고, 유형(표·지도·네트워크·통시) → 방식 순서로 **일반 텍스트 질문**을 한 번씩 한다. 사용자가 유형·방식을 이미 정했으면 묻지 않는다.
- 좌표·지명 비정·연대를 지어내지 않는다. 출처 없는 좌표는 `[GAP:좌표]`로 비우고 지도에서 뺀다.
- 산출물마다 매니페스트(`corpus/_figure-manifest-template.md`)를 남기고 `python tools/verify.py`로 확인한다.
