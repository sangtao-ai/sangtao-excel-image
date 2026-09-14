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
"""


def app_dir() -> Path:
    """Thu muc dat chuong trinh (canh file .exe khi da dong goi)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / CONFIG_NAME


def _parse(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, _, value = line.partition("=")
            if name.strip().lower() in ("api_key", "apikey", "key"):
                value = value.strip().strip('"').strip("'")
                if value:
                    return value
        elif len(line) > 16 and " " not in line:
            return line  # ca file chi co moi cai key
    return None


def load() -> str | None:
    """Uu tien bien moi truong, sau do toi config.txt."""
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return env

    path = config_path()
    if path.exists():
        try:
            return _parse(path.read_text(encoding="utf-8-sig"))
        except OSError:
            return None
    return None


def save(api_key: str) -> Path:
    path = config_path()
    path.write_text(
        TEMPLATE.replace("api_key =", f"api_key = {api_key}"),
        encoding="utf-8",
    )
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
