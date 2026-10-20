"""history-research-harness 도서관 공통 설정 — 검색 위계(references/library/sources.txt)와 경로.

library_index · library_search · endnote_sync · refresh · verify 가 이 파서 하나를 공유한다
(도구마다 sources.txt를 따로 해석해 서로 다른 폴더를 보는 일을 막는다).

sources.txt 형식 — 한 줄에 `키: 값`, `#`로 시작하는 줄은 주석:
  tier1: <폴더>[, <폴더> ...]   1차 지정 로컬 폴더. 여러 줄 또는 콤마(,)·세미콜론(;) 구분.
  endnote: <.Data 폴더>          2차 EndNote 라이브러리(선택). 여러 줄 = 여러 라이브러리, 첫 줄이 기준.
  openurl: <리졸버 URL>          도서관 OpenURL 리졸버(선택).
상대경로는 **하네스 루트**(이 저장소 최상위 폴더) 기준, 절대경로·`~`도 허용.
양식: references/library/sources.example.txt (복사해 sources.txt로 고쳐 쓴다 — sources.txt는 개인
로컬 경로를 담으므로 git에 올리지 않는다).
"""
import os
import re

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)                       # 하네스 루트
LIBDIR = os.path.join(ROOT, "references", "library")
CONFIG = os.path.join(LIBDIR, "sources.txt")
EXAMPLE = os.path.join(LIBDIR, "sources.example.txt")
CATALOG = os.path.join(LIBDIR, "catalog.json")
FULLTEXT_DB = os.path.join(LIBDIR, "fulltext.db")

CONFIG_REL = "references/library/sources.txt"
EXAMPLE_REL = "references/library/sources.example.txt"


def has_config():
    return os.path.isfile(CONFIG)


def config_notice():
    """sources.txt가 없을 때 도구들이 공통으로 내는 한 줄 안내."""
    return (f"[안내] {CONFIG_REL} 없음 — 보유 자료 검색층(선택적 로컬 데이터층) 미설정. "
            f"{EXAMPLE_REL}를 sources.txt로 복사해 tier1 폴더를 적으면 켜진다.")


def _config_lines():
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            return f.read().splitlines()
    except (FileNotFoundError, OSError):
        return []


def _entries(key):
    """'key: value' 줄들의 값(주석·빈 줄 제외, 키는 대소문자 무시)."""
    out = []
    for ln in _config_lines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        if k.strip().lower() == key.lower():
            out.append(v.strip())
    return out


def _config_value(key):
    """sources.txt의 'key: value' 단일값(첫 매치). 없으면 ''."""
    vals = _entries(key)
    return vals[0].strip('"').strip("'") if vals else ""


def resolve_path(p):
    """설정값 경로 → 절대경로. 상대경로는 하네스 루트 기준."""
    p = os.path.expanduser(p.strip().strip('"').strip("'"))
    return os.path.abspath(p if os.path.isabs(p) else os.path.join(ROOT, p))


def tier1_entries():
    """sources.txt의 tier1 항목 전부: [(설정값, 절대경로, 실재여부)]. verify.py가 미실재 폴더를 알릴 때 쓴다."""
    out = []
    for v in _entries("tier1"):
        for p in re.split(r"[,;]", v):
            p = p.strip().strip('"').strip("'")
            if not p:
                continue
            full = resolve_path(p)
            out.append((p, full, os.path.isdir(full)))
    seen, uniq = set(), []
    for e in out:
        if e[1] not in seen:
            seen.add(e[1])
            uniq.append(e)
    return uniq


def tier1_dirs():
    """sources.txt의 tier1 폴더(실재 폴더만)."""
    return [full for _, full, ok in tier1_entries() if ok]


def endnote_dirs():
    """sources.txt의 endnote: 줄에 적힌 EndNote .Data 폴더들(첫 줄=기준 라이브러리).
    설정이 없으면 빈 리스트 — 2차층 비활성(개인 기본 경로를 가정하지 않는다)."""
    dirs = []
    for v in _entries("endnote"):
        v = v.strip().strip('"').strip("'")
        if v:
            dirs.append(resolve_path(v))
    return list(dict.fromkeys(dirs))


def openurl_base():
    """도서관 OpenURL 리졸버 기본 URL(sources.txt의 openurl:). 없으면 ''."""
    return _config_value("openurl")


def index_key(abspath):
    """색인 DB에 저장할 경로 키: 하네스 루트 기준 상대경로(슬래시 통일).
    다른 드라이브 등 상대화가 불가능하면 절대경로(슬래시 통일)."""
    try:
        return os.path.relpath(abspath, ROOT).replace("\\", "/")
    except ValueError:
        return os.path.abspath(abspath).replace("\\", "/")


def from_index_key(key):
    """index_key의 역변환."""
    p = key.replace("/", os.sep)
    return p if os.path.isabs(p) else os.path.join(ROOT, p)
