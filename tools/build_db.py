#!/usr/bin/env python3
"""build_db.py — 발췌 카드(CSV)에서 SQLite DB를 **재생성**하는 재현 스크립트.

목적
  논문 워크스페이스의 관찰-장소-범주 데이터(관계형 데이터층, 계약: corpus/_relational-schema.md)를
  질의 가능한 관계형 DB로 파생한다. **카드(CSV)가 진실이고 DB는 파생 산출물**이다. 매 실행 시
  DB를 통째로 재빌드한다(산출물마다 ①생성 코드=이 파일 ②환경=표준 라이브러리 sqlite3
  ③평문 설명=이 독스트링 ④입력 데이터=아래 CSV들). 좌표·데이터는 지어내지 않고 오직 CSV에서만 읽는다.

입력 (모두 논문 워크스페이스 폴더 안, 런타임에 읽음)
  places.csv       : place_id,name,name_zh,lon,lat,type,level,source,certainty,modern_name,note
  observations.csv : obs_id,observer,place_id,place_name,p_key,year,quote_ref,note
  obs_categories.csv : obs_id,cat_id            (관찰 ↔ 범주 다대다)
  categories.csv   : cat_id,name,definition,source_terms,scope
  (name_zh 열은 '원어 표기' 자리 — 사료 언어가 한문이 아니어도 열 이름은 계약대로 둔다)

출력
  <워크스페이스>/relational.sqlite (--db로 변경) — 위 CSV에서 재생성된 SQLite DB.
                     외래키: observations.place_id → places.place_id
                             obs_categories.obs_id → observations.obs_id
                             obs_categories.cat_id → categories.cat_id

실행법
  python tools/build_db.py <논문 폴더명 또는 경로> [--db 출력.sqlite]
  예) python tools/build_db.py my-paper         → _workspace/my-paper/ 의 CSV를 읽음

입력 CSV가 하나라도 없으면 친절한 에러를 내고 멈춘다(빈 DB를 만들지 않는다).
"""
import argparse
import os
import sys
import csv
import sqlite3

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 이 파일 위치(tools/) 기준으로 하네스 루트를 잡는다. 데이터 폴더는 main()이 인자로 정한다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = None
DB_PATH = None
DB_NAME = "relational.sqlite"


def set_paths(paper, db=None):
    """논문 폴더(이름 → _workspace/<이름>, 또는 경로)와 DB 경로를 정한다."""
    global DATA_DIR, DB_PATH
    cand = paper if os.path.isdir(paper) else os.path.join(ROOT, "_workspace", paper)
    DATA_DIR = os.path.abspath(cand)
    DB_PATH = os.path.abspath(db) if db else os.path.join(DATA_DIR, DB_NAME)

# 입력 CSV와 각 CSV가 반드시 가져야 할 헤더(스키마 계약).
INPUTS = {
    "places": {
        "file": "places.csv",
        "columns": [
            "place_id", "name", "name_zh", "lon", "lat", "type",
            "level", "source", "certainty", "modern_name", "note",
        ],
    },
    "observations": {
        "file": "observations.csv",
        "columns": [
            "obs_id", "observer", "place_id", "place_name",
            "p_key", "year", "quote_ref", "note",
        ],
    },
    "categories": {
        "file": "categories.csv",
        "columns": ["cat_id", "name", "definition", "source_terms", "scope"],
    },
    "obs_categories": {
        "file": "obs_categories.csv",
        "columns": ["obs_id", "cat_id"],
    },
}

# 테이블 생성 DDL(외래키 선언 포함). 부모 → 자식 순서.
SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE places (
    place_id    TEXT PRIMARY KEY,
    name        TEXT,
    name_zh     TEXT,
    lon         REAL,
    lat         REAL,
    type        TEXT,
    level       TEXT,
    source      TEXT,
    certainty   TEXT,
    modern_name TEXT,
    note        TEXT
);

CREATE TABLE categories (
    cat_id       TEXT PRIMARY KEY,
    name         TEXT,
    definition   TEXT,
    source_terms TEXT,
    scope        TEXT
);

CREATE TABLE observations (
    obs_id     TEXT PRIMARY KEY,
    observer   TEXT,
    place_id   TEXT,
    place_name TEXT,
    p_key      TEXT,
    year       TEXT,
    quote_ref  TEXT,
    note       TEXT,
    FOREIGN KEY (place_id) REFERENCES places(place_id)
);

CREATE TABLE obs_categories (
    obs_id TEXT,
    cat_id TEXT,
    PRIMARY KEY (obs_id, cat_id),
    FOREIGN KEY (obs_id) REFERENCES observations(obs_id),
    FOREIGN KEY (cat_id) REFERENCES categories(cat_id)
);
"""


class BuildError(Exception):
    """입력·스키마 문제를 사용자에게 친절히 전달하기 위한 예외."""


def _read_csv(name):
    """INPUTS[name]의 CSV를 읽어 dict 행 리스트로 돌려준다.

    파일이 없거나 헤더가 계약과 다르면 BuildError를 던진다(데이터를 지어내지 않음).
    """
    spec = INPUTS[name]
    path = os.path.join(DATA_DIR, spec["file"])
    if not os.path.isfile(path):
        raise BuildError(
            "입력 CSV를 찾을 수 없습니다: {p}\n"
            "  → 이 스크립트는 발췌 카드에서 내보낸 CSV만 읽습니다(데이터를 지어내지 않음).\n"
            "  → {f} 를 {d} 에 두고 다시 실행하세요.".format(
                p=path, f=spec["file"], d=DATA_DIR
            )
        )
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in spec["columns"] if c not in header]
        if missing:
            raise BuildError(
                "{f} 의 헤더가 스키마와 다릅니다.\n"
                "  누락된 열: {miss}\n"
                "  기대한 열: {want}\n"
                "  실제 헤더: {have}".format(
                    f=spec["file"],
                    miss=", ".join(missing),
                    want=", ".join(spec["columns"]),
                    have=", ".join(header),
                )
            )
        rows = list(reader)
    return rows


def _rows_to_tuples(rows, columns):
    """dict 행들을 columns 순서의 튜플로. 빈 문자열은 NULL(None)로 정규화."""
    out = []
    for r in rows:
        out.append(tuple((r.get(c) or None) for c in columns))
    return out


def build():
    """CSV들을 읽어 DB를 재생성한다. 성공 시 (DB경로, 행수 dict) 반환."""
    # 1) 먼저 네 CSV를 모두 읽는다(하나라도 없으면 여기서 친절히 실패 → 빈 DB 안 만듦).
    data = {name: _read_csv(name) for name in INPUTS}

    # 2) 기존 DB 삭제 후 재생성(카드=진실, DB=파생).
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA foreign_keys = ON;")

        # 3) 부모 테이블 먼저, 자식 테이블 나중(외래키 충족 순서).
        insert_order = ["places", "categories", "observations", "obs_categories"]
        counts = {}
        for name in insert_order:
            cols = INPUTS[name]["columns"]
            tuples = _rows_to_tuples(data[name], cols)
            placeholders = ", ".join(["?"] * len(cols))
            sql = "INSERT INTO {t} ({c}) VALUES ({p})".format(
                t=name, c=", ".join(cols), p=placeholders
            )
            try:
                conn.executemany(sql, tuples)
            except sqlite3.IntegrityError as e:
                # 외래키/PK 위반 등을 스택트레이스 대신 친절한 에러로 바꾼다.
                raise BuildError(
                    "{f} 삽입 중 무결성 오류: {e}\n"
                    "  → 참조하는 place_id / obs_id / cat_id 가 부모 CSV에 있는지,\n"
                    "     또는 중복된 기본키(id)가 없는지 확인하세요.".format(
                        f=INPUTS[name]["file"], e=e
                    )
                )
            counts[name] = len(tuples)

        conn.commit()

        # 4) 외래키 무결성 점검(고아 참조가 있으면 사용자에게 알림).
        violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if violations:
            detail = "\n".join(
                "  {tbl} rowid={rid} → {parent}".format(tbl=v[0], rid=v[1], parent=v[2])
                for v in violations
            )
            raise BuildError(
                "외래키 무결성 위반이 있습니다(참조 대상이 없는 행):\n" + detail +
                "\n  → CSV의 place_id / obs_id / cat_id 참조를 확인하세요."
            )
    finally:
        conn.close()

    return DB_PATH, counts


def query_convergent_observations(db_path=None):
    """예시 쿼리: '한 place에 수렴하는 관찰'.

    place_id별로 관찰을 집계한다:
      - obs_count    : 그 장소에 걸린 관찰 수
      - observers    : 서로 다른 관찰자 수 / 관찰자 목록
      - categories   : 그 장소에서 관측된 서로 다른 범주 수 / 범주 목록
    여러 관찰자·여러 범주가 한 장소로 수렴할수록 상단에 온다(독립 관찰의 수렴도).
    """
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = """
        SELECT
            p.place_id                          AS place_id,
            p.name                              AS name,
            p.name_zh                           AS name_zh,
            COUNT(DISTINCT o.obs_id)            AS obs_count,
            COUNT(DISTINCT o.observer)          AS observer_count,
            GROUP_CONCAT(DISTINCT o.observer)   AS observers,
            COUNT(DISTINCT oc.cat_id)           AS category_count,
            GROUP_CONCAT(DISTINCT c.name)       AS categories
        FROM places p
        JOIN observations o     ON o.place_id = p.place_id
        LEFT JOIN obs_categories oc ON oc.obs_id = o.obs_id
        LEFT JOIN categories c      ON c.cat_id = oc.cat_id
        GROUP BY p.place_id
        ORDER BY observer_count DESC, category_count DESC, obs_count DESC
        """
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="관계형 데이터층 CSV → SQLite DB 재생성(파생물)")
    ap.add_argument("paper", help="논문 워크스페이스 폴더명(_workspace/ 아래) 또는 경로")
    ap.add_argument("--db", help=f"출력 DB 경로(기본: <워크스페이스>/{DB_NAME})")
    args = ap.parse_args()
    set_paths(args.paper, args.db)
    if not os.path.isdir(DATA_DIR):
        sys.stderr.write(f"[build_db] 워크스페이스 폴더 없음: {DATA_DIR}\n")
        return 1
    try:
        db_path, counts = build()
    except BuildError as e:
        sys.stderr.write("[build_db] 빌드 실패:\n" + str(e) + "\n")
        return 1

    print("[build_db] 재생성 완료: {p}".format(p=db_path))
    for name in ["places", "categories", "observations", "obs_categories"]:
        print("  {t:16s} {n:6d} 행".format(t=name, n=counts[name]))

    # 예시 쿼리 시연: 한 place에 수렴하는 관찰.
    rows = query_convergent_observations(db_path)
    if rows:
        print("\n[예시] 한 place에 수렴하는 관찰 (관찰자·범주 수렴도 순):")
        for r in rows[:20]:
            print(
                "  {name}({zh}) — 관찰 {oc}, 관찰자 {vc}[{vs}], 범주 {cc}[{cs}]".format(
                    name=r["name"],
                    zh=r["name_zh"] or "",
                    oc=r["obs_count"],
                    vc=r["observer_count"],
                    vs=r["observers"] or "",
                    cc=r["category_count"],
                    cs=r["categories"] or "",
                )
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
