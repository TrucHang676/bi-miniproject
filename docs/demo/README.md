# Video Demo

- **Link video:** [Google Drive / YouTube]
- **Thời lượng:**

## Kịch bản demo

| Thời điểm | Nội dung | Người trình bày |
|-----------|----------|-----------------|
| 00:00 | Giới thiệu bài toán & dataset | |
|       | Mage: chạy Full Load, xem log | |
|       | Mage: chạy Incremental Load (batch mới) | |
|       | dbt: `dbt run`, `dbt test`, lineage graph | |
|       | Data Warehouse: kiểm tra dữ liệu đã cập nhật | |
|       | Power BI: Refresh, Dashboard Overview | |
|       | Power BI: Dashboard Diagnostic (drill-down/through) | |
|       | AI: tạo Summary & giải thích biến động | |
|       | Tổng kết | |

## Slide chuyển cảnh

File `slide_chuyen_canh.html` (mở bằng Edge / Chrome, không cần mạng) chứa 15 slide chèn giữa các đoạn quay: bộ 1.0 – 1.7 cho video phần 1, bộ 2.0 – 2.6 cho video phần 2. Màu và font lấy từ theme dashboard (`powerbi/theme_olist.json`, Segoe UI); bố cục canh giữa, gạch chân cong và thanh tiến trình nối mũi tên học theo thẻ chữ video BTVN SSIS (không dùng nét vẽ tay, màu kem). Ảnh dự phòng 1920×1080 của từng slide nằm trong `slide_chuyen_canh/` (tên file = mã slide).

Mỗi slide mở đầu phần có một hình minh họa vẽ từ nội dung thật của đồ án: 9 bảng CSV (geolocation nét đứt vì không nạp), kiến trúc CSV → Staging → DDS, galaxy schema (mỗi đường nối là một khóa ngoại trong model dbt), 10 batch trong `data/batches/manifest.csv`, tên block của 2 pipeline Mage, lineage dbt, và ảnh thu nhỏ 3 trang dashboard (vị trí, loại visual và màu thẻ KPI lấy từ file `.pbip`). Đồ án đổi ở phần nào thì sửa hàm tương ứng trong `ILLU` / `PAGES` của file html.

**Quay:** mở file, bấm `F` để toàn màn hình, dùng `→` / `Space` sang slide sau, `←` lùi, `Home` về slide đầu, `1` / `2` về bìa video 1 / 2, `R` chạy lại hiệu ứng, `H` hiện hướng dẫn phím. Mỗi slide quay khoảng 4 giây (hiệu ứng vào dưới 1,5 giây rồi đứng yên). Con trỏ chuột tự ẩn sau 2 giây.

**Mở thẳng một slide:** `slide_chuyen_canh.html?s=2.3`; thêm `&tinh=1` để hiện ngay trạng thái cuối.

**Sửa chữ:** nội dung nằm trong mảng `SLIDES` của file. Dấu `\n` là chỗ chủ động xuống dòng. Sửa xong thì chụp lại ảnh PNG của slide đó (PowerShell, ở thư mục gốc repo):

```powershell
$url = ([System.Uri](Resolve-Path docs\demo\slide_chuyen_canh.html).Path).AbsoluteUri
Start-Process msedge -Wait -ArgumentList "--headless --hide-scrollbars --disable-gpu --user-data-dir=`"$env:TEMP\edge_shot_$(Get-Random)`" --window-size=1920,1080 --virtual-time-budget=2000 `"--screenshot=$PWD\docs\demo\slide_chuyen_canh\2.3.png`" `"$url`?s=2.3&tinh=1`""
```

Mỗi lần chụp cần một thư mục `--user-data-dir` mới; dùng lại thư mục cũ thì Edge thoát ngay mà không chụp.
