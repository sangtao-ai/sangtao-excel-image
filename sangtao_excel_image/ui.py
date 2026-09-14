"""In tien trinh ra man hinh.

Gom vao mot cho de runner khong lan logic hien thi, va de sau nay lam GUI thi
chi can thay lop nay.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import api, report, sheet


def _enable_utf8() -> bool:
    """Chuyen console sang UTF-8 neu duoc; tra ve co in duoc ky tu dac biet khong.

    Cua so dong lenh tren Windows mac dinh dung bang ma cu, in ra dau tieng Viet
    va cac ky hieu nhu ✓ thanh o vuong. Thu chuyen sang UTF-8 truoc; khong duoc
    thi bao de chuyen sang dung ky tu ASCII.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass

    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    if encoding.replace("-", "") in ("utf8", "utf8mb4", "cp65001"):
        return True

    try:
        "✓ —".encode(encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNICODE_OK = _enable_utf8()

# Bo ky hieu thay doi theo kha nang cua cua so dong lenh.
if UNICODE_OK:
    OK, FAIL, WARN, SKIP, RETRY, UP, DOT, ARROW, DASH, ELLIPSIS = (
        "✓", "✗", "!", "–", "↻", "↑", "·", "→", "—", "…"
    )
else:
    OK, FAIL, WARN, SKIP, RETRY, UP, DOT, ARROW, DASH, ELLIPSIS = (
        "[OK]", "[X]", "[!]", "-", "[R]", ">>", "-", "->", "-", "..."
    )


def _short(text: str, width: int = 58) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + ELLIPSIS


class ConsoleUI:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._ticks = 0

    @staticmethod
    def _p(message: str = "") -> None:
        try:
            print(message, flush=True)
        except UnicodeEncodeError:
            # Khong bao gio de viec in an lam hong lan chay.
            encoding = getattr(sys.stdout, "encoding", "ascii") or "ascii"
            print(message.encode(encoding, "replace").decode(encoding), flush=True)

    # ------------------------------------------------------------ tong quan

    def header(
        self, input_path: Path, out_dir: Path, count: int, *, threads: int = 1
    ) -> None:
        self._p()
        self._p("=" * 64)
        self._p(f"  Tao anh hang loat tu file Excel {DASH} sangtao.ai")
        self._p("=" * 64)
        self._p(f"  File vao   : {input_path.name}")
        self._p(f"  So dong    : {count}")
        if threads > 1:
            self._p(f"  Chay cung luc: {threads} anh")
        self._p(f"  Luu ket qua: {out_dir}")
        self._p("=" * 64)
        self._p()

    def balance(self, data: dict) -> None:
        parts = []

        credit = data.get("availableCredit")
        if credit is None:
            credit = data.get("credits")
        if credit is not None:
            parts.append(f"{credit:g} credit")

        # Goi thang khong tinh bang credit — so luot con lai chi biet duoc khi
        # tao job dau tien, nen o day chua hien duoc.
        if data.get("quotaRemaining") is not None:
            parts.append(f"{data['quotaRemaining']} luot trong goi")

        if parts:
            self._p(f"  Tai khoan: {(' ' + DOT + ' ').join(parts)}")
            self._p()

    def quota(self, result) -> None:
        """Hien so luot con lai, doc tu job dau tien tao thanh cong."""
        if getattr(result, "quota_remaining", None) is None:
            return
        self._p(f"  Goi thang: con {result.quota_remaining} luot")
        self._p()

    def estimate(self, count: int, *, threads: int = 1) -> None:
        # Moi anh 30-90 giay; chay nhieu luong thi chia deu ra.
        low = max(1, round(count * 30 / 60 / threads))
        high = max(low, round(count * 90 / 60 / threads))
        self._p(
            f"  Uoc tinh: {count} anh, moi anh 30-90 giay "
            f"{ARROW} khoang {low}-{high} phut."
        )
        self._p("  Cu de cua so nay chay. Dung giua chung thi bam Ctrl+C.")
        self._p()

    # --------------------------------------------------------------- tung dong

    def row_start(self, index: int, total: int, row: sheet.Row) -> None:
        self._ticks = 0
        self._p(f"[{index}/{total}] dong {row.line}: {_short(row.prompt)}")

    def uploading(self, path: Path) -> None:
        self._p(f"        {UP} dang tai anh tham chieu len: {path.name}")

    def job_created(self, data: dict) -> None:
        if not self.verbose:
            return
        queue = data.get("queuePosition")
        extra = f", dang xep hang thu {queue}" if queue else ""
        self._p(f"        {DOT} job {data.get('jobId', '')[:12]}{ELLIPSIS}{extra}")

    def job_tick(self, result: api.JobResult) -> None:
        self._ticks += 1
        if self._ticks % 3:
            return
        sys.stdout.write(f"\r        {DOT} dang tao anh{ELLIPSIS} ({self._ticks * 8}s)")
        sys.stdout.flush()

    def _clear_tick(self) -> None:
        if self._ticks >= 3:
            sys.stdout.write("\r" + " " * 46 + "\r")
            sys.stdout.flush()

    def row_done(self, entry: report.Entry, result: api.JobResult) -> None:
        self._clear_tick()
        cost = f" {DOT} {entry.credit_cost:g} credit" if entry.credit_cost else ""
        self._p(f"        {OK} {entry.file}{cost}")

    def dry_run_ok(self, urls: list[str]) -> None:
        detail = f", {len(urls)} anh tham chieu" if urls else ""
        self._p(f"        {OK} hop le{detail} (dry-run, chua tao anh)")

    def retrying(self, result: api.JobResult, attempt: int) -> None:
        self._clear_tick()
        self._p(f"        {RETRY} {result.failure_kind} {DASH} thu lai (lan {attempt + 1})")

    def queue_full(self) -> None:
        self._clear_tick()
        self._p(f"        {DOT} he thong dang ban, cho 60 giay roi thu lai{ELLIPSIS}")

    def skip(self, reason: str) -> None:
        self._p(f"        {SKIP} bo qua: {reason}")

    def warn(self, message: str) -> None:
        self._clear_tick()
        self._p(f"        {WARN} {message}")

    def fail(self, message: str) -> None:
        self._clear_tick()
        self._p(f"        {FAIL} {message}")

    def interrupted(self) -> None:
        self._p()
        self._p("  Da dung theo yeu cau. Phan da lam van duoc giu lai.")

    # ------------------------------------------------------------------- ket

    def summary(self, rep: report.Report, out_dir: Path, *, dry_run: bool = False) -> None:
        self._p()
        self._p("=" * 64)

        if dry_run:
            checked = len(rep.entries) - rep.failed
            self._p(f"  Kiem tra xong: {checked} dong hop le"
                    + (f" {DOT} {rep.failed} dong co loi" if rep.failed else ""))
            self._p("  Chua tao anh nao, chua tru tien.")
        else:
            self._p(f"  Xong: {rep.done} anh"
                    + (f" {DOT} {rep.failed} loi" if rep.failed else "")
                    + (f" {DOT} {rep.skipped} bo qua" if rep.skipped else ""))
            if rep.total_credit:
                self._p(f"  Da dung: {rep.total_credit:g} credit")
            self._p(f"  Anh luu tai: {out_dir}")
            self._p(f"  Bang ket qua: {out_dir / '_ket-qua.xlsx'}")

        self._p("=" * 64)

        if rep.failed:
            self._p()
            self._p("  Cac dong bi loi:")
            for entry in rep.entries:
                if entry.status == "error":
                    self._p(f"    dong {entry.line}: {_short(entry.error, 70)}")
            self._p()
            if dry_run:
                self._p("  Sua lai nhung dong do roi chay lai de kiem tra.")
            else:
                self._p("  Sua lai nhung dong do roi chay lai file. "
                        "Job loi khong bi tru tien.")
        elif dry_run:
            self._p()
            self._p("  File hop le. Chay lai khong co --dry-run de tao anh that.")
        self._p()
