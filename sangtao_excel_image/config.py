"""Doc/ghi API key.

Key la thong tin bi mat: chi nam trong config.txt canh chuong trinh, khong bao
gio in ra man hinh, khong ghi vao bang ket qua, khong dat vao ten file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CONFIG_NAME = "config.txt"
ENV_VAR = "SANGTAO_API_KEY"

TEMPLATE = """\
# Dan API key cua ban vao dong duoi day.
# Lay key tai: sangtao.ai → Cai dat → API Key
#
# Day la thong tin bi mat — dung gui file nay cho nguoi khac,
# dung dua len GitHub hay nhom chat.

api_key =

# So anh tao cung luc. Nhan tu 1 den 5, mac dinh 3.
# Cang nhieu cang nhanh, nhung dat cao qua thi nang may chu ma
# khong nhanh them bao nhieu. Khong ro thi cu de nguyen 3.

so_luong_cung_luc = 3
"""


def app_dir() -> Path:
    """Thu muc dat chuong trinh (canh file .exe khi da dong goi)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / CONFIG_NAME


KEY_NAMES = ("api_key", "apikey", "key")
THREAD_NAMES = ("so_luong_cung_luc", "soluongcungluc", "threads", "luong")


def _settings(text: str) -> dict[str, str]:
    """Doc config.txt thanh cac cap ten = gia tri."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if value:
                out[name.strip().lower()] = value
        elif len(line) > 16 and " " not in line and "api_key" not in out:
            out["api_key"] = line  # ca file chi co moi cai key
    return out


def _read() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return _settings(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return {}


def load() -> str | None:
    """Uu tien bien moi truong, sau do toi config.txt."""
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return env

    data = _read()
    for name in KEY_NAMES:
        if data.get(name):
            return data[name]
    return None


def load_threads() -> int | None:
    """So anh chay cung luc dat trong config.txt, None neu khong dat."""
    data = _read()
    for name in THREAD_NAMES:
        value = data.get(name)
        if value:
            try:
                return int(value)
            except ValueError:
                return None
    return None


def save(api_key: str) -> Path:
    """Ghi API key, giu nguyen nhung gi nguoi dung da chinh trong file."""
    path = config_path()

    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            lines = TEMPLATE.splitlines()
    else:
        lines = TEMPLATE.splitlines()

    out: list[str] = []
    written = False
    for line in lines:
        stripped = line.strip()
        # Chi dung vao dong cai dat that, khong dung vao dong ghi chu.
        if not stripped.startswith("#") and "=" in stripped:
            name = stripped.partition("=")[0].strip().lower()
            if name in KEY_NAMES:
                out.append(f"api_key = {api_key}")
                written = True
                continue
        out.append(line)

    if not written:
        out.append(f"api_key = {api_key}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def ensure_template() -> Path:
    path = config_path()
    if not path.exists():
        path.write_text(TEMPLATE, encoding="utf-8")
    return path


def mask(api_key: str) -> str:
    """Dang hien thi an bot, dung khi can xac nhan voi nguoi dung."""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}{'*' * 8}{api_key[-4:]}"
