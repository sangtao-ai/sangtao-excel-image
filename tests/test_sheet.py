"""Kiem tra phan doc file - noi de vo nhat khi gap file that cua nguoi dung."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sangtao_excel_image import sheet  # noqa: E402


def write_xlsx(path: Path, rows: list[list]) -> Path:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def write_csv(path: Path, rows: list[list], *, encoding="utf-8-sig", delimiter=",") -> Path:
    with path.open("w", newline="", encoding=encoding) as fh:
        csv.writer(fh, delimiter=delimiter).writerows(rows)
    return path


# ------------------------------------------------------------------ co ban

def test_doc_duoc_cot_co_ban(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "images", "aspectRatio", "format"],
        ["mot canh hoang hon tren bien", "", "9:16", "png"],
    ])
    rows = sheet.read(path)
    assert len(rows) == 1
    assert rows[0].prompt == "mot canh hoang hon tren bien"
    assert rows[0].aspect_ratio == "9:16"
    assert rows[0].format == "png"
    assert rows[0].images == []


def test_chi_can_cot_prompt(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [["prompt"], ["ve mot con meo"]])
    rows = sheet.read(path)
    assert len(rows) == 1
    assert rows[0].aspect_ratio is None
    assert rows[0].format is None


def test_thieu_cot_prompt_thi_dung_han(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [["promt", "images"], ["x", ""]])
    with pytest.raises(sheet.SheetError) as exc:
        sheet.read(path)
    # Bao loi phai chi ra cot nao dang co, de nguoi dung tu sua duoc.
    assert "promt" in str(exc.value)


def test_ten_cot_khong_phan_biet_hoa_thuong_va_khoang_trang(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["  Prompt ", "Images", "Aspect Ratio", "FORMAT"],
        ["canh rung mua", "", "1:1", "PNG"],
    ])
    rows = sheet.read(path)
    assert rows[0].prompt == "canh rung mua"
    assert rows[0].aspect_ratio == "1:1"
    assert rows[0].format == "png"


# ------------------------------------------------------------ anh tham chieu

def test_nhieu_anh_phan_cach_bang_cham_phay(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "images"],
        ["x y z", "https://a.com/1.jpg; https://a.com/2.jpg"],
    ])
    rows = sheet.read(path)
    assert rows[0].images == ["https://a.com/1.jpg", "https://a.com/2.jpg"]


def test_nhieu_anh_phan_cach_bang_xuong_dong(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "images"],
        ["x y z", "C:\\a\\1.png\nC:\\a\\2.png"],
    ])
    rows = sheet.read(path)
    assert rows[0].images == ["C:\\a\\1.png", "C:\\a\\2.png"]


def test_cot_image_danh_so(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "image1", "image2", "image3"],
        ["x y z", "https://a.com/1.jpg", "", "https://a.com/3.jpg"],
    ])
    rows = sheet.read(path)
    assert rows[0].images == ["https://a.com/1.jpg", "https://a.com/3.jpg"]


def test_tron_ca_hai_kieu_cot_anh(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "images", "image1"],
        ["x y z", "https://a.com/1.jpg", "https://a.com/2.jpg"],
    ])
    rows = sheet.read(path)
    assert rows[0].images == ["https://a.com/1.jpg", "https://a.com/2.jpg"]


def test_cot_image_danh_so_giu_dung_thu_tu(tmp_path):
    # Cot xep lon xon trong file nhung phai ra dung thu tu 1,2,10.
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "image10", "image2", "image1"],
        ["x y z", "https://a.com/10.jpg", "https://a.com/2.jpg", "https://a.com/1.jpg"],
    ])
    rows = sheet.read(path)
    assert rows[0].images == [
        "https://a.com/1.jpg",
        "https://a.com/2.jpg",
        "https://a.com/10.jpg",
    ]


def test_anh_trung_nhau_chi_giu_mot(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "images"],
        ["x y z", "https://a.com/1.jpg; https://a.com/1.jpg"],
    ])
    rows = sheet.read(path)
    assert rows[0].images == ["https://a.com/1.jpg"]


# --------------------------------------------------------------- gia tri xau

def test_format_sai_thi_canh_bao_va_bo_qua(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "format"],
        ["mot canh bien dep", "webp"],
    ])
    rows = sheet.read(path)
    assert rows[0].format is None
    assert any("format" in w for w in rows[0].warnings)


def test_aspect_ratio_sai_thi_canh_bao_va_bo_qua(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "aspectRatio"],
        ["mot canh bien dep", "vuong"],
    ])
    rows = sheet.read(path)
    assert rows[0].aspect_ratio is None
    assert any("aspectRatio" in w for w in rows[0].warnings)


def test_dong_trong_bi_bo_qua(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "images"],
        ["canh mot", ""],
        [None, None],
        ["", ""],
        ["canh hai", ""],
    ])
    rows = sheet.read(path)
    assert [r.prompt for r in rows] == ["canh mot", "canh hai"]


def test_dong_thieu_prompt_van_duoc_giu_de_bao_loi(tmp_path):
    # Khong bo qua im lang: nguoi dung can biet dong nay bi thieu.
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "aspectRatio"],
        ["", "9:16"],
    ])
    rows = sheet.read(path)
    assert len(rows) == 1
    assert rows[0].prompt == ""


def test_so_dong_khop_voi_excel(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt"],
        ["canh mot"],
        ["canh hai"],
    ])
    rows = sheet.read(path)
    # Dong 1 la tieu de, nen du lieu bat dau tu dong 2.
    assert [r.line for r in rows] == [2, 3]


# ---------------------------------------------------------------------- csv

def test_doc_csv(tmp_path):
    path = write_csv(tmp_path / "a.csv", [
        ["prompt", "images", "aspectRatio", "format"],
        ["canh bien hoang hon", "https://a.com/1.jpg", "16:9", "png"],
    ])
    rows = sheet.read(path)
    assert rows[0].prompt == "canh bien hoang hon"
    assert rows[0].images == ["https://a.com/1.jpg"]


def test_csv_phan_cach_bang_cham_phay(tmp_path):
    path = write_csv(tmp_path / "a.csv", [
        ["prompt", "aspectRatio"],
        ["mot canh rung sau mua", "9:16"],
    ], delimiter=";")
    rows = sheet.read(path)
    assert rows[0].prompt == "mot canh rung sau mua"
    assert rows[0].aspect_ratio == "9:16"


def test_csv_utf8_co_bom(tmp_path):
    # Excel luu "CSV UTF-8" kem BOM o dau file.
    path = tmp_path / "a.csv"
    path.write_bytes("prompt\nmột cảnh biển đẹp\n".encode("utf-8-sig"))
    rows = sheet.read(path)
    assert rows[0].prompt == "một cảnh biển đẹp"


def test_csv_utf16_tu_excel(tmp_path):
    # Lua chon "Unicode Text (*.txt)" cua Excel luu UTF-16 kem BOM, phan cach
    # bang tab. Day la dinh dang duy nhat ngoai UTF-8 giu duoc tieng Viet.
    path = tmp_path / "a.csv"
    path.write_bytes("prompt\taspectRatio\nmột cảnh biển đẹp\t9:16\n".encode("utf-16"))
    rows = sheet.read(path)
    assert len(rows) == 1
    assert rows[0].prompt == "một cảnh biển đẹp"
    assert rows[0].aspect_ratio == "9:16"


def test_csv_utf8_khong_bom(tmp_path):
    path = tmp_path / "a.csv"
    path.write_bytes("prompt\nmột cảnh biển đẹp\n".encode("utf-8"))
    rows = sheet.read(path)
    assert rows[0].prompt == "một cảnh biển đẹp"


def test_xlsx_giu_nguyen_tieng_viet(tmp_path):
    path = write_xlsx(tmp_path / "a.xlsx", [
        ["prompt", "aspectRatio"],
        ["một cảnh biển đẹp lúc hoàng hôn", "9:16"],
    ])
    rows = sheet.read(path)
    assert rows[0].prompt == "một cảnh biển đẹp lúc hoàng hôn"


def test_csv_co_dau_phay_trong_prompt(tmp_path):
    path = write_csv(tmp_path / "a.csv", [
        ["prompt", "aspectRatio"],
        ["mot canh bien, co thuyen, luc hoang hon", "9:16"],
    ])
    rows = sheet.read(path)
    assert rows[0].prompt == "mot canh bien, co thuyen, luc hoang hon"
    assert rows[0].aspect_ratio == "9:16"


# -------------------------------------------------------------- duoi file la

def test_bao_loi_ro_rang_voi_file_xls_cu(tmp_path):
    path = tmp_path / "a.xls"
    path.write_bytes(b"x")
    with pytest.raises(sheet.SheetError, match=".xlsx"):
        sheet.read(path)


def test_bao_loi_voi_duoi_file_khong_ho_tro(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("prompt")
    with pytest.raises(sheet.SheetError):
        sheet.read(path)


def test_bao_loi_khi_khong_co_file(tmp_path):
    with pytest.raises(sheet.SheetError, match="Khong tim thay"):
        sheet.read(tmp_path / "khong-ton-tai.xlsx")


def test_file_mau_doc_duoc():
    mau = Path(__file__).resolve().parent.parent / "mau.xlsx"
    if not mau.exists():
        pytest.skip("chua sinh file mau")
    rows = sheet.read(mau)
    assert len(rows) >= 3
    assert all(r.prompt for r in rows)
    # Khong dong nao trong file mau duoc co canh bao.
    assert all(not r.warnings for r in rows)
