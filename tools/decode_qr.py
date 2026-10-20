"""decode_qr.py — QR 이미지에서 URL/텍스트만 추출(방문 안 함 — 링크 확인은 사람이). 의존: opencv-python, numpy."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    if len(sys.argv) < 2:
        print("사용: python tools/decode_qr.py <이미지경로>")
        return 2
    import cv2
    import numpy as np
    # cv2.imread는 Windows 비ASCII 경로를 못 읽음 → fromfile+imdecode
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print(f"[오류] 이미지를 못 읽음: {sys.argv[1]}")
        return 1
    det = cv2.QRCodeDetector()
    # 중앙 로고가 있어도 대개 인식됨. 멀티/단일 둘 다 시도.
    ok, texts, _, _ = det.detectAndDecodeMulti(img)
    results = [t for t in (texts or []) if t] if ok else []
    if not results:
        data, _, _ = det.detectAndDecode(img)
        if data:
            results = [data]
    if not results:
        # 확대·대비 보정 후 재시도
        big = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        data, _, _ = det.detectAndDecode(big)
        if data:
            results = [data]
    if not results:
        print("[실패] QR을 디코딩하지 못함(중앙 로고 간섭 가능) — 다른 각도/고해상 이미지로 재시도.")
        return 1
    print("=== 디코드 결과(방문 전, 확인용) ===")
    for r in results:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
