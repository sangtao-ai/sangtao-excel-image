"""Chay thu toan bo luong voi API gia lap.

Khong goi mang that: thay lop van chuyen cua requests bang mot ban gia, nen
test van di qua dung code that cua client (header, parse, retry).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sangtao_excel_image import api, runner, sheet  # noqa: E402
from sangtao_excel_image.ui import ConsoleUI  # noqa: E402

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
)


class FakeResponse:
    def __init__(self, payload=None, *, status=200, content=b""):
        self._payload = payload
        self.status_code = status
        self.content = content
        self.ok = 200 <= status < 300

    def json(self):
        if self._payload is None:
            raise ValueError("khong phai json")
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise api.requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=8192):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeApi:
    """Gia lap may chu: dem so job, tra ket qua theo kich ban dat truoc."""

    def __init__(self, *, script=None):
        self.script = script or {}
        self.created: list[dict] = []
        self.polls: dict[str, int] = {}
        self.downloads: list[str] = []
        self.presigns: list[dict] = []
        self.uploads: list[str] = []
        self.headers: dict = {}

    # --- lop van chuyen ma client goi ---

    def request(self, method, url, timeout=None, json=None, **kwargs):
        if url.endswith("/agents/jobs/create"):
            return self._create(json)
        if "/jobs/" in url:
            return self._poll(url.rsplit("/", 1)[1])
        if url.endswith("/account/balance"):
            return FakeResponse({"success": True, "data": {"credits": 1000}})
        if url.endswith("/images/presign"):
            self.presigns.append(json)
            return FakeResponse({"success": True, "data": {
                "sasUrl": "https://storage.test/upload?sig=x",
                "publicUrl": "https://cdn.test/def.png",
            }})
        return FakeResponse({"success": False, "error": "khong ro duong dan"}, status=404)

    def _create(self, body):
        index = len(self.created)
        self.created.append(body)
        job_id = f"job{index:03d}"
        self.polls[job_id] = 0
        return FakeResponse({"success": True, "data": {
            "jobId": job_id,
            "status": "WaitingForAgent",
            "creditCost": 4.0,
            "queuePosition": 0,
            "chargeSource": "Credit",
        }})

    def _poll(self, job_id):
        self.polls[job_id] = self.polls.get(job_id, 0) + 1
        outcome = self.script.get(job_id, "complete")

        if callable(outcome):
            outcome = outcome(self.polls[job_id])

        if outcome == "processing":
            return FakeResponse({"success": True, "data": {
                "jobId": job_id, "status": "Processing", "progress": 40.0,
            }})
        if isinstance(outcome, tuple):
            kind, message = outcome
            return FakeResponse({"success": True, "data": {
                "jobId": job_id, "status": "error",
                "failureKind": kind, "error": message, "creditCost": 0.0,
            }})
        return FakeResponse({"success": True, "data": {
            "jobId": job_id,
            "status": "complete",  # chu thuong, dung nhu API that
            "progress": 100.0,
            "resultUrl": f"https://cdn.test/{job_id}.png",
            "resultImages": [f"https://cdn.test/{job_id}.png"],
            "creditCost": 4.0,
            "chargeSource": "Credit",
        }})


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda *_: None)
    monkeypatch.setattr(runner.time, "sleep", lambda *_: None)


@pytest.fixture
def fake(monkeypatch, no_sleep):
    server = FakeApi()

    def fake_get(url, stream=False, timeout=None, **kwargs):
        server.downloads.append(url)
        return FakeResponse(content=PNG)

    def fake_put(url, data=None, headers=None, timeout=None, **kwargs):
        server.uploads.append(url)
        assert headers.get("x-ms-blob-type") == "BlockBlob"
        return FakeResponse({}, status=201)

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.requests, "put", fake_put)
    return server


def make_client(server) -> api.SangTaoClient:
    client = api.SangTaoClient("test-key")
    client.session.request = server.request
    return client


def make_sheet(tmp_path, rows) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["prompt", "images", "aspectRatio", "format"])
    for row in rows:
        ws.append(row)
    path = tmp_path / "jobs.xlsx"
    wb.save(path)
    return path


def run(tmp_path, server, rows_data):
    path = make_sheet(tmp_path, rows_data)
    rows = sheet.read(path)
    options = runner.Options(input_path=path, out_dir=tmp_path / "out")
    return runner.Runner(make_client(server), options, ConsoleUI()).run(rows)


# ------------------------------------------------------------------ luong OK

def test_chay_het_va_tai_anh_ve(tmp_path, fake):
    rep = run(tmp_path, fake, [
        ["mot canh bien hoang hon rat dep", "", "9:16", "png"],
        ["mot khu rung mua nhiet doi", "", "16:9", ""],
    ])

    assert rep.done == 2
    assert rep.failed == 0
    assert rep.total_credit == 8.0

    # Anh duoc tai ve that, danh so theo thu tu dong.
    assert (tmp_path / "out" / "0001.png").read_bytes() == PNG
    assert (tmp_path / "out" / "0002.png").read_bytes() == PNG


def test_chi_gui_truong_co_gia_tri(tmp_path, fake):
    run(tmp_path, fake, [["mot canh bien hoang hon rat dep", "", "", ""]])

    body = fake.created[0]
    assert body["model"] == api.MODEL
    assert body["prompt"] == "mot canh bien hoang hon rat dep"
    # Khong gui key rong — API bo qua truong la trong im lang nen phai sach.
    assert "aspectRatio" not in body
    assert "format" not in body
    assert "referenceImages" not in body


def test_gui_dung_tham_so_khi_co(tmp_path, fake):
    run(tmp_path, fake, [
        ["mot canh bien hoang hon", "https://a.com/1.jpg", "9:16", "jpeg"],
    ])
    body = fake.created[0]
    assert body["aspectRatio"] == "9:16"
    assert body["format"] == "jpeg"
    assert body["referenceImages"] == ["https://a.com/1.jpg"]


def test_bao_cao_ghi_du_thong_tin(tmp_path, fake):
    rep = run(tmp_path, fake, [["mot canh bien hoang hon rat dep", "", "", ""]])
    entry = rep.entries[0]
    assert entry.status == "complete"
    assert entry.job_id == "job000"
    assert entry.url == "https://cdn.test/job000.png"
    assert entry.file == "0001.png"
    assert entry.credit_cost == 4.0
    assert entry.line == 2  # dong 1 la tieu de


def test_file_ket_qua_duoc_tao(tmp_path, fake):
    run(tmp_path, fake, [["mot canh bien hoang hon rat dep", "", "", ""]])
    assert (tmp_path / "out" / "_ket-qua.csv").exists()
    assert (tmp_path / "out" / "_ket-qua.xlsx").exists()


# --------------------------------------------------------------- poll nhieu lan

def test_poll_toi_khi_xong(tmp_path, fake):
    fake.script["job000"] = lambda n: "processing" if n < 3 else "complete"
    rep = run(tmp_path, fake, [["mot canh bien hoang hon rat dep", "", "", ""]])
    assert rep.done == 1
    assert fake.polls["job000"] == 3


# ----------------------------------------------------------------------- loi

def test_loi_co_dinh_khong_retry(tmp_path, fake):
    fake.script["job000"] = ("PROMPT_UNCLEAR", "Mo ta chua du ro")
    rep = run(tmp_path, fake, [["xanh", "", "", ""]])

    assert rep.failed == 1
    assert len(fake.created) == 1  # khong tao job thu hai
    assert "PROMPT_UNCLEAR" in rep.entries[0].error


def test_loi_tam_thoi_duoc_retry(tmp_path, fake):
    calls = {"n": 0}

    def script(_):
        calls["n"] += 1
        return "complete" if calls["n"] > 1 else ("GENERATION_TIMEOUT", "Qua gio")

    fake.script["job000"] = script
    fake.script["job001"] = "complete"

    rep = run(tmp_path, fake, [["mot canh bien hoang hon rat dep", "", "", ""]])
    assert rep.done == 1
    assert len(fake.created) == 2  # co tao lai


def test_anh_tham_chieu_thieu_thi_bao_loi_khong_tao_job(tmp_path, fake):
    rep = run(tmp_path, fake, [
        ["mot canh bien hoang hon rat dep", "khong-co-that.png", "", ""],
    ])
    assert rep.failed == 1
    assert fake.created == []  # khong tra tien cho job chac chan hong
    assert "khong-co-that.png" in rep.entries[0].error


def test_dong_thieu_prompt_bi_bo_qua(tmp_path, fake):
    rep = run(tmp_path, fake, [
        ["", "", "9:16", ""],
        ["mot canh bien hoang hon rat dep", "", "", ""],
    ])
    assert rep.skipped == 1
    assert rep.done == 1
    assert len(fake.created) == 1


def test_mot_dong_hong_khong_chan_cac_dong_sau(tmp_path, fake):
    fake.script["job000"] = ("CONTENT_REJECTED", "Vi pham chinh sach")
    rep = run(tmp_path, fake, [
        ["mot canh vi pham chinh sach nao do", "", "", ""],
        ["mot canh bien hoang hon rat dep", "", "", ""],
    ])
    assert rep.failed == 1
    assert rep.done == 1


# ---------------------------------------------------------------- idempotency

def test_moi_dong_co_idempotency_key_rieng(tmp_path, fake):
    run(tmp_path, fake, [
        ["canh mot rat dep va chi tiet", "", "", ""],
        ["canh hai rat dep va chi tiet", "", "", ""],
    ])
    keys = [b["idempotencyKey"] for b in fake.created]
    assert len(set(keys)) == 2


# --------------------------------------------------------------------- upload

def test_anh_tren_may_duoc_upload_truoc(tmp_path, fake):
    logo = tmp_path / "logo.png"
    logo.write_bytes(PNG)

    run(tmp_path, fake, [["mot canh bien hoang hon rat dep", "logo.png", "", ""]])

    # Dung hai buoc: presign roi PUT, khong co buoc xac nhan nao nua.
    assert len(fake.presigns) == 1
    assert fake.presigns[0] == {"fileName": "logo.png", "contentType": "image/png"}
    assert fake.uploads == ["https://storage.test/upload?sig=x"]

    # URL tu presign duoc dung lam anh tham chieu.
    assert fake.created[0]["referenceImages"] == ["https://cdn.test/def.png"]


def test_anh_dung_lai_nhieu_dong_chi_upload_mot_lan(tmp_path, fake):
    (tmp_path / "logo.png").write_bytes(PNG)

    run(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "logo.png", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "logo.png", "", ""],
        ["canh ba rat dep va nhieu chi tiet", "logo.png", "", ""],
    ])

    assert len(fake.presigns) == 1  # ba dong nhung chi upload mot lan
    assert len(fake.created) == 3
    for body in fake.created:
        assert body["referenceImages"] == ["https://cdn.test/def.png"]


def test_cung_noi_dung_khac_ten_file_van_dung_lai(tmp_path, fake):
    # Cache theo noi dung file chu khong theo duong dan.
    (tmp_path / "a.png").write_bytes(PNG)
    (tmp_path / "b.png").write_bytes(PNG)

    run(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "a.png", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "b.png", "", ""],
    ])
    assert len(fake.presigns) == 1


def test_anh_khac_noi_dung_thi_upload_rieng(tmp_path, fake):
    (tmp_path / "a.png").write_bytes(PNG)
    (tmp_path / "b.png").write_bytes(PNG + b"\x00")

    run(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "a.png", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "b.png", "", ""],
    ])
    assert len(fake.presigns) == 2


# ------------------------------------------------------------- chay song song

def run_threads(tmp_path, server, rows_data, threads):
    path = make_sheet(tmp_path, rows_data)
    rows = sheet.read(path)
    options = runner.Options(
        input_path=path, out_dir=tmp_path / "out", threads=threads
    )
    return runner.Runner(make_client(server), options, ConsoleUI()).run(rows)


def test_chay_song_song_du_so_anh(tmp_path, fake):
    rep = run_threads(tmp_path, fake, [
        [f"canh so {i} rat dep va nhieu chi tiet", "", "", ""] for i in range(6)
    ], threads=3)

    assert rep.done == 6
    assert len(fake.created) == 6
    for i in range(1, 7):
        assert (tmp_path / "out" / f"{i:04d}.png").exists()


def test_bao_cao_giu_dung_thu_tu_dong(tmp_path, fake):
    # Job ve khong theo thu tu, nhung bao cao phai theo thu tu dong trong Excel.
    fake.script["job000"] = lambda n: "processing" if n < 4 else "complete"
    fake.script["job001"] = lambda n: "processing" if n < 2 else "complete"

    rep = run_threads(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "", "", ""],
        ["canh ba rat dep va nhieu chi tiet", "", "", ""],
    ], threads=3)

    assert [e.line for e in rep.entries] == [2, 3, 4]
    assert [e.prompt.split()[1] for e in rep.entries] == ["mot", "hai", "ba"]


def test_ten_file_khop_voi_so_dong_khi_chay_song_song(tmp_path, fake):
    fake.script["job000"] = lambda n: "processing" if n < 5 else "complete"

    rep = run_threads(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "", "", ""],
    ], threads=2)

    by_line = {e.line: e for e in rep.entries}
    assert by_line[2].file == "0001.png"   # dong 2 -> 0001
    assert by_line[3].file == "0002.png"   # dong 3 -> 0002


def test_mot_dong_hong_khong_anh_huong_dong_khac_khi_song_song(tmp_path, fake):
    fake.script["job001"] = ("CONTENT_REJECTED", "Vi pham chinh sach")

    rep = run_threads(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "", "", ""],
        ["canh ba rat dep va nhieu chi tiet", "", "", ""],
    ], threads=3)

    assert rep.done == 2
    assert rep.failed == 1
    assert len(rep.entries) == 3


def test_anh_chung_chi_upload_mot_lan_du_chay_song_song(tmp_path, fake):
    # Nhieu luong cung can mot anh thi chi mot luong upload, khong phai moi
    # luong mot lan.
    (tmp_path / "logo.png").write_bytes(PNG)

    run_threads(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "logo.png", "", ""],
        ["canh hai rat dep va nhieu chi tiet", "logo.png", "", ""],
        ["canh ba rat dep va nhieu chi tiet", "logo.png", "", ""],
        ["canh bon rat dep va nhieu chi tiet", "logo.png", "", ""],
    ], threads=4)

    assert len(fake.presigns) == 1
    assert len(fake.uploads) == 1


def test_moi_dong_van_co_idempotency_key_rieng_khi_song_song(tmp_path, fake):
    run_threads(tmp_path, fake, [
        [f"canh so {i} rat dep va nhieu chi tiet", "", "", ""] for i in range(5)
    ], threads=3)

    keys = [b["idempotencyKey"] for b in fake.created]
    assert len(set(keys)) == 5


def test_dong_bo_qua_van_dung_cho_khi_song_song(tmp_path, fake):
    rep = run_threads(tmp_path, fake, [
        ["canh mot rat dep va nhieu chi tiet", "", "", ""],
        ["", "", "9:16", ""],
        ["canh ba rat dep va nhieu chi tiet", "", "", ""],
    ], threads=3)

    assert [e.line for e in rep.entries] == [2, 3, 4]
    assert rep.entries[1].status == "skipped"


def test_dry_run_khong_tao_job(tmp_path, fake):
    path = make_sheet(tmp_path, [["mot canh bien hoang hon rat dep", "", "", ""]])
    rows = sheet.read(path)
    options = runner.Options(input_path=path, out_dir=tmp_path / "out", dry_run=True)
    rep = runner.Runner(make_client(fake), options, ConsoleUI()).run(rows)

    assert fake.created == []
    assert rep.skipped == 1
