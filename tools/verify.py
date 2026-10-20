#!/usr/bin/env python3
"""verify.py — history-research-harness 기계적 가드레일 + GC. 안 날조 척추를 '희망'에서 '강제'로.

가드레일(하드 FAIL):
  초고(04~08)가 화이트리스트 밖 P-키/표제 인용 · 原文 미완 카드 인용 · 파일 손상(NUL·제어문자)
  · 좌표 출처 공란(지리 날조) · 관찰 quote_ref 카드 미실재(인용문 날조)
  · 관계형 외래키 미등록 · 마스터 좌표 불일치.
GC(정보 — 실패 아님):
  orphan, 결손, 原文 미완, 확인 미해결(면수·전거·연대·[확인 필요]), 코드펜스 무결성,
  지리(표준 스키마 승급·약한 출처·[GAP:좌표]·노선 정박·도표 매니페스트),
  보유 자료 실재 대조(references/library/sources.txt의 tier1 폴더), 관계형 통계, 승급 후보, 수치 역추적.

구현 메모(리뷰에서 막은 우회들):
  utf-8-sig(BOM) 통일 · 서지 substring 우회 차단(정규화+길이 문턱) · 초고 글롭 07/08 포함
  · quote_ref verbatim 대조 · TITLE 볼드 오탐 제거 · GAP 마커를 原文미완·확인 카운트에 포함
  · 좌표 배열 가드.
"""
import os, re, glob, sys, csv, json
try: sys.stdout.reconfigure(encoding='utf-8')  # Windows cp949 콘솔에서 한글/em-dash 출력 보장
except Exception: pass
TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
try:
    import _libconfig as LIB  # sources.txt 파서 — library_index/library_search와 같은 해석을 공유
except Exception:
    LIB = None
PKEY = re.compile(r'P-\d{3}')
# [GAP:원문 …]도 原文 미완으로 집계
WON  = re.compile(r'\[[^\]]*?(?:원문|原文)\s*삽입|\[GAP:\s*(?:원문|原文)[^\]]*\]')
# 확인 미해결: [GAP:면수/전거/연대 …] + 구식 [확인 필요]·[…확인]·[…보강 필요] 변종.
# ([GAP:연대] = 연호·간지·역법 환산 미검증 — 면수·전거와 같은 "인용/게재 전 채울 것" 집계)
CHK  = re.compile(r'\[[^\]]*?확인(?:\s*필요)?\]|\[[^\]]*?보강 필요\]|\[GAP:\s*(?:면수|전거|연대)[^\]]*\]')
# 볼드(**…**) 내부를 표제로 오탐하지 않게 lookaround — *이탤릭 표제*와 『서명』만
TITLE = re.compile(r'(?<!\*)\*([^*\n]+)\*(?!\*)|『([^』\n]+)』')
GAPC = re.compile(r'\[GAP:\s*좌표\]')
WEAK = re.compile(r'통설|관례|추정|미상|불명|\?')
def read(p):
    try: return open(p, encoding='utf-8-sig', errors='ignore').read()
    except Exception: return ""
def csv_rows(p):
    """BOM 안전 CSV 읽기(utf-8-sig). 실패 시 None — BOM이 첫 열명을 오염시켜 가드레일이 통째로 skip되는 우회를 막는다."""
    try: return list(csv.DictReader(open(p, encoding='utf-8-sig', errors='ignore')))
    except Exception: return None
fails = []
def bytecheck(p, rel):
    try: d = open(p, 'rb').read()
    except Exception: return
    if b'\x00' in d: fails.append(f"{rel}: NUL 바이트 {d.count(bytes([0]))}개 — 파일 손상")
    ctrl = sum(1 for b in d if b < 9 or b in (11, 12) or 14 <= b <= 31)
    if ctrl: fails.append(f"{rel}: 제어문자 {ctrl}개 — 파일 손상 의심")
def drafts_of(d):
    """P-키 가드레일 대상 초고: 04~08(서론·본론·결론·초록). 화이트리스트류·매니페스트는 제외.
    (리뷰 수리: 구 글롭 0[456]은 결론 07·초록 08이 무검사 사각지대였다.)"""
    out = []
    for f in sorted(glob.glob(os.path.join(d, "0[45678]_*.md"))):
        b = os.path.basename(f).lower()
        if "whitelist" in b or b.endswith(".manifest.md"): continue
        out.append(f)
    return out
def scan(d):
    name = os.path.basename(d)
    wl = set(PKEY.findall(read(os.path.join(d, "02_sources_whitelist.md"))))
    cards = {}
    for f in sorted(glob.glob(os.path.join(d, "passages", "P-*.md"))):
        m = PKEY.search(os.path.basename(f)); t = read(f)
        if m: cards[m.group(0)] = {"won": len(WON.findall(t)), "chk": len(CHK.findall(t))}
    if not wl and not cards: return
    orphan = sorted(set(cards) - wl); missing = sorted(wl - set(cards))
    won_cards = sorted(k for k, c in cards.items() if c["won"])
    chk_cards = [k for k, c in cards.items() if c["chk"]]; nchk = sum(c["chk"] for c in cards.values())
    print(f"\n## {name}:  WL P-키 {len(wl)} · 카드 {len(cards)}")
    print(f"   [GC] orphan(카드>WL): {orphan or '없음'}")
    print(f"   [GC] 결손(WL>카드): {missing or '없음'}")
    print(f"   [GC] 原文 미완(인용 불가): {won_cards or '없음'}")
    print(f"   [GC] 카드 확인 미해결(면수·전거·연대·확인 필요): {len(chk_cards)}장 / {nchk}건")
    if missing: fails.append(f"{name}: WL이 가리키나 카드 없는 키 {missing}")
    for draft in drafts_of(d):
        txt = read(draft)
        cited = set(PKEY.findall(txt)); bad = sorted(cited - wl)
        empty = sorted(k for k in cited if cards.get(k, {}).get("won"))
        nchk_d = len(CHK.findall(txt)); ngapd = len(re.findall(r'\[GAP:\s*연대', txt))
        tail = f" · 확인 미해결 {nchk_d}건" + (f"(연대 {ngapd})" if ngapd else "") if nchk_d else ""
        print(f"   [가드레일] {os.path.basename(draft)}: 인용 {len(cited)}키{tail}")
        if bad: fails.append(f"{name}/{os.path.basename(draft)}: 화이트리스트 밖 인용 {bad} ← 날조 위험")
        if empty: fails.append(f"{name}/{os.path.basename(draft)}: 原文 미완 카드 인용 {empty}")
def _normt(s):
    """표제 대조 정규화: 공백·구두점 제거 + 소문자."""
    return re.sub(r"[\s·・:：,，.。'\"“”‘’()（）\[\]〈〉《》『』<>\-_/?!;；]", "", (s or "").lower())
def biblio(d):
    name = os.path.basename(d)
    reg = read(os.path.join(d, "03_biblio_whitelist.md"))
    if not reg: return
    registered = set(); t3 = 0
    for ln in reg.splitlines():
        s = ln.lstrip()
        if s[:3] in ("[T1", "[T2", "[T3"):
            if s.startswith("[T3"): t3 += 1
            for m in TITLE.finditer(ln): registered.add((m.group(1) or m.group(2)).strip())
    reg_norm = {_normt(r) for r in registered if _normt(r)}
    cited = {}
    for draft in drafts_of(d):
        for ln in read(draft).splitlines():
            if re.match(r'\[\^[^\]]+\]:', ln):
                for m in TITLE.finditer(ln):
                    tok = (m.group(1) or m.group(2)).strip(); cjk = m.group(2) is not None
                    if cjk or (re.match(r'[A-Z]', tok) and ' ' in tok): cited.setdefault(tok, os.path.basename(draft))
    def ok(t):
        """리뷰 수리: 구현이 `t in r or r in t`(무제한 substring)여서 한두 글자짜리 짧은 표제만
        등록해도 그 글자를 포함하는 긴 표제(예: 'X' 등록 → 'X新譯' 통과)가 빠져나가는 우회가 있었다.
        → 정규화 완전일치, 또는 짧은 쪽이 6자 이상일 때만 포함일치."""
        nt = _normt(t)
        if not nt: return True
        if nt in reg_norm: return True
        for nr in reg_norm:
            if min(len(nt), len(nr)) >= 6 and (nt in nr or nr in nt): return True
        return False
    unreg = sorted(t for t in cited if not ok(t))
    print(f"\n## {name} [서지 화이트리스트]:  등록 {len(registered)} · 각주 인용표제 {len(cited)} · T3 미확인 {t3}")
    if unreg: fails.append(f"{name}: 레지스트리 밖 서지 인용 {unreg} ← 가짜 서지 위험(확인 후 03_biblio_whitelist 등록)")
def _num(x):
    """노선 정점↔노드 대조용(2자리 반올림 매칭 — 설계상 의도)."""
    try: return round(float(x), 2)
    except Exception: return None
def _numx(x):
    """마스터 상속 대조용(반올림 없음 — 리뷰 수리: 2자리 반올림은 ~1km 오차를 통과시켰다)."""
    try: return float(x)
    except Exception: return None
def geo_scan(d):
    """지리 재현성: 좌표 출처 정박·표준 스키마·노선 정박·도표 매니페스트."""
    name = os.path.basename(d)
    nodes = {}      # (lon,lat) -> 출처 있음 여부
    noschema, weak = [], []
    gapcoord = 0
    for f in sorted(glob.glob(os.path.join(d, "*.csv"))):
        rel = os.path.basename(f)
        rows = csv_rows(f)
        if not rows: continue
        cols = {c.lower(): c for c in rows[0].keys() if c}
        if 'lon' not in cols or 'lat' not in cols: continue
        has_src = 'source' in cols
        nm = cols.get('name'); cc = cols.get('certainty')
        for i, r in enumerate(rows, 1):
            lon = _num(r.get(cols['lon'])); lat = _num(r.get(cols['lat']))
            if lon is None or lat is None: continue
            src = (r.get(cols['source']) if has_src else '') or ''
            label = (r.get(nm) if nm else '') or '?'
            if has_src and not src.strip():
                fails.append(f"{name}/{rel} 행{i}({label}): 좌표 출처 공란 ← 지리 날조 위험")
            nodes[(lon, lat)] = nodes.get((lon, lat), False) or bool(src.strip())
            cert = (r.get(cc) if cc else '') or ''
            if WEAK.search(src) or cert.strip().lower() == 'low':
                weak.append(f"{rel}:{label}({(cert or src[:14]).strip()})")
            if any(GAPC.search(str(v or '')) for v in r.values()): gapcoord += 1
        if not has_src: noschema.append(f"{rel}(source 열 없음)")
    for f in sorted(glob.glob(os.path.join(d, "*.geojson"))):
        rel = os.path.basename(f)
        try: gj = json.load(open(f, encoding='utf-8-sig', errors='ignore'))
        except Exception: continue
        for feat in (gj.get('features') or []):
            geom = feat.get('geometry') or {}; props = feat.get('properties') or {}
            if geom.get('type') == 'Point':
                c = geom.get('coordinates') or []
                if len(c) < 2: continue  # 리뷰 수리: 불완전 좌표 IndexError 가드
                lon = _num(c[0]); lat = _num(c[1])
                if lon is None: continue
                src = str(props.get('source', '') or '')
                if 'source' not in props: noschema.append(f"{rel}:{props.get('name','?')}(source 속성 없음)")
                nodes[(lon, lat)] = nodes.get((lon, lat), False) or bool(src.strip())
                if WEAK.search(src): weak.append(f"{rel}:{props.get('name','?')}({src[:14]})")
    unmatched = total_v = 0
    for f in sorted(glob.glob(os.path.join(d, "*.geojson"))):
        if 'smooth' in os.path.basename(f).lower(): continue
        try: gj = json.load(open(f, encoding='utf-8-sig', errors='ignore'))
        except Exception: continue
        for feat in (gj.get('features') or []):
            geom = feat.get('geometry') or {}
            if geom.get('type') == 'LineString':
                for pt in (geom.get('coordinates') or []):
                    if len(pt) < 2: continue  # 리뷰 수리: IndexError 가드
                    lon = _num(pt[0]); lat = _num(pt[1]); total_v += 1
                    if (lon, lat) not in nodes: unmatched += 1
    stems, nomani = set(), []
    for f in sorted(glob.glob(os.path.join(d, "fig*"))):
        b = os.path.basename(f)
        m = re.match(r'(fig\d+)', b)
        if not m or b.endswith(".manifest.md"): continue
        st = m.group(1)
        if st in stems: continue
        stems.add(st)
        if not os.path.exists(os.path.join(d, st + ".manifest.md")): nomani.append(st)
    if not (nodes or stems): return
    print(f"\n## {name} [지리 재현성]:  등록 좌표 {len(nodes)} · 도표 {len(stems)}")
    print(f"   [GC] 표준 스키마 승급 대상(출처 열/속성 없음): {noschema or '없음'}")
    print(f"   [GC] 약한 출처/저확신(확인·강등): {weak or '없음'}")
    print(f"   [GC] [GAP:좌표] 미해결: {gapcoord}건")
    print(f"   [GC] 노선 정점 중 등록 노드 밖(보간 제외 파일): {unmatched}/{total_v}")
    print(f"   [GC] 매니페스트 없는 도표: {nomani or '없음'}")
    if stems and not os.path.exists(os.path.join(d, "_provenance.md")) \
       and not os.path.exists(os.path.join(d, "observations.csv")):
        print(f"   [GC] 처리 이력 없음: _provenance.md 부재 — 도표 생성 결정의 기록 필요")
def relational_scan(d):
    """관계형 데이터층: 관찰-사건 외래키 무결성 + quote_ref verbatim 대조.
    리뷰 수리: 종전엔 P-키 '존재'만 봐 인용문 자체는 지어낼 수 있었다(결속이 연극).
    이제 quote_ref가 해당 카드 본문에 실재하는지 대조한다(공백 정규화, 강정규화 폴백)."""
    name = os.path.basename(d)
    obs = csv_rows(os.path.join(d, "observations.csv"))
    if obs is None: return  # 이 논문은 관계형층 미사용
    places = csv_rows(os.path.join(d, "places.csv")) or []
    occ = csv_rows(os.path.join(d, "obs_categories.csv")) or []
    cats = csv_rows(os.path.join(d, "categories.csv")) or []
    place_ids = {(r.get("place_id") or "").strip() for r in places}
    # 상태 3분법: confirmed(확정)/unresolved(미해결)/rejected(검토 후 배제). 배제된 장소를 관찰이 인용 = FAIL.
    rejected_pl = {(r.get("place_id") or "").strip() for r in places
                   if (r.get("status") or "").strip().lower() == "rejected"}
    st_cnt = {}
    for r in places:
        st = (r.get("status") or "").strip().lower() or "(미표시)"
        st_cnt[st] = st_cnt.get(st, 0) + 1
    cat_ids = {(r.get("cat_id") or "").strip() for r in cats}
    obs_ids = {(r.get("obs_id") or "").strip() for r in obs}
    card_txt = {}
    for f in glob.glob(os.path.join(d, "passages", "P-*.md")):
        m = PKEY.search(os.path.basename(f))
        if m: card_txt[m.group(0)] = re.sub(r"\s+", " ", read(f))
    hard = lambda s: re.sub(r"[^0-9A-Za-z㐀-鿿가-힣]", "", s.lower())
    qmiss = 0
    for r in obs:
        oid = r.get("obs_id", "?"); pid = (r.get("place_id") or "").strip(); pk = (r.get("p_key") or "").strip()
        if not pk or pk not in card_txt:
            fails.append(f"{name}/observations {oid}: p_key '{pk}' 카드 없음 ← 관찰이 사료에 미결속(날조 위험)")
            continue
        if pid and pid not in place_ids:
            fails.append(f"{name}/observations {oid}: place_id '{pid}' 미등록 ← 관계 무결성")
        if pid and pid in rejected_pl:
            fails.append(f"{name}/observations {oid}: 배제(rejected) 장소 '{pid}' 인용 ← 기각된 비정을 근거로 사용")
        q = re.sub(r"\s+", " ", (r.get("quote_ref") or "").strip())
        if q:
            if q not in card_txt[pk] and hard(q) not in hard(card_txt[pk]):
                qmiss += 1
                fails.append(f"{name}/observations {oid}: quote_ref가 {pk} 카드에 미실재 ← 인용문 날조 위험")
    for r in occ:
        if (r.get("obs_id") or "").strip() not in obs_ids: fails.append(f"{name}/obs_categories: obs_id '{r.get('obs_id')}' 미등록")
        if (r.get("cat_id") or "").strip() not in cat_ids: fails.append(f"{name}/obs_categories: cat_id '{r.get('cat_id')}' 미등록")
    gap_pl = sum(1 for r in places if not (r.get("lon") or "").strip())
    linked = {(r.get("place_id") or "").strip() for r in obs}
    orphan_pl = len(place_ids - linked); unused_cats = sorted(cat_ids - {(r.get("cat_id") or "").strip() for r in occ})
    print(f"\n## {name} [관계형 데이터층]:  관찰 {len(obs)} · 장소 {len(places)} · 범주 {len(cats)} · 링크 {len(occ)} · quote 대조 {len(obs)-qmiss}/{len(obs)}")
    print(f"   [GC] 좌표 없는 장소([GAP:좌표]): {gap_pl} · 관찰 미연결 장소: {orphan_pl}")
    print(f"   [GC] 미사용 범주: {unused_cats or '없음'}")
    print(f"   [GC] 장소 상태(3분법): " + " · ".join(f"{k} {v}" for k, v in sorted(st_cnt.items())))
    # 처리 이력: AI 파생 산출물이 있는데 _provenance.md가 없으면 GC(기록되지 않은 결정은 검토될 수 없다)
    if not os.path.exists(os.path.join(d, "_provenance.md")):
        print(f"   [GC] 처리 이력 없음: _provenance.md 부재 — 파생 산출물의 결정 기록 필요(양식 corpus/_provenance-template.md)")
# '장'은 章 상호참조("2장은…") 오탐으로 제외(카드 매수는 건·개로 센다) · '개월'은 기간이라 제외
NUMQ = re.compile(r'([0-9][0-9,]*(?:\.[0-9]+)?)\s*(건|곳|명|편|회|개(?!월)|점|척|%|퍼센트)')
def numeric_scan(d):
    """수치 역추적: 초고(04~08)와 투고 계열 원고([12][0-9]_*draft*.md)의 수량 주장이
    증거층(카드·CSV·매니페스트·화이트리스트·상류 문서·처리 이력)으로 역추적되는가.
    전형적 실패는 "문장은 참인데 결속이 끊긴" 수치다. 거짓 FAIL로 살아있는 논문을 막지 않도록
    GC — 하드 승격은 저자 결정.
    ⚠ 자기 중화 금지: CLAUDE.md는 증거층에 넣지 않는다 — 적발 사례를 운용 기록에 숫자로
    적는 순간 그 기록이 증거가 되어 같은 적발이 영구히 꺼진다.
    한계(기록): 단위 없는 비율(예: 19/57)은 미탐 · 결속은 단위 불문 문자열 일치(GC 수준)."""
    drafts = list(drafts_of(d))
    for f in sorted(glob.glob(os.path.join(d, "[12][0-9]_*draft*.md"))):
        b = os.path.basename(f).lower()
        if "whitelist" in b or "리포트" in b or "report" in b or b.endswith(".manifest.md"): continue
        drafts.append(f)
    if not drafts: return
    name = os.path.basename(d)
    ev = []
    for pat in ("passages/P-*.md", "*.csv", "*.manifest.md", "0[0123]_*.md",
                "_provenance.md", "_meta.md", "glossary.md"):
        for f in glob.glob(os.path.join(d, pat)): ev.append(read(f))
    evidence = "\n".join(ev)  # 원문 그대로 — 일괄 콤마 스트립은 CSV 열 경계를 병합시킨다
    def bound(n):
        forms = {n}
        if n.isdigit() and len(n) > 3: forms.add("{:,}".format(int(n)))  # 천 단위 표기 변형도 인정
        return any(re.search(r'(?<![\d.])' + re.escape(x) + r'(?![\d.])', evidence) for x in forms)
    total = 0; miss = []
    for draft in drafts:
        for ln in read(draft).splitlines():
            if re.match(r'\[\^[^\]]+\]:', ln): continue
            for m in NUMQ.finditer(ln):
                total += 1
                if not bound(m.group(1).replace(",", "")):
                    miss.append(f"{os.path.basename(draft)}: {m.group(1)}{m.group(2)}")
    if not total: return
    uniq = sorted(set(miss))
    shown = uniq[:12]
    tail = f" 외 {len(uniq)-12}건" if len(uniq) > 12 else ""
    print(f"\n## {name} [수치 역추적]:  수량 주장 {total} · 증거층 결속 {total-len(miss)} · 미결속 {len(miss)}")
    print(f"   [GC] 증거층 미결속 수치(확인·결속 요): {shown or '없음'}{tail}")
def _load_gazetteer_master():
    p = os.path.join(ROOT, "corpus", "gazetteer-master.csv")
    try: lines = [l for l in open(p, encoding="utf-8-sig") if not l.lstrip().startswith("#")]
    except Exception: return None
    m = {}
    for r in csv.DictReader(lines):
        gm = (r.get("gm_id") or "").strip()
        if gm: m[gm] = (r.get("name", ""), _numx(r.get("lon")), _numx(r.get("lat")))
    return m
GAZM = _load_gazetteer_master()
def _master_categories():
    txt = read(os.path.join(ROOT, "references", "perception-categories.md"))
    names, insec1 = set(), False
    for ln in txt.splitlines():
        if ln.startswith("## 1."): insec1 = True; continue
        if ln.startswith("## 2."): insec1 = False; continue
        if insec1 and ln.startswith("|") and "cat_id" not in ln and "---" not in ln:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[1]: names.add(cells[1])
    return names
PMASTER = _master_categories()
def master_scan(d):
    """승급층: 논문 places.gm_id ↔ 마스터 게이지티어 정합(무반올림) + 범주 승급 후보."""
    if GAZM is None: return
    name = os.path.basename(d)
    places = csv_rows(os.path.join(d, "places.csv"))
    if places is None: return
    linked = promote_pl = partial = 0
    for r in places:
        gm = (r.get("gm_id") or "").strip()
        lon = _numx(r.get("lon")); lat = _numx(r.get("lat"))
        if gm:
            linked += 1
            if gm not in GAZM:
                fails.append(f"{name}/places {r.get('place_id')}: gm_id '{gm}' 마스터에 없음 ← 상속 링크 파손")
            elif lon is not None and lat is not None:
                if (lon, lat) != (GAZM[gm][1], GAZM[gm][2]):
                    fails.append(f"{name}/places {r.get('place_id')}({r.get('name')}): 좌표 {lon},{lat} ≠ 마스터 {gm} ← 마스터 불일치")
            elif lon is not None or lat is not None:
                partial += 1  # 리뷰 수리: lon/lat 한쪽만 있는 행을 불일치 FAIL로 오판하지 않음(데이터 결손 GC)
        elif lon is not None and lat is not None:
            promote_pl += 1
    cats = csv_rows(os.path.join(d, "categories.csv")) or []
    promote_cat = sorted(r.get("name", "") for r in cats
                         if (r.get("scope", "").strip() == "common") and r.get("name", "") not in PMASTER)
    print(f"\n## {name} [승급층]:  마스터 {len(GAZM)} · 상속 링크 {linked} · 좌표 승급후보 {promote_pl} · 좌표 결손(부분) {partial}")
    print(f"   [GC] 범주 승급 후보(common 미등재): {promote_cat or '없음'}")
def integ(rel):
    t = read(os.path.join(ROOT, rel))
    if t and t.count("```") % 2: fails.append(f"{rel}: 코드펜스 불균형(잘림 의심)")

# ── 보유 자료 실재 대조 ──────────────────────────────────────────────────────
# 03_biblio_whitelist.md의 [T1/T2/T3] 줄이 파일명(…pdf/md 등)을 선언하면, 그 파일이
# references/library/sources.txt의 tier1 폴더에 실재하는지 본다(GC — 선언만 있고 파일이
# 없으면 "갖고 있다"는 주장이 검증되지 않은 것). 폴더 해석은 tools/_libconfig.py와 같다.
HOLD_EXT = (".pdf", ".md", ".txt", ".docx", ".hwp", ".hwpx")
HOLD_DECL = re.compile(r"([^\s—()+\[\]`]+\.(?:pdf|md|txt|docx|hwpx?))\b", re.I)
def _holdings_index():
    """(색인 집합 | None, 안내문). None이면 대조 생략."""
    if LIB is None:
        return None, "tools/_libconfig.py를 불러오지 못함 — 보유 자료 대조 생략"
    if not LIB.has_config():
        return None, (f"{LIB.CONFIG_REL} 없음 — 보유 자료 실재 대조 생략(선택 기능, 양식: {LIB.EXAMPLE_REL})")
    entries = LIB.tier1_entries()
    roots = [full for _, full, ok in entries if ok]
    absent = [raw for raw, _, ok in entries if not ok]
    if not roots:
        why = f"설정된 폴더 없음: {absent}" if absent else "tier1 줄 없음"
        return None, f"{LIB.CONFIG_REL}에 실재하는 tier1 폴더가 없음({why}) — 보유 자료 실재 대조 생략"
    idx = set()
    for base in roots:
        for root, _, fs in os.walk(base):
            for f in fs:
                if f.lower().endswith(HOLD_EXT): idx.add(f.lower())
    note = f"tier1 폴더 {len(roots)}곳 · 파일 {len(idx)}" + (f" · 미실재 폴더 {absent}" if absent else "")
    return idx, note
HIDX, HNOTE = _holdings_index()
def holdings_has(fname):
    """선언 파일명이 tier1 폴더에 실재하는가. 약칭 흡수: 5자+ 부분일치."""
    if HIDX is None: return None
    fl = fname.lower()
    if fl in HIDX: return True
    stem = fl.rsplit(".", 1)[0]
    if len(stem) >= 5:
        for g in HIDX:
            if stem in g or g.rsplit(".", 1)[0] in stem: return True
    return False
def holdings_scan(d):
    """절대 원칙 3중: whitelist 표제가 선언한 보유 파일이 tier1 폴더에 실재하는가(GC)."""
    if HIDX is None: return
    reg = read(os.path.join(d, "03_biblio_whitelist.md"))
    if not reg: return
    name = os.path.basename(d)
    decl = found = 0; missing = []
    for ln in reg.splitlines():
        if ln.lstrip()[:3] not in ("[T1", "[T2", "[T3"): continue
        fs = HOLD_DECL.findall(ln)
        if not fs: continue
        decl += 1
        if any(holdings_has(f) for f in fs): found += 1
        else:
            m = TITLE.search(ln); missing.append((m.group(1) or m.group(2)).strip() if m else ln.lstrip()[:24])
    if not decl: return
    print(f"\n## {name} [보유 자료 실재]:  {HNOTE} · 파일선언 {decl} · 실재확인 {found} · 미확인 {len(missing)}")
    if missing: print(f"   [GC] 선언했으나 tier1 폴더에 미실재(확인 요): {missing}")

print("=== history-research-harness 기계 점검 (verify.py) ===")
if HIDX is None: print(f"[GC] {HNOTE}")
SKIP_WORKSPACE_DIRS = {"_external_cache"}
for d in sorted(glob.glob(os.path.join(ROOT, "_workspace", "*"))):
    if os.path.basename(d) in SKIP_WORKSPACE_DIRS:
        continue
    if os.path.isdir(d): scan(d); biblio(d); geo_scan(d); holdings_scan(d); relational_scan(d); master_scan(d); numeric_scan(d)
for f in glob.glob(os.path.join(ROOT, "_workspace", "**", "*.md"), recursive=True):
    rel_parts = os.path.relpath(f, os.path.join(ROOT, "_workspace")).split(os.sep)
    if rel_parts and rel_parts[0] in SKIP_WORKSPACE_DIRS:
        continue
    bytecheck(f, os.path.relpath(f, ROOT))
# 규범 문서 무결성(코드펜스 균형·손상 바이트). 부재 파일은 FAIL이 아니다(read()가 ""를 돌려 건너뜀).
INTEGRITY = ["CLAUDE.md", "README.md", "AGENTS.md", "Claude-History.md", "research-profile.md",
             ".claude/skills/집필/SKILL.md", ".claude/skills/심사/SKILL.md", ".claude/skills/윤문/SKILL.md",
             ".claude/skills/DB/SKILL.md", ".claude/skills/시각화/SKILL.md",
             ".claude/agents/question-sharpener.md", ".claude/agents/source-verifier.md",
             ".claude/agents/structure-architect.md", ".claude/agents/prose-writer.md",
             ".claude/agents/intro-reconciler.md", ".claude/agents/citation-auditor.md",
             ".claude/agents/peer-reviewer.md",
             "corpus/_review-template.md"]
absent_integ = []
for rel in INTEGRITY:
    if not os.path.exists(os.path.join(ROOT, rel)): absent_integ.append(rel); continue
    integ(rel); bytecheck(os.path.join(ROOT, rel), rel)
if absent_integ:
    print(f"\n[GC] 무결성 점검 대상 {len(INTEGRITY)}개 중 부재 {len(absent_integ)}개: {absent_integ[:6]}"
          + (f" 외 {len(absent_integ)-6}개" if len(absent_integ) > 6 else ""))
if not (os.path.exists(os.path.join(ROOT, "environment.yml")) or
        os.path.exists(os.path.join(ROOT, "requirements.txt"))):
    print("\n[GC] 환경 lockfile 없음 — 지도 재현 불가 위험(environment.yml 권장)")
print("\n=== 결과 ===")
if fails:
    print("하드 FAIL:"); [print("   -", x) for x in fails]; sys.exit(1)
print("하드 FAIL 없음 (면수·전거·연대 확인 미해결과 [GAP:좌표]는 알려진 작업분 — 인용/게재 전 채울 것)")
