# -*- coding: utf-8 -*-
"""
md2hwpx.py — 한국어 학술 원고(Markdown) → 투고 스타일 HWPX 변환기 (v1.2)

원리
  투고 양식 .hwpx(템플릿)의 header.xml(글자·문단 스타일 정의)은 그대로 두고,
  Contents/section0.xml(본문)만 원고 내용으로 교체한다. 페이지·각주 설정(secPr)과
  머리말·꼬리말(hp:header/hp:footer)은 템플릿 첫 문단에서 복사·재주입한다. 스타일 ID는
  템플릿 header의 **스타일 이름**(바탕글·제목·중제목·소제목·각주·인용문·큰제목·이름)으로
  자동 해석하므로, 같은 이름 체계를 쓰는 투고 양식이면 학술지를 가리지 않는다.

템플릿
  투고지의 hwpx 양식은 저장소에 들어 있지 않다(학술지 배포 파일 — 재배포 금지일 수 있음).
  저자가 투고지 홈페이지에서 받은 양식을 `--template`으로 지정한다(필수). 로컬에 보관하려면
  references/hwpx-templates/ 같은 git 밖 폴더에 둔다.

절대 원칙 (history-research-harness 상속 — 위반 금지)
  - 이 도구는 **순수 구조 변환기**다. 사료·전거·번역·자구를 만들거나 고치지 않는다.
    (머리말도 템플릿 원문을 **복사**만 한다 — 텍스트를 짓거나 고치지 않는다.)
  - 원본 md와 템플릿은 **읽기만** 한다(무수정).
  - `[GAP:...]` 등 불확실성 마커는 **그대로 보존**한다.
  - 처리 못 하는 md 요소(이미지·굵게·목록 등)는 **조용히 버리지 않고 경고**한다.
  - 산출물은 **AI 잠정 라벨**을 파일명·리포트에 단다. 저자 게이트 대상이다.

내장 자기검증 (하네스 차단력)
  변환 후 산출물을 다시 열어 본문·각주·표 셀을 md와 대조하고, 파서와 무관한 불변식
  (별표 보존·각주 번호 연속·secPr 위치·머리말 보존·마크다운 잔존·GAP 수)을 함께 확인한다.
  하나라도 어긋나면 FAIL(코드 1)로 종료하고 산출물을 신뢰하지 않는다.

도구 변경 내역
  v1.2  머리말·꼬리말(hp:header/hp:footer) 보존 — 템플릿 section0의 머리말 컨트롤을 추출해 첫
        문단에 재주입(머리말 텍스트는 템플릿 원문 그대로 = 투고지 고유값, 저자 확인) ·
        md 표(| a | b |) → OWPML 표(hp:tbl) 변환(테두리 borderFill 자동 탐색·열 너비 균등분할·
        셀 텍스트는 이탤릭/각주 처리) · 자기검증에 머리말 개수 대조·표 셀 텍스트 대조 추가.
  v1.1  (적대 검증 반영) secPr 첫 문단 무조건 부착 · 이탤릭 flanking 규칙(별표 소실 방지)
        · 별표 보존 불변식 · 각주 정의/제목/인용문까지 미처리 스캔 · '바탕글' 부재 안전 폴백
        · 임의 각주 라벨 · 저자행 키워드 요구 · charPr 단일패스 파싱 · 인용문 각주·이탤릭 처리
        · secpr 텍스트 제거 · 각주 styleIDRef 교정 · html.unescape · HTML 오경고 제거 · h1~h6
        · 각주 번호 검증.

사용
  python tools/md2hwpx.py <원고.md> --template <투고지양식.hwpx> [--out O.hwpx] [--report R.md]
  산출물 기본 이름: <원고>_투고스타일_AI잠정.hwpx (+ _hwpx변환리포트_<원고>.md)
"""
import argparse
import datetime
import hashlib
import html
import io
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

TOOL_VERSION = '1.2'

ROLE_STYLE_NAME = {
    'title': '큰제목', 'author': '이름', 'chapter': '제목', 'section': '중제목',
    'subsection': '소제목', 'body': '바탕글', 'blockquote': '인용문', 'footnote': '각주',
}

# 이탤릭: CommonMark flanking 근사 — 여는 *는 비공백이 뒤따르고, 닫는 *는 비공백이 앞서며,
# **(굵게)나 홀로 뜬 *(재구형 마커 등)는 소비하지 않는다.
ITALIC_RE = re.compile(r'(?<!\*)\*(?=\S)([^*]+?)(?<=\S)\*(?!\*)')

# 각주 라벨: 숫자뿐 아니라 임의 라벨 허용([^ibid] 등)
FN_REF_RE = re.compile(r'\[\^([^\]]+)\]')
FN_DEF_RE = re.compile(r'^\[\^([^\]]+)\]:\s?(.*)$')

# 표(table): 앞뒤가 |로 감싸인 라인 = 표행, 대시·콜론뿐인 셀 = 구분행
TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
TABLE_DELIM_CELL_RE = re.compile(r'^:?-{1,}:?$')

# 머리말·꼬리말 컨트롤: <hp:ctrl><hp:header ...>...</hp:header></hp:ctrl> (footer 동일).
# header/footer는 서로 중첩되지 않으므로 비탐욕 매칭으로 하나씩 잡힌다(내부 autoNum ctrl 포함).
HEADER_FOOTER_CTRL_RE = re.compile(r'<hp:ctrl>\s*<hp:(header|footer)\b.*?</hp:\1>\s*</hp:ctrl>', re.S)

# 처리하지 못하는(→ 경고) md 요소 (라인 단위, HTML은 안전 이스케이프되므로 제외).
# 표는 v1.2부터 hp:tbl로 변환하므로 여기서 제외(굵게·이미지·코드 등 셀 안 인라인 요소는 여전히 스캔됨).
UNHANDLED_LINE = [
    ('이미지(image)', re.compile(r'!\[[^\]]*\]\([^)]*\)')),
    ('굵게(bold **)', re.compile(r'\*\*')),
    ('목록(list)', re.compile(r'^\s*([-+]|\d+\.)\s+\S')),
    ('인라인코드(`)', re.compile(r'`[^`]+`')),
    ('5·6수준 제목', re.compile(r'^#{5,6}\s')),
]


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def sha256_file(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def unpaired_stars(text):
    return text.count('*') - 2 * len(ITALIC_RE.findall(text))


# ── 표(table) 파싱 도우미 ─────────────────────────────────
def split_table_row(s):
    """'| a | b |' -> ['a','b']. 이스케이프된 '\\|'는 리터럴 '|'로 복원."""
    s = s.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    cells = re.split(r'(?<!\\)\|', s)
    return [c.strip().replace('\\|', '|') for c in cells]


def is_delim_row(s):
    """'|---|:--:|' 같은 표 구분행인가(대시·콜론뿐인 셀로만 이뤄짐)."""
    if not TABLE_ROW_RE.match(s):
        return False
    cells = split_table_row(s)
    return bool(cells) and all(TABLE_DELIM_CELL_RE.match(c) for c in cells)


def elem_text_chunks(elements):
    """요소 목록에서 텍스트 조각을 평탄화(표 셀 포함) — 별표·GAP 스캔 공용."""
    for kind, payload in elements:
        if kind == 'table':
            for row in payload:
                for cell in row:
                    yield cell
        else:
            yield payload


# ── 템플릿 스타일 해석 ───────────────────────────────────
def load_template(path):
    z = zipfile.ZipFile(path)
    header = z.read('Contents/header.xml').decode('utf-8')
    section = z.read('Contents/section0.xml').decode('utf-8')

    styles = {}  # name -> (paraPrIDRef, charPrIDRef, styleId)
    for m in re.finditer(r'<hh:style ([^>]*?)/?>', header):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if a.get('name'):
            styles[a['name']] = (a.get('paraPrIDRef'), a.get('charPrIDRef'), a.get('id'))

    # charPr: self-closing과 컨테이너를 단일 패스로 (self-closing이 뒤 요소를 삼키지 않게)
    charprs = {}  # id -> (height, italic)
    for m in re.finditer(r'<hh:charPr id="(\d+)"([^>]*?)(?:/>|>(.*?)</hh:charPr>)', header, re.S):
        cid, attrs, body = m.group(1), m.group(2), (m.group(3) or '')
        h = re.search(r'height="(\d+)"', attrs)
        charprs[cid] = (int(h.group(1)) if h else 1000, '<hh:italic/>' in body)
    return z, header, section, styles, charprs


def resolve_roles(styles, charprs, warnings):
    # 바탕글 부재 시 안전 폴백: 첫 스타일 또는 ('0','0','0')
    if '바탕글' in styles:
        body_fallback = styles['바탕글']
    elif styles:
        any_name = next(iter(styles))
        body_fallback = styles[any_name]
        warnings.append(f'스타일 "바탕글" 없음 → "{any_name}"로 폴백')
    else:
        body_fallback = ('0', '0', '0')
        warnings.append('템플릿에 스타일 정의가 없음 → 기본 ID(0)로 폴백')

    roles = {}
    for role, name in ROLE_STYLE_NAME.items():
        if name in styles:
            para, char, sid = styles[name]
        else:
            warnings.append(f'스타일 "{name}"({role}) 없음 → 바탕글로 대체')
            para, char, sid = body_fallback
        roles[role] = {'para': para, 'char': char, 'style': sid or '0'}

    italic_ids = [(cid, h) for cid, (h, it) in charprs.items() if it]

    def italic_for(base_char):
        if base_char not in charprs or not italic_ids:
            return None
        base_h = charprs[base_char][0]
        return min(italic_ids, key=lambda x: abs(x[1] - base_h))[0]

    for r in ('body', 'footnote', 'blockquote'):
        roles[r]['italic'] = italic_for(roles[r]['char'])
    if roles['body']['italic'] is None:
        warnings.append('이탤릭 글자모양 없음 → 이탤릭(*..*)은 일반 글자로 처리')
    return roles


# ── Markdown 파싱 ────────────────────────────────────────
def parse_md_text(raw, warnings):
    """raw(주석 제거 전 문자열) -> (elements, defs). 경고를 warnings에 적재."""
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    lines = raw.split('\n')

    # 1) 각주 정의 수집 — 들여쓰기된 줄만 이어붙임(표준 md), 빈 줄 없이 붙은 본문은 경고
    defs = {}
    body_lines = []
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        s = raw_line.rstrip()
        m = FN_DEF_RE.match(s)
        if m:
            label, buf = m.group(1), [m.group(2).strip()]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    break
                if FN_DEF_RE.match(nxt.rstrip()) or re.match(r'^#{1,6}\s', nxt) or nxt.strip() == '---':
                    break
                if re.match(r'^\s+\S', nxt):          # 들여쓰기 → 각주 이어짐
                    buf.append(nxt.strip()); i += 1; continue
                warnings.append(f'각주 [^{label}] 정의 뒤 빈 줄 없이 본문 — 본문으로 처리: {nxt.strip()[:40]}')
                break
            defs[label] = ' '.join(x for x in buf if x)
            continue
        body_lines.append((i + 1, s))
        i += 1

    # 2) 미처리 요소 스캔 — 각주 정의·제목·인용문 포함 전 라인 대상
    for lineno in range(len(lines)):
        s = lines[lineno]
        if s.strip() == '---':
            continue
        for kind, pat in UNHANDLED_LINE:
            if pat.search(s):
                warnings.append(f'[미처리 {kind}] {lineno + 1}행: {s.strip()[:50]}')

    # 3) 본문 요소 목록화 (표는 여러 줄이므로 인덱스 기반으로 앞을 내다봄)
    elements = []
    k = 0
    while k < len(body_lines):
        lineno, s = body_lines[k]
        st = s.strip()
        if not st or st == '---':
            k += 1
            continue
        # 표: 현재 행이 표행이고 바로 다음 행이 구분행이면 표 블록으로 소비
        if (TABLE_ROW_RE.match(s) and k + 1 < len(body_lines)
                and is_delim_row(body_lines[k + 1][1])):
            header_cells = split_table_row(s)
            ncol = len(header_cells)
            rows = [header_cells]
            j = k + 2                       # 구분행 건너뜀
            while j < len(body_lines):
                s2 = body_lines[j][1]
                if not s2.strip() or not TABLE_ROW_RE.match(s2):
                    break
                cells = split_table_row(s2)
                if len(cells) != ncol:
                    warnings.append(f'표 행 열수 불일치({len(cells)}≠{ncol}) — 채움/자름: {s2.strip()[:40]}')
                    cells = (cells + [''] * ncol)[:ncol]
                rows.append(cells)
                j += 1
            elements.append(('table', rows))
            k = j
            continue
        # 표행처럼 보이나 구분행이 없음 → 경고 후 본문 문단으로 보존(내용 무손실)
        if TABLE_ROW_RE.match(s):
            warnings.append(f'[미처리 표(구분행 없음)] {lineno}행: {st[:50]}')
            elements.append(('para', st))
            k += 1
            continue
        if re.match(r'^##\s+각주\s*$', s):
            k += 1
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', s)
        if m:
            level = len(m.group(1))
            kind = {1: 'title', 2: 'chapter', 3: 'section'}.get(level, 'subsection')
            elements.append((kind, m.group(2).strip()))
            k += 1
            continue
        if s.lstrip().startswith('>'):
            elements.append(('blockquote', re.sub(r'^\s*>\s?', '', s)))
            k += 1
            continue
        # 제목 직후의 [저자/소속] 한 줄만 author (GAP·편집주 오분류 방지)
        if (re.match(r'^\[[^\]]*\]$', st) and elements and elements[-1][0] == 'title'
                and re.search(r'저자|소속|author', st, re.I)):
            elements.append(('author', st))
            k += 1
            continue
        elements.append(('para', st))
        k += 1

    # 4) 별표 불균형 경고 (이탤릭 짝이 안 맞거나 굵게) — 표 셀 포함 평탄화
    for txt in elem_text_chunks(elements):
        if unpaired_stars(txt) > 0:
            warnings.append(f'[별표(*) 불균형/굵게] {txt[:40]}')
    for lab, txt in defs.items():
        if unpaired_stars(txt) > 0:
            warnings.append(f'[별표(*) 불균형/굵게] 각주^{lab}: {txt[:40]}')

    # 5) 라벨이 숫자 아닌 각주 알림(지원은 하되 저자 확인용)
    nonnum = [l for l in defs if not l.isdigit()]
    if nonnum:
        warnings.append('숫자 아닌 각주 라벨: ' + ', '.join(f'^{l}' for l in nonnum))
    return elements, defs


def parse_md(path, warnings):
    return parse_md_text(open(path, encoding='utf-8').read(), warnings)


# ── run/문단 조립 ────────────────────────────────────────
def italic_runs(text, char_normal, char_italic):
    out, pos = [], 0
    if char_italic:
        for m in ITALIC_RE.finditer(text):
            if m.start() > pos:
                out.append((char_normal, text[pos:m.start()]))
            out.append((char_italic, m.group(1)))
            pos = m.end()
    if pos < len(text):
        out.append((char_normal, text[pos:]))
    return [(c, t) for c, t in out if t]


def runs_xml(pairs):
    return ''.join(f'<hp:run charPrIDRef="{c}"><hp:t>{esc(t)}</hp:t></hp:run>' for c, t in pairs)


class Builder:
    def __init__(self, roles):
        self.roles = roles
        self.fn_no = 0
        self.fn_map = []
        self.missing = []
        self.tbl_no = 0

    def footnote(self, label, defs, anchor_char):
        self.fn_no += 1
        n = self.fn_no
        self.fn_map.append((n, label))
        text = defs.get(label)
        if text is None:
            self.missing.append(label)
            text = f'[GAP:각주정의누락 ^{label}]'
        fr = self.roles['footnote']
        pairs = italic_runs(text, fr['char'], fr.get('italic'))
        autofmt = ('<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" '
                   'suffixChar=")" supscript="0"/>')
        fn_para = (
            f'<hp:p id="0" paraPrIDRef="{fr["para"]}" styleIDRef="{fr["style"]}" '
            f'pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{fr["char"]}"><hp:ctrl>'
            f'<hp:autoNum num="{n}" numType="FOOTNOTE">{autofmt}</hp:autoNum>'
            f'</hp:ctrl><hp:t> </hp:t></hp:run>' + runs_xml(pairs) + '</hp:p>')
        return (
            f'<hp:run charPrIDRef="{anchor_char}"><hp:ctrl>'
            f'<hp:footNote number="{n}" instId="{2000000000 + n}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
            f'vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" '
            f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            + fn_para + '</hp:subList></hp:footNote></hp:ctrl></hp:run>')

    def inline(self, text, role_key, defs):
        """각주 참조 + 이탤릭을 처리한 run 열."""
        r = self.roles[role_key]
        out, pos = [], 0
        for m in FN_REF_RE.finditer(text):
            if m.start() > pos:
                out.append(runs_xml(italic_runs(text[pos:m.start()], r['char'], r.get('italic'))))
            out.append(self.footnote(m.group(1), defs, r['char']))
            pos = m.end()
        if pos < len(text):
            out.append(runs_xml(italic_runs(text[pos:], r['char'], r.get('italic'))))
        return ''.join(out)

    def para(self, role_key, inner):
        r = self.roles[role_key]
        return (f'<hp:p id="0" paraPrIDRef="{r["para"]}" styleIDRef="{r["style"]}" '
                f'pageBreak="0" columnBreak="0" merged="0">{inner}</hp:p>')

    def plain(self, role_key, text):
        r = self.roles[role_key]
        return self.para(role_key, f'<hp:run charPrIDRef="{r["char"]}"><hp:t>{esc(text)}</hp:t></hp:run>')

    def empty(self):
        r = self.roles['body']
        return self.para('body', f'<hp:run charPrIDRef="{r["char"]}"><hp:t></hp:t></hp:run>')

    def table(self, rows, defs, text_width, grid_border):
        """md 표(list[list[str]]) → OWPML hp:tbl. 셀 텍스트는 본문과 같은 인라인 처리
        (이탤릭·각주). 표는 문단 안 run에 treatAsChar로 담긴다. 자구는 만들지 않는다."""
        r = self.roles['body']
        char = r['char']
        self.tbl_no += 1
        tbl_id = 1000000000 + self.tbl_no   # 도형 객체 고유 id(문단 id=0·각주 instId와 겹치지 않게)
        ncol = max((len(row) for row in rows), default=1) or 1
        nrow = len(rows)
        base = text_width // ncol
        widths = [base] * ncol
        widths[-1] += text_width - base * ncol   # 나머지는 마지막 열에 몰아 합을 정확히 맞춤
        row_h = 834                              # 초기 높이(한글이 내용에 맞춰 재계산)
        out = [
            f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
            f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="NONE" '
            f'repeatHeader="1" rowCnt="{nrow}" colCnt="{ncol}" cellSpacing="0" '
            f'borderFillIDRef="{grid_border}" noAdjust="0">'
            f'<hp:sz width="{sum(widths)}" widthRelTo="ABSOLUTE" height="{row_h * nrow}" '
            f'heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
            f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
            f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:inMargin left="140" right="140" top="140" bottom="140"/>']
        for ri in range(nrow):
            out.append('<hp:tr>')
            row = rows[ri]
            for ci in range(ncol):
                cell = row[ci] if ci < len(row) else ''
                inner = self.inline(cell, 'body', defs) if cell.strip() else ''
                if not inner:                    # 빈 셀도 run 하나는 있어야 유효
                    inner = f'<hp:run charPrIDRef="{char}"/>'
                cell_p = (f'<hp:p id="0" paraPrIDRef="{r["para"]}" styleIDRef="{r["style"]}" '
                          f'pageBreak="0" columnBreak="0" merged="0">{inner}</hp:p>')
                out.append(
                    f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
                    f'dirty="0" borderFillIDRef="{grid_border}">'
                    f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                    f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
                    f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                    f'{cell_p}</hp:subList>'
                    f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri}"/>'
                    f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                    f'<hp:cellSz width="{widths[ci]}" height="{row_h}"/>'
                    f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
                    f'</hp:tc>')
            out.append('</hp:tr>')
        out.append('</hp:tbl>')
        tbl_xml = ''.join(out)
        # 표는 문단 안 run에 담고(treatAsChar), 뒤에 빈 <hp:t/>를 둔다(템플릿 실물 구조)
        return (f'<hp:p id="0" paraPrIDRef="{r["para"]}" styleIDRef="{r["style"]}" '
                f'pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="{char}">{tbl_xml}<hp:t></hp:t></hp:run></hp:p>')


def extract_secpr_run(section):
    """템플릿 첫 문단의 secPr run을 뽑되, 혹시 든 본문 텍스트(<hp:t>)는 제거."""
    p0 = section.find('<hp:p ')
    run_start = section.find('<hp:run', p0)
    secpr_end = section.find('</hp:secPr>', run_start)
    run = section[run_start: section.find('</hp:run>', secpr_end) + len('</hp:run>')]
    return re.sub(r'<hp:t\b[^>]*>.*?</hp:t>', '', run, flags=re.S)


def extract_header_footer(section):
    """템플릿 section의 머리말·꼬리말 컨트롤을 문서 순서 그대로 이어붙여 반환.
    머리말은 자체 문단·스타일·이미지 참조를 갖는데 그 정의는 header.xml/BinData에
    보존되므로 컨트롤을 verbatim 복사하면 그대로 산다. 텍스트는 만들지 않는다."""
    return ''.join(m.group(0) for m in HEADER_FOOTER_CTRL_RE.finditer(section))


def extract_text_width(section, warnings):
    """secPr의 pagePr(용지 폭·여백)에서 본문 열 폭(HWPUNIT)을 계산 — 표 폭 기준값."""
    try:
        pp = re.search(r'<hp:pagePr\b.*?</hp:pagePr>', section, re.S).group(0)
        w = int(re.search(r'\bwidth="(\d+)"', pp).group(1))
        mtag = re.search(r'<hp:margin\b[^>]*/>', pp).group(0)
        left = int(re.search(r'\bleft="(\d+)"', mtag).group(1))
        right = int(re.search(r'\bright="(\d+)"', mtag).group(1))
        gutter = int(re.search(r'\bgutter="(\d+)"', mtag).group(1))
        tw = w - left - right - gutter
        if tw > 1000:
            return tw
    except Exception:
        pass
    warnings.append('페이지 폭 해석 실패 → 표 폭 기본값 30000 사용')
    return 30000


def find_grid_borderfill(header, warnings):
    """header.xml에서 네 변이 모두 그려지는(NONE 아님) borderFill id를 찾음 = 격자 표용.
    없으면 존재하는 첫 borderFill로 폴백(무효 참조 방지)+경고. 하나도 없으면 None."""
    first = None
    for m in re.finditer(r'<hh:borderFill id="(\d+)".*?</hh:borderFill>', header, re.S):
        bid, block = m.group(1), m.group(0)
        if first is None:
            first = bid
        sides = {}
        for side in ('left', 'right', 'top', 'bottom'):
            mm = re.search(rf'<hh:{side}Border\b[^>]*type="([^"]*)"', block)
            sides[side] = mm.group(1) if mm else 'NONE'
        if all(v != 'NONE' for v in sides.values()):
            return bid
    if first is not None:
        warnings.append(f'격자(네 변) 테두리 borderFill 없음 → borderFill={first}로 폴백(표 테두리 한글 확인)')
    else:
        warnings.append('템플릿에 borderFill 정의 없음 → 표 테두리 미지정(한글 확인)')
    return first


# ── 메인 변환 ────────────────────────────────────────────
def convert(md_path, template_path, out_path):
    warnings = []
    z, header, section, styles, charprs = load_template(template_path)
    roles = resolve_roles(styles, charprs, warnings)
    elements, defs = parse_md(md_path, warnings)

    root_open = re.search(r'<hs:sec\b[^>]*>', section).group(0)
    secpr_run = extract_secpr_run(section)
    header_footer = extract_header_footer(section)      # 머리말·꼬리말 컨트롤(verbatim)
    text_width = extract_text_width(section, warnings)  # 표 폭 기준
    grid_border = find_grid_borderfill(header, warnings)
    n_headers = len(re.findall(r'<hp:header\b', header_footer))
    n_footers = len(re.findall(r'<hp:footer\b', header_footer))

    b = Builder(roles)
    paras = []
    for kind, text in elements:
        if kind == 'title':
            paras.append(b.plain('title', text)); paras.append(b.empty())
        elif kind == 'author':
            paras.append(b.plain('author', text)); paras.append(b.empty())
        elif kind == 'chapter':
            paras.append(b.empty()); paras.append(b.plain('chapter', text)); paras.append(b.empty())
        elif kind == 'section':
            paras.append(b.empty()); paras.append(b.plain('section', text))
        elif kind == 'subsection':
            paras.append(b.plain('subsection', text))
        elif kind == 'blockquote':
            paras.append(b.para('blockquote', b.inline(text, 'blockquote', defs)))
        elif kind == 'table':
            # 격자 테두리를 못 찾으면(None) 폴백으로 '0'을 써도 유효 XML — 테두리만 안 보일 수 있음
            paras.append(b.table(text, defs, text_width, grid_border if grid_border else '0'))
        else:  # para
            paras.append(b.para('body', b.inline(text, 'body', defs)))

    # secPr와 머리말·꼬리말은 맨 첫 문단에 부착 (원고가 무엇으로 시작하든).
    # 둘 다 섹션 단위 컨트롤이므로 어느 문단의 run에 앵커돼도 문서 전체에 적용된다.
    if paras:
        first = paras[0]
        cut = first.index('>') + 1
        hf_run = ''
        if header_footer:
            hf_run = (f'<hp:run charPrIDRef="{roles["body"]["char"]}">'
                      f'{header_footer}<hp:t></hp:t></hp:run>')
        paras[0] = first[:cut] + secpr_run + hf_run + first[cut:]

    new_sec = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
               + root_open + ''.join(paras) + '</hs:sec>')

    members = z.infolist()
    data = {m.filename: z.read(m.filename) for m in members}
    data['Contents/section0.xml'] = new_sec.encode('utf-8')
    title_txt = next((t for k, t in elements if k == 'title'), '')
    if 'Preview/PrvText.txt' in data:
        data['Preview/PrvText.txt'] = (title_txt + '\n(AI 변환 잠정본)').encode('utf-8')

    if os.path.exists(out_path):
        os.remove(out_path)
    with zipfile.ZipFile(out_path, 'w') as zout:
        zout.writestr(zipfile.ZipInfo('mimetype'), data['mimetype'], compress_type=zipfile.ZIP_STORED)
        for m in members:
            if m.filename == 'mimetype':
                continue
            zout.writestr(m.filename, data[m.filename], compress_type=zipfile.ZIP_DEFLATED)

    used = {lab for _, lab in b.fn_map}
    orphans = [lab for lab in defs if lab not in used]
    n_tables = sum(1 for k, _ in elements if k == 'table')
    return {'roles': roles, 'elements': elements, 'defs': defs, 'builder': b,
            'warnings': warnings, 'orphans': orphans, 'n_para_elements': len(elements),
            'n_headers': n_headers, 'n_footers': n_footers, 'n_tables': n_tables,
            'grid_border': grid_border, 'text_width': text_width}


# ── 자기검증 ─────────────────────────────────────────────
def _visible(xml_text):
    ts = re.findall(r'<hp:t[^>]*>(.*?)</hp:t>', xml_text, re.S)
    return html.unescape(''.join(re.sub(r'<[^>]+>', '', t) for t in ts))


def self_verify(md_path, template_path, out_path, roles):
    res = {'errors': [], 'checks': []}
    z = zipfile.ZipFile(out_path)
    infos = z.infolist()
    if not (infos[0].filename == 'mimetype' and infos[0].compress_type == 0):
        res['errors'].append('mimetype 위치/압축 오류')
    for n in z.namelist():
        if n.endswith(('.xml', '.hpf', '.rdf')):
            try:
                ET.fromstring(z.read(n))
            except Exception as e:
                res['errors'].append(f'XML 문법 오류 {n}: {str(e)[:60]}')

    sec = z.read('Contents/section0.xml').decode('utf-8')

    # 머리말·꼬리말은 템플릿 원문(= md 비파생)이고 내부에 중첩 <hp:p>·별표·텍스트를 품으므로,
    # md 대조 불변식은 이를 걷어낸 판본을 기준으로 한다. 표도 중첩 <hp:p>를 만드므로 본문
    # 문단 대조 전에 제거하고 따로 대조한다.
    sec_nohf = HEADER_FOOTER_CTRL_RE.sub('', sec)                       # 머리말·꼬리말 제거
    sec_wo = re.sub(r'<hp:ctrl><hp:footNote.*?</hp:footNote></hp:ctrl>', '', sec_nohf, flags=re.S)  # +각주 제거
    sec_notbl = re.sub(r'<hp:tbl\b.*?</hp:tbl>', '', sec_wo, flags=re.S)  # +표 제거 → 순수 본문 문단

    # 기대값: 변환기 파서 재사용(텍스트 대조) + 파서 무관 불변식(별표·번호·secPr·머리말·잔존·GAP)
    elements, defs = parse_md(md_path, [])

    def norm(t):  # 이탤릭 마커만 제거(닫힌 짝) — 나머지 문자는 보존
        return ITALIC_RE.sub(r'\1', t)

    # 본문 문단 대조(표 제외 — 표는 아래에서 셀 단위로 별도 대조)
    expected_body = []
    for kind, txt in elements:
        if kind == 'table':
            continue
        expected_body.append(norm(re.sub(r'\[\^[^\]]+\]', '', txt)))
    expected_body = [x for x in expected_body if x.strip()]

    got_body = [t.strip() for t in (_visible(m.group(1)) for m in re.finditer(r'<hp:p [^>]*>(.*?)</hp:p>', sec_notbl, re.S)) if t.strip()]

    if len(expected_body) != len(got_body):
        res['errors'].append(f'본문 문단 수 불일치: 기대 {len(expected_body)} / 산출 {len(got_body)}')
    bmis = sum(1 for e, g in zip(expected_body, got_body) if e.strip() != g)
    if bmis:
        res['errors'].append(f'본문 문자 불일치 {bmis}문단')
    res['checks'].append(f'본문 {len(got_body)}문단 대조(불일치 {bmis})')

    # 표 셀 텍스트 대조(각주 제거된 sec_wo에서 표를 뽑아 셀 순서대로 md 셀과 대조)
    exp_tables = [rows for kind, rows in elements if kind == 'table']
    out_tables = re.findall(r'<hp:tbl\b.*?</hp:tbl>', sec_wo, re.S)
    if len(exp_tables) != len(out_tables):
        res['errors'].append(f'표 수 불일치: md {len(exp_tables)} / 산출 {len(out_tables)}')
    tcell_mis = tcell_tot = 0
    for rows, tbl in zip(exp_tables, out_tables):
        ncol = max((len(r) for r in rows), default=1)
        exp_cells = [norm(re.sub(r'\[\^[^\]]+\]', '', (r[c] if c < len(r) else ''))).strip()
                     for r in rows for c in range(ncol)]
        got_cells = [_visible(c).strip() for c in re.findall(r'<hp:tc\b.*?</hp:tc>', tbl, re.S)]
        tcell_tot += len(exp_cells)
        if len(exp_cells) != len(got_cells):
            res['errors'].append(f'표 셀 수 불일치: 기대 {len(exp_cells)} / 산출 {len(got_cells)}')
            continue
        tcell_mis += sum(1 for e, g in zip(exp_cells, got_cells) if e != g)
    if exp_tables:
        if tcell_mis:
            res['errors'].append(f'표 셀 문자 불일치 {tcell_mis}개')
        res['checks'].append(f'표 {len(out_tables)}개·셀 {tcell_tot}개 대조(불일치 {tcell_mis})')

    # 각주 텍스트 대조 (머리말 제거판에서 — 머리말 내 page autoNum·오염 배제)
    ref_order = FN_REF_RE.findall('\n'.join(
        l for l in re.sub(r'<!--.*?-->', '', open(md_path, encoding='utf-8').read(), flags=re.S).split('\n')
        if not FN_DEF_RE.match(l.rstrip())))
    footnotes = re.findall(
        r'<hp:footNote number="(\d+)"[^>]*>.*?<hp:t> </hp:t></hp:run>(.*?)</hp:p></hp:subList>', sec_nohf, re.S)
    if len(footnotes) != len(ref_order):
        res['errors'].append(f'각주 수 불일치: 참조 {len(ref_order)} / 산출 {len(footnotes)}')
    fmis = 0
    for (num, fx), lab in zip(footnotes, ref_order):
        exp = norm(defs.get(lab, ''))
        if _visible(fx).strip() != exp.strip():
            fmis += 1
    if fmis:
        res['errors'].append(f'각주 문자 불일치 {fmis}개')
    res['checks'].append(f'각주 {len(footnotes)}개 대조(불일치 {fmis})')

    # ── 파서 무관 불변식 ──
    # (a) secPr가 첫 문단에 있는가 (머리말 제거판 기준)
    first_p = re.search(r'<hp:p\b.*?</hp:p>', sec_nohf, re.S)
    if not (first_p and '<hp:secPr' in first_p.group(0)):
        res['errors'].append('secPr가 첫 문단에 없음(OWPML 위반 가능)')
    else:
        res['checks'].append('secPr 첫 문단 부착 확인')

    # (a2) 머리말·꼬리말 보존: 템플릿 section0의 hp:header/hp:footer 개수 = 산출 개수
    tpl_sec = zipfile.ZipFile(template_path).read('Contents/section0.xml').decode('utf-8')
    exp_h = len(re.findall(r'<hp:header\b', tpl_sec)); exp_f = len(re.findall(r'<hp:footer\b', tpl_sec))
    got_h = len(re.findall(r'<hp:header\b', sec)); got_f = len(re.findall(r'<hp:footer\b', sec))
    if got_h != exp_h or got_f != exp_f:
        res['errors'].append(f'머리말/꼬리말 보존 실패: 템플릿(머리말 {exp_h}·꼬리말 {exp_f}) / 산출(머리말 {got_h}·꼬리말 {got_f})')
    else:
        res['checks'].append(f'머리말 {got_h}개·꼬리말 {got_f}개 보존 확인')

    # (b) 각주 번호가 1..N 연속인가 (머리말 제거판 — 머리말 page autoNum 제외)
    nums = [int(n) for n, _ in footnotes]
    innernums = [int(x) for x in re.findall(r'<hp:autoNum num="(\d+)" numType="FOOTNOTE"', sec_nohf)]
    if nums != list(range(1, len(nums) + 1)) or innernums != list(range(1, len(innernums) + 1)):
        res['errors'].append('각주 번호가 1..N 연속이 아님')
    else:
        res['checks'].append(f'각주 번호 1..{len(nums)} 연속 확인')

    # (c) 별표 보존: 원본 별표(표 셀 포함) = 산출 별표 + 2×이탤릭런 (머리말 텍스트 제외판)
    src_stars = sum(t.count('*') for t in elem_text_chunks(elements)) + sum(t.count('*') for t in defs.values())
    out_visible = _visible(sec_nohf)
    out_stars = out_visible.count('*')
    italic_ids = {roles[r].get('italic') for r in ('body', 'footnote', 'blockquote')} - {None}
    n_italic = sum(1 for cid in re.findall(r'<hp:run charPrIDRef="(\d+)"', sec_nohf) if cid in italic_ids)
    if src_stars != out_stars + 2 * n_italic:
        res['errors'].append(f'별표(*) 보존 불변식 실패: 원본 {src_stars} ≠ 산출 {out_stars} + 2×{n_italic}')
    else:
        res['checks'].append(f'별표 보존 확인(원본 {src_stars} = 산출 {out_stars}+2×{n_italic})')

    # (d) 마크다운 각주참조 잔존 금지
    left = len(FN_REF_RE.findall(out_visible))
    if left:
        res['errors'].append(f'마크다운 각주참조 잔존 {left}건')

    # (e) [GAP] 수 보존
    gap_md = len(re.findall(r'\[GAP', re.sub(r'<!--.*?-->', '', open(md_path, encoding='utf-8').read(), flags=re.S)))
    gap_out = out_visible.count('[GAP')
    if gap_md != gap_out:
        res['errors'].append(f'[GAP] 마커 수 불일치: md {gap_md} / 산출 {gap_out}')
    else:
        res['checks'].append(f'[GAP] 마커 {gap_out}개 보존')

    res['ok'] = not res['errors']
    return res


# ── 리포트 ───────────────────────────────────────────────
def write_report(path, md_path, template_path, out_path, conv, verify):
    b = conv['builder']
    renum = [(n, o) for n, o in b.fn_map if str(n) != o]
    o = io.StringIO()
    o.write('# HWPX 변환 리포트 [AI 생성, 잠정]\n\n')
    o.write(f'- 생성: {datetime.datetime.now().isoformat(timespec="seconds")}\n')
    o.write(f'- 변환기: md2hwpx.py v{TOOL_VERSION} (순수 구조 변환·원본 무수정)\n')
    o.write(f'- 원본(불변): `{os.path.basename(md_path)}`  sha256 `{sha256_file(md_path)[:16]}…`\n')
    o.write(f'- 템플릿: `{os.path.basename(template_path)}`  sha256 `{sha256_file(template_path)[:16]}…`\n')
    o.write(f'- 산출물: `{os.path.basename(out_path)}`\n\n')
    o.write('## 자기검증\n')
    o.write(f'- 판정: **{"PASS" if verify["ok"] else "FAIL"}**\n')
    for c in verify['checks']:
        o.write(f'  - {c}\n')
    for e in verify['errors']:
        o.write(f'  - ⚠ {e}\n')
    o.write('\n## 구조 보존 (v1.2)\n')
    o.write(f'- 머리말(hp:header) {conv.get("n_headers", 0)}개 · 꼬리말(hp:footer) {conv.get("n_footers", 0)}개 '
            '템플릿에서 복사·재주입 — **머리말 텍스트는 템플릿(투고지) 원문 그대로**라 호수·연도·DOI·'
            '페이지 등은 저자가 한글에서 고쳐야 한다(도구는 자구를 만들지 않음).\n')
    o.write(f'- 표(hp:tbl) {conv.get("n_tables", 0)}개 생성'
            + (f' (셀 테두리 borderFill={conv.get("grid_border")}, 표 폭 {conv.get("text_width")} HWPUNIT 균등분할)'
               if conv.get('n_tables') else '')
            + ' — md 표 셀 병합은 표현 못 하므로 빈 칸으로 보존, 한글에서 확인.\n')
    o.write('\n## 스타일 매핑 (템플릿 이름 기준 자동 해석)\n')
    for role in ('title', 'author', 'chapter', 'section', 'subsection', 'body', 'blockquote', 'footnote'):
        r = conv['roles'][role]
        o.write(f'- {role} → "{ROLE_STYLE_NAME[role]}" (para={r["para"]}, char={r["char"]}, style={r["style"]}'
                + (f', italic={r.get("italic")}' if r.get('italic') else '') + ')\n')
    if conv['warnings']:
        o.write('\n## ⚠ 경고 (저자 확인 필요)\n')
        for w in conv['warnings']:
            o.write(f'- {w}\n')
    o.write('\n## 각주 재번호 맵 (인쇄번호 ← md라벨)\n')
    o.write(f'- 각주 {b.fn_no}개, 번호 바뀐 것 {len(renum)}개, 정의누락 {len(b.missing)}, 고아정의 {len(conv["orphans"])}\n')
    if renum:
        o.write('- 재번호: ' + ', '.join(f'^{oo}→{nn}' for nn, oo in renum) + '\n')
    if b.missing:
        o.write('- ⚠ 정의누락 각주: ' + ', '.join(f'^{x}' for x in b.missing) + '\n')
    if conv['orphans']:
        o.write('- ⚠ 본문에서 참조 안 된 정의: ' + ', '.join(f'^{x}' for x in conv['orphans']) + '\n')
    open(path, 'w', encoding='utf-8').write(o.getvalue())


TEMPLATE_HELP = ('투고지 hwpx 양식을 --template로 지정하라 — 양식 파일은 저장소에 포함되지 않는다'
                 '(학술지 홈페이지에서 받은 투고 양식 .hwpx; 스타일 이름 바탕글·제목·중제목·소제목·각주·'
                 '인용문·큰제목·이름을 쓰는 양식이면 그대로 맞물린다).')


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')   # Windows 콘솔에서도 한글 경로·메시지 출력 보장
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='한국어 원고 md → 투고 스타일 hwpx')
    ap.add_argument('md')
    ap.add_argument('--template', default=None, help='투고지 hwpx 양식 경로(필수)')
    ap.add_argument('--out', default=None)
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    md_path = os.path.abspath(args.md)
    if not os.path.exists(md_path):
        print('ERROR: 원고 없음:', md_path); sys.exit(2)
    if not args.template:
        print('ERROR: 템플릿 미지정 —', TEMPLATE_HELP); sys.exit(2)
    template_path = os.path.abspath(args.template)
    if not os.path.exists(template_path):
        print('ERROR: 템플릿 없음:', template_path, '—', TEMPLATE_HELP); sys.exit(2)
    if not zipfile.is_zipfile(template_path):
        print('ERROR: 템플릿이 hwpx(zip) 형식이 아님:', template_path, '— 한글에서 .hwpx로 다시 저장'); sys.exit(2)

    stem = os.path.splitext(os.path.basename(md_path))[0]
    out_path = os.path.abspath(args.out) if args.out else \
        os.path.join(os.path.dirname(md_path), f'{stem}_투고스타일_AI잠정.hwpx')
    report_path = os.path.abspath(args.report) if args.report else \
        os.path.join(os.path.dirname(md_path), f'_hwpx변환리포트_{stem}.md')

    conv = convert(md_path, template_path, out_path)
    verify = self_verify(md_path, template_path, out_path, conv['roles'])
    write_report(report_path, md_path, template_path, out_path, conv, verify)

    print(f'산출물: {out_path}')
    print(f'리포트: {report_path}')
    print(f'문단요소 {conv["n_para_elements"]} · 각주 {conv["builder"].fn_no} · 표 {conv["n_tables"]} '
          f'· 머리말 {conv["n_headers"]} · 경고 {len(conv["warnings"])}')
    print(f'자기검증: {"PASS" if verify["ok"] else "FAIL"}')
    for e in verify['errors']:
        print('  ⚠', e)
    if not verify['ok']:
        sys.exit(1)


if __name__ == '__main__':
    main()
