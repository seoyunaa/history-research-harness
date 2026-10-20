# -*- coding: utf-8 -*-
"""
test_md2hwpx.py — md2hwpx 회귀 테스트 (8종 엣지케이스 + v1.2 머리말·표)

실행:
  python tools/test_md2hwpx.py                       # 합성 최소 템플릿으로 실행(기본)
  python tools/test_md2hwpx.py --template 양식.hwpx   # 실제 투고지 양식으로 실행
  (환경변수 MD2HWPX_TEMPLATE로 지정해도 된다)

투고지 hwpx 양식은 저장소에 없다(학술지 배포 파일). 그래서 기본은 임시 폴더에 **합성 최소
템플릿**(스타일 8종·이탤릭 글자모양·격자 테두리·머리말 2+꼬리말 1·템플릿 본문과 감사 각주)을
만들어 변환기의 구조 불변식을 시험한다. 합성 템플릿은 시험용 골격일 뿐 한글에서 여는 것을
보증하지 않는다 — 실제 양식으로 최종 확인하려면 --template을 준다.
각 케이스를 변환·자기검증하고, 자기검증 PASS와 케이스별 기대 동작(각주 재번호·경고·머리말
보존·표 셀 대조)을 확인한다. 하나라도 어긋나면 코드 1로 종료. 산출물은 임시폴더에만 쓰고
원본/템플릿은 건드리지 않는다.
"""
import os
import sys
import re
import zipfile
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8')   # Windows 콘솔(cp949·cp1252)에서도 한글 출력이 깨지거나 죽지 않게
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import md2hwpx as M  # noqa: E402

_fails = []
TPL = None          # main()에서 결정
SYNTHETIC = False   # 합성 템플릿 사용 여부


# ── 합성 최소 템플릿 ───────────────────────────────────────
_NS_HEAD = 'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
_NS_SEC = ('xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
           'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"')
_XMLDECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
_SUBLIST = ('<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" '
            'linkListIDRef="0" linkListNextIDRef="0" textWidth="42520" textHeight="4252" '
            'hasTextRef="0" hasNumRef="0">')
_P = '<hp:p id="0" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
TEMPLATE_BODY_MARK = '템플릿 원논문 본문(산출물에 남으면 안 됨)'
TEMPLATE_FN_MARK = '감사의 글 각주(산출물에 남으면 안 됨)'


def _border(bid, kind):
    sides = ''.join(f'<hh:{s}Border type="{kind}" width="0.12 mm" color="#000000"/>'
                    for s in ('left', 'right', 'top', 'bottom'))
    return (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" '
            f'breakCellSeparateLine="0">{sides}</hh:borderFill>')


def build_synthetic_template(path):
    styles = [('바탕글', 0, 0), ('큰제목', 1, 4), ('이름', 2, 0), ('제목', 3, 4),
              ('중제목', 4, 0), ('소제목', 5, 0), ('인용문', 6, 2), ('각주', 7, 2)]
    header = (
        _XMLDECL + f'<hh:head {_NS_HEAD} version="1.4" secCnt="1"><hh:refList>'
        '<hh:borderFills itemCnt="2">' + _border(1, 'NONE') + _border(2, 'SOLID') + '</hh:borderFills>'
        '<hh:charProperties itemCnt="5">'
        '<hh:charPr id="0" height="1000" textColor="#000000"><hh:fontRef hangul="0"/></hh:charPr>'
        '<hh:charPr id="1" height="1000" textColor="#000000"><hh:italic/></hh:charPr>'
        '<hh:charPr id="2" height="900" textColor="#000000"/>'
        '<hh:charPr id="3" height="900" textColor="#000000"><hh:italic/></hh:charPr>'
        '<hh:charPr id="4" height="1600" textColor="#000000"/>'
        '</hh:charProperties></hh:refList>'
        f'<hh:styles itemCnt="{len(styles)}">'
        + ''.join(f'<hh:style id="{i}" type="PARA" name="{n}" engName="" paraPrIDRef="{pp}" '
                  f'charPrIDRef="{cp}" nextStyleIDRef="{i}" langID="1042" lockForm="0"/>'
                  for i, (n, pp, cp) in enumerate(styles))
        + '</hh:styles></hh:head>')
    secpr_run = (
        '<hp:run charPrIDRef="0"><hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" '
        'tabStop="8000" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" '
        'masterPageCnt="0"><hp:pagePr landscape="WIDELY" width="59528" height="84188" '
        'gutterType="LEFT_ONLY"><hp:margin header="4252" footer="4252" gutter="0" left="8504" '
        'right="8504" top="5668" bottom="4252"/></hp:pagePr></hp:secPr><hp:ctrl><hp:colPr id="" '
        'type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/></hp:ctrl></hp:run>')

    def hf(tag, hid, page_type, inner):
        return (f'<hp:ctrl><hp:{tag} id="{hid}" applyPageType="{page_type}">{_SUBLIST}{_P}'
                f'{inner}</hp:p></hp:subList></hp:{tag}></hp:ctrl>')
    page_no = ('<hp:run charPrIDRef="0"><hp:ctrl><hp:autoNum num="1" numType="PAGE">'
               '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar="" supscript="0"/>'
               '</hp:autoNum></hp:ctrl><hp:t></hp:t></hp:run>')
    hf_run = ('<hp:run charPrIDRef="0">'
              + hf('header', 1, 'ODD', '<hp:run charPrIDRef="0"><hp:t>학술지명 *제0호* 러닝헤드</hp:t></hp:run>')
              + hf('header', 2, 'EVEN', '<hp:run charPrIDRef="0"><hp:t>논문 제목 러닝헤드</hp:t></hp:run>')
              + hf('footer', 3, 'BOTH', page_no)
              + '<hp:t></hp:t></hp:run>')
    tpl_fn = ('<hp:run charPrIDRef="0"><hp:ctrl><hp:footNote number="1" instId="1">' + _SUBLIST
              + '<hp:p id="0" paraPrIDRef="7" styleIDRef="7" pageBreak="0" columnBreak="0" merged="0">'
              '<hp:run charPrIDRef="2"><hp:ctrl><hp:autoNum num="1" numType="FOOTNOTE">'
              '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
              f'</hp:autoNum></hp:ctrl><hp:t> </hp:t></hp:run><hp:run charPrIDRef="2"><hp:t>{TEMPLATE_FN_MARK}</hp:t>'
              '</hp:run></hp:p></hp:subList></hp:footNote></hp:ctrl></hp:run>')
    section = (_XMLDECL + f'<hs:sec {_NS_SEC}>' + _P + secpr_run + hf_run
               + f'<hp:run charPrIDRef="0"><hp:t>{TEMPLATE_BODY_MARK}</hp:t></hp:run>' + tpl_fn
               + '</hp:p></hs:sec>')
    container = (_XMLDECL + '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
                 'media-type="application/hwpml-package+xml"/></ocf:rootfiles></ocf:container>')
    hpf = (_XMLDECL + '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" '
           'unique-identifier="" id=""><opf:metadata/><opf:manifest>'
           '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
           '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
           '</opf:manifest><opf:spine><opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/hwp+zip', compress_type=zipfile.ZIP_STORED)
        for name, data in (('META-INF/container.xml', container), ('Contents/content.hpf', hpf),
                           ('Contents/header.xml', header), ('Contents/section0.xml', section),
                           ('Preview/PrvText.txt', '합성 시험용 템플릿')):
            z.writestr(name, data.encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
    return path


def template_counts(path):
    sec = zipfile.ZipFile(path).read('Contents/section0.xml').decode('utf-8')
    return len(re.findall(r'<hp:header\b', sec)), len(re.findall(r'<hp:footer\b', sec))


# ── 공통 도우미 ────────────────────────────────────────────
def check(name, cond, detail=''):
    mark = 'ok ' if cond else 'FAIL'
    print(f'  [{mark}] {name}' + (f' — {detail}' if detail and not cond else ''))
    if not cond:
        _fails.append(f'{name}: {detail}')


def run(md_text):
    d = tempfile.mkdtemp(prefix='md2hwpx_test_')
    mp = os.path.join(d, 't.md')
    open(mp, 'w', encoding='utf-8').write(md_text)
    op = os.path.join(d, 't.hwpx')
    conv = M.convert(mp, TPL, op)
    ver = M.self_verify(mp, TPL, op, conv['roles'])
    sec = zipfile.ZipFile(op).read('Contents/section0.xml').decode('utf-8')
    return conv, ver, sec


def n_footnotes(sec):
    return len(re.findall(r'<hp:footNote number="\d+"', sec))


# ── 1) 이탤릭 flanking: *이탤릭*은 소비, 홀로 뜬 *·**굵게**는 보존(별표 불변식) ──
def t1_italic_flanking():
    conv, ver, sec = run(
        '# 제목\n[저자: 홍길동]\n\n본문에 *이탤릭*과 홀로 뜬 *별표 그리고 **굵게**가 있다.\n')
    check('1 이탤릭 flanking: 자기검증 PASS', ver['ok'], str(ver['errors']))
    check('1 별표 보존 불변식 통과', any('별표 보존' in c for c in ver['checks']))
    check('1 굵게/불균형 경고 발생', any('별표' in w for w in conv['warnings']))


# ── 2) secPr는 원고가 무엇으로 시작하든 첫 문단에 부착 ──
def t2_secpr_first_para():
    conv, ver, sec = run('그냥 본문으로 시작하는 원고.\n\n두 번째 문단.\n')
    check('2 제목 없이 시작: PASS', ver['ok'], str(ver['errors']))
    check('2 secPr 첫 문단 확인', any('secPr' in c for c in ver['checks']))


# ── 3) 임의 각주 라벨 + 등장순 재번호 ──
def t3_footnote_labels():
    conv, ver, sec = run(
        '# 제목\n[저자: 갑]\n\n첫[^5] 둘[^ibid] 셋[^2].\n\n[^5]: 다섯.\n[^ibid]: 같은 책.\n[^2]: 둘.\n')
    check('3 임의 라벨 각주: PASS', ver['ok'], str(ver['errors']))
    check('3 각주 3개', conv['builder'].fn_no == 3, str(conv['builder'].fn_no))
    check('3 재번호 5→1, ibid→2, 2→3',
          conv['builder'].fn_map == [(1, '5'), (2, 'ibid'), (3, '2')], str(conv['builder'].fn_map))


# ── 4) 인용문 안 이탤릭·각주 ──
def t4_blockquote():
    conv, ver, sec = run('# 제목\n[저자: 을]\n\n> 인용에 *강조*와 각주[^1]가 있다.\n\n[^1]: 인용 각주.\n')
    check('4 인용문 각주·이탤릭: PASS', ver['ok'], str(ver['errors']))
    check('4 각주 1개', n_footnotes(sec) == 1, str(n_footnotes(sec)))


# ── 5) GAP 마커 보존 ──
def t5_gap():
    conv, ver, sec = run('# 제목\n[저자: 병]\n\n여기 [GAP:원문] 그리고 [GAP:연대] 보존.\n')
    check('5 GAP 보존: PASS', ver['ok'], str(ver['errors']))
    check('5 GAP 2개 보존 확인', any('[GAP] 마커 2개' in c for c in ver['checks']))


# ── 6) h1~h6 제목 (5·6수준은 미처리 경고 + 소제목 처리) ──
def t6_headings():
    conv, ver, sec = run('# 큰제목\n[저자: 정]\n\n## 장\n### 절\n#### 소절\n##### 소소절\n')
    check('6 h1~h6: PASS', ver['ok'], str(ver['errors']))
    check('6 5수준 제목 미처리 경고', any('5·6수준' in w for w in conv['warnings']))


# ── 7) 저자행은 키워드(저자/소속/author) 있을 때만 — 없으면 본문 ──
def t7_author_keyword():
    conv, ver, sec = run('# 제목\n[편집자 주: 확인]\n\n본문.\n')
    kinds = [k for k, _ in conv['elements']]
    check('7 키워드 없는 [..]는 author 아님', 'author' not in kinds, str(kinds))
    check('7 PASS', ver['ok'], str(ver['errors']))


# ── 8) --- 구분선·빈 줄은 버림 ──
def t8_hr_blank():
    conv, ver, sec = run('# 제목\n[저자: 무]\n\n---\n\n문단 하나.\n\n---\n')
    check('8 --- 구분선 스킵: PASS', ver['ok'], str(ver['errors']))


# ── 9) 머리말·꼬리말 보존 + 템플릿 원논문 본문·각주(감사) 비유출 ──
def t9_header_footer():
    exp_h, exp_f = template_counts(TPL)
    conv, ver, sec = run('# 제목\n[저자: 기]\n\n문장[^1] 또[^2].\n\n[^1]: 하나.\n[^2]: 둘.\n')
    check('9 머리말·꼬리말: PASS', ver['ok'], str(ver['errors']))
    check(f'9 머리말 {exp_h}개 보존(템플릿 기준)', conv['n_headers'] == exp_h, str(conv['n_headers']))
    check(f'9 꼬리말 {exp_f}개 보존(템플릿 기준)', conv['n_footers'] == exp_f, str(conv['n_footers']))
    check(f'9 산출 머리말 {exp_h}개', len(re.findall(r'<hp:header\b', sec)) == exp_h)
    check('9 템플릿 감사각주 비유출(각주=md 2개만)', n_footnotes(sec) == 2, str(n_footnotes(sec)))
    check('9 보존 검증항목 존재', any(f'머리말 {exp_h}개' in c for c in ver['checks']))
    if SYNTHETIC:
        check('9 템플릿 본문 비유출', TEMPLATE_BODY_MARK not in sec)
        check('9 템플릿 각주 문구 비유출', TEMPLATE_FN_MARK not in sec)


# ── 10) 표 변환: 이탤릭 셀·굵게 셀·빈 셀·셀 각주·열수 불일치 ──
def t10_table():
    md = ('# 표 제목\n[저자: 표]\n\n앞 문단.\n\n'
          '| 대상 | 라틴 | 한문 |\n|---|---|---|\n'
          '| 바람 길목 | *동굴* | 山川道里 |\n'
          '| 경계[^a] | — | · |\n'
          '| **수렴** | 초원 | |\n'
          '| 짧은행 |\n\n'
          '뒤 문단[^b].\n\n[^a]: 셀 각주.\n[^b]: 본문 각주.\n')
    conv, ver, sec = run(md)
    check('10 표 변환: PASS', ver['ok'], str(ver['errors']))
    check('10 표 1개', conv['n_tables'] == 1, str(conv['n_tables']))
    check('10 hp:tbl 생성', '<hp:tbl' in sec)
    check('10 표 셀 대조 검증항목', any('표 1개' in c for c in ver['checks']))
    check('10 열수 불일치 경고', any('열수 불일치' in w for w in conv['warnings']))
    check('10 셀 각주 먼저 번호', conv['builder'].fn_map == [(1, 'a'), (2, 'b')], str(conv['builder'].fn_map))
    check('10 각주 2개', n_footnotes(sec) == 2, str(n_footnotes(sec)))
    # 셀 텍스트가 실제로 들어갔나(육안 대조 보강)
    check('10 셀 텍스트 山川道里 존재', '山川道里' in sec)
    check('10 굵게 별표 셀 리터럴 보존', '**수렴**' in M._visible(sec))


# ── 11) CLI: 템플릿 미지정은 명확한 오류(코드 2) ──
def t11_cli_requires_template():
    import subprocess
    d = tempfile.mkdtemp(prefix='md2hwpx_cli_')
    mp = os.path.join(d, 't.md')
    open(mp, 'w', encoding='utf-8').write('# 제목\n\n본문.\n')
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    r = subprocess.run([sys.executable, os.path.join(HERE, 'md2hwpx.py'), mp],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    out = (r.stdout or '') + (r.stderr or '')
    check('11 템플릿 미지정 → 종료코드 2', r.returncode == 2, f'rc={r.returncode}')
    check('11 안내 문구(--template)', '--template' in out, out[-200:])
    check('11 산출물 미생성', not any(f.endswith('.hwpx') for f in os.listdir(d)), str(os.listdir(d)))


def main():
    global TPL, SYNTHETIC
    tpl = os.environ.get('MD2HWPX_TEMPLATE')
    if '--template' in sys.argv:
        i = sys.argv.index('--template')
        if i + 1 >= len(sys.argv):
            print('사용: python tools/test_md2hwpx.py [--template 양식.hwpx]')
            sys.exit(2)
        tpl = sys.argv[i + 1]
    if tpl:
        if not os.path.isfile(tpl):
            print(f'[오류] 지정한 템플릿 없음: {tpl}')
            sys.exit(2)
        TPL = os.path.abspath(tpl)
        print(f'템플릿: {TPL} (실제 양식)')
    else:
        TPL = build_synthetic_template(os.path.join(tempfile.mkdtemp(prefix='md2hwpx_tpl_'), 'synthetic.hwpx'))
        SYNTHETIC = True
        print(f'템플릿: 합성 최소 템플릿 {TPL} (실제 투고지 양식 확인은 --template)')
    tests = [t1_italic_flanking, t2_secpr_first_para, t3_footnote_labels, t4_blockquote,
             t5_gap, t6_headings, t7_author_keyword, t8_hr_blank, t9_header_footer, t10_table,
             t11_cli_requires_template]
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception as e:
            check(t.__name__ + ' 예외', False, repr(e))
    print()
    if _fails:
        print(f'회귀 테스트 실패 {len(_fails)}건:')
        for f in _fails:
            print('  -', f)
        sys.exit(1)
    print(f'회귀 테스트 전부 통과 ({len(tests)}종, {"합성 템플릿" if SYNTHETIC else "실제 양식"}).')


if __name__ == '__main__':
    main()
