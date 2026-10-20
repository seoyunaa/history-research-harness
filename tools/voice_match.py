# -*- coding: utf-8 -*-
"""voice_match.py — 저자 문체 실측 대조기 (긍정 voice-match 렌즈)

초안(md) 또는 추출 텍스트(txt)·조판 PDF를 저자 본인 게재본의 실측 대역과 대조한다.
대역은 references/style-profile-ko.md의 `voice-match` 블록(아래 형식)에서 읽고, 블록이
없으면 이 파일의 **예시 대역**(EXAMPLE_* — 한국어 인문학 논문의 대략적 경향을 넓게 반올림한
견본값)을 쓴다. ⚠ 예시 대역은 어느 저자의 문체도 아니다 — references/style-profile-ko.md에
본인 게재본 실측치를 적고 재보정할 것(본인 게재본 PDF를 이 도구로 재측정하면 실측치를 얻는다).

역할 경계:
  - 이 도구는 **긍정 실측 대조**만 한다 — 문장 리듬 분포·어휘 지문·수사 빈도가
    저자 게재본 대역 안에 있는가. 금지 점검(의인화·철학투·번역투)은 register-rules-ko
    와 적대검증 렌즈의 몫이고, 인용·서지 검증은 verify.py의 몫이다.
  - 판정은 전부 **GC급(참고)** 이다. 하드 FAIL 없음 — 문체는 날조가 아니고,
    수치 이탈이 곧 결함은 아니다(짧은 초안·고증 논문 장르차). 채택은 저자 게이트.

목표 대역 산출: 어휘·수사 항목은 문장 100개당 빈도 대역이다. 프로파일에 편별 실측 계수
(본인 게재본 n편의 항목별 횟수)와 편별 문장 수를 적으면, 각 편을 100문장당으로 정규화한 뒤
n편의 최소~최대를 대역으로 기계 파생한다(손으로 옮겨 적은 대역보다 갱신이 정확하다).
대역을 직접 `lo-hi`로 적어도 된다.

프로파일 블록 형식(references/style-profile-ko.md 안, 선택 — 없는 키는 예시 대역 유지):
  ```voice-match
  sentences: 300, 280, 310          # 본인 게재본 편별 문장 수(편 수 n = 항목 수)
  mean: 60-70                       # 평균 문장 길이(자) 대역
  median: 55-65
  commas: 0.6-0.9                   # 쉼표/문장
  buckets: 15-20, 40-48, 22-30, 8-13, 2-5   # ≤40 / 41~70 / 71~100 / 101~130 / 131~ (%)
  rhetq: 5, 4, 5                    # 수사의문 편별 계수(또는 100문장당 대역 1-2)
  이러한: 12, 20, 9                  # 어휘 항목(아래 LEXICON 이름) 편별 계수(또는 대역 3-8)
  ```

사용:
  python tools/voice_match.py <파일.md|.txt|.pdf> [파일2 ...] [--out 리포트.md] [--profile 프로파일.md]
  (md  = 하네스 초안: > 메타·각주 정의·[GAP]·[^n] 제거 후 측정 — 주 용도.
   pdf = 게재본 조판 PDF: pymupdf 글꼴 크기 필터 — 본문 크기 스팬만 남겨
         각주·머리글·쪽번호·작은 글꼴의 사료 블록 인용을 기계적으로 제외
         (프로파일 측정 규약과 동일). 보정·게재본 재실측용.
   txt = 평문 추출본(차선): [p.N]·머리글·쪽번호·각주 하단부 휴리스틱 제거.
         페이지 넘김 각주·표 병합 잔재가 남을 수 있어 pdf 직접 입력을 권장.)
"""
import argparse
import io
import re
import statistics
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 어휘 지문 탐지 항목: 이름 → (탐지 정규식, 프로파일 절) ─────────────────────
LEXICON = {
    "이는(문두 지시어)":        (r"(?<![가-힣])이는(?![가-힣])", "§2"),
    "이러한":                   (r"이러한", "§2"),
    "즉(재진술)":               (r"(?<![가-힣])즉(?![가-힣])", "§5"),
    "매우":                     (r"(?<![가-힣])매우(?![가-힣])", "§5"),
    "보여준다/보여주는":        (r"보여\s?주(?:ㄴ|는|다|었|지)|보여준", "§5"),
    "알 수 있다":               (r"알 수 있", "§5"),
    "생각된다":                 (r"생각된", "§5"),
    "것으로 보인다":            (r"것으로 보인", "§5"),
    "것이다(종결)":             (r"것이다", "§5"),
    "그러나":                   (r"(?<![가-힣])그러나(?![가-힣])", "§5"),
    "하지만":                   (r"(?<![가-힣])하지만(?![가-힣])", "§5"),
    "또한":                     (r"(?<![가-힣])또한(?![가-힣])", "§5"),
    "따라서":                   (r"(?<![가-힣])따라서(?![가-힣])", "§5"),
    "그런데":                   (r"(?<![가-힣])그런데(?![가-힣])", "§5"),
    "그렇다면":                 (r"그렇다면", "§5"),
    "요컨대":                   (r"요컨대", "§5"),
    "오히려":                   (r"오히려", "§4"),
    "아마도":                   (r"아마도", "§5"),
    "단순(대조 지문)":          (r"단순", "§4"),
    "가능성이 크다/높다/있다":  (r"가능성이 (크|높|있)", "§5"),
    "주목 틀(~점은 …사실이다)": (r"주목(?:할|해야 할|할 만한)\s?(?:점|부분|것)은", "§2"),
}

# ── 예시 대역(기본값) ────────────────────────────────────────────────────────
# 예시 대역 — references/style-profile-ko.md에 본인 게재본 실측치를 적고 재보정.
# 한국어 인문학 논문의 대략적 경향을 넓게 반올림한 견본값으로, 도구의 작동을 보이기 위한 것일
# 뿐 목표 문체가 아니다. 프로파일에 `voice-match` 블록이 있으면 해당 키는 그 값으로 바뀐다.
EXAMPLE_LEX_BANDS = {                               # 문장 100개당 빈도 대역(lo, hi)
    "이는(문두 지시어)": (7, 12), "이러한": (3, 8), "즉(재진술)": (4, 6), "매우": (2, 5),
    "보여준다/보여주는": (2.5, 5.5), "알 수 있다": (2, 3.5), "생각된다": (2, 3.5),
    "것으로 보인다": (1, 2.5), "것이다(종결)": (5, 10), "그러나": (3, 4.5), "하지만": (2, 4),
    "또한": (3.5, 5.5), "따라서": (2.5, 3.5), "그런데": (1, 3), "그렇다면": (0.5, 2.5),
    "요컨대": (0, 1), "오히려": (0, 1), "아마도": (0, 1), "단순(대조 지문)": (1.5, 4),
    "가능성이 크다/높다/있다": (1, 3), "주목 틀(~점은 …사실이다)": (0.5, 1.5),
}
EXAMPLE_RHETQ_BAND = (1, 2)                         # 수사의문 문장 100개당(§4)
EXAMPLE_BUCKET_BANDS = [(15, 20), (40, 48), (22, 30), (8, 13), (2, 5)]   # §1.1 길이 분포(%)
EXAMPLE_MEAN_BAND, EXAMPLE_MEDIAN_BAND, EXAMPLE_COMMA_BAND = (60, 72), (55, 68), (0.6, 0.9)

DEFAULT_PROFILE = Path(__file__).resolve().parent.parent / "references" / "style-profile-ko.md"

# 실행 시 load_profile()이 채우는 현행 대역
P = {}

# 문장 단위 탐지 항목(문장 끝 패턴)
RHET_Q = re.compile(r"(?:\?|(?:일까|을까|는가|인가|던가)[.…]?)\s*$")   # 수사의문(물음표 혼용)

# 회피 표현 — 예시 게재본 실측 0회 (register 5절과 겹치지만 실측 대조로 재확인)
AVOID = {
    "시사하는 바가 크다": r"시사하는 바가 크",
    "~라는 점에서 의의가 있다": r"점에서 의의가 있",
    "이중 피동(되어지-)": r"되어지",
    "홀로 마무리 '주목할 만하다.'": r"주목할 만하다[.]\s*$",
}

# 문단 끝 판정 동사 (프로파일 §2 — 문단은 추론 동사 판정으로 닫는다)
VERDICT_END = re.compile(
    r"(?:보여\s?준다|보여주고 있다|알 수 있다|생각된다|판단된다|확인된다|입증된다|실증된다"
    r"|짐작된다|추정된다|기대된다|드러내\s?준다|시사한다|결론지을 수 있다|보아야 할 것이다"
    r"|것이다|것으로 보인다|가능성이 크다|가능성이 높다|생각한다|주목된다|남아 있다|하고자 한다)"
    r"[.…」”\"']*\s*$"
)

# ── 레지스터·평이성 진단 (register-rules-ko ★절 기계화) ─────────────────────
# 학술 산문은 평이하게 서술하는데, 모델 문장은 문학적(철학적·은유적·의인화)으로 쏠리기
# 쉽다. 리듬 대역이 맞아도 이 축은 안 잡히므로 별도 스캔.
# 출처: register-rules-ko 「철학투 추상어 금지」·「의인화 금지」·8절 버릇말 watch-list.
# 전부 GC 후보 — 방법 문단 정의어·정치체 고유기능은 예외이므로 육안 확인.

# 철학투: 방법·이론 추상명사 (예고문·전환문·요약문의 뼈대로 쓰면 안 됨)
PHIL_NOUNS = ["실재", "층위", "표지", "작동", "정박", "지시 대상", "지시대상", "기제", "국면"]
METHOD_TERMS = ["수렴", "발산"]        # 방법 문단 정의 자리 한 번은 허용 — 그 밖은 구체어

# 의인화: 추상 주어 + 인격/의지 동사. 정치체(제국·국가·행정)도 넣되, 동사 게이트가
# 고유기능 동사(통치·정복·명령·재건·발의)를 ANTHRO_VERB에서 배제하므로 "제국이 통치하였다"는
# 안 걸리고 "제국이 물려받았다"만 걸린다(허용 경계 = 정치체 고유기능).
ANTHRO_SUBJ = ["정복", "공백", "해체", "봉쇄", "전황", "마비", "글자", "물길", "시설",
               "자연", "전설", "왕래", "정책", "질서", "역사", "기억", "손길", "시대",
               "제국", "국가", "행정"]
ANTHRO_VERB = ["끊었", "끊는", "죽였", "죽인", "메운", "메웠", "만든", "만들었",
               "부른", "불렀", "요약", "물려받", "삼켰", "삼킨", "품었",
               "나누어 보", "돌아오지", "지녔", "낳았", "낳는", "불러", "쥐었", "겪었"]
_ANTHRO_RE = re.compile(
    r"(" + "|".join(ANTHRO_SUBJ) + r")\s*(?:은|는|이|가|도|의|마저|조차)")

# 은유·버릇말 (8절 watch-list): 서술어·명사 은유 (저확률 회귀어)
METAPHOR_WATCH = ["세운다", "세웠다", "떠받친", "떠받쳐", "갈린다", "갈렸", "비운다", "비웠",
                  "호명", "이음매", "빈자리", "물꼬", "손짓", "숨결", "발걸음"]

# 문제화 렌즈 어휘 (register-rules-ko 「문제화 렌즈 어휘 격리」): _problematization.md
# 안에서만 허용 — 본문·각주 유입은 격리 위반 후보(GC). 단독 "장치"는 일반어(제도적 장치 등)라
# 오탐이 커서 목록에서 뺀다 — "담론"이 잡히므로 "담론 장치"는 자동 포착.
PROBLEM_VOCAB = ["문제화", "주체 위치", "담론", "계보학적", "에피스테메"]

BUCKETS = [(0, 40), (41, 70), (71, 100), (101, 130), (131, 10**9)]

# 추출 txt의 러닝헤드(학술지명+권호) 휴리스틱 — 특정 학술지에 매이지 않는 일반형
RUNNING_HEADS = [
    r"^\S.{0,40}\s*第\s*\d+\s*(?:輯|集|号|號|卷|期)", r"^\S.{0,40}\s*제\s*\d+\s*(?:집|호|권)",
    r"^\d{1,4}\s*$", r"^\[p\.\d+\]\s*$",
]


def _band(s, cast=float):
    a, b = [x.strip() for x in s.replace("~", "-").split("-", 1)]
    return cast(a), cast(b)


def band_per100(counts, sentences):
    """편별 계수 → 문장 100개당 대역(n편의 최소~최대)."""
    vals = [c / s * 100 for c, s in zip(counts, sentences)]
    return min(vals), max(vals)


def load_profile(path):
    """예시 대역에서 시작해, 프로파일 md의 ```voice-match 블록이 있으면 그 키만 덮어쓴다."""
    prof = {
        "lex": dict(EXAMPLE_LEX_BANDS), "rhetq": EXAMPLE_RHETQ_BAND,
        "buckets": list(EXAMPLE_BUCKET_BANDS), "mean": EXAMPLE_MEAN_BAND,
        "median": EXAMPLE_MEDIAN_BAND, "commas": EXAMPLE_COMMA_BAND,
        "n_papers": None,
        "source": "예시 대역(기본값) — references/style-profile-ko.md에 본인 게재본 실측치를 적고 재보정",
        "overridden": [],
    }
    p = Path(path) if path else DEFAULT_PROFILE
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError:
        return prof
    m = re.search(r"^```[ \t]*voice-match[ \t]*\r?\n(.*?)^```", text, re.M | re.S)
    if not m:
        return prof
    sentences, pending = None, {}          # pending: 편별 계수 항목(문장 수를 안 뒤 정규화)
    for ln in m.group(1).splitlines():
        ln = ln.split("#", 1)[0].strip()
        if not ln or ":" not in ln:
            continue
        key, val = [x.strip() for x in ln.split(":", 1)]
        try:
            if key == "sentences":
                sentences = tuple(int(x) for x in val.split(","))
                continue
            if key in ("mean", "median", "commas"):
                prof[key] = _band(val)
            elif key == "buckets":
                bands = [_band(x) for x in val.split(",")]
                if len(bands) != len(BUCKETS):
                    raise ValueError("buckets는 5구간")
                prof["buckets"] = bands
            elif key == "rhetq" or key in LEXICON:
                if "," in val or val.strip().isdigit():
                    pending[key] = tuple(int(x) for x in val.split(","))
                else:
                    band = _band(val)
                    if key == "rhetq":
                        prof["rhetq"] = band
                    else:
                        prof["lex"][key] = band
            else:
                print(f"[voice-match 블록] 모르는 키 무시: {key}", file=sys.stderr)
                continue
        except ValueError:
            print(f"[voice-match 블록] 값 해석 실패 — 무시: {ln}", file=sys.stderr)
            continue
        prof["overridden"].append(key)
    # 편별 계수는 편별 문장 수와 개수가 같아야 정규화된다 — 안 맞으면 예시 대역 유지
    for key, counts in pending.items():
        if not sentences or len(counts) != len(sentences):
            print(f"[voice-match 블록] '{key}' 편별 계수 {len(counts)}개 ↔ sentences "
                  f"{len(sentences) if sentences else 0}개 불일치 — 예시 대역 유지", file=sys.stderr)
            if key in prof["overridden"]:
                prof["overridden"].remove(key)
            continue
        band = band_per100(counts, sentences)
        if key == "rhetq":
            prof["rhetq"] = band
        else:
            prof["lex"][key] = band
    if sentences:
        prof["n_papers"] = len(sentences)
    if prof["overridden"]:
        prof["source"] = (f"{p.name} voice-match 블록(덮어쓴 키: {', '.join(prof['overridden'])})"
                          + ("" if {"mean", "median", "commas", "buckets"} <= set(prof["overridden"])
                             else " + 나머지는 예시 대역"))
    return prof


def clean_md(text):
    """하네스 초안 md → 측정용 본문 문단 리스트.

    측정 대상은 본문 산문뿐 — 메타 헤더는 세 형식 전부 제거한다: ① `> …` 블록 인용
    ② `<!-- … -->` HTML 주석(초안 변경 기록·계획 노트가 여기 든다, 여러 줄) ③ `#` 헤딩.
    (HTML 주석 미제거 시 하네스 용어[정박·층위]·체크리스트가 본문으로 새어 리듬·레지스터
    측정을 오염시킨다.)
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)   # HTML 주석 블록 제거
    lines = []
    for ln in text.splitlines():
        s = ln.rstrip()
        if s.startswith(">"):            # 메타 헤더·블록 인용(프로파일 규약: 리듬 제외)
            continue
        if s.startswith("#"):
            continue
        if re.match(r"^\[\^", s):        # 각주 정의
            continue
        if s.strip() in ("---", "***") or s.startswith("|"):
            continue
        if re.match(r"^\*\*각주\*\*", s.strip()):
            continue
        lines.append(s)
    body = "\n".join(lines)
    body = re.sub(r"\[\^\d+\]", "", body)              # 각주 참조
    body = re.sub(r"\[GAP:[^\]]*\]", "", body)          # 갭 마커
    body = re.sub(r"\[p\.\d+\]", "", body)
    body = re.sub(r"\*\*([^*]*)\*\*", r"\1", body)      # 굵게
    body = re.sub(r"\*([^*]*)\*", r"\1", body)
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body)]
    return [p for p in paras if p]


def clean_txt(text):
    """조판 PDF 추출 txt → 측정용 본문(문단 경계 없음, 한 덩어리).

    페이지마다: [p.N] 마커 이후 첫 각주 시작줄(^\\s*\\d+\\)\\s)부터 페이지 끝까지 버린다
    (각주는 페이지 하단 배치). 머리글·쪽번호·목차·초록·참고문헌 제거.
    """
    pages = re.split(r"\[p\.\d+\]", text)
    kept = []
    for pg in pages:
        out = []
        in_fn = False
        for ln in pg.splitlines():
            if not ln.strip():
                continue
            if any(re.match(rh, ln.strip()) for rh in RUNNING_HEADS):
                continue
            if re.match(r"^\s*\d{1,3}\)\s", ln):        # 각주 시작 → 페이지 나머지 버림
                in_fn = True
            if in_fn:
                continue
            out.append(ln.strip())
        kept.append(" ".join(out))
    body = " ".join(kept)
    # 참고문헌·초록 이후 절단
    for stop in (r"參考文獻", r"참고문헌", r"〈Abstract〉", r"<Abstract>", r"Abstract\b", r"中文摘要", r"국문초록"):
        m = re.search(stop, body)
        if m:
            body = body[: m.start()]
    body = re.sub(r"(?<=[가-힣.\"”」』)])\d{1,3}\)", "", body)   # 인라인 각주 첨자 1)
    body = re.sub(r"\s+", " ", body).strip()
    return [body]                                        # 문단 경계 미상 → 단일 문단


def clean_pdf(path):
    """게재본 조판 PDF → 본문 크기 스팬만 (글꼴 크기 필터).

    본문 크기 = 글자수 가중 최빈 글꼴 크기. 그보다 작은 스팬(각주·머리글·쪽번호·
    사료 블록 인용·표)은 제외 — 프로파일의 측정 규약("머리글·각주·참고문헌·초록 제거,
    사료 블록 인용은 리듬 통계 제외")을 조판 정보로 기계화한 것.
    """
    import fitz  # pymupdf
    from collections import Counter
    doc = fitz.open(path)
    sizes = Counter()
    x0s = Counter()
    raw_blocks = []          # (bx0, [line_spans]) — line_spans = [(size, text), ...]
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            lines = []
            bx0 = None
            for line in block["lines"]:
                lx0 = round(line["bbox"][0])
                bx0 = lx0 if bx0 is None else min(bx0, lx0)
                ls = [(round(sp["size"], 1), sp["text"]) for sp in line["spans"] if sp["text"].strip()]
                if ls:
                    lines.append(ls)
                    for sz, t in ls:
                        sizes[sz] += len(t)
            if lines and bx0 is not None:
                x0s[bx0] += sum(len(t) for ls in lines for _, t in ls)
                raw_blocks.append((bx0, lines))
    body_size = sizes.most_common(1)[0][0]
    body_x0 = x0s.most_common(1)[0][0]
    # 블록 텍스트 조립: 라인 안은 스팬 직결(스팬 경계 공백 오염 방지 — 작은 글꼴
    # 스팬[인라인 각주 첨자]은 여기서 자연 탈락), 라인 사이만 공백.
    block_texts = []
    for bx0, lines in raw_blocks:
        if bx0 - body_x0 > 15:          # 들여쓰기 블록 = 사료 블록 인용·표 (리듬 제외)
            block_texts.append(None)
            continue
        lt = [("".join(t for sz, t in ls if abs(sz - body_size) <= 0.5)).strip() for ls in lines]
        block_texts.append(" ".join(t for t in lt if t))
    # 반복 블록(머리글: 학술지명·논문 제목 러닝헤드) 및 쪽번호 블록 제거
    freq = Counter(t for t in block_texts if t)
    parts = []
    for t in block_texts:
        if not t:
            continue
        if freq[t] >= 4:                 # 4면 이상 반복 = 러닝헤드
            continue
        if re.fullmatch(r"[\d\s\-‒–]{1,8}", t):   # 쪽번호
            continue
        parts.append(t)
    body = re.sub(r"\s+", " ", " ".join(parts)).strip()
    # 목차 중복 제거: "Ⅰ. 머리말"이 목차와 본문에 두 번 나오면 두 번째(본문)부터
    first = body.find("Ⅰ. 머리말")
    if first != -1:
        second = body.find("Ⅰ. 머리말", first + 1)
        if second != -1:
            body = body[second:]
    for stop in (r"參\s*考\s*文\s*獻", r"참\s*고\s*문\s*헌", r"〈Abstract〉", r"<Abstract>", r"Abstract\b", r"中文摘要", r"국문초록"):
        m = re.search(stop, body)
        if m:
            body = body[: m.start()]
            break
    body = re.sub(r"(?<=[가-힣.\"”」』)])\d{1,3}\)", "", body)   # 인라인 각주 첨자(본문 크기)
    # 각주 첨자 스팬 탈락 지점의 문장 경계 공백 복원("했다.그러나" → "했다. 그러나")
    body = re.sub(r"(?<=[.?!])(?=[가-힣“\"「『‘])", " ", body)
    return [body]


_MASK = "␂"          # 인용 마스크용 제어 픽처


def mask_long_quotes(s):
    """긴 직접 인용(사료 블록 상당, 60자 초과)은 리듬 통계에서 제외 — 프로파일 측정 규약."""
    def repl(m):
        inner = m.group(2)
        if len(inner) > 60:
            return m.group(1) + "〔인용〕" + m.group(3)
        return m.group(0).replace(".", _MASK).replace("?", _MASK).replace("!", _MASK)
    pat = re.compile(r"([“\"「『])([^”\"」』]{1,600})([”\"」』])")
    return pat.sub(repl, s)


def split_sentences(para):
    s = mask_long_quotes(para)
    s = re.sub(r"…\(중략\)…", "〔중략〕", s)
    parts = re.split(r"(?<=[.?!])\s+", s)
    out = []
    for p in parts:
        p = p.strip().replace(_MASK, ".")
        if len(p) >= 5:                                  # 파편(쪽번호 등) 제거
            out.append(p)
    return out


def measure(paras, has_paragraphs):
    sents, para_sents = [], []
    for p in paras:
        ss = split_sentences(p)
        sents.extend(ss)
        if has_paragraphs and ss:
            para_sents.append(ss)
    n = len(sents)
    if n == 0:
        return None
    lens = [len(s) for s in sents]
    text_all = " ".join(sents)
    m = {
        "n_sentences": n,
        "mean": statistics.mean(lens),
        "median": statistics.median(lens),
        "commas": sum(s.count(",") + s.count("、") for s in sents) / n,
        "buckets": [sum(1 for L in lens if lo <= L <= hi) / n * 100 for lo, hi in BUCKETS],
        "lexical": {},
        "avoid": {},
        "rhetq": sum(1 for s in sents if RHET_Q.search(s)) / n * 100,
        "longest": max(lens),
        "counting": len(re.findall(r"(?<![가-힣])(첫째|둘째|셋째)(?![가-힣])", text_all)),
    }
    for name, (pat, sec) in LEXICON.items():
        band = P["lex"].get(name)
        if band is None:
            continue
        m["lexical"][name] = (len(re.findall(pat, text_all)) / n * 100, band, sec)
    for name, pat in AVOID.items():
        hits = [s for s in sents if re.search(pat, s)]
        m["avoid"][name] = hits
    m["register"] = measure_register(sents)
    if has_paragraphs and para_sents:
        m["para_n"] = [len(ss) for ss in para_sents]
        m["verdict_end"] = sum(1 for ss in para_sents if VERDICT_END.search(ss[-1])) / len(para_sents) * 100
        first_mid_last = [0, 0, 0]
        for ss in para_sents:
            for i, s in enumerate(ss):
                if len(s) <= 40:
                    if i == 0:
                        first_mid_last[0] += 1
                    elif i == len(ss) - 1:
                        first_mid_last[2] += 1
                    else:
                        first_mid_last[1] += 1
        m["short_pos"] = first_mid_last
    return m


def measure_register(sents):
    """레지스터·평이성 진단 — 철학투·의인화·은유(register-rules ★절)를 문장에서 잡는다.

    반환: {phil:[문장…], method:[…], anthro:[…], metaphor:[…], problem:[…]} (각 최대 표시분).
    전부 GC 후보 — 방법 문단 정의어·정치체 고유기능은 예외라 육안 확인.
    """
    r = {"phil": [], "method": [], "anthro": [], "metaphor": [], "problem": []}
    for s in sents:
        hit_phil = [w for w in PHIL_NOUNS if w in s]
        if hit_phil:
            r["phil"].append((s, hit_phil))
        hit_prob = [w for w in PROBLEM_VOCAB if w in s]
        if hit_prob:
            r["problem"].append((s, hit_prob))
        hit_meth = [w for w in METHOD_TERMS if w in s]
        if hit_meth:
            r["method"].append((s, hit_meth))
        subj = _ANTHRO_RE.search(s)
        if subj and any(v in s for v in ANTHRO_VERB):
            r["anthro"].append((s, subj.group(1)))
        hit_met = [w for w in METAPHOR_WATCH if w in s]
        if hit_met:
            r["metaphor"].append((s, hit_met))
    return r


def flag(val, lo, hi):
    if lo <= val <= hi:
        return "OK"
    if val < lo:
        return "LOW " + ("(강)" if val < lo * 0.6 else "(약)")
    return "HIGH " + ("(강)" if val > hi * 1.4 else "(약)")


def report(path, m):
    L = []
    L.append(f"## {path}")
    L.append("")
    L.append(f"- 문장 수 {m['n_sentences']} (짧은 초안일수록 대역 이탈 분산이 크다 — 참고용)")
    L.append("")
    L.append("### 1. 문장 리듬 (프로파일 §1)")
    L.append("")
    L.append("| 지표 | 측정 | 게재본 대역 | 판정 |")
    L.append("|---|---|---|---|")
    mb, md, cb = P["mean"], P["median"], P["commas"]
    L.append(f"| 평균 길이 | {m['mean']:.0f}자 | {mb[0]:g}~{mb[1]:g}자 | {flag(m['mean'], *mb)} |")
    L.append(f"| 중앙값 | {m['median']:.0f}자 | {md[0]:g}~{md[1]:g}자 | {flag(m['median'], *md)} |")
    L.append(f"| 쉼표/문장 | {m['commas']:.2f} | {cb[0]:g}~{cb[1]:g} | {flag(m['commas'], *cb)} |")
    names = ["≤40자(단문)", "41~70자(척추)", "71~100자", "101~130자", "131자~(만연)"]
    for name, pct, (lo, hi) in zip(names, m["buckets"], P["buckets"]):
        L.append(f"| {name} | {pct:.0f}% | {lo:g}~{hi:g}% | {flag(pct, lo, hi)} |")
    L.append(f"| 최장문 | {m['longest']}자 | ~180자 이하(증거 나열문만 장문) | {'OK' if m['longest'] <= 180 else 'HIGH'} |")
    L.append("")
    L.append("### 2. 어휘 지문 (문장 100개당, 프로파일 §2·§4·§5)")
    L.append("")
    L.append("| 항목 | 측정 | 대역 | 판정 |")
    L.append("|---|---|---|---|")
    if P.get("rhetq"):
        rq = P["rhetq"]
        L.append(f"| 수사의문 | {m['rhetq']:.1f} | {rq[0]:.1f}~{rq[1]:.1f} | {flag(m['rhetq'], *rq)} |")
    for name, (val, (lo, hi), sec) in m["lexical"].items():
        L.append(f"| {name} | {val:.1f} | {lo:.1f}~{hi:.1f} | {flag(val, lo, hi)} |")
    L.append("")
    L.append(f"- 계수 예고(첫째/둘째/셋째): {m['counting']}회 — 논증 전개형 글은 쓰고 고증·반박형 글은 0회일 수 있다. 장르 선택은 저자 몫(§5).")
    L.append("")
    L.append("### 3. 회피 표현 (게재본 실측 0회 항목)")
    L.append("")
    any_avoid = False
    for name, hits in m["avoid"].items():
        if hits:
            any_avoid = True
            L.append(f"- **{name}**: {len(hits)}회")
            for h in hits[:3]:
                L.append(f"  - 「{h[:60]}…」" if len(h) > 60 else f"  - 「{h}」")
    if not any_avoid:
        L.append("- 없음 (통과)")
    L.append("")
    L.append("### 3.5 레지스터·평이성 진단 (★말투 — register-rules ★절 기계화)")
    L.append("")
    L.append("> 리듬 대역과 **별개 축**. 저자는 평이하게 서술하는데 모델 기본값은 문학적(철학투·은유·의인화)으로 쏠린다 — 그 이탈을 잡는다. 전부 GC 후보(방법 문단 정의어·정치체 고유기능은 예외), 육안 확인·수선은 저자.")
    L.append("")
    reg = m["register"]
    total_flags = sum(len(reg[k]) for k in ("phil", "anthro", "metaphor", "problem"))
    if total_flags == 0:
        L.append("- 철학투·의인화·은유·문제화 어휘 후보: 없음 (통과)")
    else:
        if reg["phil"]:
            L.append(f"- **철학투 추상어**({len(reg['phil'])}) — 예고문·전환문·요약문의 뼈대면 구체어로. 「의인화 금지」 아님, 「철학투 추상어 금지」:")
            for s, ws in reg["phil"][:5]:
                L.append(f"  - [{'·'.join(ws)}] 「{s[:70]}…」" if len(s) > 70 else f"  - [{'·'.join(ws)}] 「{s}」")
        if reg["anthro"]:
            L.append(f"- **의인화 후보**({len(reg['anthro'])}, ⚠오탐 가능 — 정치체 고유기능은 허용) — 추상 주어+인격 동사. 「의인화 금지」:")
            for s, subj in reg["anthro"][:5]:
                L.append(f"  - [{subj}…] 「{s[:70]}…」" if len(s) > 70 else f"  - [{subj}…] 「{s}」")
        if reg["metaphor"]:
            L.append(f"- **은유·버릇말**({len(reg['metaphor'])}, 8절 watch-list — 한 글에 2회 넘으면 분산):")
            for s, ws in reg["metaphor"][:5]:
                L.append(f"  - [{'·'.join(ws)}] 「{s[:70]}…」" if len(s) > 70 else f"  - [{'·'.join(ws)}] 「{s}」")
        if reg["problem"]:
            L.append(f"- **문제화 렌즈 어휘**({len(reg['problem'])}, 격리 위반 후보) — _problematization.md 밖 유입 금지, 통상 언어로. 「문제화 렌즈 어휘 격리」:")
            for s, ws in reg["problem"][:5]:
                L.append(f"  - [{'·'.join(ws)}] 「{s[:70]}…」" if len(s) > 70 else f"  - [{'·'.join(ws)}] 「{s}」")
    if reg["method"]:
        L.append(f"- (참고) 방법어 '수렴/발산' {len(reg['method'])}회 — 방법 문단 정의 자리 1회는 허용, 그 밖은 구체어(§철학투).")
    if "para_n" in m:
        L.append("")
        L.append("### 4. 문단 아키텍처 (md 전용, 프로파일 §2)")
        L.append("")
        pn = m["para_n"]
        modal = statistics.mode(pn) if pn else 0
        L.append(f"- 문단 수 {len(pn)}, 문장수 최빈 {modal} (예시 게재본 최빈 4~6, 범위 2~7)")
        outliers = sum(1 for x in pn if x < 2 or x > 7)
        L.append(f"- 범위 밖(1문장 또는 8+) 문단: {outliers}개")
        L.append(f"- 판정 동사로 닫는 문단: {m['verdict_end']:.0f}% (게재본: '거의 예외 없이')")
        f_, m_, l_ = m["short_pos"]
        L.append(f"- 단문(≤40자) 위치: 문단 첫 {f_} / 중간 {m_} / 끝 {l_} — 게재본 규칙: 단문은 반박 피벗·매듭 판정문·개막 연타 세 자리에만(§1.2). 중간 단문이 많으면 자리를 검토.")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="저자 문체 실측 대조 (GC급 참고 — 하드 FAIL 없음)")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", help="리포트 md 저장 경로")
    ap.add_argument("--profile", help="voice-match 블록을 담은 프로파일 md (기본: references/style-profile-ko.md)")
    args = ap.parse_args()
    P.update(load_profile(args.profile))
    chunks = [
        "# voice_match 리포트 — 게재본 실측 대조 (전 항목 GC급 참고)",
        "",
        f"> 대역 출처: {P['source']}" + (f" (게재본 {P['n_papers']}편 기준)" if P.get("n_papers") else ""),
        "> 대역은 목표가 아니라 이탈 진단선이다. 수치를 맞추려 연결어·재진술을 삽입하지 않는다"
        " — 수치 안이어도 저자답지 않을 수 있고, 좋은 이탈도 있다. 판정·수선은 저자 게이트"
        "(문체 수선은 원고 완성 후 최종 윤문에서 일괄).",
        "",
    ]
    for f in args.files:
        p = Path(f)
        if p.suffix.lower() == ".pdf":
            paras, has_p = clean_pdf(p), False
        elif p.suffix.lower() == ".md":
            paras, has_p = clean_md(p.read_text(encoding="utf-8", errors="replace")), True
        else:
            paras, has_p = clean_txt(p.read_text(encoding="utf-8", errors="replace")), False
        m = measure(paras, has_p)
        if m is None:
            chunks.append(f"## {f}\n\n- 측정할 본문이 없음\n")
            continue
        chunks.append(report(f, m))
    out = "\n".join(chunks)
    print(out)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"\n[저장] {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
