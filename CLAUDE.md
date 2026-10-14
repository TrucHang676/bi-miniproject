# CLAUDE.md – Mini project BI tích hợp AI (môn CSC12107)

## Cách làm việc với người dùng
- Luôn trả lời bằng **tiếng Việt**.
- Người dùng là sinh viên năm 4 ngành Hệ thống thông tin, **mới làm quen Docker / Mage / dbt**. Hướng dẫn từng bước nhỏ, giải thích bằng ví dụ đời thường (VD: Mage = khâu đi chợ & sơ chế, dbt = khâu nấu, DW = tủ đồ ăn đã bày sẵn), tránh dồn quá nhiều khái niệm một lúc.
- Người dùng hay gửi ảnh chụp màn hình từng bước → đọc kỹ ảnh trước khi trả lời.
- Đây là bài nhóm: code/tài liệu phải đủ rõ để thành viên khác đọc hiểu, và phục vụ được báo cáo PDF + video demo. Thành viên khác cũng commit vào repo (VD NhutThanh viết `business_questions.md`, phác thảo dashboard) → trước khi sửa tài liệu nên `git pull` / xem `git log` để không ghi đè việc của bạn.
- Commit: message bằng **tiếng Anh** (tiêu đề ngắn + gạch đầu dòng), **không** thêm dòng `Co-Authored-By: Claude` hay ghi chú AI nào.

## Đề bài (tóm tắt từ `2627.Yêu cầu.pdf`)
Xây dựng hệ thống BI hoàn chỉnh trên một dataset Kaggle:

| Thành phần | Yêu cầu chính |
|---|---|
| **Mage.ai** | Pipeline nạp CSV → `staging`; kiểm tra cấu trúc & chất lượng cơ bản; **Full Load + Incremental Load** (mô phỏng batch vì dữ liệu tĩnh); ghi log trạng thái, số dòng, lỗi; chạy lại được |
| **dbt** | Làm sạch, chuẩn hóa, tích hợp; **dbt tests**; phụ thuộc model rõ ràng; **dbt docs** |
| **Data Warehouse** | Xác định quy trình nghiệp vụ, **grain**, fact/dim/measures, Star hoặc Snowflake schema; nạp từ staging qua dbt. Đề cho phép SQL Server / Postgres / DuckDB → **nhóm chốt SQL Server** |
| **Power BI** | Semantic model (relationships, DAX measures, hierarchies); tối thiểu 2 dashboard: **Overview (descriptive)** và **Diagnostic** (drill-down/through, yếu tố đóng góp, bằng chứng định lượng) |
| **Generative AI** | LLM tạo **summary** từ KPI + **giải thích xu hướng/biến động**; kết quả phải dựa trên số liệu đã tính, kiểm chứng được, hạn chế bịa. Khuyến khích hỏi đáp ngôn ngữ tự nhiên |

**Sản phẩm nộp:** báo cáo PDF, source code (Mage, dbt, SQL, AI), file `.pbix`, link Kaggle + hướng dẫn chạy, video demo end-to-end.

## Mốc thời gian (nhóm tự chia)
- **Seminar 1** (deadline chưa rõ): phân tích nghiệp vụ (dataset, câu hỏi, KPI, thiết kế DW) **+ toàn bộ pipeline** Mage → staging → dbt → DW star schema. Lý do: Seminar 2 giả định đã có kho dữ liệu.
- **Seminar 2** (hạn **23:00 05/11/2026**): dashboard Power BI + báo cáo phân tích + source + video demo.
- **Seminar 3 – điểm cộng** (hạn **23:00 14/11/2026**): lập lịch ETL, dashboard theo dõi mỗi lần chạy ETL, AI giải thích kết quả. → Thiết kế bảng `etl_log` thật kỹ ngay từ Seminar 1.

## Dataset: Brazilian E-Commerce Public Dataset by Olist
- Kaggle: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce (license CC BY-NC-SA 4.0)
- 9 file CSV trong `data/raw/` (tải ngày 10/10/2026, **đã commit lên repo** để cả nhóm khỏi tải lại; CSV đánh dấu `-text` trong `.gitattributes`).
- Dữ liệu ~99k đơn hàng, mua từ 09/2016 đến 10/2018, sàn TMĐT Brazil, tiền tệ BRL.

| Bảng | Số dòng | Khóa |
|---|---|---|
| orders | 99.441 | `order_id` |
| order_items | 112.650 | (`order_id`, `order_item_id`) |
| order_payments | 103.886 | (`order_id`, `payment_sequential`) |
| order_reviews | 99.224 | `review_id` **không** unique (98.410 giá trị) |
| customers | 99.441 | `customer_id` (1 customer_id = 1 đơn) |
| products | 32.951 | `product_id` |
| sellers | 3.095 | `seller_id` |
| geolocation | 1.000.163 | không có khóa; 19.015 zip |
| product_category_name_translation | 71 | `product_category_name` |

Toàn vẹn tham chiếu tốt: 0 dòng mồ côi giữa các bảng chính.

### Bẫy dữ liệu đã phát hiện (bắt buộc xử lý ở staging/dbt)
1. **Đầu/cuối kỳ thưa** (09/2016: 4 đơn, 12/2016: 1, 09/2018: 16, 10/2018: 4) → phân tích xu hướng trong khoảng **01/2017 – 08/2018**.
2. **Khách thật là `customer_unique_id`** (96.096 người, 2.997 mua lại), không phải `customer_id`. `dim_customer` dựa trên `customer_unique_id`.
3. **Fan-out khi JOIN**: 1 đơn có nhiều item, nhiều payment, có thể nhiều review (547 đơn) → doanh thu tính từ `order_items` (price + freight_value), gom payments/reviews về 1 dòng/đơn trước khi join. Không SUM sau khi join items × payments.
4. **reviews có xuống dòng trong ô có dấu ngoặc kép** → dùng CSV parser chuẩn (pandas / `COPY ... CSV`), không đọc theo dòng.
5. **geolocation bẩn**: 261.831 dòng trùng, nhiều tọa độ/zip, tên thành phố lẫn có dấu/không dấu (`sao paulo`/`são paulo`), 42 điểm ngoài Brazil → gom 1 dòng/zip (trung bình lat/lng). 278 zip khách & 7 zip seller không có trong geolocation.
6. **Zip code phải giữ dạng text** (có số 0 đầu, VD `01037`).
7. products: 610 sp thiếu category; 2 category thiếu bản dịch (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) → bổ sung bằng dbt seed. Tên cột gốc sai chính tả (`product_name_lenght`, `product_description_lenght`) → đổi tên ở staging.
8. orders: 8 đơn `delivered` thiếu ngày giao; 6 đơn `canceled` lại có ngày giao; 166 đơn có `order_delivered_carrier_date` < ngày mua; 775 đơn không có item (chủ yếu canceled/unavailable).
9. payments: 9 dòng `payment_value = 0`, 3 dòng `payment_type = not_defined`.
10. **Dữ liệu bị cắt cuối kỳ**: từ 23/08/2018 số đơn/ngày rơi từ ~273 xuống 1–144; chỉ 37 đơn giao sau 03/09/2018 → thời gian giao TB các tháng 06–08/2018 (9,2 → 7,7 ngày) thấp giả tạo, không diễn giải là cải thiện.
11. **Giỏ hàng tách đơn**: khách mua từ nhiều người bán bị tách thành nhiều đơn cách nhau vài giây (dùng chung `review_id`) → tỉ lệ mua lại theo đơn 3,12% bị thổi phồng; theo lần mua là 2,34%.

### Số liệu tham chiếu (để đối chiếu kết quả dbt / Power BI / AI)
- Tổng price: ~13,59 triệu BRL; freight: ~2,25 triệu; tổng payment: ~16,01 triệu.
- Đơn delivered: 96.478; tỉ lệ giao trễ (so **theo ngày** với ngày dự kiến): **6,77%** (so cả giờ ra 8,11% là sai vì ngày dự kiến luôn 00:00:00); số ngày giao TB 12,6 / trung vị 10,2.
- Review: 5★ 57,8% · 4★ 19,3% · 3★ 8,2% · 2★ 3,2% · 1★ 11,5%; 41% có bình luận.
- Thanh toán: credit_card 74%, boleto 19%. Bang lớn nhất: SP (~42% khách).

### Câu hỏi nghiệp vụ & KPI (đã chốt 12/10/2026 – chi tiết `docs/business_questions.md`)
- 3 trang dashboard × 2 câu hỏi × 2 biểu đồ = **Q1–Q6**, 12 biểu đồ; phạm vi 01/2017 – 08/2018. Bố cục từng trang: `powerbi/README.md`.
  - Trang 1 Tổng quan (descriptive): Q1 doanh thu theo tháng & YoY (tăng nhờ số đơn hay AOV), Q2 top 10 danh mục / top 5 bang.
  - Trang 2 Giao hàng & trải nghiệm (diagnostic): Q3 tháng/bang giao trễ > 10%, Q4 giao trễ ảnh hưởng điểm review.
  - Trang 3 Người bán & vận chuyển (diagnostic): Q5 trễ do người bán bàn giao hay do vận chuyển (nội bang / liên bang), Q6 người bán ≥ 30 đơn vi phạm ngưỡng → drill-through.
- **13 KPI** (K1–K13) + 5 measure bổ trợ (M1–M5). Quy ước: *đơn hợp lệ* = khác `canceled`/`unavailable` và có item; doanh thu = `SUM(price)` (không gồm freight, không lấy từ payments); KPI giao hàng chỉ trên đơn delivered `is_date_valid = 1`; review 1 dòng/đơn.
- Không có câu hỏi nào dùng thanh toán → **không cần `fact_payment`**. Địa lý phân tích theo **Vùng → Bang → Thành phố** (vùng thêm bằng dbt seed `state → region`), không cần tọa độ.

### Hướng thiết kế DW (chưa chốt – `docs/dw_design.md` vẫn là template)
- Theo ánh xạ quy trình ở mục 7 của `business_questions.md`: **Bán hàng** (grain 1 sản phẩm trong 1 đơn → `fact_order_item`), **Giao hàng** (grain 1 đơn, hoặc 1 đơn – 1 người bán cho K12), **Đánh giá** (1 review / đơn).
- Dim dự kiến: `dim_date` (role-playing: ngày mua, giao, dự kiến, trả lời review), `dim_customer` (`customer_unique_id`), `dim_seller`, `dim_product` (category tiếng Anh), địa lý vùng/bang, `dim_order_status`.

## Cấu trúc thư mục
Đề bài gốc nằm ngoài repo: `../2627.Yêu cầu.pdf`.
```
bi-miniproject/               # Repo chính của nhóm (thư mục chứa file này)
├── CLAUDE.md                 # File này (đã commit cho cả nhóm; ghi chú riêng từng máy → CLAUDE.local.md, bị ignore)
├── data/raw | batches        # CSV gốc | batch chia để mô phỏng incremental
├── scripts/                  # profile_olist.py, check_keys.py (sắp có: split_batches.py)
├── sql/ (checks/)            # Tạo DB, schema, bảng etl_log; query kiểm tra
├── mage/                     # Project Mage (pipeline full / incremental)
├── dbt/                      # models/staging → intermediate → marts; seeds; tests; macros
├── powerbi/                  # .pbix, measures.dax; README.md có phác thảo bố cục 3 trang
├── ai/                       # prompts/ (summary, explain_trend, qa), outputs/ (cặp KPI đầu vào – kết quả AI)
└── docs/                     # dataset, business_questions, data_dictionary, data_profiling, decisions, dw_design, setup_guide; report/, demo/, images/
```
Mỗi thư mục có `README.md` dạng template – khi làm xong phần nào thì điền vào template tương ứng thay vì tạo tài liệu mới.

## Quy ước
- DB: **SQL Server** (dbt adapter `dbt-sqlserver`). Mọi SQL, kiểu dữ liệu, ví dụ viết theo cú pháp T-SQL, không dùng cú pháp Postgres.
- Kiểu dữ liệu: `DATETIME2` cho mốc thời gian, `DATE` cho cột chỉ có ngày, `NVARCHAR` cho cột chữ có thể có dấu (tên thành phố, bình luận review → `NVARCHAR(MAX)`), `CHAR(5)` cho zip, `VARCHAR(32)` cho mã hash, `DECIMAL(10,2)` cho tiền. Chi tiết từng cột: `docs/data_dictionary.md`.
- Schema trong DB: `staging` (Mage nạp), `etl_log` (log pipeline), `dds` (Dimensional Data Store – dbt tạo dim/fact; tên theo cách gọi Stage → DDS của giảng viên, đổi từ `dwh` ngày 12/10/2026).
- dbt: `stg_` (view, 1 model / 1 bảng nguồn) → `int_` (view/ephemeral) → `dim_` / `fact_` (table/incremental).
- `dim_date.date_key` dạng int `YYYYMMDD`; dimension dùng surrogate key `<tên>_key`.
- Bí mật (`.env`, `dbt/profiles.yml`, API key) không commit; chỉ commit `.env.example`.

## Trạng thái hiện tại (cập nhật lần cuối 13/10/2026)
- [x] Chọn dataset Olist, tải về `data/raw/`.
- [x] BS-4 profiling: `scripts/profile_olist.py` → `docs/data_profiling.md` (sinh tự động, 23 vấn đề xếp theo mức độ) + `docs/data_dictionary.md` (viết tay).
- [x] Tạo khung thư mục + `.gitignore` + template `.md`.
- [x] Repo GitHub **private**: https://github.com/TrucHang676/bi-miniproject (nhánh `main`, push lần đầu 10/10/2026). Chỉ thư mục `bi-miniproject/` là repo; `CLAUDE.md` đã chuyển từ `Seminar/` vào gốc repo (13/10/2026); `docs/report/*.docx` (có MSSV) bị ignore, **không** commit. GitHub CLI đã đăng nhập tài khoản `TrucHang676` (nếu terminal VS Code chưa nhận lệnh `gh` thì dùng `& "C:\Program Files\GitHub CLI\gh.exe"`).
- [x] `docs/business_questions.md` (NhutThanh, 12/10/2026): bối cảnh, đối tượng, khả năng/giới hạn của dữ liệu, Q1–Q6 SMART, K1–K13 + M1–M5, ánh xạ câu hỏi → quy trình, câu hỏi cho AI. **14/10/2026**: đã tính lại toàn bộ cột "Kiểm chứng sơ bộ" từ CSV gốc → dữ liệu đủ trả lời Q1–Q6. Đã sửa: Q5 (11/2017 & 02/2018 trễ do **cả** bàn giao lẫn vận chuyển, chỉ 03/2018 thuần do vận chuyển), M1/M2 trả BLANK ngoài 01–08/2018 (vì 10/2016 có 324 đơn), định nghĩa Q6/M5 rõ hơn (số mới 191/633), ghi chú review gán chung cho mọi người bán trong đơn.
- [x] `powerbi/README.md`: phác thảo bố cục 3 trang dashboard + trang ẩn drill-through "Chi tiết người bán" (phần semantic model vẫn là template).
- [ ] Điền `docs/dataset.md`, `docs/dw_design.md` (bước tiếp theo hợp lý: thiết kế DW dựa trên mục 7 của business_questions).
- [x] Chốt DB: **SQL Server** (10/10/2026); data_dictionary.md và data_profiling.md đã dùng kiểu SQL Server.
- [ ] Chưa quyết định chạy SQL Server bằng Docker (image `mcr.microsoft.com/mssql/server`) hay cài trực tiếp trên Windows.
- [x] BS-5 chốt khóa & incremental: `docs/decisions.md` (D1–D7), kiểm chứng bằng `scripts/check_keys.py`. Tóm tắt: watermark `order_purchase_timestamp` theo tháng, nạp bằng MERGE theo PK; Full Load = đơn đến hết 2017-12, Incremental = 2018-01…2018-08 + batch nhỏ 2018-09+; bảng con theo `order_id`, customers theo `customer_id`; products/sellers/translation/geolocation nạp 1 lần; `dim_customer` theo `customer_unique_id` (SCD1); tỉ lệ mua lại tính theo lần mua = 2,34%.
- [x] Chốt **phương án B** (mô phỏng cập nhật trạng thái, D8 trong `docs/decisions.md`): mỗi batch chỉ chứa thông tin trước cutoff = đầu tháng sau; đơn cũ có mốc mới được gửi lại → MERGE có cả INSERT và UPDATE; review đi theo tháng trả lời; batch cuối `2018-09+` đối soát về trạng thái gốc. Products/sellers giữ nạp 1 lần.
- [ ] Chưa viết script chia batch (phải theo đúng quy tắc D8) / pipeline Mage – **chưa code, chờ người dùng giao task**.
- [ ] Chưa có `docker-compose.yml`, chưa init project Mage / dbt.
- [ ] Chưa chọn LLM cho phần AI; chưa điền thành viên & phân công trong `README.md`.
- [x] Báo cáo Word (`docs/report/*.docx`, người dùng tự dán): đã soạn nội dung **Chương 1** (Giới thiệu tổng quan: bối cảnh, mục tiêu, phạm vi, công nghệ) và **Chương 2** (Mô tả dataset & bài toán: nguồn/giấy phép, quy mô, data dictionary dạng `bảng (cột, ...)` + mô tả, profiling bản rút gọn, đối tượng sử dụng, câu hỏi Q1–Q10, KPI). ⚠ Bản Chương 2 này soạn **trước** khi chốt `business_questions.md` (nay là Q1–Q6, K1–K13) → cần đối chiếu và sửa lại mục câu hỏi/KPI trong Word. Người dùng muốn nhận nội dung dạng **plain text trong chat** để copy vào Word, không tạo file.
- [x] Lược đồ quan hệ 9 bảng nguồn: `docs/images/olist_relational_schema.drawio` (style ER: header xám gradient, crow's foot, PK gạch chân, FK in nghiêng; geolocation nối nét đứt vì không có khóa).
- [ ] **Chưa chốt có nạp `geolocation` hay không** (12/10/2026, người dùng bảo để đó). Nếu bỏ: phân tích địa lý theo bang/thành phố của customers/sellers, Q7 đổi thành "cùng bang / khác bang", bỏ `dim_geography` dạng tọa độ, sửa mục 1.3 và 2.5.2 của báo cáo; nếu giữ: gom 1 dòng/zip ở dbt. Báo cáo Chương 1–2 hiện vẫn viết theo hướng **có** dùng geolocation (gom theo zip). Lưu ý: Q1–Q6 mới đều phân tích theo vùng/bang (Q5 nội bang/liên bang lấy từ bang của customers/sellers) → không câu nào cần tọa độ; nghiêng về bỏ, nhưng người dùng chưa chốt.

→ Khi xong một việc hoặc chốt một quyết định, **cập nhật mục này** để phiên sau nắm được tiến độ.

## Môi trường máy
- Windows 11; shell mặc định PowerShell 5.1 (không có `&&`), có Git Bash.
- Python: gọi bằng **`py`** (Python 3.13, có pandas). Lệnh `python` trỏ tới alias Microsoft Store → không chạy.
- Docker Desktop (WSL2) phải được mở trước khi chạy container.
- Bản demo Mage + Postgres của lớp chạy được ở `../../Demo/mage-demo-main` (tính từ thư mục repo) (Mage 0.9.79, Postgres 17, login Mage `admin@admin.com` / `admin`, DB `warehouse` / `labuser` / `labpass123`) → chỉ dùng tham khảo cấu trúc Mage / docker-compose; đồ án dùng SQL Server nên phần database, kết nối Mage (MSSQL) và dbt adapter phải làm lại.
- DBeaver: nếu lỗi `invalid value for parameter "TimeZone": "Asia/Saigon"` thì thêm `-Duser.timezone=Asia/Ho_Chi_Minh` vào `%LOCALAPPDATA%\DBeaver\dbeaver.ini`.
