#!/usr/bin/env python3
"""library_index.py — 보유 자료 전문(全文) 색인 (검색 위계 tier 태그).

검색 위계(`references/library/sources.txt`)대로 텍스트를 SQLite FTS5(trigram — 한문·한글
부분일치)로 색인한다. 각 문서에 tier를 매긴다:

  tier 1 = 저자 지정 우선 폴더(sources.txt의 tier1)         ← .pdf .md .txt .docx
  tier 2 = EndNote 라이브러리(catalog.json의 PDF)

  → references/library/fulltext.db

스캔본(추출 텍스트 ≈0)은 needs_ocr.txt로 **표시만** 하고 내용을 지어내지 않는다(안 날조 척추).
검색은 tools/library_search.py (tier 순서로 1차부터). 웹(3차)은 source-verifier가 최후.

사용:
  python tools/endnote_sync.py            # 먼저 catalog.json (2차) 생성/갱신
  python tools/library_index.py           # 1차 폴더 + EndNote 색인 (변경분만)
  python tools/library_index.py --rebuild # 전체 재색인
"""
import os, sys, json, time, sqlite3, re
import _libconfig as C

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MIN_CHARS_PER_PAGE = 8            # 이보다 적으면 스캔본(OCR 필요)로 간주
TEXT_EXT = {".pdf", ".md", ".markdown", ".txt", ".docx"}


def ensure_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS docs(
        pdf_path TEXT PRIMARY KEY, key TEXT, title TEXT, authors TEXT, year TEXT,
        container TEXT, grp TEXT, n_pages INT, n_chars INT, needs_ocr INT,
        mtime REAL, size INT, tier INT DEFAULT 2, source TEXT DEFAULT 'endnote')""")
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(
        pdf_path UNINDEXED, key UNINDEXED, page UNINDEXED, body, tokenize='trigram')""")
    cols = {r[1] for r in con.execute("PRAGMA table_info(docs)")}
    if "tier" not in cols:      # 기존 인덱스 마이그레이션(EndNote 문서 = 2차)
        con.execute("ALTER TABLE docs ADD COLUMN tier INT DEFAULT 2")
    if "source" not in cols:
        con.execute("ALTER TABLE docs ADD COLUMN source TEXT DEFAULT 'endnote'")


def _extract_pdf_fitz(abspath):
    import fitz
    doc = fitz.open(abspath)
    pages, total = [], 0
    for i, page in enumerate(doc, 1):
        try:
            txt = page.get_text("text") or ""
        except Exception:
            txt = ""
        total += len(txt.strip())
        if txt.strip():
            pages.append((i, txt))
    npg = doc.page_count
    doc.close()
    return pages, npg, total


def _extract_pdf_pypdf(abspath):
    from pypdf import PdfReader
    reader = PdfReader(abspath)
    pages, total = [], 0
    for i, page in enumerate(reader.pages, 1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        total += len(txt.strip())
        if txt.strip():
            pages.append((i, txt))
    return pages, len(reader.pages), total


def _extract_pdf_pdfplumber(abspath):
    import pdfplumber
    pages, total = [], 0
    with pdfplumber.open(abspath) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            total += len(txt.strip())
            if txt.strip():
                pages.append((i, txt))
        return pages, len(pdf.pages), total


def extract_pdf(abspath):
    """PDF 추출기를 순서대로 시도한다: PyMuPDF(fitz) → pypdf → pdfplumber."""
    errors = []
    best = ([], 0, 0)
    for name, extractor in (
        ("fitz", _extract_pdf_fitz),
        ("pypdf", _extract_pdf_pypdf),
        ("pdfplumber", _extract_pdf_pdfplumber),
    ):
        try:
            pages, npg, total = extractor(abspath)
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
            continue
        if total > best[2] or (total == best[2] and npg > best[1]):
            best = (pages, npg, total)
        if total:
            return pages, npg, total
    if best[1]:
        return best
    raise RuntimeError("PDF text extraction failed: " + " | ".join(errors))


def extract(abspath, ext):
    """(pages, n_pages, total_chars). pages = [(page_no, text), ...]."""
    if ext == ".pdf":
        return extract_pdf(abspath)
    if ext == ".docx":
        import docx
        d = docx.Document(abspath)
        txt = "\n".join(p.text for p in d.paragraphs)
        return ([(1, txt)] if txt.strip() else []), 1, len(txt.strip())
    # .md .markdown .txt
    txt = open(abspath, encoding="utf-8", errors="ignore").read()
    # OCR Markdown in core-library preserves the physical source PDF page with
    # this marker.  Indexing it as one long "page 1" hides the most useful
    # return path for researchers, so split only this explicit, lossless form.
    # Ordinary notes without markers retain their existing one-document shape.
    if ext in {".md", ".markdown"}:
        markers = list(re.finditer(r"(?m)^<!--\s*PDF_PAGE\s*:\s*(\d+)\s*-->\s*$", txt))
        if markers:
            pages = []
            for index, marker in enumerate(markers):
                body_end = markers[index + 1].start() if index + 1 < len(markers) else len(txt)
                body = txt[marker.end():body_end].strip()
                if body:
                    pages.append((int(marker.group(1)), body))
            return pages, max(int(marker.group(1)) for marker in markers), sum(
                len(body) for _, body in pages
            )
    return ([(1, txt)] if txt.strip() else []), 1, len(txt.strip())


def purge_resumable_ocr_fragments(con):
    """Remove stale index entries for OCR worker fragments.

    A completed resumable OCR folder has both ``pages/page_####.txt`` and a
    parent ``ocr_report.json``.  The page-marked Markdown is the canonical
    index target, so old fragment rows must disappear even though their source
    files are deliberately retained for safe OCR resumption and audit.
    """
    candidates = con.execute(
        "SELECT pdf_path FROM docs WHERE pdf_path LIKE '%/pages/page_%.txt'"
    ).fetchall()
    stale = []
    for (pdf_path,) in candidates:
        absolute = C.from_index_key(pdf_path)
        parent = os.path.dirname(os.path.dirname(absolute))
        if (
            os.path.basename(os.path.dirname(absolute)) == "pages"
            and re.fullmatch(r"page_\d{4}\.txt", os.path.basename(absolute))
            and os.path.isfile(os.path.join(parent, "ocr_report.json"))
        ):
            stale.append(pdf_path)
    for pdf_path in stale:
        con.execute("DELETE FROM pages WHERE pdf_path=?", (pdf_path,))
        con.execute("DELETE FROM docs WHERE pdf_path=?", (pdf_path,))
    return len(stale)


def purge_volume_index_stubs(con):
    """Remove stale index entries for crawl/volume-index/ navigation stubs.

    walk 단계가 이 경로의 md(권 목차 링크뿐인 stub)를 색인에서 제외하지만, 규칙 도입
    전에 색인된 행은 ``--rebuild`` 전까지 남는다.  증분 실행은 파일을 다시 열지 않으므로
    지워지지 않아, 매 실행 초입에 경로 패턴으로 정리한다.
    """
    n = con.execute(
        "SELECT COUNT(*) FROM docs WHERE pdf_path LIKE '%crawl/volume-index/%'"
    ).fetchone()[0]
    con.execute("DELETE FROM pages WHERE pdf_path LIKE '%crawl/volume-index/%'")
    con.execute("DELETE FROM docs WHERE pdf_path LIKE '%crawl/volume-index/%'")
    return n


def parse_budget(argv):
    """``--budget SECONDS`` (또는 ``--budget=SECONDS``) → 초(float). 없으면 None(무제한)."""
    for i, a in enumerate(argv):
        if a == "--budget":
            try:
                return float(argv[i + 1])
            except (IndexError, ValueError):
                sys.exit("[오류] --budget 뒤에 초 단위 숫자를 지정하세요 (예: --budget 1500).")
        if a.startswith("--budget="):
            try:
                return float(a.split("=", 1)[1])
            except ValueError:
                sys.exit("[오류] --budget 값이 숫자가 아닙니다 (예: --budget 1500).")
    return None


def checkpoint(con, n, t0, budget):
    """n%50 커밋 지점: 진행 커밋·출력 후, 시간예산 소진 시 깔끔히 정상 종료(exit 0).

    증분 스킵(mtime·size)이 있어 다음 실행이 커밋된 지점부터 자연히 이어받는다.
    """
    con.commit()
    print(f"  … {n}건 ({time.time()-t0:.0f}s)")
    if budget is not None and (time.time() - t0) >= budget:
        print(f"  [시간예산] {budget:.0f}s 소진 — {n}건 커밋 후 정상 종료, "
              "다음 실행이 증분으로 이어감")
        con.close()
        sys.exit(0)


def index_one(con, pdf_path, abspath, tier, source, meta, have, rebuild, ocr_list):
    """한 파일 색인. 반환: 'skip' | 'ocr' | 'ok' | 'fail'."""
    st = os.stat(abspath)
    if not rebuild and pdf_path in have and abs(have[pdf_path][0] - st.st_mtime) < 1 and have[pdf_path][1] == st.st_size:
        return "skip"
    con.execute("DELETE FROM docs WHERE pdf_path=?", (pdf_path,))
    con.execute("DELETE FROM pages WHERE pdf_path=?", (pdf_path,))
    ext = os.path.splitext(abspath)[1].lower()
    try:
        pages, npg, total = extract(abspath, ext)
    except Exception as e:
        print(f"  [열기실패] {pdf_path}: {e}")
        return "fail"
    for pno, txt in pages:
        con.execute("INSERT INTO pages(pdf_path,key,page,body) VALUES(?,?,?,?)",
                    (pdf_path, meta["key"], pno, txt))
    needs_ocr = 1 if (ext == ".pdf" and npg and total < MIN_CHARS_PER_PAGE * npg) else 0
    if needs_ocr:
        ocr_list.append(f"[{tier}차] {meta['key']}  {pdf_path}")
    con.execute("""INSERT INTO docs(pdf_path,key,title,authors,year,container,grp,
                   n_pages,n_chars,needs_ocr,mtime,size,tier,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pdf_path, meta["key"], meta["title"], meta["authors"], meta["year"],
                 meta["container"], meta["grp"], npg, total, needs_ocr, st.st_mtime, st.st_size, tier, source))
    return "ocr" if needs_ocr else "ok"


def main():
    rebuild = "--rebuild" in sys.argv
    budget = parse_budget(sys.argv)
    if not C.has_config() and not os.path.exists(C.CATALOG):
        # 선택적 로컬 데이터층 — 새 clone에는 sources.txt도 EndNote 카탈로그도 없다. 건너뛰기(정상 종료).
        print(C.config_notice())
        print("  색인 건너뜀 — 분계선·복원: references/local-data-layer.md")
        return 0
    if not C.tier1_dirs() and not os.path.exists(C.CATALOG):
        print(f"[안내] {C.CONFIG_REL}에 실재하는 tier1 폴더가 없고 EndNote 카탈로그(catalog.json)도 없음 — 색인 건너뜀.")
        for raw, full, ok in C.tier1_entries():
            if not ok:
                print(f"  · 폴더 없음: {raw} → {full}")
        return 0
    os.makedirs(C.LIBDIR, exist_ok=True)
    con = sqlite3.connect(C.FULLTEXT_DB)
    if rebuild:
        con.execute("DROP TABLE IF EXISTS docs")
        con.execute("DROP TABLE IF EXISTS pages")
    ensure_schema(con)
    purged_fragments = purge_resumable_ocr_fragments(con)
    purged_stubs = purge_volume_index_stubs(con)
    con.commit()
    have = {r[0]: (r[1], r[2]) for r in con.execute("SELECT pdf_path,mtime,size FROM docs")}

    t0 = time.time()
    stat = {"skip": 0, "ok": 0, "ocr": 0, "fail": 0}
    ocr_list = []
    n = 0

    # ── tier 1: 저자 지정 우선 폴더 ──
    t1dirs = C.tier1_dirs()
    for base in t1dirs:
        label = os.path.basename(base)
        for root, _, files in os.walk(base):
            for f in files:
                if os.path.splitext(f)[1].lower() not in TEXT_EXT:
                    continue
                # Our resumable OCR tool keeps page_####.txt fragments beside
                # its final page-marked Markdown and ocr_report.json.  The
                # Markdown is the researcher-facing searchable artifact;
                # indexing both creates duplicate hits with a misleading p.1.
                if (
                    os.path.basename(root) == "pages"
                    and re.fullmatch(r"page_\d{4}\.txt", f)
                    and os.path.isfile(os.path.join(os.path.dirname(root), "ocr_report.json"))
                ):
                    continue
                # core-library crawl/volume-index/ 아래 md는 본문 없는 권 목차
                # 네비게이션 stub이다(웹 수집본의 권별 목록 페이지 — 내용이 목차
                # 링크뿐). 색인하면 검색 잡음이므로 건너뛴다.
                if "crawl/volume-index/" in (root.replace("\\", "/") + "/"):
                    continue
                ap = os.path.join(root, f)
                rel = C.index_key(ap)
                meta = {"key": os.path.splitext(f)[0][:60], "title": f, "authors": "",
                        "year": "", "container": "", "grp": f"1차:{label}"}
                r = index_one(con, rel, ap, 1, label, meta, have, rebuild, ocr_list)
                stat[r] += 1; n += 1
                if n % 50 == 0:
                    checkpoint(con, n, t0, budget)

    # ── tier 2: EndNote 라이브러리(들) ──
    if os.path.exists(C.CATALOG):
        cat = json.load(open(C.CATALOG, encoding="utf-8"))
        meta_ddir = cat.get("_meta", {}).get("data_dir", "")
        for rc in cat["records"]:
            ddir = rc.get("data_dir") or meta_ddir      # 레코드가 속한 라이브러리 .Data 폴더
            for p in rc.get("pdfs", []):
                if not p.get("exists"):
                    continue
                ap = os.path.join(ddir, p["path"].replace("/", os.sep))
                if not os.path.exists(ap):
                    continue
                key_path = p.get("index_path", p["path"])   # 색인 기본키(라이브러리 간 구분)
                meta = {"key": rc["key"], "title": rc["title"], "authors": "; ".join(rc["authors"]),
                        "year": rc["year"], "container": rc["container"], "grp": ", ".join(rc["groups"])}
                r = index_one(con, key_path, ap, 2, "endnote", meta, have, rebuild, ocr_list)
                stat[r] += 1; n += 1
                if n % 50 == 0:
                    checkpoint(con, n, t0, budget)
    con.commit()

    all_ocr = [
        f"[{r[0]}차] {r[1]}  {r[2]}"
        for r in con.execute(
            "SELECT tier,key,pdf_path FROM docs WHERE needs_ocr=1 ORDER BY tier,key,pdf_path"
        )
    ]
    if all_ocr:
        with open(os.path.join(C.LIBDIR, "needs_ocr.txt"), "w", encoding="utf-8") as f:
            f.write("# 텍스트 추출 ≈0 (스캔본 추정) — OCR 필요. 인용 전 원문 확인.\n\n")
            f.write("\n".join(all_ocr))

    d1 = con.execute("SELECT COUNT(*) FROM docs WHERE tier=1").fetchone()[0]
    d2 = con.execute("SELECT COUNT(*) FROM docs WHERE tier=2").fetchone()[0]
    npages = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    con.close()
    print("=== library_index 완료 ===")
    if purged_fragments:
        print(f"  OCR 재개용 쪽 조각 중복 제거: {purged_fragments}건")
    if purged_stubs:
        print(f"  낡은 권목차 stub 색인 제거(crawl/volume-index/): {purged_stubs}건")
    print(f"  1차 폴더: {[os.path.basename(x) for x in t1dirs] or '(sources.txt에 tier1 없음)'}")
    print(f"  색인 문서: 1차 {d1} · 2차(EndNote) {d2} · 면 {npages}")
    print(f"  신규 {stat['ok']} · OCR필요 {stat['ocr']} · 변경없음 {stat['skip']} · 실패 {stat['fail']} · {time.time()-t0:.0f}s")
    if all_ocr:
        print(f"  → OCR 필요 전체 {len(all_ocr)}건: references/library/needs_ocr.txt")
    print("  → 검색: python tools/library_search.py \"질의어\"  (1차부터)")


if __name__ == "__main__":
    sys.exit(main())
