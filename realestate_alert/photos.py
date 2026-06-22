from __future__ import annotations
import base64, io, re
from pathlib import Path

PIC_ORDER = {"000241": 0, "000245": 1, "000247": 2, "000244": 3}  # 외관·내부 먼저, 지적도 뒤
MAX_SIDE = 1280
QUALITY = 70


def _safe(identity: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_-]", "_", identity)


def save_photos(cs_pic_list: list[dict], identity: str, base_dir: Path) -> dict[int, str]:
    try:
        from PIL import Image
    except ImportError:
        return {}
    folder = _safe(identity)
    out_dir = base_dir / folder
    ordered = sorted(cs_pic_list, key=lambda p: (PIC_ORDER.get(p.get("cortAuctnPicDvsCd"), 9),
                                                 int(p.get("cortAuctnPicSeq", 0) or 0)))
    result: dict[int, str] = {}
    n = 0
    for p in ordered:
        b64 = p.get("picFile")
        if not b64:
            continue
        try:
            raw = base64.b64decode(b64, validate=True)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        n += 1
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{n:02d}.jpg"
        img.save(out_dir / fname, "JPEG", quality=QUALITY, optimize=True)
        result[n] = f"{folder}/{fname}"
    return result
