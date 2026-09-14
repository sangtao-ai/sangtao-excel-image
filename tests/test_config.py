"""Kiem tra doc/ghi config.txt."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sangtao_excel_image import config  # noqa: E402


@pytest.fixture
def here(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "app_dir", lambda: tmp_path)
    monkeypatch.delenv(config.ENV_VAR, raising=False)
    return tmp_path


def test_template_co_san_so_luong_mac_dinh(here):
    config.ensure_template()
    assert config.load_threads() == 3


def test_doc_duoc_so_luong_nguoi_dung_sua(here):
    (here / "config.txt").write_text(
        "api_key = abc\nso_luong_cung_luc = 5\n", encoding="utf-8"
    )
    assert config.load_threads() == 5


def test_luu_api_key_khong_lam_mat_cai_dat_khac(here):
    # Nguoi dung sua so luong roi moi nhap key — khong duoc mat cai da sua.
    (here / "config.txt").write_text(
        "api_key =\nso_luong_cung_luc = 5\n", encoding="utf-8"
    )
    config.save("key-moi")

    assert config.load() == "key-moi"
    assert config.load_threads() == 5


def test_luu_api_key_khi_chua_co_file(here):
    config.save("key-moi")
    assert config.load() == "key-moi"
    assert config.load_threads() == 3  # van co dong mac dinh tu template


def test_ghi_de_key_cu(here):
    config.save("key-cu")
    config.save("key-moi")
    text = (here / "config.txt").read_text(encoding="utf-8")
    assert config.load() == "key-moi"
    assert "key-cu" not in text


def test_gia_tri_so_luong_khong_hop_le_thi_bo_qua(here):
    (here / "config.txt").write_text(
        "api_key = abc\nso_luong_cung_luc = nhieu\n", encoding="utf-8"
    )
    # None nghia la dung mac dinh, khong phai nem loi.
    assert config.load_threads() is None


def test_khong_co_file_thi_khong_nem_loi(here):
    assert config.load() is None
    assert config.load_threads() is None


def test_dong_ghi_chu_khong_bi_hieu_nham_la_cai_dat(here):
    (here / "config.txt").write_text(
        "# api_key = day-la-vi-du-trong-ghi-chu\napi_key = key-that\n",
        encoding="utf-8",
    )
    assert config.load() == "key-that"


def test_bien_moi_truong_uu_tien_hon_file(here, monkeypatch):
    (here / "config.txt").write_text("api_key = trong-file\n", encoding="utf-8")
    monkeypatch.setenv(config.ENV_VAR, "tu-moi-truong")
    assert config.load() == "tu-moi-truong"


def test_file_chi_co_moi_cai_key(here):
    # Nguoi dung xoa het roi dan moi key vao.
    (here / "config.txt").write_text("stai_abcdefgh12345678\n", encoding="utf-8")
    assert config.load() == "stai_abcdefgh12345678"


def test_mask_khong_lo_key(here):
    masked = config.mask("stai_abcdefgh12345678")
    assert "abcdefgh" not in masked
    assert masked.startswith("stai")
