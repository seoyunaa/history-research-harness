#!/usr/bin/env python3
"""library_search.py — 보유 자료 전문 검색 (검색 위계: 0차 등록부 → 1차 로컬 → 2차 EndNote → 3차 웹).

library_index.py가 만든 fulltext.db(FTS5 trigram)를 질의하고 **tier 순서로 1차부터** 낸다.
1·2차에 아무것도 없으면 "3차(웹) 검색 단계로"라고 명시한다(웹은 source-verifier 최후 수단).
설정(references/library/sources.txt)이나 색인이 없으면 안내만 하고 0건으로 정직하게 끝낸다(종료코드 0).

사용:
  python tools/library_search.py "검색어"                # 전문 검색(1차→2차)
  python tools/library_search.py "검색어" --docs         # 문서 단위
  python tools/library_search.py "검색어" --tier 1       # 1차만
  python tools/library_search.py "검색어" --meta         # 서지(표제·파일명)만
"""
import os, sys, json, sqlite3, re
import _libconfig as C

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BADGE = {1: "①", 2: "②"}
CJK = re.compile(r"[가-힣㐀-鿿豈-﫿]")   # 한글+한자(2글자 이하는 trigram 색인이 못 잡아 LIKE로 폴백)

CORE_CATALOG = os.path.join(C.ROOT, "core-library", "catalog.yml")


def registry_hits(terms):
    """0차: core-library 사료 등록부(catalog.yml, 선택) 표제 조회. 없거나 실패하면 조용히 0건."""
    t = terms.strip().lower()
    if not t or not os.path.exists(CORE_CATALOG):
        return []
    try:
        import yaml
        cat = yaml.safe_load(open(CORE_CATALOG, encoding="utf-8"))
    except Exception:
        return []
    hits = []
    for s in (cat or {}).get("sources", []) or []:
        hay = " ".join(str(s.get(k) or "") for k in ("source_id", "title_ko", "title_original")).lower()
        if t in hay:
            hits.append(s)
    # Mixed local collections retain their own manifest rather than being
    # mislabeled as a single primary source. Their titles remain discoverable.
    for collection in (cat or {}).get("collections", []) or []:
        manifest = collection.get("manifest")
        if not manifest:
            continue
        try:
            with open(os.path.join(C.ROOT, "core-library", manifest), encoding="utf-8") as f:
                entries = json.load(f).get("entries", [])
        except (OSError, ValueError):
            continue
        for entry in entries:
            if t not in entry.get("title", "").lower():
                continue
            hits.append({"source_id": entry["sha256"][:16], "title_ko": entry["title"],
                         "status": "search_ready" if entry.get("has_search_text") else "registered",
                         "directory": collection["directory"], "registry_path": collection["registry"],
                         "current_stage": entry.get("status", "") + " · " + entry.get("reason", ""),
                         "files_summary": "추출문/상태: core-library/" + collection["directory"] + "/" + entry["markdown"]})
    return hits


def print_registry(terms):
    """등록부 적중을 ⓪줄로 출력. 반환: 적중 수. (판본·경로·상태의 정본은 해당 source.yml)"""
    hits = registry_hits(terms)
    for s in hits:
        stage = str(s.get("current_stage") or "")[:60]
        original = f"({s['title_original']})" if s.get("title_original") else ""
        print(f"  ⓪ [등록부] {s.get('title_ko') or s.get('source_id')}"
              f"{original} — {s.get('status') or '?'}"
              f" · core-library/{s.get('registry_path') or s.get('directory', '') + '/source.yml'}"
              + (f" · {stage}" if stage else ""))
        # 파일 상태 요약(build_core_catalog.py가 채우면 한 줄 덧붙임; 없으면 생략 — 하위호환)
        fs = str(s.get("files_summary") or "").strip()
        if fs:
            print(f"       {fs}")
    return len(hits)


def q_phrase(s):
    return '"' + s.replace('"', '""') + '"'


def _fmt(key, tier, source, authors, year, title, container, pdf_path=None, page=None):
    b = BADGE.get(tier, f"{tier}차")
    if tier == 1:
        # tier1은 경로째 보여줘 폴더를 되짚지 않게 한다(DB 저장값=하네스 루트 기준 상대경로).
        where = f" · {pdf_path} p.{page}" if pdf_path and page else ""
        if pdf_path and page and not pdf_path.lower().endswith(".pdf"):
            where += " (추출문 — 원본 면수 미확인)"
        return f"  {b} [{source}] {title[:70]}{where}"
    where = f" · {os.path.basename(pdf_path)} p.{page}" if pdf_path and page else ""
    au = (authors or "[저자미상]").split(";")[0]
    cont = f" 《{container}》" if container else ""
    return f"  {b} [{key}] {au}({year}) {title[:56]}{cont}{where}"


def meta_search(terms, limit):
    t = terms.lower()
    n1 = 0
    # 0차: 사료 등록부
    print(f"[서지·파일명 검색] '{terms}'")
    n0 = print_registry(terms)
    # 1차: tier1 폴더 파일명
    for base in C.tier1_dirs():
        label = os.path.basename(base)
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith(".provenance.json"):
                    continue
                if t in f.lower():
                    print(_fmt(f, 1, label, "", "", f, "")); n1 += 1
                    if n1 >= limit:
                        break
    # 2차: EndNote 카탈로그
    n2 = 0
    if os.path.exists(C.CATALOG):
        for r in json.load(open(C.CATALOG, encoding="utf-8"))["records"]:
            hay = " ".join([r["title"], r["container"], " ".join(r["keywords"]),
                            " ".join(r["authors"]), " ".join(r["groups"])]).lower()
            if t in hay:
                pdf = "📄" if r["has_pdf"] else "—"
                grp = f"  {{{', '.join(r['groups'])}}}" if r["groups"] else ""
                print(f"  ② {pdf}[{r['key']}] {'; '.join(r['authors']) or '[저자미상]'} ({r['year']}) {r['title'][:60]}{grp}")
                n2 += 1
                if n2 >= limit:
                    break
    tail = ""
    if not (n0 or n1 or n2):
        tail = "  ⟹ 보유 자료에 없음 → 3차(웹) 검색 단계로"
    elif n0 and not (n1 or n2):
        tail = "  ⟹ 등록부에는 있음 — 해당 source.yml의 판본·경로부터 확인"
    print(f"  → 0차(등록부) {n0}건 · 1차 {n1}건 · 2차 {n2}건" + tail)


def no_index(terms):
    """fulltext.db가 없을 때: 등록부(0차)만 보고 안내 후 정상 종료(0건도 정직한 결과)."""
    n0 = print_registry(terms)
    print("[안내] fulltext.db 없음 — 색인할 로컬 자료가 있으면 먼저 `python tools/library_index.py`. "
          "(전문 색인은 선택적 로컬 데이터층 — references/local-data-layer.md)")
    if not C.has_config():
        print("  " + C.config_notice())
    if n0:
        print("  ⟹ 0차 등록부에는 있음 — 위 source.yml의 판본·경로부터 확인")
    else:
        print("  ⟹ 보유 자료 색인 0건 → 3차(웹) 검색 단계로 (source-verifier가 서지 확인 후에만 등재)")


def full_search(terms, limit, docs_mode, only_tier):
    if not os.path.exists(C.FULLTEXT_DB):
        return no_index(terms)
    n0 = print_registry(terms)  # 0차: 사료 등록부 표제 조회
    con = sqlite3.connect(C.FULLTEXT_DB)
    con.row_factory = sqlite3.Row
    m = q_phrase(terms)
    tclause = f" AND d.tier={int(only_tier)}" if only_tier else ""
    try:
        if docs_mode:
            rows = con.execute(f"""
                SELECT d.tier, d.source, p.key, d.title, d.authors, d.year, d.container,
                       d.grp, COUNT(*) nhit
                FROM pages p JOIN docs d ON d.pdf_path=p.pdf_path
                WHERE pages MATCH ?{tclause}
                GROUP BY p.pdf_path ORDER BY d.tier ASC, nhit DESC LIMIT ?""",
                (m, limit)).fetchall()
        else:
            rows = con.execute(f"""
                SELECT d.tier, d.source, p.key, p.page, p.pdf_path, d.title, d.authors,
                       d.year, d.container, snippet(pages, 3, '《', '》', ' … ', 10) snip, bm25(pages) rk
                FROM pages p JOIN docs d ON d.pdf_path=p.pdf_path
                WHERE pages MATCH ?{tclause} ORDER BY d.tier ASC, rk LIMIT ?""",
                (m, limit)).fetchall()
    except sqlite3.OperationalError as e:
        sys.exit(f"[검색오류] {e}\n  (2자 이하 CJK는 --meta 서지검색을 쓰세요.)")
    con.close()

    if not rows:
        print(f"[전문검색] '{terms}' — 1·2차 전문 색인에 없음")
        if n0:
            print("  ⟹ 0차 등록부에는 있음 — 위 source.yml의 판본·경로부터 확인 (전문 미색인 자료일 수 있음)")
        else:
            print("  ⟹ 3차(웹) 검색 단계로 (source-verifier가 서지 확인 후에만 등재)")
        return

    n1 = sum(1 for r in rows if r["tier"] == 1)
    if docs_mode:
        print(f"[전문검색·문서] '{terms}' — {len(rows)}개 (1차 {n1} · 2차 {len(rows)-n1})")
        for r in rows:
            print(_fmt(r["key"], r["tier"], r["source"], r["authors"], r["year"],
                       r["title"], r["container"]) + f" — {r['nhit']}면 적중"
                  + (f"  {{{r['grp']}}}" if r["tier"] == 2 and r["grp"] else ""))
    else:
        print(f"[전문검색] '{terms}' — 상위 {len(rows)}면 (1차 {n1} · 2차 {len(rows)-n1})")
        for r in rows:
            print(_fmt(r["key"], r["tier"], r["source"], r["authors"], r["year"],
                       r["title"], r["container"], r["pdf_path"], r["page"]))
            snip = re.sub(r"\s+", " ", r["snip"] or "").strip()[:150]
            if snip:
                print(f"        {snip}")
    if n1 == 0:
        print("  (1차 폴더에는 없음 — 위 결과는 2차 EndNote. 더 필요하면 3차 웹.)")


def like_full_search(terms, limit, only_tier):
    """2글자 이하 CJK 전문검색: trigram 색인이 3글자 미만을 못 잡으므로 본문(pages.body)을
    LIKE로 직접 훑는다. 전체 스캔이라 수 초 걸릴 수 있으나, 짧은 한자·한글 질의(두 글자
    인명·지명·관직명 등)의 유일한 본문 검색 경로다."""
    if not os.path.exists(C.FULLTEXT_DB):
        return no_index(terms)
    n0 = print_registry(terms)   # 0차: 사료 등록부 표제 조회
    con = sqlite3.connect(C.FULLTEXT_DB)
    con.row_factory = sqlite3.Row
    tclause = f" AND d.tier={int(only_tier)}" if only_tier else ""
    like = "%" + terms.replace("%", r"\%").replace("_", r"\_") + "%"
    rows = con.execute(f"""
        SELECT d.tier, d.source, p.key, p.page, p.pdf_path, d.title, d.authors,
               d.year, d.container, p.body
        FROM pages p JOIN docs d ON d.pdf_path=p.pdf_path
        WHERE p.body LIKE ? ESCAPE '\\'{tclause} ORDER BY d.tier ASC LIMIT ?""",
        (like, limit)).fetchall()
    con.close()
    if not rows:
        print(f"[전문검색·2글자] '{terms}' — 본문에 없음")
        if n0:
            print("  ⟹ 0차 등록부에는 있음 — 위 source.yml의 판본·경로부터 확인")
        else:
            print("  ⟹ 3차(웹) 검색 단계로")
        return
    n1 = sum(1 for r in rows if r["tier"] == 1)
    print(f"[전문검색·2글자(LIKE)] '{terms}' — 상위 {len(rows)}면 (1차 {n1} · 2차 {len(rows)-n1})")
    for r in rows:
        print(_fmt(r["key"], r["tier"], r["source"], r["authors"], r["year"],
                   r["title"], r["container"], r["pdf_path"], r["page"]))
        body = re.sub(r"\s+", " ", r["body"] or "")
        idx = body.find(terms)
        if idx >= 0:
            s, e = max(0, idx - 40), min(len(body), idx + len(terms) + 40)
            snip = ("…" if s > 0 else "") + body[s:e] + ("…" if e < len(body) else "")
            print(f"        {snip}")
    if n1 == 0:
        print("  (1차 폴더에는 없음 — 위 결과는 2차 EndNote. 더 필요하면 3차 웹.)")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit("사용: python tools/library_search.py \"질의어\" [--limit N] [--docs] [--meta] [--tier 1|2]")
    docs_mode = "--docs" in args
    meta_mode = "--meta" in args
    limit, only_tier = 20, None
    def _intopt(flag, default):
        # 리뷰 수리: 값 누락·비정수 시 IndexError/ValueError 크래시 → 친절한 종료
        i = args.index(flag)
        if i + 1 >= len(args) or not args[i + 1].lstrip("-").isdigit():
            sys.exit(f"{flag} 뒤에 정수가 와야 합니다. 예: {flag} 10")
        v = int(args[i + 1]); del args[i:i + 2]
        return v
    if "--limit" in args: limit = _intopt("--limit", limit)
    if "--tier" in args: only_tier = _intopt("--tier", only_tier)
    args = [a for a in args if a not in ("--docs", "--meta")]
    terms = " ".join(args).strip()
    if not terms:
        sys.exit("질의어가 비었습니다. 사용: python tools/library_search.py \"질의어\"")
    if not C.has_config() and not os.path.exists(C.FULLTEXT_DB) and not os.path.exists(C.CATALOG):
        # 보유 자료층이 하나도 없는 새 clone — 등록부(0차)만 보고 안내 후 정상 종료.
        print(C.config_notice())
        n0 = print_registry(terms)
        print(f"  → 0차(등록부) {n0}건 · 1차 0건 · 2차 0건"
              + ("  ⟹ 등록부의 source.yml부터 확인" if n0 else "  ⟹ 보유 자료에 없음 → 3차(웹) 검색 단계로"))
        return 0
    if meta_mode:
        meta_search(terms, limit)
    elif len(terms) < 3:
        if CJK.search(terms):
            print(f"(질의 '{terms}' 3자 미만·CJK → 본문 직접검색[LIKE] + 등록부)")
            like_full_search(terms, limit, only_tier)
        else:
            print(f"(질의 '{terms}' 3자 미만 → 서지·파일명 검색으로 우회)")
            meta_search(terms, limit)
    else:
        full_search(terms, limit, docs_mode, only_tier)


if __name__ == "__main__":
    sys.exit(main())
