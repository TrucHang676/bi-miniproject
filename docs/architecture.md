# Kiến trúc hệ thống

> Sơ đồ: [images/architecture.drawio](images/architecture.drawio) (2 trang: `[Seminar] - Kiến trúc tổng thể`, `[Seminar] - Luồng dữ liệu`);
> ảnh xuất: [images/architecture.png](images/architecture.png) (trang 1), [images/data_flow.png](images/data_flow.png) (trang 2).
> Dùng cho báo cáo Chương 4 (Hình 4.1, Hình 4.2). Trạng thái ghi trong file cập nhật ngày 16/11/2026.

## 1. Kiến trúc được chọn: Single DDS

- Theo bài giảng, kiến trúc **Single DDS** (Dimensional Data Store) có 2 vùng lưu trữ:
  - **Stage**: giữ tạm dữ liệu vừa trích xuất, gần như nguyên dạng nguồn;
  - **DDS**: dữ liệu đã làm sạch, tích hợp, tổ chức theo mô hình đa chiều (fact / dimension) để phân tích.
- **Lý do chọn:** chỉ có 1 nguồn dữ liệu (Olist), quy mô ~100 nghìn đơn, xử lý theo lô; Q1–Q6 trả lời được trực tiếp từ mô hình đa chiều
  → không cần thêm NDS (Normalized Data Store – kho chuẩn hóa trung gian) hay ODS (Operational Data Store – dữ liệu vận hành gần thời gian thực).
- Tên schema `dds` trong database lấy theo cách gọi này (đổi từ `dwh` ngày 12/10/2026).

## 2. Kiến trúc tổng thể (Hình 4.1)

![Kiến trúc tổng thể](images/architecture.png)

### 2.1. Các tầng

| Tầng | Thành phần | Vai trò |
|---|---|---|
| Nguồn dữ liệu | 8 file CSV Olist (`data/raw/`), script `scripts/split_batches.py` | Dữ liệu tĩnh → chia thành **10 batch** theo tháng mua (FULL, 2018-01 … 2018-08, 2018-09+) để mô phỏng dữ liệu mới đến định kỳ |
| Tích hợp & biến đổi | Mage.ai, dbt | **Mage** (Extract – Load): đọc batch, kiểm tra chất lượng, MERGE vào `staging`, ghi nhật ký; nạp xong thì **gọi dbt** trong cùng lần chạy (điều phối cả luồng); trigger của Mage chạy `incremental_load` theo lịch. **dbt** (Transform): biến đổi `staging` thành dim / fact trong `dds`, chạy dbt test |
| Kho dữ liệu | PostgreSQL 17, database `olist_dw` | 4 schema: `staging`, `dds`, `etl_log` (nhật ký ETL và 3 view giám sát), `dq` (dòng dữ liệu lỗi) + 2 schema làm việc dbt tự tạo: `dbt_stg`, `dbt_int` (view trung gian `stg_`, `int_`, seed) |
| Khai thác & trình bày | Power BI Desktop; ứng dụng trợ lý AI (Streamlit) gọi Google Gemini; dashboard theo dõi ETL (Streamlit) | **Power BI**: semantic model + 3 trang dashboard và trang ẩn Chi tiết người bán. **Trợ lý AI**: tính lại số liệu của 12 biểu đồ từ `dds`, gửi kèm prompt tới Gemini để tóm tắt KPI, giải thích biến động, hỏi đáp; mọi con số trong câu trả lời được đối chiếu tự động. **Dashboard theo dõi ETL**: đọc `etl_log` và `dq` để theo dõi từng lần chạy |

### 2.2. Triển khai

| Thành phần | Chạy ở đâu | Truy cập |
|---|---|---|
| PostgreSQL 17 | Container `olist-postgres` (image `postgres:17`); dữ liệu trong volume `bi-miniproject_pgdata`; script `sql/init/` tự chạy khi volume còn trống | `localhost:5432` |
| Mage.ai 0.9.79 + dbt-core 1.8.7 | Container `olist-mage` (build từ `docker/Dockerfile`); cả repo gắn vào `/home/src`; pipeline Mage gọi `dbt build` sau khi nạp staging, chạy tay bằng `docker compose exec mage dbt ...`; 2 trigger lập lịch lưu trong `mage/olist_etl/pipelines/incremental_load/triggers.yaml` | http://localhost:6789 |
| Power BI Desktop (bản Microsoft Store 2.159), DBeaver | Cài trực tiếp trên Windows; file `.pbix` dùng chung trên OneDrive của nhóm | Kết nối DB qua `localhost:5432` |
| Ứng dụng trợ lý AI ([../ai/README.md](../ai/README.md)) | Streamlit chạy trên máy từng người (Python 3.13), đọc `dds` qua `localhost:5432`; ảnh trợ lý AI trên header Power BI mở ứng dụng đúng trang và bộ lọc | http://localhost:8501 |
| LLM | Google Gemini qua Google AI Studio (gói miễn phí): `gemini-3.5-flash`, dự phòng `gemini-3.5-flash-lite` và Groq `llama-3.3-70b-versatile` (khi có key); gọi qua cổng tương thích OpenAI, key trong `.env` | Dịch vụ bên ngoài |
| Dashboard theo dõi ETL ([../monitor/README.md](../monitor/README.md)) | Streamlit chạy trên máy, phiên kết nối chỉ đọc `etl_log` và `dq` | http://localhost:8502 |

Hai container khai báo chung trong `compose.yaml` (Docker Compose, project `bi-miniproject`) → cả nhóm dựng cùng một môi trường bằng `docker compose up -d --build`.
Hướng dẫn chạy từng bước: [setup_guide.md](setup_guide.md).

## 3. Luồng dữ liệu (Hình 4.2)

![Luồng dữ liệu](images/data_flow.png)

### 3.1. Đối chiếu Single DDS → đồ án

| Thành phần Single DDS | Trong đồ án | Chi tiết | Trạng thái (16/11/2026) |
|---|---|---|---|
| Source System | 10 batch CSV trong `data/batches/` | [../data/batches/README.md](../data/batches/README.md) | ✅ Script chia batch xong, tự kiểm tra 9/9 PASS |
| Stage ETL | Pipeline Mage: kiểm tra → MERGE vào `staging` (Full Load / Incremental Load), xóa mềm; cuối mỗi lần chạy gọi dbt (BS-34) | [pipeline_rules.md](pipeline_rules.md), [decisions.md](decisions.md) D1–D8, [../mage/README.md](../mage/README.md) | ✅ Pipeline `full_load` + `incremental_load` xong (BS-21 → BS-24); chạy đủ 9 kịch bản kiểm thử, nạp hết 10 batch khớp 100% `data/raw/`. ✅ Nối dbt vào pipeline (BS-34): 1 lần chạy = CSV → `staging` → `dds`, LSET chỉ tiến khi dbt xong. ✅ Lập lịch (Seminar 3): 2 trigger cho `incremental_load` (5 phút một lần khi demo, hằng tháng khi vận hành), kiểm thử T1–T8 đạt ([schedule_rules.md](schedule_rules.md)) |
| Stage | Schema `staging`: 8 bảng giữ nguyên cấu trúc CSV + `_batch_id`, `_loaded_at` | [data_dictionary.md](data_dictionary.md) | ✅ Đã tạo bảng (`sql/init/01_staging_tables.sql`) |
| DDS ETL + DQ | dbt: model `stg_` → `int_` → `dim_` / `fact_`, seed, dbt test | [source_to_target_mapping.md](source_to_target_mapping.md), [dbt_rules.md](dbt_rules.md), [../dbt/README.md](../dbt/README.md) | ✅ Ánh xạ xong (BS-15); 20 model + 155 dbt test xong (BS-28 → BS-31); đạt đủ 6 kịch bản kiểm thử B7, kể cả nạp từng batch ([../dbt/README.md](../dbt/README.md) mục 4) |
| DDS | Schema `dds`: 3 fact + 6 dim, lược đồ Galaxy | [dw_design.md](dw_design.md) | ✅ Thiết kế xong; dbt dựng đủ 9 bảng, số liệu khớp nghiệm thu (`sql/checks/02_dds_checks.sql`) |
| Control + Audit | Schema `etl_log`: `pipeline_run`, `table_load`, `quality_check`, `dbt_result`; 3 view `v_run`, `v_batch_progress`, `v_quality_issue` | `sql/init/02_etl_log.sql`, `05_dbt_log.sql`, `06_etl_monitor.sql`, [../mage/README.md](../mage/README.md) mục Ghi log, [../monitor/README.md](../monitor/README.md) | ✅ Mage ghi đủ 4 bảng ở mọi lần chạy (`dbt_result`: kết quả từng seed / model / test của bước dbt); Incremental đọc `pipeline_run` để lấy LSET. ✅ Dashboard theo dõi ETL (BS-54) đọc nhật ký qua 3 view; đối chiếu độc lập 1.989 / 1.989 số khớp |
| DQ database | Schema `dq`: dòng bị Mage loại (`rejected_rows`) + dòng vi phạm dbt test (`store_failures`) | [decisions.md](decisions.md) (bảng cuối, 19/10/2026), `sql/init/03_dq.sql` | ✅ Mage ghi dòng bị loại vào `rejected_rows`; dbt test lưu dòng vi phạm vào `dq` – mỗi test 1 bảng, 155 bảng (xem bằng `sql/checks/03_dbt_test_demo.sql`) |
| Metadata | dbt docs, data dictionary, ánh xạ nguồn → đích | [../dbt/README.md](../dbt/README.md) mục 7, [data_dictionary.md](data_dictionary.md), [source_to_target_mapping.md](source_to_target_mapping.md) | ✅ Tài liệu xong; dbt docs: trang mở đầu, mô tả mọi cột model / seed, macro, exposure Dashboard Power BI, ảnh lineage; mô tả ghi cả vào `COMMENT` của bảng / cột trong Postgres |
| MDB | Semantic model trong Power BI (quan hệ, DAX, hierarchy) | [../powerbi/README.md](../powerbi/README.md), [semantic_model.md](semantic_model.md) | ✅ 16 quan hệ (1 quan hệ inactive cho ngày trả lời đánh giá), 5 hierarchy, 99 measure; nghiệm thu B6, B7 đạt |
| Application | Dashboard Power BI (3 trang); ứng dụng trợ lý AI (tóm tắt, giải thích biến động, hỏi đáp) | [../powerbi/README.md](../powerbi/README.md), [../ai/README.md](../ai/README.md), [generative_ai.md](generative_ai.md) | ✅ 3 trang Tổng quan, Giao hàng, Người bán và trang ẩn Chi tiết người bán trả lời Q1–Q6. ✅ Trợ lý AI dùng Gemini; số đầu vào của AI khớp dashboard 50 / 50, mọi con số trong câu trả lời được kiểm tự động |

### 3.2. Luồng chính

1. **Source → Stage ETL:** Mage đọc lần lượt từng batch. **Trước khi nạp**, kiểm tra cấu trúc (đủ, đúng cột) và chất lượng cơ bản (khóa không rỗng, không trùng).
   Lỗi nặng (VD thiếu cột) → dừng, lần chạy ghi `FAILED`; dòng hỏng lẻ → loại riêng, phần còn lại nạp tiếp.
2. **Stage ETL → Stage:** dữ liệu đạt được **MERGE theo khóa chính** vào `staging` – dòng mới thì thêm, dòng đã có thì cập nhật
   (phương án B – D8: đơn cũ được gửi lại ở batch sau với trạng thái mới). Đơn nguồn báo xóa (`deleted_orders.csv`) được **xóa mềm**
   (`_is_deleted = TRUE`), dbt bỏ qua khi dựng `dds`. Quy tắc chi tiết cho pipeline: [pipeline_rules.md](pipeline_rules.md).
3. **Stage → DDS ETL + DQ → DDS:** dbt đọc `staging`, biến đổi qua 3 lớp `stg_` (làm sạch từng bảng) → `int_` (tích hợp, tính toán dùng chung)
   → `dim_` / `fact_` (bảng trong `dds`); seed bổ sung vùng của bang và bản dịch 2 danh mục còn thiếu; dbt test kiểm tra kết quả.
   dbt chạy **ngay trong lần chạy Mage**, sau khi `staging` đã commit (block `dbt_build`, Full Load thêm `--full-refresh`); chỉ khi dbt xong lần chạy mới ghi `SUCCESS`
   → LSET chỉ tiến khi batch đã vào tới `dds` ([pipeline_rules.md](pipeline_rules.md) B12).
4. **DDS → Application:** 2 nhánh như mô hình –
   (a) Power BI kết nối `dds`, dựng semantic model (đóng vai MDB) rồi dashboard;
   (b) ứng dụng trợ lý AI tính lại số liệu của 12 biểu đồ bằng SQL trên `dds` theo đúng công thức DAX, gửi kèm prompt tới Gemini.
   AI không tự viết SQL, chỉ được lấy thêm số của biểu đồ khác qua công cụ `lay_so_lieu`; mọi con số trong câu trả lời được đối chiếu
   với dữ liệu AI đã nhận, nên AI chỉ nói dựa trên số đã tính và đối chiếu được với dashboard.
5. **Điều phối và giám sát (Seminar 3):** trigger của Mage chạy `incremental_load` theo lịch, mỗi lần đi trọn bước 1 → 3; dashboard theo dõi ETL
   đọc `etl_log` và `dq` để biết mỗi lần chạy thành công hay lỗi, lỗi ở khâu nào, kho đã nạp tới batch nào.

### 3.3. Ba vùng hỗ trợ

| Vùng | Lưu gì | Dùng để |
|---|---|---|
| **Control + Audit** (`etl_log`) | Thông tin **về** mỗi lần chạy: trạng thái, khoảng dữ liệu (`lset`, `cet`), số dòng đọc / thêm / cập nhật / loại, kết quả từng phép kiểm tra, kết quả từng seed / model / test của bước dbt | **Audit**: biết pipeline chạy ổn không (dashboard theo dõi ETL dựng từ đây). **Control**: Incremental đọc lần chạy thành công gần nhất để chọn batch kế tiếp → chạy lại được |
| **DQ database** (`dq`) | **Chính các dòng dữ liệu lỗi**, giữ nguyên nội dung + lý do, từ 2 điểm kiểm tra (Mage, dbt test) | Người phụ trách xem dòng nào hỏng để sửa nguồn rồi nạp lại. `etl_log` chỉ **đếm**, không giữ nội dung |
| **Metadata** | dbt docs (tự sinh: mô tả model, cột, test, sơ đồ lineage) + `data_dictionary.md`, `source_to_target_mapping.md` (nhóm viết) | Hiểu ý nghĩa dữ liệu, biết bảng nào được làm từ bảng nào |

## 4. Câu hỏi hay gặp khi trình bày

| Câu hỏi | Trả lời ngắn |
|---|---|
| Sao không đưa CSV thẳng vào Power BI? | (1) 9 bảng rời, dữ liệu bẩn – nối sai là doanh thu bị nhân lên (1 đơn nhiều sản phẩm × nhiều lần thanh toán); (2) làm sạch + test **một lần** ở dbt, mọi báo cáo dùng chung; (3) dữ liệu đến theo đợt → cần nạp thêm (incremental) và ghi lịch sử mỗi lần nạp |
| Mage khác dbt chỗ nào? | Mage chuyển dữ liệu **từ ngoài vào** database (E, L); dbt biến đổi dữ liệu **bên trong** database (T) – dbt không tự đọc file CSV |
| Mage và dbt nối với nhau thế nào? | Trong cùng 1 lần chạy: Mage nạp `staging` (commit) → block `dbt_build` gọi `dbt build` → dbt xong mới ghi `SUCCESS` (chốt LSET). dbt lỗi thì lần chạy `FAILED`, LSET đứng yên, lần sau nạp lại đúng batch đó (MERGE ra 0/0) rồi chạy dbt lại. Lập lịch (Seminar 3) chỉ gắn trigger cho pipeline `incremental_load` là cả luồng chạy, không sửa code pipeline |
| Mage kiểm tra chất lượng khác dbt test chỗ nào? | Mage kiểm tra **trước khi nạp** `staging` (đủ file, đúng cột, khóa không rỗng / không trùng, đúng kiểu dữ liệu) và loại dòng hỏng; dbt test kiểm tra **sau khi biến đổi**, chỉ phát hiện chứ không xóa dòng sai |
| `etl_log` khác `dq` chỗ nào? | `etl_log` ghi **về** lần chạy (con số, trạng thái); `dq` giữ **chính dòng dữ liệu lỗi** |
| dbt `store_failures` có thay được `rejected_rows` không? | Không – dòng Mage loại không bao giờ vào database nên dbt không thấy; `store_failures` còn ghi đè mỗi lần chạy, không giữ lịch sử |
| Xóa một đơn ở nguồn rồi chạy Incremental thì sao? | Incremental chỉ thấy dòng **có mặt** trong batch, không thể coi "vắng mặt" là "bị xóa" (mỗi batch chỉ là một phần dữ liệu). Nên nguồn phải **báo xóa** bằng file `deleted_orders.csv`; Mage **xóa mềm** (`_is_deleted = TRUE`, giữ dấu vết, đếm vào `etl_log`); dbt bỏ đơn đó khi dựng `dds` → biến mất khỏi dashboard. Olist thật không xóa đơn – đơn hủy là đổi trạng thái `canceled`, tức nguồn đã dùng soft delete (slide 53) |
| Sao chọn Single DDS? | 1 nguồn, dữ liệu nhỏ, xử lý theo lô, câu hỏi chỉ cần mô hình đa chiều → không cần NDS / ODS |
| Sao không dùng Copilot trong Power BI? | Copilot cần Fabric capacity trả phí; nhóm dùng ứng dụng Streamlit đi kèm Power BI và Gemini gói miễn phí, dữ liệu gửi đi chỉ là số đã tổng hợp từ bộ dữ liệu công khai |
| Làm sao biết AI không bịa số? | AI chỉ nhận số tính sẵn từ `dds` (khớp dashboard), không tự viết SQL; `ai/kiem_so.py` đối chiếu từng con số trong câu trả lời và tô cam số không tìm thấy; mỗi lần hỏi lưu log trong `ai/outputs/` |
