# Hệ thống BI tích hợp AI phân tích hoạt động kinh doanh thương mại điện tử

> Mini project môn **Hệ thống thông tin phục vụ trí tuệ kinh doanh** (CSC12107), Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM.
> Lớp CQ2023/1, **Nhóm 3**. Giảng viên hướng dẫn: TS. Hồ Thị Hoàng Vy.

Hệ thống đi trọn từ dữ liệu thô đến quyết định: **Mage.ai** nạp CSV vào vùng `staging`, **dbt** làm sạch và dựng kho `dds` (Galaxy schema) trên **PostgreSQL 17**, **Power BI** trình bày 3 trang dashboard, và một **trợ lý AI** (Gemini) tóm tắt, giải thích số liệu trên dashboard. Toàn bộ chạy trên máy cá nhân bằng Docker.

## 1. Giới thiệu

| Mục | Nội dung |
|---|---|
| Bối cảnh | Olist là nền tảng giúp các cửa hàng nhỏ ở Brazil bán hàng trên các sàn thương mại điện tử lớn. Dữ liệu đơn hàng, thanh toán, vận chuyển, đánh giá nằm rải rác ở nhiều bảng và có lỗi, nên nhà quản lý khó có cái nhìn tổng hợp và kịp thời. |
| Dataset | [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle, giấy phép CC BY-NC-SA 4.0): 9 file CSV, 99.441 đơn hàng mua từ 09/2016 đến 10/2018, tiền tệ BRL. Chi tiết: [data/raw/README.md](data/raw/README.md). |
| Mục tiêu | Giúp ban điều hành sàn theo dõi doanh thu, phát hiện vấn đề giao hàng và người bán, hiểu nguyên nhân dựa trên số liệu (chi tiết: [docs/business_questions.md](docs/business_questions.md)). |
| Phạm vi phân tích | Đơn mua từ **01/2017 đến 08/2018** (các tháng đầu và cuối kỳ quá thưa hoặc bị cắt dở). Dữ liệu tĩnh nên nạp tăng dần được mô phỏng bằng 10 batch theo tháng mua. |

### Câu hỏi nghiệp vụ và kết quả chính

| Trang dashboard | Câu hỏi | Kết quả chính (01/2017 – 08/2018) |
|---|---|---|
| 1. Tổng quan (Descriptive) | **Q1.** Doanh thu 01–08/2018 tăng bao nhiêu so với cùng kỳ, tăng nhờ số đơn hay nhờ giá trị đơn? | Doanh thu tăng 138% (3,08 lên 7,34 triệu BRL), số đơn tăng 137%, giá trị đơn trung bình chỉ tăng 0,4%: tăng trưởng đến từ số đơn. |
| | **Q2.** Danh mục và bang nào đóng góp doanh thu nhiều nhất? | 10 danh mục dẫn đầu chiếm 62,4% doanh thu; 5 bang dẫn đầu chiếm 73,9%, riêng São Paulo 38,3%. |
| 2. Giao hàng (Diagnostic) | **Q3.** Tháng nào, bang nào có tỉ lệ giao trễ vượt ngưỡng 10%? | Toàn kỳ 6,79%; ba tháng vượt ngưỡng là 11/2017 (12,4%), 02/2018 (14,1%), 03/2018 (19,0%); bang cao nhất là Alagoas (21,5%). |
| | **Q4.** Giao trễ làm điểm đánh giá giảm bao nhiêu? | Đơn đúng hạn 4,29★, đơn trễ 2,27★ (thấp hơn 2,02★); trễ 1–3 ngày đã còn 3,29★. |
| 3. Người bán (Diagnostic) | **Q5.** Giao trễ do người bán bàn giao chậm hay do vận chuyển? | Bàn giao trễ làm tỉ lệ giao trễ tăng 3,9 lần (21,1% so với 5,4%); đợt trễ 03/2018 chủ yếu do khâu vận chuyển. |
| | **Q6.** Người bán nào cần ưu tiên xử lý? | 191 trên 633 người bán có từ 30 đơn vượt ngưỡng (bàn giao trễ trên 10% hoặc điểm dưới 3,5), chiếm 21,9% doanh thu toàn sàn. |

## 2. Thành viên nhóm

| MSSV | Họ tên | Phụ trách | Phần chính trong repo |
|---|---|---|---|
| 23120193 | Trần Kim Yến | Thiết kế data warehouse; data ingestion; kiểm thử; dashboard phân tích (semantic model, trang Giao hàng); dashboard theo dõi ETL; quay video demo; viết tài liệu | [docs/dw_design.md](docs/dw_design.md), [mage/](mage/README.md), [docs/semantic_model.md](docs/semantic_model.md), [monitor/](monitor/README.md) |
| 23120198 | Nguyễn Nhựt Thanh | Phân tích nghiệp vụ; data transformation; kiểm thử; dashboard phân tích (trang Người bán); tích hợp Generative AI; quay video demo; viết tài liệu | [docs/business_questions.md](docs/business_questions.md), [docs/source_to_target_mapping.md](docs/source_to_target_mapping.md), model trong [dbt/](dbt/README.md), [ai/](ai/README.md), [docs/demo/](docs/demo/README.md) |
| 23120201 | Nguyễn Thị Trúc Hằng | Khảo sát dữ liệu; thiết kế kiến trúc hệ thống; data transformation; dashboard phân tích (trang Tổng quan); lập lịch ETL; quay video demo; viết tài liệu | [scripts/](scripts/README.md), [docs/data_profiling.md](docs/data_profiling.md), [docs/decisions.md](docs/decisions.md), [docs/architecture.md](docs/architecture.md), môi trường Docker và [sql/init/](sql/README.md), khởi tạo dbt, bước dbt trong Mage, lập lịch ETL |

## 3. Kiến trúc hệ thống

![Kiến trúc tổng thể](docs/images/architecture.png)

```
Kaggle CSV ─► split_batches.py ─► data/batches ─► Mage.ai ─► staging ─► dbt ─► dds (Galaxy) ─► Power BI
                                                     │       (Mage gọi dbt)        │
                                                     │                             └─► Trợ lý AI ◄─► Gemini
                                                     └─► etl_log (nhật ký ETL), dq (dòng dữ liệu lỗi) ─► Dashboard theo dõi ETL
```

Hệ thống theo kiến trúc **Single DDS** của bài giảng (Source → Stage ETL → Stage → DDS ETL → DDS → Application). Mỗi lần chạy pipeline Mage gồm hai khâu: nạp batch vào `staging` rồi gọi `dbt build` dựng lại `dds`; chỉ khi cả hai thành công thì mốc nạp (LSET) mới tiến. Chi tiết các tầng và luồng dữ liệu: [docs/architecture.md](docs/architecture.md).

| Schema (database `olist_dw`) | Vai trò | Ghi bởi |
|---|---|---|
| `staging` | 8 bảng nạp từ CSV, giữ tên cột gốc, thêm cột kỹ thuật `_batch_id`, `_loaded_at` | Mage |
| `etl_log` | Nhật ký mỗi lần chạy: `pipeline_run`, `table_load`, `quality_check`, `dbt_result`; 3 view cho dashboard theo dõi ETL | Mage |
| `dq` | Dòng bị loại khi nạp (`rejected_rows`) và dòng vi phạm từng dbt test | Mage, dbt |
| `dbt_stg`, `dbt_int` | View trung gian `stg_`, `int_` và bảng seed | dbt |
| `dds` | Kho dữ liệu: 6 dimension, 3 fact (`fact_sales`, `fact_delivery`, `fact_review`) | dbt (Power BI và AI chỉ đọc schema này) |

## 4. Công nghệ sử dụng

| Thành phần | Công nghệ | Phiên bản |
|---|---|---|
| Môi trường | Docker Desktop, Docker Compose | – |
| Data Warehouse | PostgreSQL | 17 |
| Data Ingestion, lập lịch | Mage.ai | 0.9.79 |
| Transformation | dbt-core, dbt-postgres, package dbt_utils | 1.8.7; 1.8.2; 1.3.3 |
| BI | Power BI Desktop (bản Microsoft Store) | 2.159 |
| Generative AI | Google Gemini qua Google AI Studio (gói miễn phí); dự phòng Groq | `gemini-3.5-flash`, `gemini-3.5-flash-lite`; `llama-3.3-70b-versatile` |
| Ứng dụng trợ lý AI, dashboard theo dõi ETL | Streamlit, Plotly | Streamlit 1.55 trở lên |
| Script phụ trợ | Python, pandas | Python 3.13 |

## 5. Cấu trúc thư mục

```
bi-miniproject/
├── compose.yaml        # 2 container: olist-postgres (PostgreSQL 17), olist-mage (Mage + dbt)
├── docker/             # Dockerfile của image Mage
├── .env.example        # Mẫu biến môi trường (thông tin DB, API key); copy thành .env
├── data/
│   ├── raw/            # 9 file CSV gốc từ Kaggle
│   └── batches/        # 10 batch mô phỏng Full Load / Incremental Load (sinh bằng script, không commit)
├── scripts/            # Khảo sát dữ liệu, kiểm chứng khóa, chia batch, tạo lỗi để demo
├── sql/
│   ├── init/           # Tạo schema, bảng staging, etl_log, dq, view giám sát (Postgres tự chạy lần đầu)
│   └── checks/         # Truy vấn kiểm tra và đối soát
├── mage/olist_etl/     # Project Mage: pipeline full_load, incremental_load, trigger lập lịch
├── dbt/                # Project dbt: staging → intermediate → marts, seeds, tests, macros
├── powerbi/            # measures.dax, theme, bản đồ bang (file .pbix nằm trên OneDrive của nhóm)
├── ai/                 # Ứng dụng trợ lý AI (Streamlit + Gemini), prompts, log các lần hỏi
├── monitor/            # Dashboard theo dõi các lần chạy ETL (Streamlit)
└── docs/               # Tài liệu thiết kế, hướng dẫn cài đặt, hình ảnh, video demo
```

| Thư mục | README |
|---|---|
| Dữ liệu gốc | [data/raw/README.md](data/raw/README.md) |
| Batch mô phỏng | [data/batches/README.md](data/batches/README.md) |
| Script phụ trợ | [scripts/README.md](scripts/README.md) |
| SQL khởi tạo và kiểm tra | [sql/README.md](sql/README.md) |
| Pipeline Mage, lập lịch | [mage/README.md](mage/README.md) |
| dbt | [dbt/README.md](dbt/README.md) |
| Power BI | [powerbi/README.md](powerbi/README.md) |
| Generative AI | [ai/README.md](ai/README.md) |
| Dashboard theo dõi ETL | [monitor/README.md](monitor/README.md) |
| Video demo | [docs/demo/README.md](docs/demo/README.md) |

## 6. Hướng dẫn chạy nhanh

Hướng dẫn đầy đủ, có kết quả đúng để tự kiểm tra ở từng bước: [docs/setup_guide.md](docs/setup_guide.md). Cần cài trước: Docker Desktop, Git, Power BI Desktop; Python 3.13 chỉ cần khi chạy ứng dụng trợ lý AI và dashboard theo dõi ETL. Mọi lệnh chạy ở thư mục gốc repo (PowerShell).

1. **Lấy code và tạo file cấu hình**

   ```powershell
   git clone https://github.com/TrucHang676/bi-miniproject.git
   cd bi-miniproject
   Copy-Item .env.example .env                         # đổi POSTGRES_PASSWORD; thêm GEMINI_API_KEY nếu chạy phần AI
   Copy-Item dbt\profiles.yml.example dbt\profiles.yml
   ```

2. **Bật hệ thống** (mở Docker Desktop trước). Lần đầu, Postgres tự tạo schema và bảng từ `sql/init/`.

   ```powershell
   docker compose up -d --build
   docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/checks/00_check_init.sql   # 23 dòng PASS
   ```

3. **Sinh batch dữ liệu và cài package dbt**

   ```powershell
   docker compose exec mage python scripts/split_batches.py   # dòng cuối: TẤT CẢ ĐẠT (9/9 PASS)
   docker compose exec mage dbt deps
   docker compose exec mage dbt debug                         # All checks passed!
   ```

4. **Chạy pipeline**: mở Mage tại http://localhost:6789 (`admin@admin.com` / `admin`), chạy `full_load` 1 lần rồi `incremental_load` 9 lần (**Triggers → Run@once**). Mỗi lần chạy, Mage nạp 1 batch vào `staging` rồi tự gọi `dbt build` dựng `dds`. Có thể chạy bằng dòng lệnh:

   ```powershell
   docker compose exec mage mage run /home/src/mage/olist_etl full_load
   docker compose exec mage mage run /home/src/mage/olist_etl incremental_load
   ```

   Hoặc bật trigger `incremental_demo` để Mage tự nạp 1 batch mỗi 5 phút ([mage/README.md](mage/README.md) mục Lập lịch).

5. **Kiểm tra kết quả** bằng DBeaver (`localhost:5432`, database `olist_dw`): [sql/checks/01_pipeline_demo.sql](sql/checks/01_pipeline_demo.sql) (nhật ký pipeline), [sql/checks/02_dds_checks.sql](sql/checks/02_dds_checks.sql) (đối soát kho `dds`). Tài liệu dbt: `docker compose exec mage dbt docs generate --static`, mở `dbt/target/static_index.html`.

6. **Power BI**: mở `Dashboard seminar [Group-3].pbix` (OneDrive của nhóm), bấm **Refresh**; tài khoản PostgreSQL lấy theo `.env`. Chi tiết: [powerbi/README.md](powerbi/README.md).

7. **Dashboard theo dõi ETL**: `py -m pip install -r monitor/requirements.txt`, bấm đúp `monitor\chay_monitor.bat`, mở http://localhost:8502.

8. **Trợ lý AI**: `py -m pip install -r ai/requirements.txt`, điền `GEMINI_API_KEY` vào `.env`, bấm đúp `ai\chay_app.bat`, mở http://localhost:8501 (hoặc bấm biểu tượng trợ lý trên header Power BI).

## 7. Kết quả đạt được

| Hạng mục | Kết quả |
|---|---|
| Nạp dữ liệu (Mage) | Full Load và Incremental Load cho 10 batch; 7 phép kiểm tra chất lượng mỗi bảng, dòng lỗi lưu vào `dq`; chạy lại một batch ra 0 INSERT, 0 UPDATE; lỗi giữa chừng thì cả batch hoàn tác. Sau batch cuối, `staging` khớp 100% dữ liệu gốc. |
| Biến đổi (dbt) | 20 model, 2 seed, 155 test; `dbt build` đạt `PASS=177 ERROR=0`; dbt docs mô tả đủ 176 cột. |
| Kho dữ liệu | Galaxy schema 6 dimension, 3 fact: `fact_sales` 101.953 dòng, `fact_delivery` 100.010 dòng, `fact_review` 100.568 dòng. |
| Power BI | Semantic model 16 quan hệ, 5 hierarchy, 99 measure; 3 trang dashboard và trang ẩn Chi tiết người bán; số liệu khớp bảng nghiệm thu. |
| Lập lịch ETL | 2 trigger lưu trong code (5 phút một lần cho demo, hằng tháng cho vận hành); kiểm thử chạy theo lịch, lỗi dữ liệu và tự phục hồi đạt. |
| Dashboard theo dõi ETL | 3 trang (tổng quan vận hành, chất lượng dữ liệu, chi tiết một lần chạy); 1.989 trên 1.989 số liệu khớp khi đối chiếu độc lập. |
| Generative AI | Tóm tắt KPI, giải thích biến động, hỏi đáp; AI chỉ dùng số liệu tính sẵn từ `dds` (khớp dashboard 50/50 số), mọi con số trong câu trả lời được đối chiếu tự động. |

## 8. Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [docs/business_questions.md](docs/business_questions.md) | Bối cảnh, đối tượng sử dụng, câu hỏi Q1–Q6, 13 KPI và 5 measure bổ trợ |
| [docs/data_dictionary.md](docs/data_dictionary.md) | Từ điển dữ liệu 9 bảng nguồn |
| [docs/data_profiling.md](docs/data_profiling.md) | Kết quả khảo sát chất lượng dữ liệu (sinh tự động) |
| [docs/decisions.md](docs/decisions.md) | Các quyết định thiết kế (khóa, nạp tăng dần, chia batch, DQ, xóa mềm, lập lịch) kèm lý do và số liệu chứng minh |
| [docs/architecture.md](docs/architecture.md) | Kiến trúc tổng thể và luồng dữ liệu |
| [docs/dw_design.md](docs/dw_design.md) | Thiết kế kho: quy trình nghiệp vụ, grain, fact, dimension, lược đồ Galaxy |
| [docs/source_to_target_mapping.md](docs/source_to_target_mapping.md) | Ánh xạ nguồn → đích đến từng cột, quy tắc biến đổi R1–R10 |
| [docs/pipeline_rules.md](docs/pipeline_rules.md), [docs/dbt_rules.md](docs/dbt_rules.md) | Quy tắc xây dựng pipeline Mage và model dbt, kịch bản kiểm thử |
| [docs/powerbi_rules.md](docs/powerbi_rules.md), [docs/semantic_model.md](docs/semantic_model.md) | Quy tắc và kết quả xây dựng semantic model |
| [docs/schedule_rules.md](docs/schedule_rules.md) | Thiết kế lập lịch ETL |
| [docs/generative_ai.md](docs/generative_ai.md) | Thiết kế phần Generative AI |
| [docs/setup_guide.md](docs/setup_guide.md) | Hướng dẫn cài đặt và chạy hệ thống |

## 9. Sản phẩm nộp

| # | Sản phẩm | Vị trí |
|---|---|---|
| 1 | Báo cáo PDF | `docs/report/` (bản PDF cuối; bản Word nháp không đưa lên Git) |
| 2 | Source code | `mage/`, `dbt/`, `sql/`, `scripts/`, `ai/`, `monitor/` |
| 3 | Power BI | File `.pbix` (khoảng 29 MB, kèm dữ liệu) nộp riêng và lưu trên OneDrive của nhóm; DAX, theme, bản đồ trong `powerbi/` |
| 4 | Link Kaggle và hướng dẫn chạy | [data/raw/README.md](data/raw/README.md), [docs/setup_guide.md](docs/setup_guide.md), mục 6 của file này |
| 5 | Video demo | [docs/demo/README.md](docs/demo/README.md) |

Dữ liệu Olist dùng theo giấy phép [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): chỉ dùng cho mục đích học tập, phi thương mại, có ghi nguồn.
