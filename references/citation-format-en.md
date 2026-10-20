# citation-format-en.md — Citation format (English manuscripts)

영문 원고의 표기법이다. 기본값은 **Chicago notes and bibliography**다. 분야 영문 저널은 각자 스타일시트가 있으므로, **투고지 스타일시트가 이 파일을 덮어쓴다.** `_meta.md`의 `target`(또는 `research-profile.md` §6)으로 어느 저널인지 명시하고, 확정 전에는 Chicago 기본값으로 쓴 뒤 투고 시 조정한다.

> 아래 세부 중 저널마다 갈리는 항목(로마자화 체계, 원어 병기 여부, 원문 인용 정책)은 추정으로 단정하지 않는다. 투고지 규정을 확인해 채우고, 미확인은 `[투고지 확인]`으로 둔다.

근거: Turabian 8판과 *Chicago Manual of Style*(서목은 `references/writing/README.md`). CMOS 17판 이후 바뀐 지점은 본문에 표시했다.

## 인용 면수 — 절대 규칙 (한국어판과 동일)

Every citation, primary or secondary, gives the exact page (or *juan*/folio/line) where the statement is found. If the location cannot be verified, do not cite — mark `[GAP:면수]` (or `[GAP:전거]` if the source itself is unverified).

## 1차 사료

사료 유형과 전통마다 관행이 다르다. 분야의 권위 판본과 약호는 `research-profile.md` §4에 적고, 첫 각주에서 약호·판본을 선언한 뒤 쓴다.

- **동아시아 한문 사료**: 서명은 로마자화 + 이탤릭, 필요시 원문 병기. 권차는 *juan*으로, 편명은 로마자(필요시 원문). 권위 판본의 권·면을 짚는다. 형식 예: `*Romanized Title* 原題, *juan* N, p. 000 (판본).` (저널에 따라 `약호 권.면` 압축형 — 첫 각주에서 약호·판본 선언 후 사용.)
- **교정본과 번역본이 병존하는 사료**(예: 이슬람권·고전·중세 사료): 교정본(critical edition)과 번역본을 구분해 인용한다. 번역 인용 시 역자·판본을 명시한다. 형식 예: `Author, *Title*, ed. Editor / trans. Translator, p. 000.`
- **서양 고전·중세 사료**: 관행적 위치 표기(권·장·절, 폴리오 recto/verso)를 쓰고, 쓴 교정본을 밝힌다.
- **문서고 자료**: Archive, collection/fonds, box/folder 또는 call number, document number/folio. 저자가 실물·목록에서 확인한 것만 쓴다.
- **DB에서 얻은 原文**: 웹 데이터베이스에서 찾은 원문도 **서지는 표점본·판본으로** 정박한다(DB는 발견 플랫폼이지 판본이 아니다 — `source-criticism.md` 1절).
- **재인용**: 원 사료를 못 봤으면 "quoted in"으로 정직하게 표시. 가능하면 원 사료를 직접 확인해 재인용을 없앤다.

## 로마자화 (투고지 우선, 기본값 제시)

- 중국어: Pinyin 기본. (저널이 Wade-Giles를 요구하면 따른다.)
- 한국어: McCune-Reischauer 또는 Revised Romanization — 저널 관행을 따른다(한국 발행 영문지는 RR이 많다).
- 일본어: revised Hepburn(장음 마크롱).
- 아랍어·페르시아어: IJMES 방식 기본.
- 그 밖의 언어: 분야 관행 전사. `research-profile.md` §2에 체계를 적고, 대상별 확정 표기는 `glossary-master.md` → 논문별 `glossary.md`에서 하나로 고정한다. 대중 표기를 쓰는 저널이면 스타일시트 우선.
- 첫 등장에서 원어를 괄호 병기할지는 투고지 정책을 따른다. 병기 기본형: 로마자 + 원문, 이후 로마자만. 널리 알려진 지명·인명은 병기 생략.

## 제도·관직 용어의 영역 (일관성)

- 관제·제도어는 분야 표준 영역을 따른다(분야의 관직 사전·표준 개설서 관행 — `research-profile.md`에 기준서를 적어 둔다). 첫 등장에서 원어+영역을 함께 제시하고 이후 하나로 통일.
- 두 언어 형태가 병존하는 용어는 어느 쪽을 기본형으로 쓸지 초고 단계에서 확정하고 `glossary.md`에 박는다.

## 2차 문헌 (Chicago notes and bibliography)

- 단행본 제목 이탤릭, 논문 제목 " ".
- 각주(first full note): Author, *Title* (Place: Publisher, year), page. 논문: Author, "Title," *Journal* vol, no. (year): page.
- 이후 short note: Author, *Short Title*, page. **Ibid.는 쓰지 않는다**(CMOS 17판 이후 비권장 — Turabian 8판과 다른 지점). 각주 번호는 구두점 뒤, 가급적 문장 끝에 몬다.
- Bibliography: 저자 성 도치, 알파벳순.
- **비영어 연구 인용**: 원제(로마자화 또는 원문) + 대괄호 영역. 형식 예: `Author, *Romanized Title* 原題 [English Translation of Title] (Place: Publisher, year).` 제목 로마자화 여부·방식은 투고지 관례 `[투고지 확인]`.
- 서지 자동 생성기(Zotero 등)는 비영어 서지에서 오류가 잦다(저자명 어순·로마자화·원문 병기) — 최종 수동 검수. **모든 각주 서지는 `03_biblio_whitelist.md` 등록분만.**

## 인용문 정책

- Block quotation(산문 5행 이상)은 별행 들여쓰기, 따옴표 없음. 번역을 원칙으로 하되 논점이 字句·音韻·판본일 때는 원문(전사 포함)을 함께 둔다.
- 필자 보충 〔 〕(또는 투고지 관행상 [ ]), 원주는 ( ). 생략은 ellipsis.
- 연대는 사료의 연대 표기(연호·왕력·간지·히즈라력 등)를 쓸 때 서력 병기 — 형식 예: `Reign-era name N (CE year)`. 월일이 음력 등 다른 역법이면 표시한다.
- 서력 환산의 역법을 밝힌다: 그레고리력 도입(1582년 이후, 지역마다 시점이 다름) 이전 또는 미도입 지역의 날짜는 율리우스력 기준인지 그레고리력 환산인지 적는다. 확인하지 못한 환산은 `[GAP:연대]`(`source-criticism.md` 5절).

## 숫자·연대 표기 (Chicago 인문학 관례)

- 100 이하(한두 단어로 표현되는 수)는 문자로, 그 이상은 숫자로.
- 세기: the thirteenth century(명사) / thirteenth-century trade(형용사, 하이픈).
- 연대 범위는 en dash: 1450–1520.

## 참고문헌 배열

Primary sources / Secondary literature / Reference works로 갈래를 나눈다. 각 갈래 안에서 로마자 알파벳순. 비라틴 문자권 저자는 로마자화한 성을 기준으로 정렬하되 원어 표기를 병기할 수 있다(투고지 우선).

## 본문/각주 분배 (언어 공통)

핵심 판정과 경쟁 가설 제거는 본문에. 부차 전거·보조 논증만 각주로. 핵심 논증을 각주에 숨기지 않는다. (영어 NB의 이점: 각주가 본문 흐름을 지키면서 논쟁·부가 정보의 공간이 된다 — 결론부에서 새 이름을 본문에 등장시키지 않고도 전거를 달 수 있다.)
