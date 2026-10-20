"""suggest_visual — 시각화 위저드의 데이터 실측기.

시각화 요청이 오면 바로 그리지 않는다. 먼저 이 도구가 데이터 파일을 열어
**어떤 신호(좌표·시간축·관계·수치·스캔이미지)가 실재하는지**를 세고, 그 근거로
유형(표·지도·네트워크·통시)을 **추천**하며, 유형별 방식 하위질문과 정확한 다음
명령을 인쇄한다. 추천의 근거는 저자의 감이 아니라 파일의 열이다(코드=진실).

反날조: 이 도구는 **유형을 제안**할 뿐 좌표·지명을 만들지 않는다.
좌표 열의 채움/빈칸을 셀 뿐 값을 창작하거나 단정하지 않으며, 최종 유형·방식은
저자가 정한다. 위저드 절차 전문은 `.claude/skills/시각화/SKILL.md` §0.

사용:
  python tools/suggest_visual.py <데이터파일> [<파일2> ...]
  # CSV / JSON / JSONL / 스캔이미지(png·jpg·tif) 지원. 여러 개면 각각 진단.

산출: 표준출력에 진단 카드(발견 신호 → 추천 유형 → 방식 질문 → 다음 명령).
      파일을 쓰지 않는다(읽기 전용 — 저자 판단 전 아무것도 승급하지 않는다).
"""
import argparse
import csv
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# --- 신호 어휘 (열 이름 정규화 후 대조) -------------------------------------
# 좌표: 경도/위도 짝. x/y는 픽셀과 혼동되므로 lon/lat류가 없을 때만 보조로 본다.
LON_NAMES = {"lon", "lng", "long", "longitude", "경도", "経度", "x_wgs", "wgs_x"}
LAT_NAMES = {"lat", "latitude", "위도", "緯度", "y_wgs", "wgs_y"}
# 관계(엣지) 짝 — 하나라도 짝이 맞으면 네트워크 신호.
REL_PAIRS = [("source", "target"), ("from", "to"), ("e1", "e2"),
             ("head", "tail"), ("subject", "object"), ("node1", "node2"),
             ("person1", "person2"), ("husband", "wife"), ("src", "dst"),
             ("start", "end_node")]
# 관계 단서(짝은 아니어도 관계형임을 시사) — 주장/혼인 CSV.
REL_HINTS = {"claim", "claims", "relation", "관계", "혼인", "marriage",
             "spouse", "부부", "혼맥", "rel_type", "relation_type"}
# 시간축 열.
TIME_NAMES = {"period", "시기", "generation", "세대", "year", "연도", "연대",
              "date", "일자", "왕대", "王代", "dynasty", "reign", "대", "때"}
# 집단/범주 열(통시엔 시간축 + 집단이 함께여야 강함).
GROUP_NAMES = {"group", "집단", "가문", "본관", "type", "유형", "범주",
               "category", "카테고리", "class", "계층", "faction", "세력"}
# 픽셀(지오레퍼런싱 GCP) — 이미지 정합 신호.
PIXEL_NAMES = {"pixel_x", "pixel_y", "px", "py"}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".bmp"}
CSV_EXT = {".csv", ".tsv"}


def norm(name):
    return (name or "").strip().strip("﻿").lower()


def read_csv_header_and_rows(path, max_rows=200):
    """주석(#) 선행행을 건너뛰고 헤더+표본행을 읽는다(gazetteer-master 관례)."""
    # 구분자 추정: .tsv면 탭.
    delim = "\t" if path.lower().endswith(".tsv") else ","
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = []
        for ln in f:
            if ln.lstrip().startswith("#"):
                continue
            lines.append(ln)
            if len(lines) > max_rows + 1:
                break
    reader = csv.DictReader(lines, delimiter=delim)
    header = [norm(h) for h in (reader.fieldnames or [])]
    rows = list(reader)
    return header, rows, reader.fieldnames or []


def count_filled(rows, fieldnames, want_norm):
    """정규화 이름이 want_norm인 열의 비어있지 않은 값 개수."""
    real = None
    for fn in fieldnames:
        if norm(fn) in want_norm:
            real = fn
            break
    if real is None:
        return None, 0
    n = sum(1 for r in rows if (r.get(real) or "").strip() not in ("", "-1", "null", "None"))
    return real, n


def diagnose_csv(path):
    header, rows, fieldnames = read_csv_header_and_rows(path)
    hset = set(header)
    signals = []
    facts = {"kind": "CSV", "rows": len(rows), "cols": len(header), "input_is_csv": True}

    lon_col, lon_n = count_filled(rows, fieldnames, LON_NAMES)
    lat_col, lat_n = count_filled(rows, fieldnames, LAT_NAMES)
    has_pixel = bool(hset & PIXEL_NAMES)
    if lon_col and lat_col:
        filled = min(lon_n, lat_n)
        facts["coords_filled"] = filled
        if filled == 0:
            signals.append(("coords",
                            f"좌표 열 {lon_col}·{lat_col}은 있으나 값이 전부 비어 있음([GAP:좌표]) — 전파 대상"))
        elif filled < len(rows):
            signals.append(("coords",
                            f"좌표 열 {lon_col}·{lat_col} 존재 ({len(rows)}행 중 {filled}행만 채움 — 나머지 [GAP:좌표])"))
        else:
            signals.append(("coords",
                            f"좌표 열 {lon_col}·{lat_col} 존재 ({len(rows)}행 전부 채움)"))
    if has_pixel:
        signals.append(("georef", f"픽셀 열({', '.join(sorted(hset & PIXEL_NAMES))}) — 스캔 정합 GCP(목적은 지오레퍼런싱)"))

    rel_found = [f"{a}·{b}" for a, b in REL_PAIRS if a in hset and b in hset]
    hint_found = sorted(hset & REL_HINTS)
    if rel_found:
        signals.append(("relation", f"관계 짝 열 {', '.join(rel_found)}"))
    elif hint_found:
        signals.append(("relation", f"관계 단서 열 {', '.join(hint_found)}"))

    time_found = sorted(hset & TIME_NAMES)
    group_found = sorted(hset & GROUP_NAMES)
    facts["has_group"] = bool(group_found)
    if time_found:
        gtxt = f" + 집단 {', '.join(group_found)}" if group_found else " (집단 열 없음 — 단순 시계열)"
        signals.append(("time", f"시간축 열 {', '.join(time_found)}{gtxt}"))

    # places 계약(corpus/_places-template.md) 신호 — 확신도·상태·비정 근거 열을 갖춘 지명 표.
    places_markers = {"certainty", "status", "loc_basis", "loc_rank", "type",
                      "level", "certainly", "modern_name", "aliases"}
    facts["places_like"] = len(hset & places_markers) >= 3 and bool(lon_col and lat_col)
    return facts, signals


def diagnose_json(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    facts = {"kind": "JSON", "rows": None, "cols": None, "input_is_csv": False}
    signals = []
    # JSONL? 첫 비어있지 않은 줄이 완결 객체면 라인 단위로 본다.
    first = ""
    for ln in text.splitlines():
        if ln.strip():
            first = ln.strip()
            break
    obj = None
    is_jsonl = False
    if first.startswith("{"):
        try:
            probe = json.loads(first)
            # 파일 전체가 하나의 JSON이면 실패하거나 뒤가 남는다 → JSONL 판정은 개수로.
            n = sum(1 for ln in text.splitlines() if ln.strip())
            try:
                json.loads(text)
                obj, is_jsonl = json.loads(text), False
            except Exception:
                obj, is_jsonl = probe, True
                facts["rows"] = n
        except Exception:
            pass
    if obj is None:
        try:
            obj = json.loads(text)
        except Exception:
            return {"kind": "JSON(파싱 실패)", "rows": None, "cols": None}, \
                   [("unknown", "JSON 파싱 실패 — 형식 확인 필요")]
    facts["kind"] = "JSONL" if is_jsonl else "JSON"

    sample = obj[0] if isinstance(obj, list) and obj else obj
    keys = set()
    if isinstance(sample, dict):
        keys = {norm(k) for k in sample.keys()}
    text_l = text[:20000].lower()

    # 개체명·관계 추출(NER/RE) 산출물.
    if {"ner", "relations"} & keys or ('"relations"' in text_l and '"ner"' in text_l):
        signals.append(("relation", "NER/RE 구조(ner·relations) — 관계 데이터(개체명·관계 추출 산출물)"))
    # 좌표 — 키 존재와 값 채움을 구분한다(키만 있고 null이면 [GAP:좌표]).
    has_coord_key = bool(keys & {"lon", "lat", "coordinates", "coord", "geometry", "위도", "경도"}) \
        or '"coordinates"' in text_l or '"geometry"' in text_l
    if has_coord_key:
        # 값이 null인가? (전파 대상 판별) — 키 집합과 동일 어휘로, 전문(truncate 없이) 계수.
        # 한글 키(위도·경도)·coord 포함, 20000자 절단 없이 세어 큰 파일도 null을 놓치지 않는다.
        cl = text.lower()
        pat_key = r'"(?:coordinates|geometry|coord|lon|lat|위도|경도)"\s*:'
        total = len(re.findall(pat_key, cl))
        nulls = len(re.findall(pat_key + r"\s*null", cl))
        facts["coords_filled"] = max(0, total - nulls)
        if total == 0:
            # 키는 감지됐으나 값 채움 여부 미상 → 보수적으로 [GAP] 쪽(반날조).
            facts["coords_filled"] = 0
            signals.append(("coords", "좌표 키 감지(값 채움 미상) — 지도 프레임이나 좌표 확인·전파 필요"))
        elif nulls >= total:
            signals.append(("coords", "좌표 키는 있으나 값이 null([GAP:좌표]) — 지도 프레임이나 좌표 정박·전파 필요"))
        elif nulls:
            signals.append(("coords", f"좌표 키 존재(일부 값 채움, {nulls}/{total}은 null [GAP:좌표])"))
        else:
            signals.append(("coords", "좌표/geometry 값 존재"))
    # 동선.
    if keys & {"journey", "via", "route", "동선", "이동"} or '"journey"' in text_l or '"via"' in text_l:
        signals.append(("route", "journey/via 노드 시퀀스 — 동선(경로) 데이터"))
    # 관계 일반.
    if keys & REL_HINTS or keys & {"source", "target", "from", "to"}:
        signals.append(("relation", "관계 키(source/target·claim 등)"))
    if not signals:
        signals.append(("table", "구조화 레코드 — 목록/집계표에 적합"))
    return facts, signals


def diagnose_image(path):
    ext = os.path.splitext(path)[1].lower()
    facts = {"kind": f"이미지({ext})", "rows": None, "cols": None}
    signals = [("georef", "스캔 이미지 — 좌표계 정합(지오레퍼런싱) 후 지도 배경")]
    return facts, signals


# --- 추천 결정 (신호 → 유형 순위) -------------------------------------------
def recommend(facts, signals):
    kinds = {k for k, _ in signals}
    recs = []  # (유형, 이유)
    if "georef" in kinds and facts.get("kind", "").startswith("이미지"):
        recs.append(("지오레퍼런싱→지도배경", "스캔 지도 — 먼저 좌표계에 정합해야 배경으로 쓴다"))
        return recs, kinds
    if "georef" in kinds:  # CSV GCP 파일
        recs.append(("지오레퍼런싱", "GCP(픽셀↔실좌표) 파일 — georef로 GeoTIFF 정합"))
    if "coords" in kinds:
        if facts.get("coords_filled", 0) == 0:
            recs.append(("지도", "지리 데이터이나 좌표 값이 비어 [GAP:좌표] — 전거 있는 앵커(게이지티어)에 좌표를 정박한 뒤 투영"))
        else:
            recs.append(("지도", "lon/lat 좌표가 실재 — 지리 투영이 가장 적합"))
    if "route" in kinds:
        recs.append(("지도(동선)", "journey/via 시퀀스 — 이동경로 선층으로"))
    if "relation" in kinds:
        why = "관계(엣지) 구조 — 인물·지명 관계망"
        if "time" in kinds:
            why += " + 시간축 있음 → 통시 인터랙티브도 가능"
        recs.append(("네트워크", why))
    if "time" in kinds and "coords" not in kinds and "relation" not in kinds:
        if facts.get("has_group"):
            recs.append(("통시", "시기·세대 열 + 집단 → 세대×집단 구성 변천 도표"))
        else:
            recs.append(("통시", "시기·세대 열(단순 시계열) → 시간 변화 도표. 집단 열이 있으면 세대×집단 구성도 가능"))
    if not recs:
        recs.append(("표", "좌표·관계·시간축 신호 없음 — 목록/집계는 표가 가장 정확"))
    # 표는 거의 항상 가능한 대안으로 덧붙인다(이미 표가 top이 아니면).
    if recs[0][0] != "표" and facts.get("kind") in ("CSV",):
        recs.append(("표", "수치·범주 집계가 필요하면 표로도"))
    return recs, kinds


# --- 방식 하위질문 인쇄 (유형별) --------------------------------------------
def method_menu(top_type, path, facts):
    p = f'"{path}"'
    out = []
    if top_type.startswith("지도"):
        is_csv = facts.get("input_is_csv", False)
        places_arg = p if is_csv else "<places.csv>"
        adapter_note = ""
        if not is_csv:
            adapter_note = ("     ↳ 이 입력은 CSV가 아니라 먼저 공통 places CSV(corpus/_places-template.md 계약)로 "
                            "변환해야 합니다. 지도 경로는 places CSV를 받습니다.\n")
        viewer_note = ""
        if facts.get("places_like"):
            viewer_note = ("     ↳ 이 파일은 certainty·status 등 places 계약 열이 있어 verify.py 지리 검사·"
                           "마스터 게이지티어(corpus/gazetteer-master.csv) 정박 대상입니다.\n")
        out.append(
            "▶ 지도를 고르면 다음 질문 — 어떤 방식?\n"
            + adapter_note +
            "  ① 스크립트  빠른 검토·도판 초안: places CSV만 읽는 짧은 스크립트(pandas/geopandas 등, 좌표 하드코딩 0)"
            " + 도표 매니페스트(corpus/_figure-manifest-template.md)\n"
            f"  ② GIS      게재본(저자 카토그래피): {places_arg}를 QGIS 등에 레이어로 불러와 저자가 도판 제작"
            "(하네스=데이터층, 배경 고지도는 ③ 지오레퍼런싱)\n"
            "  ③ 고지도 배경: python tools/georef.py <스캔이미지> <gcp.csv> <출력.tif>\n"
            + viewer_note)
    elif top_type == "네트워크":
        out.append(
            "▶ 네트워크 — 정적 4중(논문 도판+GEXF):\n"
            "  python tools/build_network.py --persons <persons.csv> [--claims <claims.csv> --a-col <A열접두> --b-col <B열접두>] --out <폴더>\n"
            "     ↳ GEXF는 Gephi 등에서 손으로 탐색할 수 있다(공개본에 인터랙티브 앱은 없다).")
    elif top_type == "통시":
        out.append(
            "▶ 통시 — 정적 막대(세대×집단):\n"
            "  python tools/build_diachronic.py --persons <p.csv> --claims <c.csv> --root <세대0 id> --out <폴더>\n"
            "     ↳ 세대 시간축은 --root(세대 0 개체)가 필수. 명시 시기 열을 쓰려면 집계 스크립트를 따로 둔다.")
    elif top_type.startswith("지오레퍼런싱"):
        out.append(
            "▶ 지오레퍼런싱 — GCP CSV(pixel_x,pixel_y,lon,lat,source,certainty)를 만든 뒤:\n"
            f"  python tools/georef.py <스캔이미지> <gcp.csv> <출력.tif> [--method tps]\n"
            "  ↳ source 공란은 도구가 거부. 회화식 고지도는 잔차 측정→오버레이 전용으로 매니페스트에 명기. 상세 references/hgis-지오레퍼런싱.md")
    elif top_type == "표":
        out.append(
            "▶ 표를 고르면 다음 질문 — 본문 표 vs 관계형 쿼리?\n"
            "  ① markdown 표(본문 삽입): 직접 작성\n"
            "  ② 관계형 집계(\"한 장소에 수렴하는 관찰\" 등): python tools/build_db.py <논문 폴더> → SQLite 질의")
    return "\n".join(out)


def diagnose(path):
    if not os.path.exists(path):
        return f"[오류] 파일 없음: {path}\n"
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        facts, signals = diagnose_image(path)
    elif ext in CSV_EXT:
        try:
            facts, signals = diagnose_csv(path)
        except Exception as e:
            return f"[오류] CSV 읽기 실패({path}): {e}\n"
    elif ext in {".json", ".jsonl", ".ndjson"}:
        facts, signals = diagnose_json(path)
    else:
        # 확장자 미상 — 내용 첫 글자로 추정.
        try:
            with open(path, encoding="utf-8-sig") as f:
                head = f.read(200).lstrip()
            if head.startswith("{") or head.startswith("["):
                facts, signals = diagnose_json(path)
            else:
                facts, signals = diagnose_csv(path)
        except Exception as e:
            return f"[오류] 형식 판별 실패({path}): {e}\n"

    recs, kinds = recommend(facts, signals)
    lines = []
    size = ""
    if facts.get("rows") is not None:
        size = f", {facts['rows']}행"
        if facts.get("cols") is not None:
            size += f"·{facts['cols']}열"
    lines.append(f"입력: {os.path.basename(path)} ({facts.get('kind')}{size})")
    lines.append("\n발견한 신호 (파일의 실재 열/키 — 창작 아님):")
    if signals:
        for _, desc in signals:
            lines.append(f"  ✓ {desc}")
    else:
        lines.append("  · 뚜렷한 신호 없음")
    lines.append("\n추천 유형 (제안 — 최종은 저자가 확정):")
    for i, (t, why) in enumerate(recs, start=1):
        mark = "  ← 추천" if i == 1 else ""
        lines.append(f"  {i}) {t}{mark}\n       {why}")
    lines.append("")
    lines.append(method_menu(recs[0][0], path, facts))
    lines.append("\n규율: 위 추천은 유형 제안일 뿐 좌표·지명·전거를 지어내지 않는다. "
                 "방식 확정·좌표 정박은 SKILL.md §0 위저드와 저자 게이트를 따른다.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="시각화 위저드 데이터 실측기 — 파일 신호로 유형을 추천한다.")
    ap.add_argument("paths", nargs="+", help="데이터 파일(CSV/JSON/JSONL/이미지) 하나 이상")
    args = ap.parse_args()
    print("=== 시각화 위저드 — 데이터 실측 (suggest_visual) ===")
    for i, p in enumerate(args.paths):
        if i:
            print("\n" + "─" * 60 + "\n")
        print(diagnose(p))
    print("다음: 유형을 고르고(위 추천 참고) 방식을 정하면, "
          ".claude/skills/시각화/SKILL.md의 해당 경로로 실행합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
