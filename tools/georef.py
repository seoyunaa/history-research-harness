"""georef — 고지도·영인본 지오레퍼런싱을 GCP 파일로 재현 가능하게.

QGIS Georeferencer의 headless 판: GDAL(gdal_translate -gcp → gdalwarp)로 스캔 이미지를
GeoTIFF로 정합한다. **GCP 목록이 텍스트 파일**이므로 좌표 화이트리스트·도표 매니페스트
체계와 동형 — GUI 클릭이 아니라 파일이 진실이다.
개념 학습: Programming Historian "Georeferencing in QGIS"(CC-BY) · IIIF 스캔은 Allmaps
(references/hgis-지오레퍼런싱.md).

GDAL 찾기(앞에서부터): --gdal-bin 폴더 → 환경변수 GDAL_BIN → PATH의 gdal_translate
→ 환경변수 QGIS_ROOT의 bin → (Windows) Program Files 아래 QGIS* 설치본의 번들 GDAL.

GCP CSV (pixel_x, pixel_y, lon, lat, source, certainty[, note]):
- pixel_x/pixel_y: 이미지 픽셀(좌상단 원점, y 아래로 증가 — QGIS Georeferencer와 동일)
- lon/lat: 실좌표(기본 EPSG:4326)
- **source 공란 = 거부**(출처 없는 좌표 금지). 대응점의 전거(게이지티어 id·고증 면수 등).
- certainty: high/medium/low — low가 있으면 경고.

변환: --method tps(기본 — 회화식 고지도류의 비선형 왜곡에 적합, GCP 10+ 권장) | poly1 | poly2

사용:
  python tools/georef.py <스캔이미지> <gcp.csv> <출력.tif> [--method tps] [--crs EPSG:4326] [--gdal-bin <폴더>]
산출: 출력.tif + <출력>.manifest.md(재현 명령·입력 SHA-256·GCP 전문·검증 요약)
"""
import argparse
import csv
import datetime
import glob
import hashlib
import os
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _exe(bin_dir, name):
    """bin_dir 안의 실행 파일 경로(Windows는 .exe). 없으면 None."""
    for cand in (name + ".exe", name):
        p = os.path.join(bin_dir, cand)
        if os.path.isfile(p):
            return p
    return None


def _qgis_env(root, env):
    """QGIS 번들 GDAL 실행 환경 — GDAL_DATA·PROJ_LIB을 실재 경로로."""
    for var, cands in (("GDAL_DATA", [os.path.join(root, "apps", "gdal", "share", "gdal"),
                                      os.path.join(root, "share", "gdal")]),
                       ("PROJ_LIB", [os.path.join(root, "apps", "proj", "share", "proj"),
                                     os.path.join(root, "share", "proj")])):
        for c in cands:
            if os.path.isdir(c):
                env[var] = c
                break
    return env


def gdal_env_and_bin(explicit=None):
    """(env, bin_dir, 설명) — 못 찾으면 (None, None, 시도 목록)."""
    env = os.environ.copy()
    tried = []
    cands = []
    if explicit:
        cands.append(("--gdal-bin", explicit, None))
    if os.environ.get("GDAL_BIN"):
        cands.append(("GDAL_BIN", os.environ["GDAL_BIN"], None))
    w = shutil.which("gdal_translate")
    if w:
        cands.append(("PATH", os.path.dirname(w), None))
    if os.environ.get("QGIS_ROOT"):
        qr = os.environ["QGIS_ROOT"]
        cands.append(("QGIS_ROOT", os.path.join(qr, "bin"), qr))
    for pf in {os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")} - {None}:
        for qr in sorted(glob.glob(os.path.join(pf, "QGIS*")), reverse=True):
            cands.append(("QGIS 설치본", os.path.join(qr, "bin"), qr))
    for label, bin_dir, qroot in cands:
        tried.append(f"{label}: {bin_dir}")
        if _exe(bin_dir, "gdal_translate") and _exe(bin_dir, "gdalwarp"):
            if qroot:
                env = _qgis_env(qroot, env)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
            return env, bin_dir, f"{label} ({bin_dir})"
    return None, None, tried


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_gcps(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            src = (r.get("source") or "").strip()
            if not src:
                print(f"[오류] gcp.csv {i}행: source 공란 — 출처 없는 좌표 금지.")
                sys.exit(2)
            rows.append({"px": float(r["pixel_x"]), "py": float(r["pixel_y"]),
                         "lon": float(r["lon"]), "lat": float(r["lat"]),
                         "source": src, "certainty": (r.get("certainty") or "").strip().lower(),
                         "note": (r.get("note") or "").strip()})
    return rows


def main():
    ap = argparse.ArgumentParser(description="GCP 파일 기반 재현 가능 지오레퍼런싱")
    ap.add_argument("image", help="스캔 이미지(png/jpg/tif)")
    ap.add_argument("gcps", help="GCP CSV (pixel_x,pixel_y,lon,lat,source,certainty[,note])")
    ap.add_argument("output", help="출력 GeoTIFF")
    ap.add_argument("--method", choices=["tps", "poly1", "poly2"], default="tps")
    ap.add_argument("--crs", default="EPSG:4326")
    ap.add_argument("--gdal-bin", help="gdal_translate·gdalwarp가 든 폴더(자동 탐색 대신)")
    args = ap.parse_args()

    env, bin_dir, how = gdal_env_and_bin(args.gdal_bin)
    if not env:
        print("[오류] GDAL(gdal_translate·gdalwarp)을 찾지 못함 — GDAL 또는 QGIS를 설치하고 PATH에 두거나 "
              "--gdal-bin / 환경변수 GDAL_BIN·QGIS_ROOT로 지정. 시도: " + "; ".join(how or ["(후보 없음)"]))
        return 2
    gcps = read_gcps(args.gcps)
    n_min = {"tps": 10, "poly1": 3, "poly2": 6}[args.method]
    if len(gcps) < n_min:
        print(f"[경고] {args.method}에 GCP {len(gcps)}개 — 권장 최소 {n_min}개(계속 진행하나 왜곡 주의).")
    lows = [g for g in gcps if g["certainty"] == "low"]
    if lows:
        print(f"[경고] certainty=low GCP {len(lows)}개 — 확인·강등 대상.")

    interim = args.output + ".gcp.tif"
    cmd1 = [_exe(bin_dir, "gdal_translate"), "-of", "GTiff", "-a_srs", args.crs]
    for g in gcps:
        cmd1 += ["-gcp", str(g["px"]), str(g["py"]), str(g["lon"]), str(g["lat"])]
    cmd1 += [args.image, interim]
    method_args = {"tps": ["-tps"], "poly1": ["-order", "1"], "poly2": ["-order", "2"]}[args.method]
    cmd2 = [_exe(bin_dir, "gdalwarp"), "-r", "bilinear", "-t_srs", args.crs,
            "-co", "COMPRESS=LZW", "-dstalpha", "-overwrite"] + method_args + [interim, args.output]

    for label, cmd in (("gdal_translate(-gcp)", cmd1), ("gdalwarp", cmd2)):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if r.returncode != 0:
            print(f"[오류] {label} 실패:\n{(r.stderr or r.stdout)[-1500:]}")
            return 1
    try:
        os.remove(interim)
    except OSError:
        pass

    gdalinfo = _exe(bin_dir, "gdalinfo")
    info, gver = "", "?"
    if gdalinfo:
        info = subprocess.run([gdalinfo, args.output], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env).stdout
        gver = (subprocess.run([gdalinfo, "--version"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env).stdout or "?").strip()
    extent = "\n".join(ln for ln in info.splitlines()
                       if ln.startswith(("Upper Left", "Lower Right", "Size is", "Coordinate System is",
                                         "    GEOGCRS", "        ID")))

    mf = os.path.splitext(args.output)[0] + ".manifest.md"
    with open(mf, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 지오레퍼런싱 매니페스트 — {os.path.basename(args.output)} ({datetime.date.today().isoformat()})\n\n")
        f.write("## ① 재현 명령\n\n```\npython tools/georef.py "
                f"\"{args.image}\" \"{args.gcps}\" \"{args.output}\" --method {args.method} --crs {args.crs}\n```\n\n")
        f.write(f"## ② 입력\n\n- 스캔: `{os.path.basename(args.image)}` · sha256 `{sha256_of(args.image)}`\n"
                f"- GCP: `{os.path.basename(args.gcps)}` · sha256 `{sha256_of(args.gcps)}` · {len(gcps)}점\n"
                f"- 변환: {args.method} · 대상 CRS {args.crs} · {gver} (탐색: {how})\n\n")
        f.write("## ③ GCP 전문 (파일이 진실 — GUI 클릭 아님)\n\n"
                "| px | py | lon | lat | source | certainty |\n|---|---|---|---|---|---|\n")
        for g in gcps:
            f.write(f"| {g['px']} | {g['py']} | {g['lon']} | {g['lat']} | {g['source']} | {g['certainty']} |\n")
        f.write(f"\n## ④ 산출 검증 (gdalinfo)\n\n```\n{extent or '(gdalinfo 없음)'}\n```\n\n")
        f.write("## ⑤ 한계\n\n- 정합 품질은 GCP의 질에 종속 — 대응점 전거(source)가 약하면 지도도 약하다. "
                "certainty=low는 확인·강등 대상.\n- 역사 지도의 지형(하도·해안선)은 현대와 다르다 — "
                "현대 베이스와 겹칠 때 그 차이 자체가 사료다.\n")
    print(f"산출: {args.output} + {os.path.basename(mf)}")
    print(extent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
