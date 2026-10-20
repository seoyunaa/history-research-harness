"""history-research-harness 통시 세력 변천 — 세대×집단 관계 주장 변천을 재현 가능하게.

시각화 문법의 출처(자체 재구현): IADIS 2023 발표 논문 "Visual Analytics for the Marriage
Network in the Goryeo Dynasty, Korea"의 DiachronicPowerChanges(서지 전체는 references/시각화-참조.md) —
"재위(시간)×본관(집단)×혼인(링크)×중심성" 문법을 임의 시대의 관계 주장 데이터로 일반화했다.
코드·데이터는 가져오지 않았다(라이선스 없음 = 저작권 보유).

反날조 규율:
- 관계 주장 결속은 build_network.py와 동일 — persons·name_variants **정확 일치**만.
- 시간축은 해석적 시기 배정이 아니라 **친자 그래프의 기계적 세대 거리**
  (--root 인물로부터 father/mother 엣지를 따라 계산)만 쓴다. 도달 불가한
  인물의 주장은 그리지 않고 [GAP: 세대 미상] 대기열로(저자 게이트).
- 집계 CSV의 각 행에 근거 claim_id를 병기해 사료 전거까지 역추적 가능하게 한다.

집계 규칙: 세대는 주장의 A측 인물(--a-col)에서, 집단은 B측 인물(--b-col)의 house_group_id에서 잡는다
(예: "각 세대의 딸들이 어느 가문과 혼인했나"면 A=딸, B=배우자. 다른 물음이면 A/B를 바꿔 준다).

출력(--out): diachronic_relations.csv(집계 파생 뷰·claim_id 병기) ·
fig_diachronic.png/.svg(세대×집단 누적 막대, 시드 불요·결정론) ·
diachronic_manifest.md(①~⑧+인용) · environment_snapshot.txt

사용:
  python tools/build_diachronic.py --persons <persons.csv> --claims <claims.csv> --root <세대0 person_id>
      --out <폴더> [--variants <name_variants.csv>] [--groups <groups.csv>]
      [--a-col person_a] [--b-col person_b] [--top-groups 8]
"""
import argparse
import collections
import datetime
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from build_network import read_csv, sha256_of, build_name_index, resolve, pkg_version, claim_sides  # noqa: E402


def generations_from_root(persons, root):
    """친자 엣지(parent→child)를 따라 root로부터의 세대 수를 기계적으로 계산.
    child 세대 = min(부모 세대)+1. 도달 불가 인물은 None(대기열)."""
    children = collections.defaultdict(list)
    for p in persons:
        for col in ("father_id", "mother_id"):
            pid = (p.get(col) or "").strip()
            if pid:
                children[pid].append(p["person_id"])
    gen = {root: 0}
    queue = collections.deque([root])
    while queue:
        cur = queue.popleft()
        for ch in children[cur]:
            g = gen[cur] + 1
            if ch not in gen or g < gen[ch]:
                gen[ch] = g
                queue.append(ch)
    return gen


def main():
    ap = argparse.ArgumentParser(description="세대×집단 관계 주장 변천(DPC 문법 재구현)")
    ap.add_argument("--persons", required=True)
    ap.add_argument("--variants")
    ap.add_argument("--claims", required=True)
    ap.add_argument("--groups", help="groups.csv (group_id, group_name_display|group_name_romanized — 집단 표시명)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", required=True, help="세대 0 기준 인물 person_id")
    ap.add_argument("--a-col", default="person_a", help="세대를 잴 A측 인명 열 접두(<접두>_raw/_norm)")
    ap.add_argument("--b-col", default="person_b", help="집단을 잴 B측 인명 열 접두")
    ap.add_argument("--top-groups", "--top-houses", dest="top_groups", type=int, default=8,
                    help="개별 표시할 집단 수(나머지는 기타)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    persons = read_csv(args.persons)
    variants = read_csv(args.variants) if args.variants else []
    claims = read_csv(args.claims)
    groups = read_csv(args.groups) if args.groups else []

    pid_row = {p["person_id"]: p for p in persons}
    if args.root not in pid_row:
        print(f"[오류] root '{args.root}'가 persons에 없음")
        return 2
    gname = {g["group_id"]: (g.get("group_name_display") or g.get("group_name_romanized") or g["group_id"])
             for g in groups}

    gen = generations_from_root(persons, args.root)
    idx = build_name_index(persons, variants)

    # 주장 → (세대, 집단) 집계. 실패는 종류별 대기열.
    agg = collections.defaultdict(list)          # (gen, group_id) -> [claim_id...]
    q_unmatched, q_nogen, q_nogroup = [], [], []
    seen_ids = collections.Counter()
    dup_ids = 0
    for rownum, c in enumerate(claims, start=2):  # 2 = 헤더 다음 행(원본 CSV 행 번호)
        cid = c.get("claim_id") or "?"
        seen_ids[cid] += 1
        if seen_ids[cid] > 1:                     # 원천의 claim_id 중복 — 행 번호로 구분(역추적 보전)
            cid = f"{cid}@r{rownum}"
            dup_ids += 1
        (a_raw, a_norm), (b_raw, b_norm) = claim_sides(c, args.a_col, args.b_col)
        a, _ = resolve(a_raw, a_norm, idx)
        b, _ = resolve(b_raw, b_norm, idx)
        if not (a and b):
            q_unmatched.append(cid)
            continue
        if a not in gen:
            q_nogen.append((cid, pid_row[a].get("display_name") or a))
            continue
        grp = (pid_row[b].get("house_group_id") or "").strip()
        if not grp:
            q_nogroup.append((cid, pid_row[b].get("display_name") or b))
            continue
        agg[(gen[a], grp)].append(cid)

    # ---- 집계 파생 뷰 CSV (claim_id 병기 = 전거 역추적) ----
    csv_path = os.path.join(args.out, "diachronic_relations.csv")
    with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("generation,group_id,group_name,count,claim_ids\n")
        for (g, h), cids in sorted(agg.items()):
            f.write(f"{g},{h},{gname.get(h, h)},{len(cids)},{';'.join(cids)}\n")

    total = sum(len(v) for v in agg.values())
    print(f"주장 {len(claims)} → 집계 {total} · 미결속 {len(q_unmatched)} · 세대미상 {len(q_nogen)} · 집단미상 {len(q_nogroup)}")

    # ---- 도판: 세대×집단 누적 막대 (결정론 — 시드 불요) ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["font.sans-serif"] = ["Malgun Gothic", "Microsoft YaHei", "AppleGothic",
                                              "Noto Sans CJK KR", "Noto Sans CJK SC", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["axes.unicode_minus"] = False

    grp_tot = collections.Counter()
    for (g, h), cids in agg.items():
        grp_tot[h] += len(cids)
    top = [h for h, _ in grp_tot.most_common(args.top_groups)]
    gens = sorted({g for g, _ in agg})
    series = {h: [sum(len(c) for (gg, hh), c in agg.items() if gg == g and hh == h) for g in gens] for h in top}
    etc = [sum(len(c) for (gg, hh), c in agg.items() if gg == g and hh not in top) for g in gens]

    fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
    cmap = plt.get_cmap("tab10")
    bottom = [0] * len(gens)
    for i, h in enumerate(top):
        vals = series[h]
        ax.bar(gens, vals, bottom=bottom, color=cmap(i % 10), width=0.7,
               label=gname.get(h, h))
        bottom = [b + v for b, v in zip(bottom, vals)]
    if any(etc):
        ax.bar(gens, etc, bottom=bottom, color="#bbbbbb", width=0.7, label="기타")
    ax.set_xlabel(f"세대(친자 그래프 상 {pid_row[args.root].get('display_name') or args.root}로부터의 거리)")
    ax.set_ylabel("결속된 관계 주장 수")
    ax.set_xticks(gens)
    ax.set_title(f"세대별 관계 상대 집단 구성 — 결속 {total}/{len(claims)}건만 표시"
                 f" (미결속·세대미상·집단미상 {len(q_unmatched)+len(q_nogen)+len(q_nogroup)}건은 대기열)",
                 fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "fig_diachronic.png"))
    fig.savefig(os.path.join(args.out, "fig_diachronic.svg"))
    plt.close(fig)

    # ---- 환경 스냅샷 ----
    env_path = os.path.join(args.out, "environment_snapshot.txt")
    try:
        freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    except Exception:
        freeze = "(pip freeze 실패)"
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {datetime.datetime.now().isoformat(timespec='seconds')} · python {sys.version.split()[0]}\n{freeze}")

    # ---- 매니페스트 ----
    cmd = (f"python tools/build_diachronic.py --persons \"{args.persons}\" --claims \"{args.claims}\""
           + (f" --variants \"{args.variants}\"" if args.variants else "")
           + (f" --groups \"{args.groups}\"" if args.groups else "")
           + f" --out \"{args.out}\" --root {args.root} --a-col {args.a_col} --b-col {args.b_col}"
           + f" --top-groups {args.top_groups}")
    with open(os.path.join(args.out, "diachronic_manifest.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 통시 세력 변천 매니페스트 — {datetime.date.today().isoformat()}\n\n")
        f.write("## ① 생성 코드 (재현 명령)\n\n```\n" + cmd + "\n```\n\n")
        f.write(f"## ② 환경\n\npython {sys.version.split()[0]} · matplotlib {pkg_version('matplotlib')} · "
                f"결정론(시드 불요) · 전체: `environment_snapshot.txt`\n\n")
        f.write("## ③ 설명·뒷받침 주장\n\n세대(x)별 관계 상대 집단(색)의 주장 건수 구성. "
                f"세대는 A측({args.a_col}) 인물의, 집단은 B측({args.b_col}) 인물의 house_group_id다. "
                "세대는 해석적 시기 배정이 아니라 친자 그래프의 기계적 거리다. "
                "각 막대의 근거 주장은 `diachronic_relations.csv`의 claim_ids로 역추적한다.\n\n")
        f.write("## ④ 입력 데이터\n\n")
        for name, path, rows in (("persons", args.persons, len(persons)), ("variants", args.variants, len(variants)),
                                 ("claims", args.claims, len(claims)), ("groups", args.groups, len(groups))):
            if path:
                f.write(f"- {name}: `{os.path.abspath(path)}` · {rows}행 · sha256 `{sha256_of(path)}`\n")
        f.write(f"\n## ⑤ 통계\n\n주장 {len(claims)} → 세대·집단 집계 {total} · "
                f"미결속 {len(q_unmatched)} · 세대미상 {len(q_nogen)} · 집단미상 {len(q_nogroup)}\n\n")
        if dup_ids:
            f.write(f"⚠ **원천 데이터 결함**: claims의 claim_id 중복 {dup_ids}건 — `@r행번호`로 구분해 역추적을 "
                    f"보전했다. 원천(claims CSV)의 claim_id 고유화가 근본 수리다(저자 게이트).\n\n")
        if q_nogen:
            f.write(f"## ⑥ [GAP: 세대 미상] — root({args.root})에서 친자 엣지로 도달 불가 ({len(q_nogen)}건)\n\n")
            for cid, nm in q_nogen:
                f.write(f"- `{cid}` — {nm} (father/mother_id 결손 또는 방계)\n")
            f.write("\n")
        if q_nogroup:
            f.write(f"## ⑦ [GAP: 집단 미상] — B측 인물의 house_group_id 공란 ({len(q_nogroup)}건)\n\n")
            for cid, nm in q_nogroup:
                f.write(f"- `{cid}` — {nm}\n")
            f.write("\n")
        f.write(f"## ⑧ 미결속 주장 ({len(q_unmatched)}건)\n\n"
                "정확 일치 실패 — build_network.py 매니페스트의 대기열과 동일 건. 저자 판별 후 재실행.\n\n")
        f.write("## 인용 (시각화 문법의 출처 — 자체 재구현)\n\n"
                "\"Visual Analytics for the Marriage Network in the Goryeo Dynasty, Korea\" (IADIS 2023) — "
                "DiachronicPowerChanges의 \"재위×본관×혼인×중심성\" 문법. 코드·데이터 미사용"
                "(서지 전체는 `references/시각화-참조.md`).\n")
    print(f"출력: {args.out} — diachronic_relations.csv · fig_diachronic.png/.svg · diachronic_manifest.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
