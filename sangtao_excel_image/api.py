"""Client cho API sangtao.ai v2.

Tham chieu: https://sangtao.ai/vi/api-docs#chatgpt-image
"""

from __future__ import annotations

import hashlib
import mimetypes
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

BASE_URL = "https://sangtao.ai/api/v2"
MODEL = "chatgpt-image-sangtao"

# Toi da 10 anh tham chieu moi job.
MAX_REFERENCE_IMAGES = 10

# Job thuong mat 30-90 giay, khong bao gio xong som hon lan poll dau.
FIRST_POLL_DELAY = 10
POLL_INTERVAL = 8
POLL_TIMEOUT = 600

# Chi retry nhung loi tam thoi. Retry mot loi co dinh chi ton them tien.
RETRYABLE_FAILURE_KINDS = {"GENERATION_TIMEOUT", "QUOTA_EXHAUSTED"}


class ApiError(Exception):
    """Loi tra ve tu API, kem errorCode de goi y cach xu ly."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


@dataclass
class JobResult:
    job_id: str
    status: str
    result_images: list[str] = field(default_factory=list)
    credit_cost: float = 0.0
    charge_source: str | None = None
    quota_remaining: int | None = None
    failure_kind: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "complete"

    @property
    def retryable(self) -> bool:
        return self.failure_kind in RETRYABLE_FAILURE_KINDS

    @property
    def result_url(self) -> str | None:
        return self.result_images[0] if self.result_images else None


class SangTaoClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: int = 60,
        upload_cache=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        # Xac thuc bang header X-Api-Key, khong phai Authorization: Bearer.
        self.session.headers.update({"X-Api-Key": api_key})

        # Cung mot file dung lai nhieu dong thi chi upload mot lan. Cache ben
        # ngoai (neu co) con nho duoc qua nhieu lan chay.
        self._upload_cache: dict[str, str] = {}
        self._persistent_cache = upload_cache
        self._upload_lock = threading.Lock()
        # Moi file mot khoa rieng: nhieu luong cung can mot anh thi mot luong
        # upload, cac luong con lai cho roi dung chung ket qua — thay vi ca ba
        # cung upload mot file.
        self._file_locks: dict[str, threading.Lock] = {}

    def __repr__(self) -> str:
        # Khong bao gio in api key ra log.
        return f"<SangTaoClient base_url={self.base_url!r}>"

    # ------------------------------------------------------------------ utils

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(f"Khong ket noi duoc toi {url}: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError:
            # "from None" de nguoi dung khong phai doc ca chuoi traceback cua
            # thu vien json khi may chu tra ve HTML hoac trang loi.
            raise ApiError(
                f"May chu tra ve du lieu khong doc duoc (HTTP {resp.status_code}).",
                status=resp.status_code,
            ) from None

        if not resp.ok or not payload.get("success", False):
            raise ApiError(
                payload.get("error") or f"HTTP {resp.status_code}",
                status=resp.status_code,
                code=payload.get("errorCode"),
            )

        return payload.get("data") or {}

    # ------------------------------------------------------------- agent jobs

    def create_job(
        self,
        prompt: str,
        *,
        reference_images: list[str] | None = None,
        aspect_ratio: str | None = None,
        image_format: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """POST /agents/jobs/create -> {jobId, status: "WaitingForAgent", ...}"""
        body: dict = {"model": MODEL, "prompt": prompt}

        # Chi gui nhung truong co gia tri, khong gui key rong.
        if reference_images:
            body["referenceImages"] = reference_images
        if aspect_ratio:
            body["aspectRatio"] = aspect_ratio
        if image_format:
            body["format"] = image_format
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key

        return self._request("POST", "/agents/jobs/create", json=body)

    def get_job(self, job_id: str) -> JobResult:
        """GET /jobs/{jobId}"""
        data = self._request("GET", f"/jobs/{job_id}")

        images = data.get("resultImages") or []
        if not images and data.get("resultUrl"):
            images = [data["resultUrl"]]

        return JobResult(
            job_id=data.get("jobId", job_id),
            # So sanh khong phan biet hoa thuong.
            status=str(data.get("status", "")).lower(),
            result_images=images,
            credit_cost=float(data.get("creditCost") or 0),
            charge_source=data.get("chargeSource"),
            quota_remaining=data.get("quotaRemaining"),
            failure_kind=data.get("failureKind"),
            error=data.get("error"),
        )

    def wait_for_job(
        self,
        job_id: str,
        *,
        on_tick=None,
        timeout: int = POLL_TIMEOUT,
    ) -> JobResult:
        """Poll toi khi job xong, hong, hoac qua han."""
        deadline = time.monotonic() + timeout

        time.sleep(min(FIRST_POLL_DELAY, timeout))

        last = None
        while True:
            last = self.get_job(job_id)
            if last.status in ("complete", "error"):
                return last

            if on_tick:
                on_tick(last)

            if time.monotonic() >= deadline:
                return JobResult(
                    job_id=job_id,
                    status="error",
                    failure_kind="CLIENT_TIMEOUT",
                    error=(
                        f"Job chua xong sau {timeout // 60} phut. Job co the van dang chay "
                        f"tren he thong - tra lai bang jobId {job_id}."
                    ),
                )

            time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))

    # ----------------------------------------------------------- upload anh

    def upload_local_image(self, path: Path) -> str:
        """Upload anh tu may len, tra ve URL cong khai dung lam anh tham chieu.

        Xin link upload roi day file len. Ket qua duoc cache theo noi dung file,
        nen mot anh dung lai o nhieu dong chi ton dung mot lan upload.
        """
        digest = _file_digest(path)

        with self._upload_lock:
            cached = self._lookup(digest)
            if not cached:
                file_lock = self._file_locks.setdefault(digest, threading.Lock())
        if cached:
            return cached

        # Chi mot luong upload file nay; nhung luong khac cho o day roi lay
        # ket qua tu cache.
        with file_lock:
            with self._upload_lock:
                cached = self._lookup(digest)
            if cached:
                return cached
            return self._do_upload(path, digest)

    def _lookup(self, digest: str) -> str | None:
        """Tim trong cache. Goi khi dang giu _upload_lock."""
        cached = self._upload_cache.get(digest)
        if not cached and self._persistent_cache is not None:
            cached = self._persistent_cache.get(digest)
            if cached:
                self._upload_cache[digest] = cached
        return cached

    def _do_upload(self, path: Path, digest: str) -> str:
        content_type = mimetypes.guess_type(path.name)[0] or "image/png"

        presign = self._request(
            "POST",
            "/images/presign",
            json={"fileName": path.name, "contentType": content_type},
        )

        sas_url = presign.get("sasUrl")
        public_url = presign.get("publicUrl")
        if not sas_url or not public_url:
            raise ApiError(f"May chu khong tra ve link upload cho {path.name}.")

        with path.open("rb") as fh:
            try:
                put = requests.put(
                    sas_url,
                    data=fh,
                    headers={
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": content_type,
                    },
                    timeout=300,
                )
            except requests.RequestException as exc:
                raise ApiError(f"Khong upload duoc {path.name}: {exc}") from exc

        if not put.ok:
            raise ApiError(f"Khong upload duoc {path.name} (HTTP {put.status_code}).")

        with self._upload_lock:
            self._upload_cache[digest] = public_url
            if self._persistent_cache is not None:
                self._persistent_cache.put(digest, public_url)
        return public_url

    # ---------------------------------------------------------------- account

    def get_balance(self) -> dict:
        data = self._request("GET", "/account/balance")
        # May chu tra ve ca API key trong response. Bo di ngay tai day de no
        # khong bao gio lot vao man hinh hay file log.
        for key in ("apiKey", "api_key", "key", "token"):
            data.pop(key, None)
        return data


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, *, timeout: int = 120) -> None:
    """Tai anh ket qua ve may. resultUrl la link cong khai, khong can header."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
            tmp.replace(dest)
    except requests.RequestException as exc:
        raise ApiError(f"Khong tai duoc anh ve: {exc}") from exc
