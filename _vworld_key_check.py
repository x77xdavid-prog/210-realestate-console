# -*- coding: utf-8 -*-
"""V-World 키 동작 확인 — 확실히 존재하는 필지(서울시청)로 검증."""
import json

from realestate_alert.land_info import LAND_PRICE_URL, LAND_USE_URL, _vworld_domain
from realestate_alert.public_data import build_url, http_get, vworld_key

# 서울 중구 태평로1가 31 (서울시청) PNU
pnu = "1114010300100310000"
print("PNU:", pnu, "(서울시청)")

for label, base in [("토지이용계획", LAND_USE_URL), ("공시지가", LAND_PRICE_URL)]:
    url = build_url(
        base,
        {
            "pnu": pnu,
            "key": vworld_key(),
            "domain": _vworld_domain(),
            "format": "json",
            "numOfRows": "3",
            "pageNo": "1",
        },
    )
    raw = http_get(url)
    print(f"\n=== {label} 원시 응답 (앞 1000자) ===")
    try:
        print(json.dumps(json.loads(raw), ensure_ascii=False, indent=1)[:1000])
    except Exception:
        print(raw[:1000])
