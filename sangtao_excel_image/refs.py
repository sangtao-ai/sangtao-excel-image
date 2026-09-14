"""Chuyen gia tri trong cot anh tham chieu thanh URL gui len API.

O cot images co the chua:
  - URL http/https  -> dung nguyen
  - duong dan file tren may -> upload len truoc, lay URL

Duong dan tuong doi duoc tinh theo vi tri file Excel, vi do la thu muc ma
nguoi dung dang nghi toi khi go.
"""

from __future__ import annotations

from pathlib import Path

from .api import MAX_REFERENCE_IMAGES, ApiError, SangTaoClient

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}


class RefError(Exception):
    """Anh tham chieu khong dung duoc - bo qua dong nay, khong tao job."""


def is_url(value: str) -> bool:
    return value.lower().startswith(("http://", "https://"))


def resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value.strip().strip('"'))
    if not path.is_absolute():
        path = base_dir / path
    return path


def resolve_all(
    values: list[str],
    *,
    client: SangTaoClient,
    base_dir: Path,
    on_upload=None,
    check_only: bool = False,
) -> list[str]:
    """Tra ve danh sach URL. Nem RefError neu co anh khong dung duoc.

    check_only=True thi chi kiem tra anh tren may co ton tai va dung dinh dang
    khong, khong upload — dung cho dry-run.
    """
    if not values:
        return []

    if len(values) > MAX_REFERENCE_IMAGES:
        raise RefError(
            f"Co {len(values)} anh tham chieu, toi da {MAX_REFERENCE_IMAGES} moi dong."
        )

    urls: list[str] = []
    for value in values:
        value = value.strip()
        if not value:
            continue

        if is_url(value):
            urls.append(value)
            continue

        path = resolve_path(value, base_dir)

        if not path.exists():
            # In duong dan tuyet doi de nguoi dung biet chinh xac da tim o dau.
            try:
                shown = path.resolve()
            except OSError:
                shown = path
            raise RefError(
                f"Khong tim thay anh tren may: {value}\n"
                f"      (da tim o: {shown})"
            )
        if not path.is_file():
            raise RefError(f"Duong dan khong phai file anh: {path}")
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise RefError(
                f"File khong phai anh: {path.name} "
                f"(chap nhan: {', '.join(sorted(IMAGE_SUFFIXES))})"
            )

        if check_only:
            urls.append(str(path))
            continue

        if on_upload:
            on_upload(path)

        try:
            urls.append(client.upload_local_image(path))
        except ApiError as exc:
            raise RefError(f"Khong upload duoc {path.name}: {exc.message}") from exc

    return urls
