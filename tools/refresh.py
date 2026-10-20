#!/usr/bin/env python3
"""refresh.py — 도서관(선택적 로컬 데이터층) 한 방 갱신.

새 파일(1차 폴더)·새 PDF(EndNote)가 생기면 이걸로:
  1) endnote_sync.py   — EndNote .enl → catalog(2차) 갱신 (sources.txt에 endnote: 줄이 있을 때만)
  2) library_index.py  — 전문색인 증분 갱신(변경분만; 평시 --budget 1200s로 폭주 차단)

로컬에 직접 만든 보조 스크립트(예: 0차 등록부 catalog.yml 재생성기)가 있으면 아래
OPTIONAL_SCRIPTS에 이름을 적어 두면 **파일이 실재할 때만** 같이 돈다(없으면 SKIP).

평시(스케줄러)는 library_index에 시간예산 1200s를 줘 대량 유입 시에도 깔끔히 끊고
증분으로 이어간다. `--nightly`는 예산 없이 끝까지 돈다.

설정(references/library/sources.txt)이 없으면 안내 한 줄만 내고 아무것도 하지 않는다(종료코드 0).
결과 1줄을 references/library/refresh.log에 남긴다. 겹침 방지 락(refresh.lock)이 있어
스케줄러와 수동 실행이 안전하게 공존한다. 증분이라 바뀐 게 없으면 몇 초로 끝난다.

사용:  python tools/refresh.py [--nightly]
"""
import os, sys, subprocess, time, datetime

import _libconfig as C

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
LOG = os.path.join(ROOT, "references", "library", "refresh.log")
LOCK = os.path.join(ROOT, "references", "library", "refresh.lock")
STALE_LOCK_SEC = 2 * 3600        # 2시간 넘은 락은 죽은 프로세스 잔재로 보고 무시

NIGHTLY = "--nightly" in sys.argv

# 로컬 보조 스크립트(공개본 미포함) — tools/에 실재할 때만 실행. (이름, 인자, 타임아웃초)
OPTIONAL_SCRIPTS = (
    # ("build_core_catalog.py", (), 300),
)

# 실행 스크립트와 (인자, 개별 타임아웃(초)). 등록부류 → EndNote → 색인 순.
SCRIPTS = OPTIONAL_SCRIPTS + (
    ("endnote_sync.py", (), 1800),
    # 평시엔 시간예산 1200s로 스스로 끊고(증분 이어받기), 야간엔 예산 없이 완주.
    ("library_index.py", () if NIGHTLY else ("--budget", "1200"), 14400 if NIGHTLY else 3300),
)


def run(script, *args, timeout=1800):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", os.path.join(TOOLS, script), *args],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", env=env, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 1, f"TIMEOUT({timeout}s)"     # 절단에 원인이 묻히지 않게 명시
    except Exception as e:
        return 1, f"[예외] {e}"


def tail(s, limit=500):
    # 예외·타임아웃 진단은 절단하지 않는다(짧게 잘린 로그에 원인이 묻히는 것 방지).
    text = (s or "").strip()
    if text.startswith("TIMEOUT(") or text.startswith("[예외]"):
        return text
    lines = [l for l in text.splitlines() if l.strip()]
    return lines[-1][:limit] if lines else ""


def acquire_lock():
    """중복 실행 방지. 살아있는 락이 있으면 False(건너뜀), 없거나 낡았으면 생성 후 True."""
    try:
        if time.time() - os.path.getmtime(LOCK) < STALE_LOCK_SEC:
            return False             # 다른 refresh가 진행 중
    except OSError:
        pass                         # 락 없음 → 진행
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()} {datetime.datetime.now().isoformat(timespec='seconds')}\n")
    return True


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not C.has_config():
        print(C.config_notice())
        print("  갱신할 로컬 도서관층이 없음 — 건너뜀.")
        return 0
    if not acquire_lock():
        print(f"[건너뜀] 다른 refresh 진행 중(락: {os.path.relpath(LOCK, ROOT)}). 2시간 지난 락은 자동 무시.")
        return 0
    try:
        t0 = time.time()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = []
        for script, args, to in SCRIPTS:
            name = script.split('.')[0]
            if not os.path.exists(os.path.join(TOOLS, script)):
                parts.append(f"{name}=SKIP(없음)")
                continue
            if script == "endnote_sync.py" and not C.endnote_dirs():
                parts.append(f"{name}=SKIP(endnote 미설정)")
                continue
            rc, out = run(script, *args, timeout=to)
            parts.append(f"{name}={'OK' if rc == 0 else 'ERR'}")
            if rc != 0:
                parts[-1] += f"({tail(out)})"
        line = f"[{stamp}] {time.time()-t0:.0f}s | " + " | ".join(parts)
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line)
    finally:
        release_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
