"""Chay lan lut tung dong: tao job -> cho -> tai anh ve."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import api, refs, report, sheet


@dataclass
class Options:
    input_path: Path
    out_dir: Path
    retry: int = 1
    poll_timeout: int = api.POLL_TIMEOUT
    dry_run: bool = False


class Runner:
    def __init__(self, client: api.SangTaoClient, options: Options, ui):
        self.client = client
        self.opt = options
        self.ui = ui
        self.base_dir = options.input_path.parent

    def run(self, rows: list[sheet.Row]) -> report.Report:
        rep = report.Report(self.opt.out_dir)
        try:
            for index, row in enumerate(rows, start=1):
                self._run_row(index, len(rows), row, rep)
        except KeyboardInterrupt:
            self.ui.interrupted()
        finally:
            rep.close()
        return rep

    # ------------------------------------------------------------- mot dong

    def _run_row(self, index: int, total: int, row: sheet.Row, rep: report.Report) -> None:
        self.ui.row_start(index, total, row)

        for warning in row.warnings:
            self.ui.warn(warning)

        if not row.prompt:
            self.ui.skip("thieu prompt")
            rep.add(report.Entry(
                line=row.line, status="skipped", prompt="",
                error="Thieu prompt - dong nay bi bo qua",
            ))
            return

        # Buoc 1: chuan bi anh tham chieu.
        try:
            reference_urls = refs.resolve_all(
                row.images,
                client=self.client,
                base_dir=self.base_dir,
                on_upload=self.ui.uploading,
                check_only=self.opt.dry_run,
            )
        except refs.RefError as exc:
            self.ui.fail(str(exc))
            rep.add(report.Entry(
                line=row.line, status="error", prompt=row.prompt,
                reference_count=len(row.images), error=str(exc),
            ))
            return

        if self.opt.dry_run:
            self.ui.dry_run_ok(reference_urls)
            rep.add(report.Entry(
                line=row.line, status="skipped", prompt=row.prompt,
                reference_count=len(reference_urls), error="dry-run, chua tao job",
            ))
            return

        # Buoc 2: tao job va cho ket qua, retry neu loi tam thoi.
        entry = self._generate(row, reference_urls, index)
        rep.add(entry)

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
                    self.ui.queue_full()
                    time.sleep(60)
                    continue
                self.ui.fail(exc.message)
                return report.Entry(
                    line=row.line, status="error", prompt=row.prompt,
                    reference_count=len(reference_urls), error=exc.message,
                )

            job_id = created.get("jobId", "")
            self.ui.job_created(created)

            try:
                last = self.client.wait_for_job(
                    job_id,
                    on_tick=self.ui.job_tick,
                    timeout=self.opt.poll_timeout,
                )
            except api.ApiError as exc:
                self.ui.fail(exc.message)
                return report.Entry(
                    line=row.line, status="error", prompt=row.prompt,
                    reference_count=len(reference_urls), job_id=job_id,
                    error=exc.message,
                )

            if last.ok:
                return self._download(row, last, reference_urls, index)

            # Job hong khong bi tinh tien, credit duoc hoan tu dong.
            if last.retryable and attempt <= self.opt.retry:
                self.ui.retrying(last, attempt)
                continue
            break

        message = "Job that bai"
        if last:
            message = f"{last.failure_kind or 'error'}: {last.error or 'khong ro nguyen nhan'}"
        self.ui.fail(message)
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
            self.ui.fail(entry.error)
            return entry

        suffix = Path(url.split("?")[0]).suffix or ".png"
        dest = self.opt.out_dir / f"{index:04d}{suffix}"

        # Anh tren may chu bi xoa sau 7 ngay, nen tai ve ngay khi job xong.
        try:
            api.download(url, dest)
            entry.file = dest.name
            self.ui.row_done(entry, result)
        except api.ApiError as exc:
            entry.error = f"Tao anh xong nhung chua tai ve duoc: {exc.message}"
            self.ui.warn(entry.error)

        return entry
