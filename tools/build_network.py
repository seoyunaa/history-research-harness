"""history-research-harness 네트워크 시각화 — 인물·관계 CSV → 재현 가능한 네트워크 4중 출력.

지리 재현성 원칙의 네트워크 판:
- 원본 = CSV(persons + relationship-claims). 그래프·도판은 파생물 — 같은 인자로 재생성.
- 反날조: 주장(claims)의 인명 문자열은 persons·name_variants와 **정확 일치**로만 결속.
  못 잇는 주장은 그리지 않고 [GAP: 미결속] 대기열로 매니페스트에 남긴다(저자 게이트).
  퍼지 매칭·유사도 추측을 하지 않는다 — 오결속은 좌표 날조와 같은 실패모드다.
- 상충 주장 보존: 관계 엣지는 certainty를 운반 — high=실선, medium/low=점선.
  같은 쌍의 복수 주장도 각각 보존한다(멀티그래프).
- 재현성: 레이아웃 시드 고정, 매니페스트에 입력 SHA-256·시드·버전·환경 스냅샷 동봉.

입력 계약:
  persons.csv  : person_id, display_name, [name_* 표기 열 — 원어·로마자 등, 모두 결속 색인에 들어감],
                 [father_id, mother_id, sex, role_primary, house_group_id, person_status]
  claims.csv   : claim_id, <A>_raw, <A>_norm, <B>_raw, <B>_norm, [rel_type, certainty, source_ref]
                 (<A>/<B> 접두는 --a-col/--b-col, 기본 person_a/person_b. 예: 혼인 주장이면
                  --a-col wife --b-col husband 처럼 원자료 열 이름에 맞춘다)
  name_variants.csv : form, person_id

출력(--out 폴더):
  network.gexf             Gephi / Gephi Lite(브라우저) 손 탐색용
  network.html             pyvis 인터랙티브(단일 파일, 자기완결)
  fig_network.png/.svg     matplotlib 정적(논문 도판 후보)
  network_manifest.md      매니페스트(도표 매니페스트 문법) + [GAP: 미결속] 대기열
  environment_snapshot.txt pip freeze 전체(재현 환경)

사용:
  python tools/build_network.py --persons <persons.csv> --out <폴더>
      [--variants <name_variants.csv>] [--claims <relationship-claims.csv>]
      [--a-col person_a] [--b-col person_b] [--rel-label 관계]
      [--seed 42] [--label-min-degree 3]
"""
import argparse
import csv
import datetime
import hashlib
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:  # BOM 방어
        return list(csv.DictReader(f))


def pkg_version(name):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return "?"


def build_name_index(persons, variants):
    """정확 일치 전용 인명 색인: 표기 → person_id 집합(동명이인은 집합으로 보존)."""
    idx = {}

    def put(form, pid):
        form = (form or "").strip()
        if form:
            idx.setdefault(form, set()).add(pid)

    for p in persons:
        pid = p["person_id"]
        # display_name + 모든 name_* 표기 열(원어·로마자·이표기 등 — 연구 대상에 맞게 열을 둔다)
        for col in ["display_name"] + [c for c in p.keys() if c and c.startswith("name_")]:
            put(p.get(col), pid)
    for v in variants:
        put(v.get("form"), v.get("person_id"))
    return idx


def resolve(name_raw, name_norm, idx):
    """norm→raw 순 정확 일치. (person_id, 방식) 또는 (None, 실패사유)."""
    for label, form in (("norm", name_norm), ("raw", name_raw)):
        form = (form or "").strip()
        if not form:
            continue
        hit = idx.get(form)
        if hit and len(hit) == 1:
            return next(iter(hit)), f"정확일치({label})"
        if hit and len(hit) > 1:
            return None, f"동명이인 {len(hit)}건({form}) — 저자 판별 필요"
    return None, "색인에 없음"


def claim_sides(c, a_col, b_col):
    """주장 행에서 양쪽 인명(raw, norm)을 꺼낸다. 열 이름은 <접두>_raw / <접두>_norm."""
    return ((c.get(f"{a_col}_raw"), c.get(f"{a_col}_norm")),
            (c.get(f"{b_col}_raw"), c.get(f"{b_col}_norm")))


def main():
    ap = argparse.ArgumentParser(description="인물·관계 CSV → 재현 가능한 네트워크")
    ap.add_argument("--persons", required=True, help="persons.csv (person_id·display_name·father_id·mother_id…)")
    ap.add_argument("--variants", help="name_variants.csv (form→person_id, 주장 결속 정확도 향상)")
    ap.add_argument("--claims", help="relationship-claims.csv (혼인·사승·동맹 등 관계 주장 — 문자열 인명)")
    ap.add_argument("--a-col", default="person_a", help="주장의 A측 인명 열 접두(<접두>_raw/_norm, 기본 person_a)")
    ap.add_argument("--b-col", default="person_b", help="주장의 B측 인명 열 접두(기본 person_b)")
    ap.add_argument("--rel-label", default="관계", help="rel_type 열이 없을 때 엣지 표시명(기본 '관계')")
    ap.add_argument("--title", default="인물 관계 네트워크", help="정적 도판 제목")
    ap.add_argument("--out", required=True, help="출력 폴더")
    ap.add_argument("--seed", type=int, default=42, help="레이아웃 시드(기본 42 — 재현 고정)")
    ap.add_argument("--label-min-degree", type=int, default=3, help="정적 도판에 라벨을 붙일 최소 연결수")
    args = ap.parse_args()

    import networkx as nx

    os.makedirs(args.out, exist_ok=True)
    persons = read_csv(args.persons)
    variants = read_csv(args.variants) if args.variants else []
    claims = read_csv(args.claims) if args.claims else []

    # ---- 노드: persons가 유일한 노드 원천 (주장에서 노드를 만들어내지 않는다) ----
    G = nx.MultiGraph()
    for p in persons:
        G.add_node(p["person_id"], label=p.get("display_name") or p["person_id"],
                   sex=p.get("sex") or "", role=p.get("role_primary") or "",
                   house=p.get("house_group_id") or "", status=p.get("person_status") or "")

    # ---- 친자 엣지: persons의 father_id/mother_id (ID 결속 — 결손은 기록) ----
    missing_parents = []
    for p in persons:
        for col, kind in (("father_id", "father"), ("mother_id", "mother")):
            pid = (p.get(col) or "").strip()
            if not pid:
                continue
            if pid in G:
                G.add_edge(pid, p["person_id"], kind="parent", subkind=kind, certainty="high")
            else:
                missing_parents.append((p["person_id"], col, pid))

    # ---- 관계 엣지: 주장을 정확 일치로만 결속, 실패는 대기열 ----
    idx = build_name_index(persons, variants)
    if claims and not any(f"{args.a_col}_raw" in c or f"{args.a_col}_norm" in c for c in claims[:1]):
        print(f"  [경고] claims에 '{args.a_col}_raw'/'{args.a_col}_norm' 열이 없음 — --a-col/--b-col을 원자료 열 접두에 맞출 것")
    matched, unmatched = [], []
    for c in claims:
        (a_raw, a_norm), (b_raw, b_norm) = claim_sides(c, args.a_col, args.b_col)
        a, how_a = resolve(a_raw, a_norm, idx)
        b, how_b = resolve(b_raw, b_norm, idx)
        if a and b:
            G.add_edge(a, b, kind="claim", rel=(c.get("rel_type") or args.rel_label),
                       claim_id=c.get("claim_id") or "",
                       certainty=(c.get("certainty") or "unknown").lower(),
                       source_ref=c.get("source_ref") or "", match=f"{how_a}/{how_b}")
            matched.append(c)
        else:
            why = []
            if not a:
                why.append(f"A측({args.a_col}) '{(a_norm or a_raw or '').strip()}': {how_a}")
            if not b:
                why.append(f"B측({args.b_col}) '{(b_norm or b_raw or '').strip()}': {how_b}")
            unmatched.append((c.get("claim_id") or "?", " · ".join(why)))

    n_parent = sum(1 for _, _, d in G.edges(data=True) if d["kind"] == "parent")
    n_rel = sum(1 for _, _, d in G.edges(data=True) if d["kind"] == "claim")
    print(f"노드 {G.number_of_nodes()} · 친자 {n_parent} · 관계 주장 {n_rel}(결속 {len(matched)}/{len(claims)}) · 미결속 {len(unmatched)}")

    # ---- 출력 1: GEXF (Gephi Lite) ----
    gexf_path = os.path.join(args.out, "network.gexf")
    nx.write_gexf(G, gexf_path)

    # ---- 출력 2: pyvis 인터랙티브 HTML (자기완결) ----
    html_path = os.path.join(args.out, "network.html")
    try:
        from pyvis.network import Network
        net = Network(height="900px", width="100%", cdn_resources="in_line", notebook=False)
        net.barnes_hut()
        for n, d in G.nodes(data=True):
            color = "#c0392b" if d.get("sex") == "F" else "#2c5f8a"
            net.add_node(n, label=d.get("label") or n, color=color,
                         title=f"{d.get('label')} | {d.get('role')} | {d.get('house')}")
        for u, v, d in G.edges(data=True):
            if d["kind"] == "parent":
                net.add_edge(u, v, color="#999999", width=1,
                             title=f"친자({d.get('subkind','')})")
            else:
                dashed = d.get("certainty") != "high"
                net.add_edge(u, v, color="#c0392b", width=2, dashes=dashed,
                             title=f"{d.get('rel')} {d.get('claim_id')} · certainty={d.get('certainty')} · {d.get('source_ref') or '[GAP:전거]'}")
        # pyvis write_html은 Windows에서 cp949로 저장을 시도한다 — utf-8로 직접 저장
        html = net.generate_html(notebook=False)
        with open(html_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    except Exception as e:
        html_path = None
        print(f"  [경고] pyvis HTML 생략: {type(e).__name__}: {e}")

    # ---- 출력 3: matplotlib 정적 (시드 고정) ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # CJK: networkx 라벨은 font_family='sans-serif'를 쓰므로 sans-serif 목록을 교체한다
    # (있는 글꼴부터 쓰인다 — Windows·macOS·Linux(Noto CJK) 순 후보)
    matplotlib.rcParams["font.sans-serif"] = ["Malgun Gothic", "Microsoft YaHei", "AppleGothic",
                                              "Noto Sans CJK KR", "Noto Sans CJK SC", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["axes.unicode_minus"] = False

    S = nx.Graph()  # 레이아웃용 단순 투영(엣지 속성은 대표 1건)
    S.add_nodes_from(G.nodes(data=True))
    for u, v, d in G.edges(data=True):
        if not S.has_edge(u, v) or (d["kind"] == "claim" and S[u][v]["kind"] == "parent"):
            S.add_edge(u, v, **{k: d.get(k, "") for k in ("kind", "certainty")})
    pos = nx.spring_layout(S, seed=args.seed, k=0.18)

    fig, ax = plt.subplots(figsize=(16, 12), dpi=150)
    deg = dict(S.degree())
    node_colors = ["#c0392b" if S.nodes[n].get("sex") == "F" else "#2c5f8a" for n in S.nodes]
    nx.draw_networkx_nodes(S, pos, node_size=[40 + 25 * deg[n] for n in S.nodes],
                           node_color=node_colors, alpha=0.85, ax=ax)
    ep = [(u, v) for u, v, d in S.edges(data=True) if d["kind"] == "parent"]
    em_hi = [(u, v) for u, v, d in S.edges(data=True) if d["kind"] == "claim" and d.get("certainty") == "high"]
    em_lo = [(u, v) for u, v, d in S.edges(data=True) if d["kind"] == "claim" and d.get("certainty") != "high"]
    nx.draw_networkx_edges(S, pos, edgelist=ep, edge_color="#bbbbbb", width=0.7, ax=ax)
    nx.draw_networkx_edges(S, pos, edgelist=em_hi, edge_color="#c0392b", width=1.8, ax=ax)
    nx.draw_networkx_edges(S, pos, edgelist=em_lo, edge_color="#e67e22", width=1.6, style="dashed", ax=ax)
    labels = {n: S.nodes[n]["label"] for n in S.nodes if deg[n] >= args.label_min_degree}
    # 라벨 글꼴은 위 sans-serif 후보 목록에서(간체 한자 인명이면 YaHei·Noto SC가 tofu를 피한다)
    nx.draw_networkx_labels(S, pos, labels=labels, font_size=7, ax=ax)
    ax.set_title(f"{args.title} — 노드 {S.number_of_nodes()} · 관계 결속 {len(matched)}/{len(claims)} "
                 f"(실선=high·점선=medium/low · 미결속 {len(unmatched)}건은 매니페스트 대기열)",
                 fontsize=11)
    ax.axis("off")
    fig.tight_layout()
    png_path = os.path.join(args.out, "fig_network.png")
    fig.savefig(png_path)
    fig.savefig(os.path.join(args.out, "fig_network.svg"))
    plt.close(fig)

    # ---- 환경 스냅샷 (산출물 provenance) ----
    env_path = os.path.join(args.out, "environment_snapshot.txt")
    try:
        freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                                capture_output=True, text=True).stdout
    except Exception:
        freeze = "(pip freeze 실패)"
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {datetime.datetime.now().isoformat(timespec='seconds')} · python {sys.version.split()[0]}\n{freeze}")

    # ---- 매니페스트 (v8 도표 매니페스트 문법) ----
    cmd = f"python tools/build_network.py --persons \"{args.persons}\"" \
          + (f" --variants \"{args.variants}\"" if args.variants else "") \
          + (f" --claims \"{args.claims}\" --a-col {args.a_col} --b-col {args.b_col}"
             f" --rel-label \"{args.rel_label}\"" if args.claims else "") \
          + f" --title \"{args.title}\"" \
          + f" --out \"{args.out}\" --seed {args.seed} --label-min-degree {args.label_min_degree}"
    mf = os.path.join(args.out, "network_manifest.md")
    with open(mf, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 네트워크 매니페스트 — {datetime.date.today().isoformat()}\n\n")
        f.write("## ① 생성 코드 (재현 명령)\n\n```\n" + cmd + "\n```\n\n")
        f.write(f"## ② 환경\n\npython {sys.version.split()[0]} · networkx {pkg_version('networkx')} · "
                f"pyvis {pkg_version('pyvis')} · matplotlib {pkg_version('matplotlib')} · "
                f"레이아웃 spring_layout(seed={args.seed}) · 전체: `environment_snapshot.txt`\n\n")
        f.write("## ③ 설명·뒷받침 주장\n\n노드=persons.csv의 인물(주장에서 노드를 만들지 않음). "
                "회색=친자(father/mother ID 결속), 적색 실선=관계 주장(certainty high), 주황 점선=관계 주장(medium/low — 상충·불확실 주장 보존). "
                "관계 엣지는 개별 주장(claim) 단위로 보존된다(멀티그래프 — 같은 쌍의 복수 주장도 각각).\n\n")
        f.write("## ④ 입력 데이터\n\n")
        for name, path, rows in (("persons", args.persons, len(persons)),
                                 ("name_variants", args.variants, len(variants)),
                                 ("claims", args.claims, len(claims))):
            if path:
                f.write(f"- {name}: `{os.path.abspath(path)}` · {rows}행 · sha256 `{sha256_of(path)}`\n")
        f.write(f"\n## ⑤ 통계\n\n노드 {G.number_of_nodes()} · 친자 엣지 {n_parent} · "
                f"관계 주장 엣지 {n_rel} (결속 {len(matched)}/{len(claims)})\n\n")
        if missing_parents:
            f.write(f"## ⑥ 친자 결손 (father/mother_id가 persons에 없음 — {len(missing_parents)}건)\n\n")
            for pid, col, ref in missing_parents:
                f.write(f"- `{pid}`의 {col} → `{ref}` (미등재)\n")
            f.write("\n")
        if unmatched:
            f.write(f"## ⑦ [GAP: 미결속] 주장 대기열 ({len(unmatched)}건 — 저자 게이트)\n\n")
            f.write("정확 일치 실패로 **그리지 않은** 주장들이다. name_variants에 표기를 등록하거나 "
                    "저자가 person_id를 판별해 결속한 뒤 재실행한다. 퍼지 매칭으로 자동 결속하지 않는다.\n\n")
            for cid, why in unmatched:
                f.write(f"- `{cid}` — {why}\n")
            f.write("\n")
        f.write("## ⑧ 한계\n\n- 이 그래프는 파생물이다 — 진실은 CSV(그리고 그 뒤의 사료 전거). "
                "관계 엣지의 근거는 각 claim의 source_ref·evidence_text로 역추적한다.\n"
                "- 정적 도판의 라벨은 연결수 기준 선별(전체 라벨은 network.html·GEXF에서).\n")
    print(f"출력: {args.out}")
    print(f"  network.gexf · {'network.html · ' if html_path else ''}fig_network.png/.svg · network_manifest.md · environment_snapshot.txt")
    if unmatched:
        print(f"[GAP: 미결속] {len(unmatched)}건 — 매니페스트 ⑦절 대기열 확인(저자 게이트).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
