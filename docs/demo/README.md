# Video Demo

**Thư mục video trên Google Drive:** https://drive.google.com/drive/folders/1MsEe3qm_t5pf9be-asin53JUk51FkqsX

| File | Nội dung | Link |
|---|---|---|
| `Video demo seminar phần 1 [Group-3].mp4` | Dữ liệu, kiến trúc và quy trình ETL (Seminar 1) | [Xem](https://drive.google.com/file/d/10U86tZOzOUcbgi1LVnkJceCn0BDHgXfy/view) |
| `Video demo seminar phần 2 [Group-3].mp4` | Lập lịch ETL, giám sát ETL, dashboard Power BI và AI giải thích kết quả (Seminar 2, 3) | [Xem](https://drive.google.com/file/d/11hFCq8lqtS1FQbQg4x2dBcjJ6Sq5vCif/view) |

Các đoạn chuyển phần trong video dùng slide của `slide_chuyen_canh.html` (mục cuối).

## Nội dung video phần 1

| Phần | Nội dung | Người trình bày |
|---|---|---|
| 1 | Giới thiệu bộ dữ liệu Olist (9 bảng, khoảng 99 nghìn đơn hàng từ 09/2016 đến 10/2018) và kết quả khảo sát chất lượng dữ liệu | Nguyễn Nhựt Thanh |
| 2 | Kiến trúc hệ thống: các tầng nguồn, tích hợp và biến đổi, kho dữ liệu, khai thác; luồng dữ liệu theo mô hình Single DDS; triển khai bằng Docker | Nguyễn Thị Trúc Hằng |
| 3 | Mô hình hóa kho dữ liệu: câu hỏi nghiệp vụ Q1–Q6, quy trình nghiệp vụ, grain của 3 bảng fact, 6 dimension, measure, khóa, lược đồ Galaxy; minh họa grain trên một đơn hàng thật | Nguyễn Thị Trúc Hằng |
| 4 | Chia batch dữ liệu để mô phỏng Full Load và Incremental Load: quy tắc chia, chạy script, kết quả 10 batch và `manifest.csv`, lần theo một đơn hàng qua các batch | Nguyễn Thị Trúc Hằng |
| 5 | Nạp dữ liệu Source → Staging bằng Mage.ai: pipeline Full Load, Incremental Load (LSET, CET), kiểm tra chất lượng đầu vào, ghi nhật ký `etl_log`, các tình huống lỗi | Trần Kim Yến |
| 6 | Biến đổi Staging → DDS bằng dbt: làm sạch, chuẩn hóa, dựng dimension và fact, dbt test, dbt docs và lineage | Nguyễn Nhựt Thanh |

## Nội dung video phần 2

| Phần | Nội dung | Người trình bày |
|---|---|---|
| 1 | Toàn bộ luồng ETL, lập lịch và dashboard giám sát ETL: 2 trigger của Mage, chạy `full_load` bằng tay, bật lịch để Mage tự nạp từng batch, lỗi dữ liệu và tự phục hồi theo lịch, đọc dashboard giám sát, làm mới Power BI | Nguyễn Thị Trúc Hằng |
| 2 | Semantic model trong Power BI: quan hệ, hierarchy, DAX measure | Trần Kim Yến |
| 3 | Dashboard trang 1 Tổng quan (Q1, Q2): doanh thu theo tháng, 10 danh mục và 5 bang có doanh thu cao nhất; drill-down, lọc chéo | Nguyễn Thị Trúc Hằng |
| 4 | Dashboard trang 2 Giao hàng (Q3, Q4): tháng và bang giao trễ vượt ngưỡng, ảnh hưởng của giao trễ đến điểm đánh giá | Trần Kim Yến |
| 5 | Dashboard trang 3 Người bán (Q5, Q6): giao trễ do bàn giao hay do vận chuyển, người bán vượt ngưỡng, drill-through sang trang Chi tiết người bán | Nguyễn Nhựt Thanh |
| 6 | AI giải thích kết quả dashboard: tóm tắt KPI, giải thích biến động, hỏi đáp, kiểm chứng số liệu trong câu trả lời | Nguyễn Nhựt Thanh |

## Đối chiếu yêu cầu đề bài

| Yêu cầu | Vị trí trong video |
|---|---|
| Mage: Full Load, Incremental Load, ghi log | Video 1 phần 5; video 2 phần 1 |
| dbt: chạy model, dbt test, lineage | Video 1 phần 6 |
| Data Warehouse: thiết kế, kiểm tra dữ liệu đã cập nhật | Video 1 phần 3; video 2 phần 1 |
| Power BI: Refresh, dashboard Overview | Video 2 phần 1 (Refresh), phần 3 |
| Power BI: dashboard Diagnostic (drill-down, drill-through) | Video 2 phần 4, 5 |
| AI: tóm tắt KPI, giải thích biến động | Video 2 phần 6 |
| Lập lịch ETL, dashboard theo dõi ETL (Seminar 3) | Video 2 phần 1 |

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
