"""Doc file .xlsx / .csv dau vao.

Cot nhan dang:
    prompt       bat buoc
    images       tuy chon - nhieu anh phan cach bang ";" hoac xuong dong
    aspectRatio  tuy chon
    format       tuy chon

Cung chap nhan kieu tach cot: image1, image2, ... image10.

API bo qua truong la trong im lang, nen tool phai bat loi go nham ten cot
o day va dung han thay vi chay tiep voi du lieu thieu.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

ALIASES: dict[str, str] = {
    "prompt": "prompt",
    "prompts": "prompt",
    "noidung": "prompt",
    "mota": "prompt",
    "images": "images",
    "image": "images",
    "refs": "images",
    "ref": "images",
    "referenceimages": "images",
    "anhthamchieu": "images",
    "aspectratio": "aspect_ratio",
    "aspect": "aspect_ratio",
    "ratio": "aspect_ratio",
    "tyle": "aspect_ratio",
    "tilekhung": "aspect_ratio",
    "format": "format",
    "dinhdang": "format",
}

NUMBERED_IMAGE = re.compile(r"^image[\s_-]*(\d+)$")

VALID_FORMATS = {"png", "jpeg"}
ASPECT_RATIO = re.compile(r"^\d{1,2}:\d{1,2}$")


class SheetError(Exception):
    """Loi ve cau truc file dau vao - dung han, khong chay tiep."""


@dataclass
class Row:
    """Mot dong trong file, da chuan hoa."""

    line: int  # so dong trong file, tinh ca dong tieu de
    prompt: str
    images: list[str] = field(default_factory=list)
    aspect_ratio: str | None = None
    format: str | None = None
    warnings: list[str] = field(default_factory=list)


def _norm_header(value: object) -> str:
    """Bo dau cach, gach duoi, va phan biet hoa thuong khi so ten cot."""
    return re.sub(r"[\s_-]+", "", str(value or "").strip().lower())


def _split_images(value: object) -> list[str]:
    """Tach nhieu anh trong mot o: phan cach bang ; hoac xuong dong."""
    if value is None:
        return []
    parts = re.split(r"[;\n\r]+", str(value))
    return [p.strip().strip('"').strip("'") for p in parts if p and p.strip()]


def _map_columns(header: list[object]) -> tuple[dict[str, int], dict[int, int]]:
    """Tra ve (cot chuan -> chi so, chi so cot image co so -> thu tu)."""
    mapping: dict[str, int] = {}
    numbered: dict[int, int] = {}

    for idx, raw in enumerate(header):
        key = _norm_header(raw)
        if not key:
            continue

        match = NUMBERED_IMAGE.match(key)
        if match:
            numbered[idx] = int(match.group(1))
            continue

        canonical = ALIASES.get(key)
        if canonical and canonical not in mapping:
            mapping[canonical] = idx

    return mapping, numbered


def _build_row(
    line: int,
    values: list[object],
    mapping: dict[str, int],
    numbered: dict[int, int],
    *,
    embedded: list[str] | None = None,
) -> Row | None:
    """Dung Row tu mot dong du lieu. Tra ve None neu dong rong hoan toan."""

    def cell(name: str) -> str:
        idx = mapping.get(name)
        if idx is None or idx >= len(values):
            return ""
        value = values[idx]
        return "" if value is None else str(value).strip()

    prompt = cell("prompt")

    images: list[str] = []
    images.extend(_split_images(values[mapping["images"]] if "images" in mapping and mapping["images"] < len(values) else None))
    for idx in sorted(numbered, key=lambda i: numbered[i]):
        if idx < len(values):
            images.extend(_split_images(values[idx]))
    if embedded:
        images.extend(embedded)

    aspect_ratio = cell("aspect_ratio") or None
    fmt = (cell("format") or "").lower() or None

    if not prompt and not images and not aspect_ratio and not fmt:
        return None  # dong trong, bo qua im lang

    row = Row(
        line=line,
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        format=fmt,
        images=_dedupe(images),
    )

    if fmt and fmt not in VALID_FORMATS:
        row.warnings.append(
            f'format "{fmt}" khong hop le (chi nhan png hoac jpeg) - bo qua, dung mac dinh'
        )
        row.format = None

    if aspect_ratio and not ASPECT_RATIO.match(aspect_ratio):
        row.warnings.append(
            f'aspectRatio "{aspect_ratio}" khong dung dang "rong:cao" (vi du 9:16) - bo qua'
        )
        row.aspect_ratio = None

    return row


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _check_header(mapping: dict[str, int], header: list[object], path: Path) -> None:
    if "prompt" in mapping:
        return
    found = [str(h).strip() for h in header if str(h or "").strip()]
    raise SheetError(
        f"Khong tim thay cot 'prompt' trong {path.name}.\n"
        f"  Cac cot doc duoc: {', '.join(found) if found else '(khong co cot nao)'}\n"
        f"  Dong dau tien cua file phai la tieu de, voi it nhat mot cot ten 'prompt'."
    )


def read_xlsx(path: Path) -> list[Row]:
    try:
        from openpyxl import load_workbook
    except ImportError:  # pragma: no cover
        raise SheetError(
            "Thieu thu vien openpyxl de doc file Excel. Chay: pip install openpyxl"
        )

    try:
        wb = load_workbook(path, data_only=True)
    except Exception as exc:
        raise SheetError(
            f"Khong mo duoc {path.name}: {exc}\n"
            f"  File co dang mo trong Excel khong? Hay dong lai roi thu lai."
        ) from exc

    try:
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    if not rows:
        raise SheetError(f"File {path.name} khong co du lieu.")

    header = list(rows[0])
    mapping, numbered = _map_columns(header)
    _check_header(mapping, header, path)

    out: list[Row] = []
    for offset, values in enumerate(rows[1:], start=2):
        row = _build_row(offset, list(values), mapping, numbered)
        if row is not None:
            out.append(row)
    return out


def _read_csv_text(path: Path) -> str:
    """Doc CSV bat ke bang ma nao.

    Excel tren Windows co lua chon "Unicode Text" luu ra UTF-16 kem BOM, va do
    la dinh dang duy nhat giu duoc tieng Viet ngoai UTF-8 — khong bang ma mot
    byte nao (cp1258, cp1252...) chua du ky tu tieng Viet. Vi vay phai nhan
    dang BOM truoc, roi moi thu cac bang ma con lai.
    """
    raw = path.read_bytes()

    for bom, encoding in (
        (b"\xff\xfe\x00\x00", "utf-32"),
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
    ):
        if raw.startswith(bom):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                break

    for encoding in ("utf-8", "utf-16", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise SheetError(
        f"Khong doc duoc {path.name} - file dung bang ma la.\n"
        f"  Mo bang Excel roi luu lai dang 'CSV UTF-8', hoac dung file .xlsx."
    )


def read_csv(path: Path) -> list[Row]:
    text = _read_csv_text(path)
    sample = text[:8192]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise SheetError(f"File {path.name} khong co du lieu.")

    header = list(rows[0])
    mapping, numbered = _map_columns(header)
    _check_header(mapping, header, path)

    out: list[Row] = []
    for offset, values in enumerate(rows[1:], start=2):
        row = _build_row(offset, list(values), mapping, numbered)
        if row is not None:
            out.append(row)
    return out


def read(path: Path) -> list[Row]:
    """Doc file dau vao, tu nhan dang theo duoi file."""
    if not path.exists():
        raise SheetError(f"Khong tim thay file: {path}")

    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if suffix == ".csv":
        return read_csv(path)
    if suffix == ".xls":
        raise SheetError(
            ".xls la dinh dang Excel cu, tool khong doc duoc.\n"
            "  Mo bang Excel roi luu lai dang .xlsx."
        )
    raise SheetError(
        f"Khong ho tro duoi file '{suffix}'. Chi nhan .xlsx hoac .csv."
    )
