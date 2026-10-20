# -*- coding: utf-8 -*-
r"""하네스 위계·경계 검사기 — 공개 저장소가 '프레임워크만' 담고 있는지 기계로 지킨다.

git 추적본(프레임워크)과 선택적 로컬 데이터층(core-library 데이터·references/library·
references/external·_workspace 논문·로그)의 분계선을 지킨다. 분계선 정본:
references/local-data-layer.md. 표준 라이브러리만 사용(무의존 — 새 clone에서 즉시 실행).

검사 항목:
  1. 필수 파일 실재 — 헌장·규범·스킬·에이전트·핵심 도구가 저장소에 있는가.            (FAIL)
  2. 우선순위·버전 단일성 — AGENTS.md→CLAUDE.md 단방향 우선 선언, 현행 버전 번호는
     CLAUDE.md 헤더에만(다른 문서의 "현행 vX" 재기재 금지).                              (FAIL)
  3. 데이터 누출 — PDF·DB·로그·바이트코드 등 데이터/파생 바이너리, 또는 로컬 전용 층의
     파일이 저장소에 들어 있는가. git이 있으면 추적 파일 기준, 없으면 파일시스템 기준.   (FAIL)
  4. 개인정보 누출 — 추적 텍스트 파일에 사용자 절대경로(<드라이브>:\Users\<이름>, /Users/<이름>,
     /home/<이름>)나 이메일 주소가 있는가. --deny-file로 저장소 밖 금칙어 목록(실명 등) 추가 대조. (FAIL)
  5. 참조 경로 정합 — 헌장·AGENTS·README·시작하기·research-profile·스킬·에이전트의 백틱
     경로가 저장소에 있거나, 선언된 선택층 아래인가(댕글링 참조 차단).                  (FAIL)
  6. 상주 예산 — CLAUDE.md는 대화 내내 상주하는 유일한 층. 상한을 넘으면 경보.          (GC)
  7. 버전 꼬리표 잔존 — 규범 문서 안 "(v13)"류 연혁 꼬리표(공개본엔 연혁 파일이 없다).   (GC)

사용:
  python tools/check_harness_hierarchy.py                        # 현재 트리 검사
  python tools/check_harness_hierarchy.py --deny-file ../deny.txt # + 금칙어(한 줄 하나) 대조
  python tools/check_harness_hierarchy.py --clone-sim            # git archive 전개로 새 clone 모사 후 재검사

종료 코드: 0=통과(GC 정보만), 1=FAIL 존재, 2=실행 환경 문제.
"""
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# ── 1. 프레임워크 필수 파일 ──
REQUIRED = [
    "CLAUDE.md", "AGENTS.md", "README.md", "시작하기.md", "Claude-History.md", "research-profile.md",
    "CHANGELOG.md", ".gitignore", ".github/workflows/verify.yml",
    "run_verify.ps1", "run_verify.cmd", "environment.yml",
    "core-library/SCHEMA.md",
    "references/local-data-layer.md", "references/glossary-master.md", "references/connectors.md",
    "references/register-rules-ko.md", "references/register-rules-en.md",
    "references/citation-format-ko.md", "references/citation-format-en.md",
    "references/source-criticism.md", "references/question-architecture.md",
    "references/problematization.md", "references/re-architecture-loop.md",
    "references/writing-craft.md", "references/style-profile-ko.md",
    "references/style-exemplars-ko.md", "references/이행-훈련.md", "references/도구-지도.md",
    "references/library/sources.example.txt",
    "corpus/registry.md", "corpus/_passage-template.md", "corpus/_review-template.md",
    "corpus/gazetteer-master.csv",
    "_workspace/_template/_meta.md",
    "tools/verify.py", "tools/verify_hook.py", "tools/_libconfig.py", "tools/library_search.py",
    "tools/library_index.py", "tools/voice_match.py", "tools/md2hwpx.py",
    "tools/check_harness_hierarchy.py", "tools/regression_traps.md",
    ".claude/skills/집필/SKILL.md", ".claude/skills/DB/SKILL.md",
    ".claude/skills/시각화/SKILL.md", ".claude/skills/윤문/SKILL.md",
    ".claude/skills/심사/SKILL.md",
    ".claude/agents/question-sharpener.md", ".claude/agents/source-verifier.md",
    ".claude/agents/structure-architect.md", ".claude/agents/prose-writer.md",
    ".claude/agents/intro-reconciler.md", ".claude/agents/citation-auditor.md",
    ".claude/agents/peer-reviewer.md",
    # Codex 등 비-Claude 도구용 스킬 사본(같은 규범을 가리키는 얇은 진입점)
    ".agents/skills/history-db/SKILL.md", ".agents/skills/history-draft/SKILL.md",
    ".agents/skills/history-visualize/SKILL.md", ".agents/skills/history-polish/SKILL.md",
    ".agents/skills/history-review/SKILL.md",
]
# 공개 전 있으면 좋은 파일(없으면 GC)
RECOMMENDED = ["LICENSE"]
# 개수만 보고하는 묶음(GC): (글롭, 기대 개수)
COUNTED = [(".codex/agents/*.toml", 7)]

# ── 3·5. 선택적 로컬 데이터층 접두(있으면 사용 — 저장소에는 없어도 됨, 들어 있으면 누출) ──
OPTIONAL_PREFIXES = (
    "core-library/", "references/library/", "references/external/",
    "references/hwpx-templates/", "_workspace/", "logs/",
)
# 선택층 안에서도 저장소에 있어야 하는 예외(프레임워크 규약·골격·양식) — .gitignore의 ! 규칙과 일치.
# references/library/ 아래는 sources.example.txt 하나만 허용(sources.txt·catalog·fulltext.db 등은 누출).
TRACKED_EXCEPTIONS = {
    "core-library/SCHEMA.md",
    "references/library/sources.example.txt",
}
TRACKED_EXCEPTION_PREFIXES = ("_workspace/_template/",)
# 문서에 등장하지만 이 저장소 밖에 사는 경로(사용자 환경의 별도 스킬 등 — 문서에 그렇게 명기)
EXTERNAL_OK = {".claude/skills/hwpx/SKILL.md"}

# 데이터 누출로 보는 파일 패턴
LEAK_SUFFIXES = (".pdf", ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".log", ".pyc",
                 ".enl", ".hwp", ".hwpx", ".docx", ".tif", ".tiff", ".lock")
LEAK_DIRS = ("__pycache__/", ".obsidian/", ".ipynb_checkpoints/")
WALK_SKIP_DIRS = {".git", "node_modules", ".venv", "venv"}

# ── 2. 버전 단일성 ──
# 현행 번호 재기재 패턴. 정본은 CLAUDE.md 헤더(첫 6줄)의 "기준: vX[.Y.Z]" 하나.
VER = r"v\d+(?:\.\d+)*"
STAMP_PATTERNS = [re.compile(r"현행\s*" + VER), re.compile(r"기준:\s*(?:CLAUDE\.md\s+)?" + VER)]
STAMP_SCAN_DOCS = ["AGENTS.md", "Claude-History.md", "README.md", "시작하기.md", "research-profile.md"]

# ── 4. 개인정보 패턴 ──
TEXT_EXT = {".md", ".py", ".txt", ".yml", ".yaml", ".json", ".csv", ".ps1", ".cmd", ".bat", ".sh",
            ".html", ".htm", ".js", ".css", ".toml", ".cfg", ".ini", ".ipynb", ".tsv", ".xml"}
ABS_PATH_PATTERNS = [
    re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"'`<>|]+", re.I),   # Windows <드라이브>:\Users\<이름>
    re.compile(r"/[a-z]/Users/[^/\s\"'`<>|]+", re.I),                    # Git Bash /<드라이브>/Users/<이름>
    re.compile(r"(?<![\w.])/Users/(?!Shared\b)[A-Za-z0-9._-]+/"),        # macOS /Users/<이름>/
    re.compile(r"(?<![\w.])/home/[A-Za-z0-9._-]+/"),                     # Linux /home/<이름>/
]
PLACEHOLDER_USERS = {"user", "username", "you", "yourname", "name", "<user>", "<name>", "me", "example",
                     "runner", "runneradmin"}   # runner = CI 가상머신 계정
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
EMAIL_OK = re.compile(r"(?:@example\.(?:com|org|net)$|^noreply@|^no-reply@|users\.noreply\.github\.com$|^git@)", re.I)

# ── 5. 참조 경로 ──
PATH_EXT = re.compile(r"\.(md|py|yml|yaml|csv|txt|json|ps1|cmd|hwpx|ipynb|html|js|css|toml)$")
REF_PREFIXES = ("references/", "corpus/", "tools/", ".claude/", "core-library/", "_workspace/",
                ".agents/", ".codex/", ".github/")
REF_SCAN_FILES = ["CLAUDE.md", "AGENTS.md", "README.md", "시작하기.md", "research-profile.md",
                  "Claude-History.md", "CHANGELOG.md"]
REF_SCAN_GLOBS = [".claude/skills/*/SKILL.md", ".claude/agents/*.md", ".agents/skills/*/SKILL.md"]
# 자리표시·논문별 산출물 경로는 참조 검사에서 뺀다(새 clone엔 원래 없다 — 거짓 FAIL 방지).
PLACEHOLDER_TOKEN = re.compile(r"(?<![A-Z])N(?![A-Za-z])|X{2,}|…|\.\.\.|YYYY|\bnn\b")   # figN·P-00N·XX 등
PER_PAPER_BASENAME = re.compile(
    r"^(?:\d{2}[_-].*|P-\d+.*|_meta\.md|glossary\.md|_library\.md|_branches\.md|_coverage\.md"
    r"|_authorial_foundation\.md|_provenance\.md|_problematization\.md|_배열판\.md|_review.*\.md"
    r"|places\.csv|observations\.csv|categories\.csv|obs_categories\.csv|persons\.csv|claims\.csv"
    r"|name_variants\.csv|groups\.csv|catalog\..*|needs_ocr\.txt|fulltext\.db|sources\.txt"
    r"|refresh\.log|source\.yml|fig\d+.*)$")

# ── 6. 상주 예산 ──
RESIDENT_FILE = "CLAUDE.md"
RESIDENT_BUDGET = 42_000
RESIDENT_TARGET = 26_000

# ── 7. 버전 꼬리표 ──
VTAG = re.compile(r"[(（]\s*v\d{1,2}(?:[·,/~\-]\s*v?\d{1,2})*\s*[)）]")
VTAG_SCAN = ["CLAUDE.md", "AGENTS.md", "README.md", "시작하기.md", "research-profile.md"]
VTAG_GLOBS = [".claude/skills/*/SKILL.md", ".claude/agents/*.md", ".agents/skills/*/SKILL.md",
              "references/*.md", "corpus/*.md"]


def read(rel):
    p = ROOT / rel
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def git_tracked():
    """git 추적 파일 집합. .git 없는 트리(공개 전 폴더·clone-sim 전개)면 None."""
    if not (ROOT / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True)
    except OSError:
        return None
    if r.returncode != 0:
        return None
    return {f for f in r.stdout.decode("utf-8", "replace").split("\0") if f}


def _glob_to_regex(pat):
    """gitignore 글롭 → 정규식(`*`·`?`는 '/'를 넘지 않고 `**`만 넘는다)."""
    out, i = "", 0
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out += r"(?:.*/)?"; i += 3; continue
        if pat.startswith("**", i):
            out += r".*"; i += 2; continue
        out += {"*": r"[^/]*", "?": r"[^/]"}.get(c, re.escape(c))
        i += 1
    return re.compile(out + r"\Z")


def load_gitignore():
    """루트 .gitignore의 근사 해석기(무의존): [(정규식, 부정?, 디렉터리 전용?, 경로형?)]."""
    rules = []
    text = read(".gitignore") or ""
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        neg = s.startswith("!")
        if neg:
            s = s[1:]
        dir_only = s.endswith("/")
        s = s.rstrip("/")
        anchored = s.startswith("/") or "/" in s
        s = s.lstrip("/")
        if s:
            rules.append((_glob_to_regex(s), neg, dir_only, anchored))
    return rules


def ignored(rel, rules):
    """git 규칙 근사: 얕은 디렉터리부터 판정, 제외된 디렉터리 아래는 다시 포함할 수 없다."""
    parts = rel.split("/")
    for depth in range(1, len(parts) + 1):
        cand = "/".join(parts[:depth])
        is_dir = depth < len(parts)
        state = None
        for rx, neg, dir_only, anchored in rules:
            if dir_only and not is_dir:
                continue
            hit = rx.match(cand) if anchored else rx.match(parts[depth - 1])
            if hit:
                state = not neg
        if state and is_dir:
            return True
        if not is_dir:
            return bool(state)
    return False


def walk_files():
    """git이 없을 때의 대체 목록: 파일시스템의 파일 중 .gitignore가 제외하지 않는 것
    (= git init 후 추적될 파일의 근사). 반환: (파일 집합, 무시된 파일 수)."""
    rules = load_gitignore()
    out, n_ign = set(), 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP_DIRS]
        for fn in filenames:
            rel = Path(dirpath, fn).relative_to(ROOT).as_posix()
            if rules and ignored(rel, rules):
                n_ign += 1
                continue
            out.add(rel)
    return out, n_ign


def backtick_paths(text):
    """백틱 스팬 중 저장소 경로 꼴만 추출(글롭·자리표시·명령·논문별 산출물·비경로는 건너뜀)."""
    out = set()
    for span in re.findall(r"`([^`\n]+)`", text):
        s = span.strip()
        while s.startswith("./"):
            s = s[2:]
        if any(c in s for c in " {}*<>|?\"'[]()=") or "/" not in s:
            continue
        s = s.split("#", 1)[0].split("§", 1)[0].rstrip(":,.;")
        if not PATH_EXT.search(s) or not s.startswith(REF_PREFIXES):
            continue
        if PLACEHOLDER_TOKEN.search(s) or "passages/" in s:
            continue
        if PER_PAPER_BASENAME.match(s.rsplit("/", 1)[-1]):
            continue
        out.add(s)
    return out


def glob_rel(patterns):
    out = []
    for pat in patterns:
        out += sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pat) if p.is_file())
    return out


def load_deny(path):
    if not path:
        return []
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as e:
        print(f"[에러] --deny-file 읽기 실패: {e}")
        sys.exit(2)
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def run_checks(deny_terms=()):
    fails, gcs = [], []
    tracked = git_tracked()
    if tracked is not None:
        files, basis = tracked, "git 추적본"
    else:
        files, n_ign = walk_files()
        basis = (f"파일시스템(.git 없음 — .gitignore 적용 후 추적될 파일로 간주, 무시 {n_ign}개)")
    gcs.append(f"[GC][기준] 검사 대상: {basis} · 파일 {len(files)}개")

    def exists_in_repo(rel):
        return rel in files

    # 1. 필수 파일 실재
    for rel in REQUIRED:
        if not exists_in_repo(rel):
            fails.append(f"[FAIL][필수] 없음(또는 추적 제외): {rel}")
    for rel in RECOMMENDED:
        if not exists_in_repo(rel):
            gcs.append(f"[GC][권장] 공개 전 추가 권장: {rel}")
    for pat, want in COUNTED:
        rx = _glob_to_regex(pat)
        n = sum(1 for f in files if rx.match(f))
        gcs.append(f"[GC][묶음] {pat}: {n}개" + ("" if n == want else f" (기대 {want})"))

    # 2. 우선순위·버전 단일성
    claude = read("CLAUDE.md")
    agents = read("AGENTS.md")
    if agents is not None and "CLAUDE.md가 우선" not in agents:
        fails.append("[FAIL][위계] AGENTS.md에 'CLAUDE.md가 우선' 선언 없음")
    if claude is not None:
        if "이 파일이 우선" not in claude:
            fails.append("[FAIL][위계] CLAUDE.md에 다른 문서 대비 '이 파일이 우선' 선언 없음")
        head = "\n".join(claude.splitlines()[:6])
        m = re.search(r"기준:\s*\**\s*(" + VER + ")", head)
        if m:
            gcs.append(f"[GC][스탬프] 정본 버전: {m.group(1)} (CLAUDE.md 헤더)")
        else:
            gcs.append("[GC][스탬프] CLAUDE.md 헤더(첫 6줄)에서 `기준: vX` 스탬프를 찾지 못함")
        body = "\n".join(claude.splitlines()[6:])
        for pat in STAMP_PATTERNS:
            for hit in pat.findall(body):
                fails.append(f"[FAIL][스탬프] CLAUDE.md 본문(헤더 밖)에 현행 번호 재기재: {hit!r}")
    for doc in STAMP_SCAN_DOCS:
        text = read(doc)
        if text is None:
            continue
        for pat in STAMP_PATTERNS:
            for hit in pat.findall(text):
                fails.append(f"[FAIL][스탬프] {doc}에 현행 번호 재기재: {hit!r} — 정본은 CLAUDE.md 헤더 하나")

    # 3. 데이터 누출
    for f in sorted(files):
        exempt = f in TRACKED_EXCEPTIONS or f.startswith(TRACKED_EXCEPTION_PREFIXES)
        low = f.lower()
        if f.startswith(OPTIONAL_PREFIXES) and not exempt:
            fails.append(f"[FAIL][누출] 로컬 전용 층의 파일: {f}")
        elif any(seg in "/" + low for seg in ("/" + d for d in LEAK_DIRS)):
            fails.append(f"[FAIL][누출] 캐시·편집기 폴더: {f}")
        elif low.endswith(LEAK_SUFFIXES):
            fails.append(f"[FAIL][누출] 데이터·파생 바이너리: {f}")

    # 4. 개인정보 누출 (텍스트 파일만)
    pii_hits = 0
    for f in sorted(files):
        if Path(f).suffix.lower() not in TEXT_EXT:
            continue
        p = ROOT / f
        try:
            text = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat in ABS_PATH_PATTERNS:
                for m in pat.finditer(line):
                    user = re.split(r"[\\/]+", m.group(0).rstrip("/\\"))[-1].lower()
                    if (user in PLACEHOLDER_USERS or user.startswith(("<", "{", "%", "$"))
                            or not user.strip("….")):
                        continue
                    fails.append(f"[FAIL][개인정보] 사용자 절대경로 {f}:{lineno}: {m.group(0)[:60]}")
                    pii_hits += 1
            for m in EMAIL.finditer(line):
                if EMAIL_OK.search(m.group(0)):
                    continue
                fails.append(f"[FAIL][개인정보] 이메일 주소 {f}:{lineno}: {m.group(0)}")
                pii_hits += 1
            for term in deny_terms:
                if term in line:
                    fails.append(f"[FAIL][금칙어] {f}:{lineno}: '{term}'")
                    pii_hits += 1
    if deny_terms:
        gcs.append(f"[GC][금칙어] {len(deny_terms)}개 대조")

    # 5. 참조 경로 정합
    ref_docs = [d for d in REF_SCAN_FILES if exists_in_repo(d)] + glob_rel(REF_SCAN_GLOBS)
    for doc in ref_docs:
        text = read(doc)
        if text is None:
            continue
        for rel in sorted(backtick_paths(text)):
            if rel in EXTERNAL_OK or exists_in_repo(rel):
                continue
            if rel.startswith(OPTIONAL_PREFIXES):
                continue  # 선언된 선택층 — 없어도 규범 위반 아님
            fails.append(f"[FAIL][참조] {doc}이 가리키는 경로가 저장소에 없음: {rel}")

    # 6. 상주 예산 — 하드가 아니라 GC. 헌장 수정 자체를 막으면 안 되므로 경보만 울린다.
    rp = ROOT / RESIDENT_FILE
    if rp.exists():
        size = rp.stat().st_size
        if size > RESIDENT_BUDGET:
            gcs.append(f"[GC][상주] {RESIDENT_FILE} {size:,}B > 상한 {RESIDENT_BUDGET:,}B — 창고화 경보. "
                       f"도구 세부를 인출층(references/)으로 내리고 헌장에는 정본 포인터만 남길 것 "
                       f"(목표선 {RESIDENT_TARGET:,}B)")
        else:
            gcs.append(f"[GC][상주] {RESIDENT_FILE} {size:,}B (상한 {RESIDENT_BUDGET:,} · 목표선 {RESIDENT_TARGET:,})")

    # 7. 버전 꼬리표 잔존 — 공개본엔 연혁 파일이 없으므로 "(v13)"류는 댕글링 꼬리표(GC)
    vt = []
    for doc in [d for d in VTAG_SCAN if exists_in_repo(d)] + glob_rel(VTAG_GLOBS):
        text = read(doc)
        if text:
            n = len(VTAG.findall(text))
            if n:
                vt.append(f"{doc}({n})")
    if vt:
        gcs.append(f"[GC][꼬리표] 연혁 버전 꼬리표 잔존 {len(vt)}개 문서: {', '.join(vt[:12])}"
                   + (f" 외 {len(vt)-12}" if len(vt) > 12 else ""))
    return fails, gcs


def clone_sim():
    """git archive HEAD를 임시 폴더에 전개하고 그 안에서 자신을 재실행 — 새 clone 모사."""
    if not (ROOT / ".git").exists():
        print("[에러] --clone-sim은 git 저장소 안에서만 의미가 있다.")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="harness-clone-sim-"))
    tar_path = tmp / "head.tar"
    r = subprocess.run(["git", "archive", "--format=tar", "-o", str(tar_path), "HEAD"],
                       cwd=str(ROOT), capture_output=True)
    if r.returncode != 0:
        print("[에러] git archive 실패:", r.stderr.decode("utf-8", "replace").strip())
        return 2
    with tarfile.open(tar_path, encoding="utf-8") as tf:
        tf.extractall(tmp / "tree")
    tar_path.unlink()
    print(f"— clone-sim: HEAD를 {tmp / 'tree'}에 전개, 그 안에서 재검사 —")
    rc = subprocess.run([sys.executable, str(tmp / "tree" / "tools" / "check_harness_hierarchy.py")],
                        cwd=str(tmp / "tree")).returncode
    return rc


def main():
    if "--clone-sim" in sys.argv:
        sys.exit(clone_sim())
    deny_path = None
    if "--deny-file" in sys.argv:
        i = sys.argv.index("--deny-file")
        if i + 1 >= len(sys.argv):
            print("[에러] --deny-file 뒤에 경로가 필요하다.")
            sys.exit(2)
        deny_path = sys.argv[i + 1]
    fails, gcs = run_checks(load_deny(deny_path))
    for g in gcs:
        print(g)
    for f in fails:
        print(f)
    print(f"-- 위계·경계 검사: FAIL {len(fails)}, GC {len(gcs)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
