"""verify.py 상시 리뷰어 훅 — Claude Code PostToolUse에서 조용히 돌고, 하드 FAIL일 때만 말한다.

'백그라운드 리뷰어'(작업 내내 인용·계산을 병행 검증) 패턴의 하네스판. 파일 수정 직후마다
verify.py(1초 안팎)를 실행해, 게이트까지 기다리지 않고 하드 FAIL을 즉시 되돌려준다.
통과·GC는 침묵한다(소음 방지 — GC는 게이트 때 verify.py 직접 실행으로 본다).

배선: .claude/settings.hook-예시.json의 hooks 절을 .claude/settings.json(로컬, git 제외)에 옮긴다
      — PostToolUse(Edit|Write) → python tools/verify_hook.py
해제: settings.json에서 hooks 절을 지우면 된다. 훅이 없어도 하네스는 동작한다
(비-Claude 도구는 AGENTS.md의 수동 실행 규칙대로 verify.py를 직접 돌린다).
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 검증과 무관한 경로의 수정은 즉시 통과(소음·지연 방지)
RELEVANT = ("_workspace", "corpus", "references", "tools", "CLAUDE.md", "AGENTS.md", "research-profile.md")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    if fp:
        try:
            rel = os.path.relpath(os.path.abspath(fp), ROOT)
        except ValueError:
            return 0  # 다른 드라이브 등 하네스 밖
        if rel.startswith("..") or not rel.startswith(RELEVANT):
            return 0  # 하네스 밖 또는 무관 경로
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        return 0  # 통과 — 침묵
    # 하드 FAIL — "하드 FAIL:" 이후의 항목(또는 FAIL 포함 줄)만 추려 Claude에게 되돌린다(exit 2 = 피드백)
    lines = out.splitlines()
    if "하드 FAIL:" in lines:
        picked = lines[lines.index("하드 FAIL:") + 1:]
    else:
        picked = [ln for ln in lines if "FAIL" in ln or "Error" in ln or "Traceback" in ln]
    sys.stderr.write("[verify.py 상시 리뷰어] 하드 FAIL — 즉시 수리 후 재검증할 것:\n")
    sys.stderr.write("\n".join(picked[-30:]) if picked else out[-2000:])
    return 2


if __name__ == "__main__":
    sys.exit(main())
