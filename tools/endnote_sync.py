#!/usr/bin/env python3
"""endnote_sync.py — EndNote 라이브러리 → 하네스 보유 사료 원장(카탈로그). (2차 검색층, 선택)

하네스의 안 날조 척추("참고문헌은 프로젝트 파일 안에서만")를, 저자가 실제로 보유한
EndNote 라이브러리(실 PDF + 실 서지)에 정박한다. 이 스크립트는 EndNote `.enl`(SQLite)을
**읽기 전용**으로 열어 다음을 낸다.

  references/library/catalog.json  — 기계 카탈로그(모든 레코드: 인용키·서지·PDF·그룹)
  references/library/catalog.md    — 사람용 색인(저자 자신의 그룹 분류로 묶음)
  references/library/README.md      — 무엇인지·갱신법(최초 실행 시에만 생성)

절대 원칙 상속: 이 카탈로그는 *저자가 EndNote에 넣은 것만* 담는다. 서지를 지어내지
않는다. reference_type 라벨은 코드에서 *추정*한 것이며 원 코드(type_code)를 함께 보존한다.

사용:
  python tools/endnote_sync.py                        # references/library/sources.txt의 endnote: 줄에서 읽음
  python tools/endnote_sync.py "<...>.Data 폴더 경로"   # 라이브러리 경로를 직접 지정

설정도 인자도 없으면 안내만 하고 건너뛴다(종료코드 0) — 개인 기본 경로를 가정하지 않는다.
EndNote가 라이브러리를 연 채여도 읽기 전용(mode=ro)이라 안전하다.
"""
import os, sys, re, json, struct, glob, html
import _libconfig as C   # 검색 위계 설정(sources.txt의 endnote: 라이브러리 목록)

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows cp949 콘솔 대비
except Exception:
    pass

ROOT = C.ROOT
OUTDIR = C.LIBDIR

# reference_type 추정 라벨(원 코드는 항상 보존). 확정 아님 — 저자 확인 대상.
TYPE_LABELS = {
    0: "논문",          # Journal Article (secondary_title=학술지)
    1: "단행본",         # Book
    2: "기타/미분류",     # (추정 미확정)
    7: "단행본(장)",      # Book Section
    28: "금석문/기타",
    33: "기타",
    35: "기타",
    38: "기타",
}

# EndNote 온라인 검색 커넥션(자동 생성 그룹) — 저자의 주제 분류가 아니므로 구분 표시.
PROVIDER_GROUPS = {
    "Jisc Library Hub Discover", "Library of Congress", "PubMed (NLM)",
    "Web of Science Core Collection (Clarivate)",
}

CJK = re.compile(r"[㐀-鿿豈-﫿]")
HANGUL = re.compile(r"[가-힣]")


def find_enl(data_dir):
    hits = glob.glob(os.path.join(data_dir, "*.enl"))
    if not hits:
        # .Data 폴더 밖(형제)에 .enl 이 있는 배치도 지원
        hits = glob.glob(os.path.join(os.path.dirname(data_dir), "*.enl"))
    return hits[0] if hits else None


def clean(s):
    """EndNote 필드 정리: XML 수치 엔티티(&#x101; 등) 복원, 제어문자·꼬리 구분자 제거."""
    if not s:
        return ""
    s = html.unescape(s)
    s = "".join(ch for ch in s if ch >= " " or ch in "\t")
    return s.strip().strip(",;·・／ ").strip()


def split_authors(raw):
    if not raw:
        return []
    # EndNote 표준은 줄바꿈(\r) 구분. 저자가 한 필드에 `·／、`로 이어 적은 경우도 분해.
    parts = re.split(r"[\r\n]+|·|・|／", raw)
    return [clean(p) for p in parts if clean(p)]


def surname(author):
    """인용키용 성(姓). 라틴은 콤마 앞, CJK/한글은 앞 토큰(중점·공백 앞)."""
    a = author.strip()
    if "," in a:
        return a.split(",", 1)[0].strip()
    if CJK.search(a) or HANGUL.search(a):
        # CJK/한글 다저자·편찬 서술: 첫 사람 앞에서 자른다(전각 구분자 포함).
        head = re.split(r"[·・／、，；;,\s]", a)[0] or a
        return re.sub(r"(编|編|著|撰|主编|主編|整理|校注|译|譯)$", "", head) or head
    # 콤마 없는 라틴명: 마지막 낱말을 성으로
    toks = a.split()
    return toks[-1] if toks else a


def make_key(authors, year, used):
    if authors:
        base = re.sub(r"[^\w㐀-鿿가-힣]", "", surname(authors[0]))
    else:
        base = "Anon"
    y = re.sub(r"[^\d]", "", str(year or ""))[:4] or "nd"
    key = f"{base}{y}"
    if key in used:
        # 리뷰 수리: 동일 성+연도 27건 초과 시 중복키 방지 — a~z 소진 후 aa~zz 확장
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        for suf in list(alphabet) + [x + y for x in alphabet for y in alphabet]:
            if f"{key}{suf}" not in used:
                key = f"{key}{suf}"
                break
    used.add(key)
    return key


def lang_bucket(text):
    if CJK.search(text):
        return "한문/중문"
    if HANGUL.search(text):
        return "한국어"
    return "구미어"


def decode_members(blob):
    """groups.members BLOB → ref_id 리스트.
    형식: marker(BE uint32, =2) + count(LE uint32) + count×refid(LE uint32)."""
    if not blob or len(blob) < 8:
        return []
    try:
        count = struct.unpack_from("<I", blob, 4)[0]
        if count <= 0 or 8 + 4 * count > len(blob) + 4:
            return []
        end = min(8 + 4 * count, len(blob) - (len(blob) % 4))
        ids = struct.unpack_from(f"<{(end - 8)//4}I", blob, 8)
        return [i for i in ids if i > 0]
    except Exception:
        return []


def read_library(data_dir, used_keys, is_primary):
    """한 EndNote .Data 폴더를 읽어 (records, gid_name, gid_members)를 낸다(읽기 전용).
    used_keys는 라이브러리 간 공유해 인용키 충돌을 막는다(기준 라이브러리를 먼저 처리하면
    그쪽 키가 불변). is_primary=True면 PDF 색인키(index_path)를 기존 'PDF/…' 그대로 둬
    이미 만든 색인을 재사용하고, 비기준 라이브러리는 하네스 루트 기준 경로로 구분키를 만든다."""
    import sqlite3
    enl = find_enl(data_dir)
    if not enl:
        raise RuntimeError(f".enl 파일을 못 찾음(폴더: {data_dir})")
    pdf_root = os.path.join(data_dir, "PDF")
    con = sqlite3.connect(f"file:{enl}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1) 그룹(저자 분류) + 멤버십
    gid_name, gid_members = {}, {}
    cur.execute("SELECT group_id, spec, members FROM groups")
    for r in cur.fetchall():
        spec = r["spec"].decode("utf-8", "ignore") if isinstance(r["spec"], bytes) else (r["spec"] or "")
        m = re.search(r"<name>(.*?)</name>", spec, re.S)
        name = (m.group(1).strip() if m else f"group{r['group_id']}")
        gid_name[r["group_id"]] = name
        gid_members[r["group_id"]] = decode_members(r["members"])
    ref_groups = {}
    for gid, ids in gid_members.items():
        nm = gid_name[gid]
        for rid in ids:
            ref_groups.setdefault(rid, []).append(nm)

    # 2) PDF 첨부
    ref_pdfs = {}
    cur.execute("SELECT refs_id, file_path, file_type FROM file_res")
    for r in cur.fetchall():
        fp = r["file_path"] or ""
        if not fp:
            continue
        abspath = os.path.join(pdf_root, fp.replace("/", os.sep))
        path = os.path.join("PDF", fp).replace("\\", "/")            # data_dir 기준 상대경로(표시용)
        index_path = path if is_primary else C.index_key(abspath)  # 색인 기본키(라이브러리 간 구분)
        ref_pdfs.setdefault(r["refs_id"], []).append({
            "path": path,
            "index_path": index_path,
            "exists": os.path.exists(abspath),
        })

    # 3) 레코드
    cols = ("id, reference_type, author, year, title, secondary_title, pages, "
            "volume, number, place_published, publisher, edition, keywords, "
            "abstract, language, call_number, url, isbn, short_title, "
            "secondary_author, translated_title, translated_author, notes")
    cur.execute(f"SELECT {cols} FROM refs WHERE trash_state=0 OR trash_state IS NULL ORDER BY id")
    records = []
    for r in cur.fetchall():
        authors = split_authors(r["author"])
        editors = split_authors(r["secondary_author"])
        title = clean(r["title"])
        key = make_key(authors, r["year"], used_keys)
        kw = [clean(k) for k in re.split(r"[\r\n;]+", r["keywords"] or "") if clean(k)]
        pdfs = ref_pdfs.get(r["id"], [])
        rec = {
            "key": key,
            "id": r["id"],
            "type_code": r["reference_type"],
            "type": TYPE_LABELS.get(r["reference_type"], f"type{r['reference_type']}"),
            "authors": authors,
            "editors": editors,
            "year": (r["year"] or "").strip(),
            "title": title,
            "container": clean(r["secondary_title"]),   # 학술지명 또는 단행본명
            "volume": clean(r["volume"]),
            "number": clean(r["number"]),
            "pages": clean(r["pages"]),
            "publisher": clean(r["publisher"]),
            "place": clean(r["place_published"]),
            "edition": clean(r["edition"]),
            "translated_title": clean(r["translated_title"]),
            "translated_author": clean(r["translated_author"]),
            "keywords": kw,
            "language": (r["language"] or "").strip(),
            "lang_bucket": lang_bucket(title + " " + (r["author"] or "")),
            "call_number": (r["call_number"] or "").strip(),
            "url": (r["url"] or "").strip(),
            "isbn": (r["isbn"] or "").strip(),
            "abstract_present": bool((r["abstract"] or "").strip()),
            "groups": ref_groups.get(r["id"], []),
            "pdfs": pdfs,
            "has_pdf": any(p["exists"] for p in pdfs),
            "data_dir": data_dir,          # 이 레코드의 PDF를 풀 기준 폴더(검색 색인이 사용)
        }
        records.append(rec)
    con.close()
    return records, gid_name, gid_members


def resolve_data_dirs():
    """읽을 EndNote .Data 폴더 목록. argv[1] > sources.txt(endnote:). 기본값 없음.
    실재하는 폴더만 남기고, 첫 폴더가 '기준 라이브러리'. 반환: (실재 폴더들, 후보 수)."""
    if len(sys.argv) > 1:
        cand = [os.path.abspath(sys.argv[1])]
    else:
        cand = C.endnote_dirs()
    valid = []
    for d in cand:
        if os.path.isdir(d):
            valid.append(d)
        else:
            print(f"  [건너뜀] .Data 폴더 없음: {d}")
    return valid, len(cand)


def main():
    data_dirs, n_cand = resolve_data_dirs()
    if not n_cand:
        # 2차층은 선택 — 설정이 없으면 정상 종료(refresh.py 등 일괄 실행을 막지 않는다).
        if not C.has_config():
            print(C.config_notice())
        print(f"[안내] EndNote 라이브러리 미설정 — {C.CONFIG_REL}에 `endnote: <...>.Data 폴더>` 줄을 "
              f"적거나 경로를 인자로 넘긴다(양식: {C.EXAMPLE_REL}). 2차층 건너뜀.")
        return 0
    if not data_dirs:
        sys.exit("[에러] 설정된 EndNote .Data 폴더가 하나도 실재하지 않음 — sources.txt의 endnote: 경로를 확인하라.")

    used_keys = set()
    libraries = []          # (label, data_dir, enl_name, records, gid_name, gid_members)
    all_records = []
    for i, d in enumerate(data_dirs):
        try:
            recs, gid_name, gid_members = read_library(d, used_keys, is_primary=(i == 0))
        except Exception as e:
            print(f"  [건너뜀] 라이브러리 읽기 실패({d}): {e}")
            continue
        enl = find_enl(d)
        label = os.path.basename(d.rstrip("/\\")) or d
        libraries.append((label, d, os.path.basename(enl) if enl else "", recs, gid_name, gid_members))
        all_records.extend(recs)

    if not all_records:
        sys.exit("[에러] 읽어낸 레코드가 없음 — 라이브러리 경로/권한을 확인하라.")

    os.makedirs(OUTDIR, exist_ok=True)

    # ── catalog.json (여러 라이브러리 병합) ──
    with_pdf = sum(1 for r in all_records if r["has_pdf"])
    stats = {
        "source_enl": [lib[2] for lib in libraries],
        "libraries": [{"label": lib[0], "data_dir": lib[1], "records": len(lib[3]),
                       "with_pdf": sum(1 for r in lib[3] if r["has_pdf"])} for lib in libraries],
        "live_records": len(all_records),
        "with_pdf": with_pdf,
        "without_pdf": len(all_records) - with_pdf,
        "by_lang": _count(all_records, "lang_bucket"),
        "by_type": _count(all_records, "type"),
    }
    payload = {"_meta": {
        "generated_by": "tools/endnote_sync.py",
        "note": "EndNote 라이브러리에서 추출한 보유 사료 원장. type 라벨은 추정(type_code 보존).",
        "data_dir": libraries[0][1],                     # 기준 라이브러리(하위호환)
        "data_dirs": [lib[1] for lib in libraries],       # 전체(검색 색인은 레코드별 data_dir 사용)
    }, "stats": stats, "records": all_records}
    with open(os.path.join(OUTDIR, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # ── catalog.md ──
    write_md(os.path.join(OUTDIR, "catalog.md"), libraries, stats)

    # ── README (최초 1회) ──
    readme = os.path.join(OUTDIR, "README.md")
    if not os.path.exists(readme):
        write_readme(readme)

    print("=== endnote_sync 완료 ===")
    for label, d, enl_name, recs, _gn, _gm in libraries:
        wp = sum(1 for r in recs if r["has_pdf"])
        print(f"  · [{label}] {enl_name}: 레코드 {len(recs)} · PDF {wp}")
    print(f"  합계 레코드(live): {len(all_records)} · PDF 보유: {with_pdf} · PDF 없음: {len(all_records)-with_pdf}")
    print(f"  언어: {stats['by_lang']}")
    print(f"  유형: {stats['by_type']}")
    print(f"  → {os.path.relpath(os.path.join(OUTDIR,'catalog.json'), ROOT)}")
    print(f"  → {os.path.relpath(os.path.join(OUTDIR,'catalog.md'), ROOT)}")


def _count(records, field):
    out = {}
    for r in records:
        v = r[field]
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _cite_line(r):
    au = "; ".join(r["authors"]) if r["authors"] else "[저자 미상]"
    pdf = "📄" if r["has_pdf"] else "—"
    cont = f" 《{r['container']}》" if r["container"] else ""
    yr = f"({r['year']})" if r["year"] else ""
    return f"- `{r['key']}` {pdf} {au} {yr} {r['title']}{cont}"


def write_md(path, libraries, stats):
    """사람용 색인. 라이브러리별 섹션으로 나눠 쓴다(라이브러리마다 그룹·id 공간이 달라 분리)."""
    lines = ["# 보유 사료 원장 (EndNote → catalog)", "",
             f"> `tools/endnote_sync.py`가 EndNote 라이브러리에서 자동 생성. **손으로 고치지 말 것**(다음 실행에 덮어씀).",
             f"> 서지를 인용에 쓰려면 논문별 `03_biblio_whitelist.md`에 등록하고 `verify.py`로 대조한다.", "",
             "## 통계", "",
             f"- live 레코드 **{stats['live_records']}** · PDF 보유 **{stats['with_pdf']}** · PDF 없음 {stats['without_pdf']}",
             f"- 언어: " + ", ".join(f"{k} {v}" for k, v in stats["by_lang"].items()),
             f"- 유형(추정): " + ", ".join(f"{k} {v}" for k, v in stats["by_type"].items()), ""]
    if len(libraries) > 1:
        lines.append("- 라이브러리: " + " · ".join(f"{lib[0]} {len(lib[3])}건" for lib in libraries))
    lines += ["", "범례: `키` = 인용키 · 📄 = PDF 실재 · — = PDF 없음(메타데이터만)", "", "---", ""]
    for label, data_dir, enl_name, records, gid_name, gid_members in libraries:
        lines += [f"## 라이브러리: {label}  ({len(records)}건)", ""]
        by_key = {r["id"]: r for r in records}
        # 저자 그룹(멤버 있는 것) 먼저, 온라인검색 그룹은 뒤로
        real = [(g, gid_name[g], m) for g, m in gid_members.items()
                if m and gid_name[g] not in PROVIDER_GROUPS]
        real.sort(key=lambda x: -len(x[2]))
        for g, name, members in real:
            lines.append(f"### {name}  ({len(members)}건)")
            for rid in members:
                r = by_key.get(rid)
                if r:
                    lines.append(_cite_line(r))
            lines.append("")
        # 그룹 미지정
        grouped_ids = {rid for _, _, m in real for rid in m}
        ungrouped = [r for r in records if r["id"] not in grouped_ids]
        lines += [f"### 그룹 미지정 ({len(ungrouped)}건)", ""]
        for r in sorted(ungrouped, key=lambda x: x["key"].lower()):
            lines.append(_cite_line(r))
        lines += ["", "---", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_readme(path):
    txt = """# references/library/ — 보유 사료 원장 (EndNote 연동, 로컬 전용)

이 폴더는 저자의 EndNote 라이브러리를 하네스가 읽을 수 있는 **보유 사료 원장**으로
옮긴 것이다. 안 날조 척추("참고문헌은 프로젝트 파일 안에서만")를 *실제로 보유한 자료*에
정박한다. 개인 서지·경로를 담으므로 git에 올리지 않는다(선택적 로컬 데이터층).

## 파일
- `catalog.json` — 기계 카탈로그. 모든 레코드에 인용키·서지·PDF 경로·저자 그룹.
- `catalog.md` — 사람용 색인. 저자 자신의 EndNote 그룹 분류로 묶음.
- (둘 다 자동 생성물. **손으로 고치지 말 것** — 다음 실행에 덮어씀.)

## 갱신
EndNote에서 자료를 추가·수정한 뒤 다시 돌린다:

    python tools/endnote_sync.py

읽을 라이브러리는 `references/library/sources.txt`의 `endnote:` 줄에 적는다
(양식: `sources.example.txt`). 일회성으로 다른 라이브러리를 읽으려면:

    python tools/endnote_sync.py "<경로>/<라이브러리>.Data"

읽기 전용(mode=ro)이라 EndNote를 열어 둔 채여도 안전하다.

## 쓰임
1. **수집 풀(도서관)의 근거** — 논문별 `_library.md`의 항목을 이 카탈로그의 인용키로
   정박하면, PDF 실재·소속 그룹이 자동으로 채워진다.
2. **서지 화이트리스트 대조** — 논문별 `03_biblio_whitelist.md`에 등록한 서지가 실제
   보유 원장에 있는지 확인하는 근거.
3. **전문 검색** — `tools/library_search.py`로 "내가 이미 뭘 갖고 있나"를 즉답.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    sys.exit(main())
