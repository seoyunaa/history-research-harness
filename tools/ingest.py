"""history-research-harness 자료 변환 라우터 — 보유 자료를 provenance 프런트매터가 붙은 Markdown으로.

확장자 라우터:
  .pdf        → pymupdf4llm (페이지 앵커 [p.N] 보존; 텍스트층 없는 스캔본은 변환하지
                않고 [GAP: OCR필요]로 보고만 한다 — 저품질 OCR이 무표기로 섞이는 것 차단)
  .docx       → pandoc(설치 시, 각주 [^1] 보존에 최적) → 폴백 markitdown
  .hwp/.hwpx  → hwp-hwpx-parser (각주 포함 추출)
  .pptx/.xlsx/.html/.htm/.epub/.csv/.msg → markitdown
  .txt/.md    → 건너뜀(이미 텍스트)

원칙(CLAUDE.md 상속):
- 원본이 진실, md는 파생물. 모든 산출 md 앞머리에 provenance 프런트매터
  (원본 경로·SHA-256·변환기·버전·변환일·ocr_engine)를 박아 처리 계보를 강제한다.
  원본 경로는 하네스 루트 안이면 루트 기준 상대경로, 밖이면 절대경로로 적는다 —
  산출 md는 로컬 데이터층이므로 git에 올리지 않는다.
- 스캔 PDF는 1차 패스에서 변환하지 않는다. `_ingest_report.md`의 OCR 대기열에
  올려 인간 게이트로 넘긴다(2차 선별: 문서 유형·문자권에 맞는 OCR 엔진).

사용:
  python tools/ingest.py <파일|폴더> [--out DIR] [--recursive] [--force]
  기본 출력: <입력 폴더>/_md/ (폴더 구조 미러). 보고서: <출력>/_ingest_report.md
"""
import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCAN_CHARS_PER_PAGE = 30   # 표본 페이지 평균 추출 문자수가 이 미만이면 스캔본으로 판정
SAMPLE_PAGES = 20          # 텍스트층 판정 표본 페이지 수(균등 추출)

ROUTES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".hwp": "hwp", ".hwpx": "hwp",
    ".pptx": "markitdown", ".xlsx": "markitdown", ".xls": "markitdown",
    ".html": "markitdown", ".htm": "markitdown", ".epub": "markitdown",
    ".csv": "markitdown", ".msg": "markitdown",
    ".txt": "skip", ".md": "skip",
}


def sha256_of(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def pkg_version(name):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return "?"


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source_ref(src):
    """원본 경로 표기: 하네스 루트 안이면 상대경로(슬래시), 밖이면 절대경로."""
    ap = os.path.abspath(src)
    try:
        rel = os.path.relpath(ap, ROOT)
    except ValueError:            # 다른 드라이브
        return ap
    return ap if rel.startswith("..") else rel.replace("\\", "/")


def front_matter(src, converter, pages=None, ocr_engine="none", note=""):
    lines = [
        "---",
        f"source: {source_ref(src)}",
        f"source_sha256: {sha256_of(src)}",
        f"source_mtime: {datetime.datetime.fromtimestamp(os.path.getmtime(src)).isoformat(timespec='seconds')}",
        f"converter: {converter}",
        f"converted: {datetime.date.today().isoformat()}",
        f"ocr_engine: {ocr_engine}",
    ]
    if pages is not None:
        lines.append(f"pages: {pages}")
    if note:
        lines.append(f"note: {note}")
    lines += ["generated_by: history-research-harness tools/ingest.py — 파생물, 원본이 진실", "---", ""]
    return "\n".join(lines)


# ---------- PDF ----------

def pdf_has_text_layer(path):
    """표본 페이지의 평균 추출 문자수로 텍스트층 유무 판정. (총페이지, 평균문자, 판정)"""
    import fitz
    doc = fitz.open(path)
    n = doc.page_count
    if n == 0:
        doc.close()
        return 0, 0.0, False
    step = max(1, n // SAMPLE_PAGES)
    idxs = list(range(0, n, step))[:SAMPLE_PAGES]
    total = sum(len(doc[i].get_text("text").strip()) for i in idxs)
    doc.close()
    avg = total / len(idxs)
    return n, avg, avg >= SCAN_CHARS_PER_PAGE


def convert_pdf(src):
    """pymupdf4llm 페이지 청크 → [p.N] 앵커로 결합. 스캔본이면 (None, 사유)."""
    npages, avg, has_text = pdf_has_text_layer(src)
    if not has_text:
        return None, f"[GAP: OCR필요] 텍스트층 없음(표본 평균 {avg:.0f}자/쪽, {npages}쪽)"
    import pymupdf4llm
    chunks = pymupdf4llm.to_markdown(src, page_chunks=True)
    parts = []
    for ch in chunks:
        pno = (ch.get("metadata") or {}).get("page")
        if pno is None:
            pno = len(parts) + 1
        parts.append(f"[p.{pno}]\n\n{(ch.get('text') or '').strip()}")
    body = "\n\n".join(parts)
    fm = front_matter(src, f"pymupdf4llm {pkg_version('pymupdf4llm')}", pages=npages,
                      note="페이지 앵커 [p.N] = PDF 물리 쪽(면수 인용 시 판본 쪽수와 대조할 것)")
    return fm + "\n" + body + "\n", None


# ---------- DOCX ----------

def convert_docx(src):
    pandoc = shutil.which("pandoc")
    if pandoc:
        r = subprocess.run([pandoc, "-f", "docx", "-t", "markdown", "--wrap=none", src],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            return front_matter(src, f"pandoc(각주 [^n] 보존)") + "\n" + r.stdout + "\n", None
        # pandoc 실패 시 markitdown 폴백으로 계속
    try:
        from markitdown import MarkItDown
    except ImportError:
        return None, "pandoc 없음 + markitdown 미설치 (pip install 'markitdown[docx]')"
    out = MarkItDown().convert(src)
    note = "markitdown 경로 — 각주 보존이 약함. 각주가 중요한 문서면 pandoc 설치 권장" if not pandoc else ""
    return front_matter(src, f"markitdown {pkg_version('markitdown')}", note=note) + "\n" + out.text_content + "\n", None


# ---------- HWP/HWPX ----------

def convert_hwp(src):
    try:
        import hwp_hwpx_parser as hp
    except ImportError:
        return None, "hwp-hwpx-parser 미설치 (pip install hwp-hwpx-parser)"
    rd = hp.read(src)
    try:
        if rd.is_encrypted():
            return None, "암호화된 HWP — 한글에서 암호 해제 후 재시도"
    except Exception:
        pass
    text = None
    for call in (lambda: rd.extract_text_with_notes(), lambda: rd.extract_text(), lambda: rd.text):
        try:
            got = call()
            if hasattr(got, "text") and isinstance(got.text, str):
                # 최신 파서는 ExtractResult를 반환한다. str(result)는 본문이
                # 아니라 repr이며, 주석을 잘라내고 줄바꿈도 이스케이프한다.
                body = got.text
                notes = []
                for n in getattr(got, "notes", []):
                    prefix = "e" if getattr(n, "note_type", "") == "endnote" else ""
                    note_text = n.text.replace("\n", "\n    ")
                    notes.append(f"[^{prefix}{n.number}]: {note_text}")
                got = body + ("\n\n## 추출 주석\n\n" + "\n\n".join(notes) if notes else "")
            if isinstance(got, tuple):   # (본문, 각주목록) 형태 방어
                body, notes = got[0], got[1] if len(got) > 1 else []
                tail = "\n\n## 각주\n" + "\n".join(f"[^{i+1}]: {n}" for i, n in enumerate(notes)) if notes else ""
                got = body + tail
            if got and str(got).strip():
                text = str(got)
                break
        except Exception:
            continue
    try:
        rd.close()
    except Exception:
        pass
    if text is None:
        return None, "HWP 추출 실패(파서가 본문을 읽지 못함) — LibreOffice+H2Orestart 경유 검토"
    return front_matter(src, f"hwp-hwpx-parser {pkg_version('hwp-hwpx-parser')}") + "\n" + text + "\n", None


# ---------- markitdown 잡식 ----------

def convert_markitdown(src):
    try:
        from markitdown import MarkItDown
    except ImportError:
        return None, "markitdown 미설치 (pip install 'markitdown[pptx,xlsx,docx]')"
    out = MarkItDown().convert(src)
    return front_matter(src, f"markitdown {pkg_version('markitdown')}") + "\n" + out.text_content + "\n", None


CONVERTERS = {"pdf": convert_pdf, "docx": convert_docx, "hwp": convert_hwp, "markitdown": convert_markitdown}


def collect_inputs(target, recursive):
    if os.path.isfile(target):
        return [target], os.path.dirname(os.path.abspath(target))
    root = os.path.abspath(target)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_md"))]
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1].lower() in ROUTES:
                files.append(os.path.join(dirpath, fn))
        if not recursive:
            break
    return files, root


def main():
    ap = argparse.ArgumentParser(description="자료 → provenance 프런트매터 Markdown 변환 라우터")
    ap.add_argument("target", help="변환할 파일 또는 폴더")
    ap.add_argument("--out", help="출력 폴더(기본: <입력 폴더>/_md/)")
    ap.add_argument("--recursive", action="store_true", help="하위 폴더까지")
    ap.add_argument("--force", action="store_true", help="기존 산출물 덮어쓰기")
    args = ap.parse_args()

    if not os.path.exists(args.target):
        print(f"[오류] 대상 없음: {args.target}")
        return 2

    files, in_root = collect_inputs(args.target, args.recursive)
    out_root = os.path.abspath(args.out) if args.out else os.path.join(in_root, "_md")
    os.makedirs(out_root, exist_ok=True)

    done, skipped, needs_ocr, errors = [], [], [], []
    for src in files:
        ext = os.path.splitext(src)[1].lower()
        route = ROUTES[ext]
        rel = os.path.relpath(src, in_root) if os.path.isdir(args.target) else os.path.basename(src)
        if route == "skip":
            skipped.append((rel, "이미 텍스트(.txt/.md)"))
            continue
        dst = os.path.join(out_root, os.path.splitext(rel)[0] + ".md")
        if os.path.exists(dst) and not args.force:
            skipped.append((rel, "산출물 존재(--force로 재변환)"))
            continue
        try:
            content, reason = CONVERTERS[route](src)
        except Exception as e:
            content, reason = None, f"{type(e).__name__}: {e}"
        if content is None:
            (needs_ocr if reason and reason.startswith("[GAP: OCR필요]") else errors).append((rel, reason))
            print(f"  건너뜀  {rel} — {reason}")
            continue
        os.makedirs(os.path.dirname(dst) or out_root, exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        done.append((rel, os.path.relpath(dst, out_root)))
        print(f"  변환    {rel} → {os.path.relpath(dst, out_root)}")

    # 보고서 — 스캔본(OCR 대기열)은 인간 게이트로 넘긴다
    report = os.path.join(out_root, "_ingest_report.md")
    with open(report, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# ingest 보고서 — {datetime.datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"입력: `{source_ref(args.target)}` · 변환 {len(done)} · 건너뜀 {len(skipped)} · OCR 대기 {len(needs_ocr)} · 오류 {len(errors)}\n\n")
        if needs_ocr:
            f.write("## [GAP: OCR필요] — 스캔본 대기열 (인간 게이트: 2차 선별 OCR)\n\n")
            f.write("근현대 인쇄물 스캔 → 범용 문서 OCR · 고문헌·세로쓰기·필사본 영인 → 해당 문자권·서체에 특화된 OCR "
                    "(엔진 선택은 저자 게이트). OCR 산출은 반드시 `ocr_engine:` 명기 후 재수록.\n\n")
            for rel, why in needs_ocr:
                f.write(f"- `{rel}` — {why}\n")
            f.write("\n")
        if errors:
            f.write("## 오류\n\n")
            for rel, why in errors:
                f.write(f"- `{rel}` — {why}\n")
            f.write("\n")
        if done:
            f.write("## 변환 완료\n\n")
            for rel, out_rel in done:
                f.write(f"- `{rel}` → `{out_rel}`\n")
    print(f"\n변환 {len(done)} · 건너뜀 {len(skipped)} · OCR 대기 {len(needs_ocr)} · 오류 {len(errors)}")
    print(f"보고서: {report}")
    if needs_ocr:
        print("스캔본은 변환하지 않았다 — 보고서의 OCR 대기열을 확인해 선별 처리할 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
