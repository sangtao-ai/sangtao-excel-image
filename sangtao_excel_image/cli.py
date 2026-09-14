"""Diem vao chuong trinh.

Chay duoc theo hai kieu:
  - Bam dup file .exe: tu tim file Excel trong thu muc, hoi API key neu chua co.
  - Go lenh: TaoAnh.exe jobs.xlsx -o D:\\anh
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, api, cache, config, sheet
from .runner import DEFAULT_THREADS, MAX_THREADS, Options, Runner
from .ui import ARROW, DASH, ELLIPSIS, ConsoleUI

SUPPORTED = (".xlsx", ".xlsm", ".csv")
SAMPLE_NAMES = {"mau.xlsx", "mau.csv", "sample.xlsx", "sample.csv"}

FB_URL = "https://www.facebook.com/cong.dac.dev"


def _pause_if_clicked(interactive: bool) -> None:
    """Giu cua so lai de nguoi dung con doc duoc ket qua."""
    if interactive:
        try:
            input(f"\nBam Enter de dong cua so{ELLIPSIS}")
        except (EOFError, KeyboardInterrupt):
            pass


def _find_input_files(folder: Path) -> list[Path]:
    files = [
        p for p in sorted(folder.iterdir())
        if p.is_file()
        and p.suffix.lower() in SUPPORTED
        and not p.name.startswith(("~$", "_"))
    ]
    # File mau xep cuoi, de file that cua nguoi dung duoc chon truoc.
    files.sort(key=lambda p: p.name.lower() in SAMPLE_NAMES)
    return files


def _choose_input(folder: Path) -> Path | None:
    files = _find_input_files(folder)

    if not files:
        print()
        print("  Khong tim thay file Excel nao trong thu muc nay.")
        print(f"  Thu muc: {folder}")
        print()
        print("  Cach dung: dat file .xlsx cua ban canh chuong trinh roi chay lai,")
        print("  hoac keo tha file .xlsx vao bieu tuong chuong trinh.")
        print()
        print("  File .xlsx can mot dong tieu de voi cac cot:")
        print("      prompt | images | aspectRatio | format")
        print("  Trong do chi 'prompt' la bat buoc.")
        return None

    if len(files) == 1:
        return files[0]

    print()
    print("  Chon file muon chay:")
    for index, path in enumerate(files, start=1):
        print(f"    {index}. {path.name}")
    print()

    while True:
        try:
            answer = input(f"  Nhap so (1-{len(files)}), hoac Enter de chon 1: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not answer:
            return files[0]
        if answer.isdigit() and 1 <= int(answer) <= len(files):
            return files[int(answer) - 1]
        print("  So khong hop le, thu lai.")


def _prompt_api_key() -> str | None:
    print()
    print("  Chua co API key.")
    print(f"  Lay key tai: sangtao.ai {ARROW} Cai dat {ARROW} API Key")
    print()
    print("  Chua co tai khoan, hoac muon dung thu truoc?")
    print("  Nhan cho minh de duoc cap 1000 anh mien phi:")
    print(f"      {FB_URL}")
    print()
    try:
        key = input("  Dan API key vao day roi bam Enter: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not key:
        return None

    path = config.save(key)
    print(f"  Da luu vao {path.name} {DASH} lan sau khong phai nhap lai.")
    print("  Luu y: day la thong tin bi mat, dung gui file nay cho nguoi khac.")
    return key


def _confirm(count: int) -> bool:
    try:
        answer = input(
            f"  Bat dau tao {count} anh? Bam Enter de chay, go 'k' de huy: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("", "c", "co", "y", "yes", "ok")


def _default_out_dir(input_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    return input_path.parent / f"ket-qua_{stamp}"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="TaoAnh",
        description="Tao anh hang loat tu file Excel qua API sangtao.ai.",
    )
    parser.add_argument("input", nargs="?", type=Path,
                        help="File .xlsx hoac .csv dau vao")
    parser.add_argument("-o", "--out", type=Path,
                        help="Thu muc luu ket qua")
    parser.add_argument("-k", "--api-key",
                        help="API key (uu tien hon config.txt)")
    parser.add_argument("-t", "--threads", type=int, default=None,
                        help=f"So anh tao cung luc (1-{MAX_THREADS}, "
                             f"mac dinh {DEFAULT_THREADS}). Cung dat duoc "
                             f"trong config.txt")
    parser.add_argument("--retry", type=int, default=1,
                        help="So lan thu lai khi loi tam thoi (mac dinh 1)")
    parser.add_argument("--timeout", type=int, default=api.POLL_TIMEOUT,
                        help="Toi da cho mot anh, tinh bang giay (mac dinh 600)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Chi kiem tra file va anh tham chieu, khong tao anh")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"TaoAnh {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = _parse_args(argv)

    # Khong co tham so nghia la nguoi dung bam dup vao file .exe.
    interactive = not argv
    ui = ConsoleUI(verbose=args.verbose)

    try:
        return _run(args, ui, interactive)
    except KeyboardInterrupt:
        print("\n  Da dung.")
        return 130
    finally:
        _pause_if_clicked(interactive)


def _run(args: argparse.Namespace, ui: ConsoleUI, interactive: bool) -> int:
    # --- file dau vao ---
    if args.input:
        input_path = args.input
        if not input_path.exists():
            print(f"  Khong tim thay file: {input_path}")
            return 1
    else:
        config.ensure_template()
        chosen = _choose_input(config.app_dir())
        if chosen is None:
            return 1
        input_path = chosen

    # --- doc file ---
    # Doc truoc khi hoi API key: file hong thi bao ngay, khong bat nguoi dung
    # dan key roi moi phat hien chon nham file.
    try:
        rows = sheet.read(input_path)
    except sheet.SheetError as exc:
        print()
        print(f"  {exc}")
        return 1

    if not rows:
        print(f"  {input_path.name} khong co dong du lieu nao.")
        return 1

    # Uu tien tham so dong lenh, sau do toi config.txt, cuoi cung la mac dinh.
    wanted = args.threads
    if wanted is None:
        wanted = config.load_threads()
    if wanted is None:
        wanted = DEFAULT_THREADS

    threads = max(1, min(wanted, MAX_THREADS))
    if wanted != threads:
        print(f"  So luong chay cung luc chi nhan 1-{MAX_THREADS}, "
              f"da dat ve {threads}.")

    out_dir = args.out or _default_out_dir(input_path)
    ui.header(input_path, out_dir, len(rows), threads=threads)

    # --- api key ---
    api_key = args.api_key or config.load()
    if not api_key:
        # Dry-run chi kiem tra file nen chay duoc khi chua co key. Anh tren may
        # can key de upload, se bao rieng o tung dong.
        if args.dry_run:
            api_key = ""
        elif not interactive:
            print("  Chua co API key. Dat vao config.txt, bien moi truong "
                  f"{config.ENV_VAR}, hoac dung tham so --api-key.")
            return 1
        else:
            api_key = _prompt_api_key()
            if not api_key:
                print("  Chua nhap API key, dung lai.")
                return 1

    upload_cache = cache.UploadCache(config.app_dir() / ".upload-cache.json")
    client = api.SangTaoClient(api_key, upload_cache=upload_cache)

    # Goi mot lenh nhe truoc de bao loi key sai ngay, thay vi de den job dau tien.
    # Bo qua khi dry-run: luc do nguoi dung dang kiem tra file, chua can key that.
    if not args.dry_run:
        try:
            ui.balance(client.get_balance())
        except api.ApiError as exc:
            if exc.status == 401:
                print("  API key khong dung. Kiem tra lai trong config.txt.")
                print(f"  Lay key tai: sangtao.ai {ARROW} Cai dat {ARROW} API Key")
                print(f"  Can key moi thi nhan: {FB_URL}")
                return 1
            # Loi khac o buoc nay khong dang de chan lai: co the chi la mang chap
            # chon, hoac endpoint kiem tra so du doi ten. Van chay tiep.
            if args.verbose:
                ui.warn(f"Khong kiem tra duoc so du: {exc.message}")

        ui.estimate(len(rows), threads=threads)

        # Bam dup roi chay thang la de tru tien ngoai y muon. Hoi mot cau truoc.
        if interactive and not _confirm(len(rows)):
            print("  Da huy, chua tao anh nao.")
            return 1

    options = Options(
        input_path=input_path,
        out_dir=out_dir,
        retry=max(0, args.retry),
        poll_timeout=args.timeout,
        dry_run=args.dry_run,
        threads=threads,
    )
    rep = Runner(client, options, ui).run(rows)
    upload_cache.save()
    ui.summary(rep, out_dir, dry_run=args.dry_run)

    return 0 if rep.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
