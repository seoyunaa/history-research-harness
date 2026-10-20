# 선택적 로컬 데이터층 (정본)

git 추적본은 **하네스 프레임워크만** 담는다. 축적된 연구 데이터(사료 PDF·판본 텍스트·서지 보유원장·색인·논문 작업공간)는 로컬 전용이며, 이 파일이 그 분계선의 정본이다. 추적 문서가 아래 로컬 경로를 언급할 때는 항상 "있으면 사용"이지 "반드시 존재"가 아니다.

## 분계선

| 층 | 경로 | git 추적 | 성격 |
|---|---|---|---|
| 헌법·규범 | `CLAUDE.md` `AGENTS.md` `research-profile.md` `references/*.md` | ✅ | 프레임워크 |
| 도구 | `tools/*.py` `run_verify.*` | ✅ | 프레임워크 |
| 모듈·에이전트 | `.claude/skills/` `.claude/agents/` | ✅ | 프레임워크 |
| 코퍼스 골격 | `corpus/`(registry·템플릿·마스터 게이지티어) | ✅ | 프레임워크 |
| core-library **규약** | `core-library/SCHEMA.md` | ✅ | 프레임워크 |
| core-library **데이터** | `core-library/`의 catalog.yml·각 source.yml·텍스트층·PDF | ❌ 로컬 전용 | 원본 사료 등록부 |
| 보유원장·전문 색인 | `references/library/`(catalog.*·fulltext.db·sources.txt) | ❌ 로컬 전용 | 서지관리 프로그램 동기화물·전문 색인 |
| 외부 반입물 | `references/external/` | ❌ 로컬 전용 | 협업·외부 데이터 캐시 |
| 논문 작업공간 | `_workspace/{논문}/`(골격 `_template/`만 추적) | ❌ 로컬 전용 | 단계 산출물·발췌 카드 |
| 로그·앱 상태 | `logs/` `*.log` | ❌ 로컬 전용 | 런타임 파생물 |

## 데이터층 없이 되는 것 / 안 되는 것

**된다(새 clone 그대로):** 집필 0~10단계 골격·윤문·심사·시각화 모듈, `tools/verify.py` 일반 가드레일, `tools/check_harness_hierarchy.py` 위계·경계 검사, 문체 실측(`voice_match.py` — 단 `style-profile-ko.md`를 저자 게재본으로 채운 뒤에 의미가 있다), hwpx 산출(`md2hwpx.py` — 투고 양식 .hwpx 템플릿은 공개본에 없으므로 사용자가 투고지 양식을 준비해 지정한다).

**안 된다(데이터층 필요):** 검색 위계 0~2차 — 0차 사료 등록부 조회(`core-library/catalog.yml`), 1차 전문 검색(`references/library/fulltext.db`), 2차 서지관리 프로그램 보유원장(EndNote 등). 해당 도구는 미설치를 감지하면 오류 대신 이 파일을 가리키는 안내문을 내고 정직하게 빈다(0차는 조용히 0건, `library_search.py` 전문 검색은 안내 후 종료). **데이터층이 없으면 웹(3차)만 남으므로, 그만큼 웹 발견의 승급을 보수적으로 한다** — 절대 원칙(날조 금지)은 데이터층 유무와 무관하게 동일하다.

## 설치·복원

- **1차 지정 로컬 폴더**: `references/library/sources.txt`에 `tier1:` 줄로 연구자가 지정한 사료 폴더를 적는다(`research-profile.md` §7). 양식은 `references/library/sources.example.txt`를 복사해 쓴다(예시 파일만 추적, `sources.txt`는 로컬 전용). 그 뒤 `python tools/library_index.py`로 전문 색인(`fulltext.db`)을 만든다.
- **서지관리 프로그램 보유원장(선택)**: EndNote를 쓰면 `python tools/endnote_sync.py`가 라이브러리를 읽기 전용으로 열어 카탈로그를 만든다. 다른 프로그램을 쓰면 이 층은 비워 둔다.
- **사료 등록부(선택)**: `core-library/`에 각 사료의 source.yml을 둔다(규약은 `core-library/SCHEMA.md`).
- **한 번에 갱신**: `python tools/refresh.py`(있는 층만 갱신).
- 원본(사료 PDF·판본 텍스트)은 재생성할 수 없으므로 **백업으로만 복원한다.** 파생물(색인·카탈로그)은 위 도구로 다시 만들 수 있다.

## 경계 검사

`python tools/check_harness_hierarchy.py`가 이 분계선을 기계로 지킨다 — 데이터 누출(추적본에 로컬 전용 파일 유입), 필수 참조 실재(추적 문서가 가리키는 프레임워크 파일의 존재), 버전 스탬프 단일성. `run_verify.*`에 편입되어 있고, `--clone-sim`이 새 clone 동작을 모사한다.
