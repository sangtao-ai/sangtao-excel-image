"""Kiem tra phan xu ly anh tham chieu."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sangtao_excel_image import refs  # noqa: E402
from sangtao_excel_image.api import MAX_REFERENCE_IMAGES  # noqa: E402

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
)


class FakeClient:
    """Ghi lai cac lan upload de kiem tra, khong goi mang."""

    def __init__(self):
        self.uploaded: list[Path] = []
        self._cache: dict[bytes, str] = {}

    def upload_local_image(self, path: Path) -> str:
        self.uploaded.append(path)
        content = path.read_bytes()
        if content not in self._cache:
            self._cache[content] = f"https://cdn.test/{len(self._cache)}.png"
        return self._cache[content]


def make_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)
    return path


def test_url_giu_nguyen_khong_upload(tmp_path):
    client = FakeClient()
    urls = refs.resolve_all(
        ["https://a.com/1.jpg", "http://b.com/2.png"],
        client=client, base_dir=tmp_path,
    )
    assert urls == ["https://a.com/1.jpg", "http://b.com/2.png"]
    assert client.uploaded == []


def test_file_tren_may_duoc_upload(tmp_path):
    make_png(tmp_path / "logo.png")
    client = FakeClient()
    urls = refs.resolve_all(["logo.png"], client=client, base_dir=tmp_path)
    assert urls == ["https://cdn.test/0.png"]
    assert len(client.uploaded) == 1


def test_duong_dan_tuong_doi_tinh_theo_file_excel(tmp_path):
    make_png(tmp_path / "anh" / "logo.png")
    client = FakeClient()
    urls = refs.resolve_all(["anh/logo.png"], client=client, base_dir=tmp_path)
    assert urls == ["https://cdn.test/0.png"]


def test_duong_dan_tuyet_doi(tmp_path):
    target = make_png(tmp_path / "logo.png")
    client = FakeClient()
    urls = refs.resolve_all([str(target)], client=client, base_dir=Path("/noi/khac"))
    assert urls == ["https://cdn.test/0.png"]


def test_tron_url_va_file_tren_may(tmp_path):
    make_png(tmp_path / "logo.png")
    client = FakeClient()
    urls = refs.resolve_all(
        ["https://a.com/1.jpg", "logo.png"],
        client=client, base_dir=tmp_path,
    )
    assert urls == ["https://a.com/1.jpg", "https://cdn.test/0.png"]


def test_thu_tu_anh_duoc_giu_nguyen(tmp_path):
    make_png(tmp_path / "a.png")
    make_png(tmp_path / "b.png")
    (tmp_path / "b.png").write_bytes(PNG + b"\x00")  # khac noi dung
    client = FakeClient()
    urls = refs.resolve_all(
        ["a.png", "https://x.com/giua.jpg", "b.png"],
        client=client, base_dir=tmp_path,
    )
    assert urls[1] == "https://x.com/giua.jpg"
    assert urls[0] != urls[2]


def test_khong_tim_thay_file_thi_bao_ro_duong_dan(tmp_path):
    client = FakeClient()
    with pytest.raises(refs.RefError) as exc:
        refs.resolve_all(["thieu.png"], client=client, base_dir=tmp_path)
    message = str(exc.value)
    assert "thieu.png" in message
    assert str(tmp_path) in message  # chi ro da tim o dau


def test_file_khong_phai_anh_bi_tu_choi(tmp_path):
    (tmp_path / "ghi-chu.txt").write_text("xin chao")
    client = FakeClient()
    with pytest.raises(refs.RefError, match="khong phai anh"):
        refs.resolve_all(["ghi-chu.txt"], client=client, base_dir=tmp_path)


def test_qua_muoi_anh_bi_tu_choi(tmp_path):
    client = FakeClient()
    values = [f"https://a.com/{i}.jpg" for i in range(MAX_REFERENCE_IMAGES + 1)]
    with pytest.raises(refs.RefError, match=str(MAX_REFERENCE_IMAGES)):
        refs.resolve_all(values, client=client, base_dir=tmp_path)


def test_dung_muoi_anh_van_chay(tmp_path):
    client = FakeClient()
    values = [f"https://a.com/{i}.jpg" for i in range(MAX_REFERENCE_IMAGES)]
    assert len(refs.resolve_all(values, client=client, base_dir=tmp_path)) == 10


def test_danh_sach_rong_tra_ve_rong(tmp_path):
    client = FakeClient()
    assert refs.resolve_all([], client=client, base_dir=tmp_path) == []


def test_bo_dau_nhay_thua_quanh_duong_dan(tmp_path):
    make_png(tmp_path / "logo.png")
    client = FakeClient()
    urls = refs.resolve_all(['"logo.png"'], client=client, base_dir=tmp_path)
    assert urls == ["https://cdn.test/0.png"]
