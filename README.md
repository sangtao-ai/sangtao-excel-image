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
  trên máy lẫn URL. Ảnh trên máy được upload tự động. Cache theo nội dung file nên
  một ảnh dùng lại ở nhiều dòng — kể cả ở các lần chạy khác nhau — chỉ upload một
  lần.
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

API key: nhắn [facebook.com/cong.dac.dev](https://www.facebook.com/cong.dac.dev) để được cấp kèm 1000 ảnh
miễn phí. Đặt vào `config.txt`, biến môi trường `SANGTAO_API_KEY`, hoặc `--api-key`.

Số ảnh chạy cùng lúc đặt trong `config.txt` (`so_luong_cung_luc`) hoặc `-t`.

```bash
python main.py jobs.xlsx --dry-run      # kiểm tra file, không tốn tiền
python main.py jobs.xlsx -o D:\anh      # chọn nơi lưu
python main.py jobs.xlsx -t 5           # 5 ảnh cùng lúc (mặc định 3, tối đa 5)
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

70 test, không gọi mạng — lớp HTTP được thay bằng bản giả nên vẫn đi qua đúng code
thật của client.

Tài liệu API: [sangtao.ai/vi/api-docs](https://sangtao.ai/vi/api-docs#chatgpt-image)

## Bảo mật

`config.txt` chứa API key và đã nằm trong `.gitignore`. Đừng commit, đừng gửi cho
người khác. Lỡ lộ thì vào sangtao.ai xoá key cũ và tạo key mới.

## Giấy phép

MIT
