"""Chay tung dong: tao job -> cho -> tai anh ve.

Chay duoc nhieu dong song song. Bao cao va ten file van theo dung thu tu dong
trong Excel du cac job ve khong theo thu tu.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import api, refs, report, sheet

DEFAULT_THREADS = 3
MAX_THREADS = 10


@dataclass
class Options:
    input_path: Path
    out_dir: Path
    retry: int = 1
    poll_timeout: int = api.POLL_TIMEOUT
    dry_run: bool = False
    threads: int = DEFAULT_THREADS


class Runner:
    def __init__(self, client: api.SangTaoClient, options: Options, ui):
        self.client = client
        self.opt = options
        self.ui = ui
        self.base_dir = options.input_path.parent
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def run(self, rows: list[sheet.Row]) -> report.Report:
        rep = report.Report(self.opt.out_dir)
        threads = max(1, min(self.opt.threads, MAX_THREADS))

        try:
            if threads == 1:
                for index, row in enumerate(rows, start=1):
                    self._run_row(index, len(rows), row, rep)
            else:
                self._run_parallel(rows, rep, threads)
        except KeyboardInterrupt:
            self._stop.set()
            self.ui.interrupted()
        finally:
            rep.close()
        return rep

    def _run_parallel(
        self, rows: list[sheet.Row], rep: report.Report, threads: int
    ) -> None:
        total = len(rows)
        results: dict[int, report.Entry] = {}
        next_to_write = 1

        def work(index: int, row: sheet.Row) -> tuple[int, report.Entry]:
            return index, self._build_entry(index, total, row)

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(work, index, row)
                for index, row in enumerate(rows, start=1)
            ]
            try:
                for future in futures:
                    index, entry = future.result()
                    results[index] = entry
                    # Ghi theo dung thu tu dong, du job ve khong theo thu tu.
                    while next_to_write in results:
                        rep.add(results.pop(next_to_write))
                        next_to_write += 1
            except KeyboardInterrupt:
                self._stop.set()
                for future in futures:
                    future.cancel()
                raise

        for index in sorted(results):
            rep.add(results[index])

    # ------------------------------------------------------------- mot dong

    def _run_row(self, index: int, total: int, row: sheet.Row, rep: report.Report) -> None:
        rep.add(self._build_entry(index, total, row))

    def _build_entry(self, index: int, total: int, row: sheet.Row) -> report.Entry:
        """Xu ly mot dong, tra ve ket qua — khong tu ghi vao bao cao."""
        with self._lock:
            self.ui.row_start(index, total, row)
            for warning in row.warnings:
                self.ui.warn(warning)

        if not row.prompt:
            with self._lock:
                self.ui.skip("thieu prompt")
            return report.Entry(
                line=row.line, status="skipped", prompt="",
                error="Thieu prompt - dong nay bi bo qua",
            )

        # Buoc 1: chuan bi anh tham chieu.
        try:
            reference_urls = refs.resolve_all(
                row.images,
                client=self.client,
                base_dir=self.base_dir,
                on_upload=lambda p: self._say(self.ui.uploading, p),
                check_only=self.opt.dry_run,
            )
        except refs.RefError as exc:
            self._say(self.ui.fail, str(exc))
            return report.Entry(
                line=row.line, status="error", prompt=row.prompt,
                reference_count=len(row.images), error=str(exc),
            )

        if self.opt.dry_run:
            self._say(self.ui.dry_run_ok, reference_urls)
            return report.Entry(
                line=row.line, status="skipped", prompt=row.prompt,
                reference_count=len(reference_urls), error="dry-run, chua tao job",
            )

        # Buoc 2: tao job va cho ket qua, retry neu loi tam thoi.
        return self._generate(row, reference_urls, index)

    def _say(self, fn, *args) -> None:
        """Goi ham in an duoi khoa, de cac luong khong in de len nhau."""
        with self._lock:
            fn(*args)

    def _generate(
        self, row: sheet.Row, reference_urls: list[str], index: int
    ) -> report.Entry:
        attempt = 0
        last: api.JobResult | None = None

        while attempt <= self.opt.retry:
            attempt += 1

            # Key gan voi lan chay + dong, nen retry trong cung lan chay dung lai
            # job cu thay vi tao job moi va bi tru tien hai lan.
            idempotency_key = f"{self.opt.out_dir.name}-{row.line}-{attempt}"

            try:
                created = self.client.create_job(
                    row.prompt,
                    reference_images=reference_urls,
                    aspect_ratio=row.aspect_ratio,
                    image_format=row.format,
                    idempotency_key=idempotency_key,
                )
            except api.ApiError as exc:
                if exc.code == "AGENT_QUEUE_FULL" and attempt <= self.opt.retry:
                    self._say(self.ui.queue_full)
                    time.sleep(60)
                    continue
                self._say(self.ui.fail, exc.message)
                return report.Entry(
                    line=row.line, status="error", prompt=row.prompt,
                    reference_count=len(reference_urls), error=exc.message,
                )

            job_id = created.get("jobId", "")
            self._say(self.ui.job_created, created)

            try:
                last = self.client.wait_for_job(
                    job_id,
                    on_tick=self._tick,
                    timeout=self.opt.poll_timeout,
                )
            except api.ApiError as exc:
                self._say(self.ui.fail, exc.message)
                return report.Entry(
                    line=row.line, status="error", prompt=row.prompt,
                    reference_count=len(reference_urls), job_id=job_id,
                    error=exc.message,
                )

            if last.ok:
                return self._download(row, last, reference_urls, index)

            # Job hong khong bi tinh tien, credit duoc hoan tu dong.
            if last.retryable and attempt <= self.opt.retry:
                self._say(self.ui.retrying, last, attempt)
                continue
            break

        message = "Job that bai"
        if last:
            message = f"{last.failure_kind or 'error'}: {last.error or 'khong ro nguyen nhan'}"
        self._say(self.ui.fail, message)
        return report.Entry(
            line=row.line, status="error", prompt=row.prompt,
            reference_count=len(reference_urls),
            job_id=last.job_id if last else "",
            error=message,
        )

    def _download(
        self,
        row: sheet.Row,
        result: api.JobResult,
        reference_urls: list[str],
        index: int,
    ) -> report.Entry:
        url = result.result_url or ""
        entry = report.Entry(
            line=row.line, status="complete", prompt=row.prompt,
            reference_count=len(reference_urls), job_id=result.job_id,
            url=url, credit_cost=result.credit_cost,
        )

        if not url:
            entry.status = "error"
            entry.error = "Job bao xong nhung khong co link anh"
            self._say(self.ui.fail, entry.error)
            return entry

        suffix = Path(url.split("?")[0]).suffix or ".png"
        dest = self.opt.out_dir / f"{index:04d}{suffix}"

        # Anh tren may chu bi xoa sau 7 ngay, nen tai ve ngay khi job xong.
        try:
            api.download(url, dest)
            entry.file = dest.name
            self._say(self.ui.row_done, entry, result)
        except api.ApiError as exc:
            entry.error = f"Tao anh xong nhung chua tai ve duoc: {exc.message}"
            self._say(self.ui.warn, entry.error)

        return entry

    def _tick(self, result: api.JobResult) -> None:
        """Nhip poll. Chay nhieu luong thi bo qua, vi cac dong se de len nhau."""
        if self.opt.threads > 1:
            return
        self.ui.job_tick(result)
