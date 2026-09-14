# Tạo ảnh hàng loạt từ Excel — sangtao.ai

Công cụ đọc file Excel/CSV, mỗi dòng là một ảnh cần tạo, gọi API
[sangtao.ai](https://sangtao.ai/vi/api-docs#chatgpt-image) rồi tải ảnh về máy.

Hỗ trợ **ảnh tham chiếu** — dán đường dẫn ảnh trên máy hoặc link, tool tự upload.

## Dành cho người dùng (không cần cài gì)

Tải `TaoAnh.zip` ở [Releases](../../releases) → giải nén → sửa `mau.xlsx` → bấm đúp `TaoAnh.exe`.

Hướng dẫn chi tiết nằm trong `HUONG-DAN.txt` (hoặc `HUONG-DAN.docx`) kèm theo.

## File đầu vào

| prompt | images | aspectRatio | format |
|---|---|---|---|
| A vintage travel poster of Ha Long Bay at sunset, bold retro typography | | 9:16 | png |
| Product photo of a ceramic mug on marble, soft daylight | `D:\anh\logo.png` | 1:1 | |
| Poster in the same art style as the references | `D:\anh\a.png; https://x.com/b.jpg` | 16:9 | png |

Chỉ `prompt` là bắt buộc.

- **images** — tối đa 10 ảnh, phân cách bằng `;` hoặc xuống dòng. Nhận cả đường dẫn
  trên máy lẫn URL. Ảnh trên máy được upload tự động qua `/images/presign`
  (2 bước: presign → PUT, không có bước confirm). Cache theo nội dung file nên một
  ảnh dùng lại ở nhiều dòng — kể cả ở các lần chạy khác nhau — chỉ upload một lần.
- Cũng nhận kiểu tách cột `image1`, `image2`, …
- Tên cột không phân biệt hoa thường (`Prompt`, `Aspect Ratio` đều hiểu).
- Gõ sai tên cột → **báo lỗi dừng ngay**, không chạy tiếp với dữ liệu thiếu.

Mỗi dòng cho ra **một** ảnh. Muốn N ảnh cùng nội dung thì copy dòng đó N lần.

## Kết quả

```
ket-qua_2026-09-14_0930/
    0001.png          ← dòng 2 trong Excel
    0002.png          ← dòng 3
    _ket-qua.xlsx     ← jobId, link, file, credit, lỗi
```

Ảnh trên máy chủ bị xoá sau 7 ngày nên tool tải về ngay khi job xong. Báo cáo được
ghi sau **từng** dòng, mất điện giữa chừng vẫn còn nguyên phần đã làm.

## Chạy từ source

```bash
git clone https://github.com/sangtao-ai/sangtao-excel-image
cd sangtao-excel-image
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt

.venv/Scripts/python main.py jobs.xlsx
```

API key lấy tại sangtao.ai → Cài đặt → API Key. Đặt vào `config.txt`, biến môi
trường `SANGTAO_API_KEY`, hoặc `--api-key`.

```bash
python main.py jobs.xlsx --dry-run      # kiểm tra file, không tốn tiền
python main.py jobs.xlsx -o D:\anh      # chọn nơi lưu
python main.py jobs.xlsx --retry 2 -v   # thử lại nhiều hơn, in chi tiết
```

`--dry-run` chạy được **không cần API key** — kiểm tra mọi dòng, mọi đường dẫn ảnh,
báo rõ dòng nào sai. Nên chạy trước khi xử lý file vài trăm dòng.

## Build exe

```bash
build.bat
```

Ra `dist/TaoAnh/` gồm exe + file mẫu + hướng dẫn, nén lại rồi đưa lên Releases.

Exe chưa ký số nên Windows SmartScreen sẽ cảnh báo lần đầu — `HUONG-DAN.txt` có
hướng dẫn ae bấm qua.

## Test

```bash
.venv/Scripts/python -m pytest tests/ -q
```

63 test, không gọi mạng — lớp HTTP được thay bằng bản giả nên vẫn đi qua đúng code
thật của client.

## Ghi chú về API

Vài điều rút ra từ docs, đã xử lý sẵn trong tool:

- Auth bằng header `X-Api-Key`, không phải `Authorization: Bearer`.
- Trường lạ **bị bỏ qua im lặng**, API vẫn trả 200 — nên tool chỉ gửi field có giá
  trị, và validate tên cột chặt ở phía mình.
- `status` lúc xong trả về **chữ thường** (`complete`), phải so sánh không phân biệt
  hoa thường.
- `failureKind` quyết định retry có ích không. `GENERATION_TIMEOUT` /
  `QUOTA_EXHAUSTED` thì thử lại được; `PROMPT_UNCLEAR` / `CONTENT_REJECTED` /
  `REFERENCE_DOWNLOAD_FAILED` thì retry chỉ tốn thêm tiền.
- Job hỏng không bị tính tiền, credit hoàn tự động.
- Nhịp giữa hai job là 45 giây ở phía nhà cung cấp — bắn song song không nhanh hơn,
  chỉ làm `queuePosition` tăng. Nên tool chạy tuần tự.
- `idempotencyKey` để retry không bị trừ tiền hai lần.
- Ảnh upload qua `/images/presign` cũng sống 7 ngày, nên cache có hạn 6 ngày —
  không bao giờ gửi URL sắp chết cho một job đang chờ.

## Bảo mật

`config.txt` chứa API key và đã nằm trong `.gitignore`. Đừng commit, đừng gửi cho
người khác. Lỡ lộ thì vào sangtao.ai xoá key cũ và tạo key mới.

## Giấy phép

MIT
