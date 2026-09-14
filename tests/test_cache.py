"""Kiem tra cache anh da upload.

Anh upload len song 7 ngay, nen cache phai tu het han — neu khong, lan chay sau
se gui URL chet va job hong ma khong hieu tai sao.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sangtao_excel_image.cache import TTL_SECONDS, UploadCache  # noqa: E402


def test_nho_va_lay_lai_duoc(tmp_path):
    path = tmp_path / "c.json"
    cache = UploadCache(path)
    cache.put("abc", "https://cdn.test/1.png")
    cache.save()

    assert UploadCache(path).get("abc") == "https://cdn.test/1.png"


def test_chua_co_thi_tra_ve_none(tmp_path):
    assert UploadCache(tmp_path / "c.json").get("abc") is None


def test_ban_ghi_qua_han_bi_bo(tmp_path):
    path = tmp_path / "c.json"
    old = time.time() - TTL_SECONDS - 10
    path.write_text(json.dumps({"uploads": {
        "cu": {"url": "https://cdn.test/cu.png", "at": old},
        "moi": {"url": "https://cdn.test/moi.png", "at": time.time()},
    }}), encoding="utf-8")

    cache = UploadCache(path)
    assert cache.get("cu") is None       # link da chet, phai upload lai
    assert cache.get("moi") is not None


def test_han_ngan_hon_bay_ngay(tmp_path):
    # Tru hao de khong bao gio gui URL sap chet cho mot job dang chay.
    assert TTL_SECONDS < 7 * 24 * 3600


def test_file_cache_hong_khong_lam_vo_chuong_trinh(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{ khong phai json", encoding="utf-8")

    cache = UploadCache(path)
    assert cache.get("abc") is None
    cache.put("abc", "https://cdn.test/1.png")
    cache.save()
    assert UploadCache(path).get("abc") == "https://cdn.test/1.png"


def test_khong_ghi_lai_khi_khong_co_gi_moi(tmp_path):
    path = tmp_path / "c.json"
    UploadCache(path).save()
    assert not path.exists()


def test_gioi_han_so_ban_ghi(tmp_path):
    from sangtao_excel_image.cache import MAX_ENTRIES

    path = tmp_path / "c.json"
    cache = UploadCache(path)
    now = time.time()
    for i in range(MAX_ENTRIES + 50):
        cache._entries[f"k{i}"] = {"url": f"https://cdn.test/{i}.png", "at": now + i}
    cache._dirty = True
    cache.save()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["uploads"]) == MAX_ENTRIES
    # Giu lai ban ghi moi nhat.
    assert f"k{MAX_ENTRIES + 49}" in data["uploads"]


def test_khong_luu_api_key_hay_duong_dan_may(tmp_path):
    # Cache chi chua hash va URL cong khai — khong co gi rieng tu.
    path = tmp_path / "c.json"
    cache = UploadCache(path)
    cache.put("a" * 64, "https://cdn.test/1.png")
    cache.save()

    text = path.read_text(encoding="utf-8")
    assert "C:\\" not in text
    assert "api" not in text.lower() or "api_key" not in text.lower()
