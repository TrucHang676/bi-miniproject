# Hướng dẫn cài đặt & chạy hệ thống

> Dành cho thành viên nhóm và người chấm muốn dựng lại hệ thống trên máy mình.
> Không cần biết trước Docker – làm lần lượt từ mục 3, mỗi bước đều có "kết quả đúng" để tự kiểm tra.
> Toàn bộ lệnh chạy trong terminal (PowerShell hoặc Git Bash) **tại thư mục gốc repo** `bi-miniproject/`.

## 1. Tổng quan môi trường

Cả hệ thống (trừ Power BI) chạy trong **Docker**, nên **không cần cài PostgreSQL, Mage, dbt hay Python lên Windows**.

```
Máy Windows                                   Docker Desktop
───────────────────────                       ──────────────────────────────────────────
VS Code ── sửa file trong repo ────────────►  olist-mage    Mage 0.9.79 + dbt 1.8.7
                                                 │  thấy cả repo tại /home/src
Trình duyệt ── http://localhost:6789 ───────►    │
                                                 │  gọi DB bằng tên "postgres", cổng 5432
DBeaver / Power BI ── localhost:5432 ───────►  olist-postgres  PostgreSQL 17
                                                    dữ liệu cất trong volume bi-miniproject_pgdata
```

Ba khái niệm cần nắm:

| Khái niệm | Ví dụ đời thường | Trong đồ án |
|---|---|---|
| **Image** | Khuôn bánh – công thức đóng gói sẵn phần mềm | `postgres:17`, `bi-miniproject-mage` (dựng từ `docker/Dockerfile`) |
| **Container** | Cái bánh đổ ra từ khuôn – phần mềm đang chạy | `olist-postgres`, `olist-mage` |
| **Volume** | Tủ lạnh riêng – cất dữ liệu, tắt/xóa container vẫn còn | `bi-miniproject_pgdata` (dữ liệu PostgreSQL) |

Các file cấu hình môi trường:

| File | Vai trò | Commit? |
|---|---|---|
| `compose.yaml` | "Thực đơn": cần 2 container nào, mở cổng nào, cất dữ liệu ở đâu | ✅ |
| `docker/Dockerfile` | Dựng image Mage cho đồ án (ghim Mage 0.9.79, dbt-postgres 1.8.2) | ✅ |
| `.env.example` | Mẫu thông tin kết nối DB – copy thành `.env` | ✅ |
| `.env` | Thông tin kết nối DB thật (có mật khẩu) – mỗi người tự tạo | ❌ (bị `.gitignore` chặn) |
| `sql/init/*.sql` | Script tạo schema + bảng – Postgres **tự chạy** lần đầu dựng DB (mục 5) | ✅ |
| `mage/olist_etl/io_config.yaml` | Cách Mage kết nối Postgres – đọc giá trị từ `.env`, không chứa mật khẩu | ✅ |
| `dbt/profiles.yml.example` | Mẫu cách dbt kết nối Postgres – copy thành `dbt/profiles.yml` (mục 6.3), cũng đọc giá trị từ `.env` | ✅ |
| `dbt/profiles.yml` | Bản thật của file trên – mỗi người tự tạo | ❌ (bị `.gitignore` chặn) |

## 2. Yêu cầu phần mềm

**Cài trên Windows:**

| Phần mềm | Phiên bản nhóm dùng | Ghi chú |
|----------|---------------------|---------|
| Docker Desktop (WSL2) | Docker 29.8, Compose v5.5 | Bản mới hơn vẫn được. Cần ~10 GB ổ trống cho image |
| Git | bất kỳ | Để clone repo |
| DBeaver (tùy chọn) | bất kỳ | Xem dữ liệu trong DB |
| Power BI Desktop | bản mới | Dùng ở Seminar 2 |
| Python + pandas (tùy chọn) | 3.10 trở lên | Chỉ để chạy script phụ trợ trong `scripts/` (profiling, chia batch) |

**Có sẵn trong container – không cài tay:**

| Thành phần | Phiên bản | Nằm ở |
|---|---|---|
| PostgreSQL | 17 (17.11) | `olist-postgres` |
| Mage.ai | 0.9.79 | `olist-mage` |
| dbt-core / dbt-postgres | 1.8.7 / 1.8.2 | `olist-mage` |

> Vì sao ghim Mage 0.9.79 thay vì `latest`? `latest` trên Docker Hub thay đổi theo thời gian – mỗi máy tải về một lúc sẽ ra bản khác nhau và dễ lỗi khó đoán. 0.9.79 là bản demo của lớp đã chạy được.

## 3. Cài đặt lần đầu

### 3.1. Lấy code

```powershell
git clone https://github.com/TrucHang676/bi-miniproject.git
cd bi-miniproject
```

Dữ liệu gốc Olist (9 file CSV) **đã có sẵn** trong `data/raw/` – không cần tải từ Kaggle.

### 3.2. Tạo file `.env`

Copy file mẫu thành file thật:

```powershell
Copy-Item .env.example .env      # PowerShell
# hoặc: cp .env.example .env     # Git Bash / macOS
```

Mở `.env`, đổi `change_me` thành mật khẩu tùy ý (nhớ lại để dùng cho DBeaver / Power BI):

```env
POSTGRES_DB=olist_dw          # tên database
POSTGRES_USER=olist_user      # user đăng nhập
POSTGRES_PASSWORD=change_me   # ← đổi chỗ này
POSTGRES_HOST=postgres        # giữ nguyên
POSTGRES_PORT=5432            # giữ nguyên
```

> **Vì sao `POSTGRES_HOST=postgres` chứ không phải `localhost`?** Bên trong Docker, các container gọi nhau bằng **tên service** trong `compose.yaml` (giống gọi tên phòng trong cùng một nhà). Biến này dành cho Mage. Còn từ Windows (DBeaver, Power BI) thì vẫn kết nối bằng `localhost`.

⚠ Đặt mật khẩu **trước** lần chạy đầu tiên. Postgres chỉ đọc 3 biến `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` **lúc tạo database lần đầu** – đổi sau đó sẽ không có tác dụng (cách xử lý ở mục 7).

### 3.3. Mở Docker Desktop

1. Mở **Docker Desktop**, đợi góc dưới bên trái hiện **Engine running**.
2. Đảm bảo không có chương trình nào khác đang chiếm cổng **5432** (PostgreSQL) và **6789** (Mage). Hay gặp nhất là bản **demo Mage của lớp** – tắt nó đi (chỉ tắt, không mất dữ liệu demo):

   ```powershell
   docker ps                              # xem container nào đang chạy
   docker stop lab-postgres lab-mage      # nếu thấy container của demo lớp
   ```

### 3.4. Bật hệ thống

```powershell
docker compose up -d --build
```

| Phần lệnh | Ý nghĩa |
|---|---|
| `up` | Tạo và bật các container ghi trong `compose.yaml` |
| `-d` | Chạy nền – terminal được trả lại ngay, đóng terminal container vẫn chạy |
| `--build` | Dựng image Mage từ `docker/Dockerfile` trước khi bật |

⏳ Lần đầu Docker phải tải image Mage (vài GB) – có thể mất 5–20 phút tùy mạng. Những lần sau bật chỉ mất vài giây.

### 3.5. Kiểm tra container đã chạy

```powershell
docker compose ps
```

Kết quả đúng:

| NAME | STATUS |
|---|---|
| `olist-mage` | `Up ...` |
| `olist-postgres` | `Up ... (healthy)` |

Nếu Postgres đang `(health: starting)` thì đợi ~10 giây rồi chạy lại lệnh. Mage chỉ bật sau khi Postgres `healthy`.

Xem Mage khởi động xong chưa:

```powershell
docker compose logs -f mage
```

Đợi đến khi thấy dòng **`Mage is running at http://localhost:6789 and serving project /home/src/mage/olist_etl`**, rồi bấm **Ctrl + C** để thoát màn hình log (container vẫn chạy).

> Sau đó log sẽ lặp mãi các dòng `Scheduler status: running` / `Active pipeline runs: []` – đây là bộ hẹn giờ của Mage báo "vẫn chạy, chưa có pipeline nào cần chạy", **không phải lỗi**.

## 4. Kiểm tra kết nối

Làm cả 3 mục dưới đây để chắc môi trường đã thông suốt: **Mage ↔ Postgres**, **Windows ↔ Postgres**, **dbt**.

### 4.1. Giao diện Mage

1. Mở trình duyệt: **http://localhost:6789**
2. Đăng nhập bằng tài khoản mặc định của Mage:
   - Email: `admin@admin.com`
   - Password: `admin`
3. Kết quả đúng: góc trên bên trái hiện **`olist_etl`** và phiên bản **v0.9.79**. (Nếu thấy `lab_project` là đang vào nhầm Mage của demo lớp.)

⚠ **Không bấm nút vàng `Update`** ở góc trên – nhóm đã ghim bản 0.9.79.

### 4.2. Mage → Postgres (tùy chọn)

Muốn tự kiểm tra Mage đọc được DB:

1. **Pipelines** → **+ New** → **Standard (batch)** → đặt tên `test_connection` → **Create**.
2. **Data loader** → **Python** → **PostgreSQL**.
3. Trong code của block, sửa dòng `query = 'your PostgreSQL query'` thành:

   ```python
   query = 'SELECT version(), current_database(), current_user'
   ```

4. Bấm ▶ (hoặc **Ctrl + Enter**). Kết quả đúng: bảng 1 dòng có **PostgreSQL 17.x**.
5. Thử xong **xóa pipeline này** (không commit): xóa thư mục `mage/olist_etl/pipelines/test_connection/` và file block vừa tạo trong `mage/olist_etl/data_loaders/`.

> Hai cột `current_database`, `current_user` hiện `********` là **bình thường**: Mage tự che mọi giá trị trùng với biến môi trường bí mật trong `.env` (8 dấu sao = `olist_dw`, 10 dấu sao = `olist_user`).

### 4.3. Windows → Postgres bằng DBeaver

1. DBeaver → 🔌+ **New Database Connection** → **PostgreSQL** → **Next**.
2. Điền:

   | Ô | Giá trị |
   |---|---|
   | Host | `localhost` |
   | Port | `5432` |
   | Database | `olist_dw` |
   | Username | `olist_user` |
   | Password | mật khẩu trong `.env` |

3. **Test Connection** (lần đầu DBeaver hỏi tải driver → **Download**). Kết quả đúng: **Connected**, server **PostgreSQL 17.x**.
4. **Finish**. Nên đổi tên kết nối thành `olist_dw (Docker)` cho dễ phân biệt.

Mở `olist_dw` → **Schemas**: có `dds` (trống – dbt tạo bảng sau), `etl_log` (3 bảng), `public` (trống), `staging` (8 bảng). Các bảng này do script khởi tạo tạo sẵn (mục 5), lúc mới dựng chưa có dòng dữ liệu nào.

### 4.4. dbt

dbt nằm sẵn trong container Mage – chạy bằng `docker compose exec mage ...` ("thò tay vào hộp `mage` để dùng đồ trong đó"):

```powershell
docker compose exec mage dbt --version
```

Kết quả đúng: `Core: installed: 1.8.7` và trong *Plugins* có `postgres: 1.8.2`. Các dòng `Update available` / `Not compatible` (mysql, mariadb, …) **bỏ qua** – đồ án chỉ dùng plugin postgres.

## 5. Khởi tạo Data Warehouse

**Không cần chạy tay gì cả.** Lần đầu `docker compose up` (mục 3.4), Postgres **tự chạy** 7 script trong `sql/init/` theo thứ tự tên file:

| File | Tạo gì |
|---|---|
| `00_schemas.sql` | 4 schema `staging`, `etl_log`, `dq`, `dds` · extension `unaccent` (bỏ dấu tên thành phố) · múi giờ DB = giờ Việt Nam |
| `01_staging_tables.sql` | 8 bảng `staging`: tên cột giữ như CSV, kiểu theo [data_dictionary.md](data_dictionary.md), khóa chính theo D1 ([decisions.md](decisions.md)), thêm 2 cột kỹ thuật `_batch_id`, `_loaded_at` |
| `02_etl_log.sql` | 3 bảng nhật ký ETL: `pipeline_run` (1 lần chạy) → `table_load` (từng bảng: số dòng thêm / cập nhật / bị loại) và `quality_check` (từng phép kiểm tra chất lượng) |
| `03_dq.sql` | Bảng `dq.rejected_rows`: **nguyên nội dung** từng dòng Mage loại (dạng JSON) + lần chạy, phép kiểm tra, lý do – khóa ngoại về `etl_log.quality_check` |
| `04_soft_delete.sql` | Xóa mềm đơn bị xóa ở nguồn: thêm cột `_is_deleted`, `_deleted_at` vào `staging.orders` và `rows_deleted` vào `etl_log.table_load` (viết dạng `ALTER ... ADD COLUMN IF NOT EXISTS`) – cách dùng: [pipeline_rules.md](pipeline_rules.md) B6 |
| `05_dbt_log.sql` | Bảng `etl_log.dbt_result`: kết quả từng seed / model / test của bước dbt mà pipeline Mage gọi sau khi nạp staging (BS-34) – [pipeline_rules.md](pipeline_rules.md) B12 |
| `06_etl_monitor.sql` | 3 **view** trong `etl_log` cho dashboard theo dõi ETL (BS-54): `v_run` (1 dòng = 1 lần chạy + tổng hợp số dòng, kiểm tra chất lượng, dbt, thời gian từng khâu), `v_batch_progress` (tiến độ 10 batch theo từng lượt nạp), `v_quality_issue` (mọi phép kiểm tra WARN / FAIL + dbt test không đạt). Không tạo bảng, không lưu dữ liệu – [monitor/README.md](../monitor/README.md) |

Database sau khi khởi tạo:

```
olist_dw
├── staging   8 bảng  – Mage nạp CSV vào (orders, order_items, order_payments, order_reviews,
│                       customers, sellers, products, category_translation)
├── etl_log   4 bảng  – Mage ghi nhật ký mỗi lần chạy (pipeline_run, table_load, quality_check, dbt_result)
│             3 view  – v_run, v_batch_progress, v_quality_issue (dashboard theo dõi ETL)
├── dq        1 bảng  – dòng dữ liệu lỗi Mage loại (rejected_rows); dbt test ghi thêm bảng khi bật store_failures
├── dds       trống   – dbt tạo dim / fact
└── public    trống
```

Vai trò từng schema theo kiến trúc Single DDS: [architecture.md](architecture.md).

**Cơ chế:** `compose.yaml` gắn thư mục `sql/init/` vào thư mục khởi tạo `/docker-entrypoint-initdb.d` của image Postgres. Lần đầu tạo DB, Postgres chạy mọi file `.sql` trong đó (vì vậy tên file đánh số `00` → `06` để chạy đúng thứ tự).

⚠ Postgres **chỉ tự chạy khi volume dữ liệu còn trống** (lần dựng đầu tiên, hoặc sau `docker compose down -v`). Những lần `up` sau, script **không** chạy lại.

### 5.1. Kiểm tra DB đã khởi tạo đủ

```powershell
docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/checks/00_check_init.sql
```

Kết quả đúng: 23 dòng, cột `ket_qua` **đều là `PASS`** (4 schema, `unaccent`, encoding UTF8, múi giờ, 13 bảng đủ cột và có khóa chính, 3 view của dashboard ETL). Dòng nào `FAIL` thì cột `thuc_te` cho biết thiếu gì – VD dòng `etl_log.dbt_result` báo `0/12 cột` nghĩa là DB tạo trước khi repo có `05_dbt_log.sql` (BS-34); 3 dòng `etl_log.v_*` FAIL nghĩa là chưa có `06_etl_monitor.sql` (BS-54) → chạy tay file đó theo mục 5.2.

> `compose.yaml` gắn cả thư mục `sql/` của repo vào container tại `/sql` (chỉ đọc), nên file SQL nào trong repo cũng chạy được bằng `psql -f /sql/<đường dẫn>`. Có thể chạy trong DBeaver thay thế: dán cả file vào SQL Editor rồi Ctrl + Enter.

### 5.2. Khi sửa file trong `sql/init/`

| Thay đổi | Cách áp dụng | Mất dữ liệu? |
|---|---|---|
| Thêm / sửa **view** (`06_etl_monitor.sql`) | Chạy lại đúng file đó như dòng dưới – file tự `DROP VIEW` rồi tạo lại | Không (view không lưu dữ liệu) |
| Thêm **bảng mới** / schema mới | Chạy lại đúng file đó: `docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/init/<tên file>` (các lệnh dùng `IF NOT EXISTS` nên phần đã có được bỏ qua) | Không |
| **Thêm cột** vào bảng đã có | Viết thành **file mới** dạng `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (như `04_soft_delete.sql`) rồi chạy tay file đó như dòng trên – DB mới cũng tự chạy file này | Không |
| Sửa **bảng đã có** (đổi / xóa cột, đổi kiểu) | `IF NOT EXISTS` sẽ **bỏ qua** bảng đã tồn tại → dựng lại DB: `docker compose down -v` rồi `docker compose up -d` | **Có** – nạp lại bằng pipeline |

Sửa xong nhớ chạy lại mục 5.1, và sửa số cột mong đợi trong `sql/checks/00_check_init.sql` nếu đổi số cột.

## 6. Chạy pipeline

### 6.1. Sinh batch dữ liệu (làm 1 lần, trước khi chạy Mage)

Dữ liệu Kaggle là ảnh chụp cuối cùng (đã biết hết 09/2016 → 10/2018). Để mô phỏng dữ liệu "về dần" cho Full Load + Incremental Load, script cắt nó thành 10 batch theo tháng – mỗi batch chỉ chứa những gì **đã xảy ra trước cuối tháng đó**; đơn cũ có thay đổi (VD vừa được giao) được gửi lại ở batch sau (D8 trong [decisions.md](decisions.md)).

```powershell
docker compose exec mage python scripts/split_batches.py
```

- Chạy bên trong container Mage nên **không cần cài Python** trên Windows (có Python + pandas thì `py scripts/split_batches.py` cũng được – kết quả giống hệt).
- Mất ~15 giây. Kết quả đúng: dòng cuối **`TẤT CẢ ĐẠT (9/9 PASS)`** – script tự đọc lại file, phát lại 10 batch và kiểm tra khớp 100% file gốc.
- Sinh ra `data/batches/FULL/`, `2018-01/` … `2018-08/`, `2018-09+/` (mỗi thư mục 1 file CSV / bảng) + `manifest.csv` (thứ tự chạy, số dòng mong đợi). Các file này **không commit** – mỗi máy tự sinh. Định dạng chi tiết: [data/batches/README.md](../data/batches/README.md).
- Chạy lại lúc nào cũng được (xóa batch cũ, ghi lại y hệt).

### 6.2. Data Ingestion (Mage.ai)

> Chi tiết các block và cơ chế: [mage/README.md](../mage/README.md); quy tắc: [pipeline_rules.md](pipeline_rules.md).
> **Từ 24/10/2026 (BS-34) mỗi lần chạy pipeline gồm cả bước dbt**: Mage nạp `staging` xong thì tự gọi `dbt build` dựng `dds`. Vì vậy máy phải làm xong phần **"Lần đầu trên mỗi máy" của mục 6.3** (có `dbt/profiles.yml`, đã `dbt deps`) **trước** khi chạy pipeline – thiếu thì block `dbt_build` báo lỗi đỏ.

1. Mở Mage tại `http://localhost:6789` → **Pipelines**.
2. **Full Load** (chạy trước, 1 lần): `full_load` → **Triggers** → **Run@once** → **Run now** → thẻ **Runs** đợi `completed` (~1 phút: nạp staging rồi `dbt build --full-refresh`).
3. **Incremental Load**: `incremental_load` → **Triggers** → **Run@once** → **Run now**. Mỗi lần chạy nạp **1** batch kế tiếp (2018-01 → … → 2018-09+) rồi `dbt build` cập nhật `dds`; nạp hết = chạy 9 lần, chạy thêm thì báo "đã nạp hết batch".
   - Chạy lại batch vừa nạp: trong hộp **Run@once** đổi biến `rerun_last` thành `true`.
   - Không bấm ▶ trên từng block để chạy lại: block nhận output cũ của block trước nên sẽ dừng với lỗi `StaleRunError` (cố ý chặn để không ghi đè lần chạy cũ).
   - Log của dbt (dòng `1 of 177 START …` → `Done. PASS=177 …`) xem ở log của block `dbt_build` / `dbt_build_full` trong thẻ **Runs**.
4. Kiểm tra kết quả: mở [`sql/checks/01_pipeline_demo.sql`](../sql/checks/01_pipeline_demo.sql) trong DBeaver – Q1 các lần chạy, Q2 từng bảng, Q3 kiểm tra chất lượng, Q4 dòng bị loại, Q5 số dòng staging (có ghi sẵn số mong đợi), Q6 bước dbt của từng lần chạy, Q7 số dòng 9 bảng `dds` + node dbt lỗi của 1 lần chạy. Đối soát số liệu `dds`: `sql/checks/02_dds_checks.sql`.

Không mở giao diện cũng chạy được: `docker compose exec mage mage run /home/src/mage/olist_etl full_load` (thay `incremental_load` cho Incremental).

**Nạp 9 batch tự động theo lịch** (Seminar 3 – thay cho bấm Run@once 9 lần): chạy `full_load` tay như bước 2 → `incremental_load` → **Triggers** → bật `incremental_demo` → cứ 5 phút Mage tự nạp 1 batch (~45 phút hết 9 batch; xem tiến độ bằng Q8 trong `01_pipeline_demo.sql`) → nạp hết thì **tắt** trigger. Trong lúc trigger bật **không** bấm Run@once và không gõ `dbt` (sẽ chạy chồng). Sau khi bật / tắt, `git status` thấy `triggers.yaml` đổi thì **không commit** (`git restore` file). Chi tiết: [mage/README.md](../mage/README.md) mục "Lập lịch".

⚠ Chạy lại `full_load` sau khi đã nạp vài batch = làm lại từ đầu: staging chỉ còn batch FULL, Incremental kế tiếp nạp lại từ 2018-01.

### 6.3. Transformation (dbt)

> Chi tiết project (tầng model, schema đích, việc còn lại): [dbt/README.md](../dbt/README.md). dbt chạy **bên trong container Mage** (mục 4.4); project nằm ở `dbt/` của repo, trong container là `/home/src/dbt` – `compose.yaml` đã trỏ sẵn tới đó nên gõ lệnh ở thư mục gốc repo.

**Lần đầu trên mỗi máy:**

```powershell
Copy-Item dbt\profiles.yml.example dbt\profiles.yml   # giống .env: file thật bị .gitignore, nhưng không chứa mật khẩu
docker compose up -d                                   # nạp biến DBT_PROJECT_DIR, DBT_PROFILES_DIR vào container Mage
docker compose exec mage dbt deps                      # cài package dbt_utils
docker compose exec mage dbt debug                     # kết quả đúng: All checks passed!
```

**Khi nạp dữ liệu: không cần gõ gì** – từ 24/10/2026 (BS-34) pipeline Mage tự chạy `dbt build` ngay sau khi nạp `staging` (mục 6.2): `full_load` chạy `dbt build --full-refresh`, `incremental_load` chạy `dbt build`. dbt lỗi thì lần chạy ghi `FAILED` và LSET không tiến; kết quả từng seed / model / test nằm ở `etl_log.dbt_result`.

**Chạy tay** (khi sửa model, gỡ lỗi – không chạy trong lúc pipeline Mage đang chạy):

```powershell
docker compose exec mage dbt build      # seed -> model -> test, dbt tự xếp đúng thứ tự
```

- Dim / fact nằm trong schema `dds`; view trung gian của dbt nằm ở `dbt_stg`, `dbt_int`; dòng vi phạm dbt test nằm ở `dq`.
- Kiểm tra kết quả bằng DBeaver: `sql/checks/02_dds_checks.sql` (số liệu `dds`, có số mong đợi); test FAIL thì `sql/checks/03_dbt_test_demo.sql` câu Q1 liệt kê test nào đang có dòng vi phạm.
- Chạy tay sau khi Full Load làm lại staging từ đầu thì thêm `--full-refresh` (pipeline `full_load` đã tự làm).
- Tài liệu dbt: `docker compose exec mage dbt docs generate --static` → mở `dbt/target/static_index.html` bằng trình duyệt.

### 6.4. Power BI

1. Mở `powerbi/[tên].pbix`.
2. Kết nối PostgreSQL: Server `localhost`, Database `olist_dw`, user/mật khẩu như `.env` (nếu báo lỗi SSL xem mục 8).
3. Nhấn **Refresh**.

### 6.5. Thành phần AI

App Trợ lý AI chạy trên máy (`localhost:8501`), cần Postgres đang chạy và key Gemini miễn phí trong `.env`.
Từng bước, cách dùng và lỗi thường gặp: [ai/HUONG_DAN_CHAY.md](../ai/HUONG_DAN_CHAY.md).

```powershell
python -m pip install -r ai/requirements.txt   # lần đầu
ai\chay_app.bat                                  # mỗi lần dùng (hoặc bấm đúp file này)
```

### 6.6. Dashboard theo dõi ETL

App Streamlit chạy trên máy (`localhost:8502`), chỉ **đọc** `etl_log` + `dq` qua 3 view của `06_etl_monitor.sql` (DB đã có từ trước BS-54 thì chạy tay file đó theo mục 5.2). Cách dùng, ý nghĩa từng biểu đồ, cách đọc số: [monitor/README.md](../monitor/README.md).

```powershell
py -m pip install -r monitor/requirements.txt    # lần đầu
monitor\chay_monitor.bat                          # mỗi lần dùng (hoặc bấm đúp file này)
```

Mở song song với lúc bật lịch `incremental_demo` (mục 6.2) và bật **Tự làm mới 30 giây** trên thanh bên → mỗi lần lịch chạy xong, dashboard tự hiện lần chạy mới.

## 7. Dùng hằng ngày

| Muốn… | Lệnh | Ghi chú |
|---|---|---|
| Bật hệ thống | `docker compose up -d` | Nhớ mở Docker Desktop trước |
| Tắt hệ thống | `docker compose down` | **Dữ liệu DB vẫn còn** (nằm trong volume) |
| Xem trạng thái | `docker compose ps` | |
| Xem log Mage / Postgres | `docker compose logs -f mage` / `docker compose logs -f postgres` | Ctrl + C để thoát |
| Khởi động lại Mage | `docker compose restart mage` | Khi Mage treo |
| Áp dụng thay đổi trong `.env` | `docker compose up -d` | `restart` **không** đọc lại `.env`; `up -d` tự tạo lại container có thay đổi. Riêng mật khẩu DB xem mục 8 |
| Dựng lại image Mage | `docker compose up -d --build` | **Chỉ cần** khi sửa `docker/Dockerfile` |
| Mở terminal trong container Mage | `docker compose exec mage bash` | Gõ `exit` để thoát |
| Mở `psql` trong container Postgres | `docker compose exec postgres psql -U olist_user -d olist_dw` | Gõ `\q` để thoát |
| Chạy 1 file SQL trong repo | `docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/<đường dẫn>` | VD `/sql/checks/00_check_init.sql` |
| ⚠ **Xóa sạch DB, làm lại từ đầu** | `docker compose down -v` rồi `docker compose up -d` | `-v` **xóa luôn volume** → mất toàn bộ dữ liệu trong DB; khi `up` lại, Postgres tự chạy `sql/init/` → schema + bảng rỗng như mới. Dữ liệu nạp lại được bằng cách chạy lại pipeline |

> Sửa file trong VS Code (pipeline Mage, model dbt, SQL) **không cần** khởi động lại gì – thư mục repo được gắn thẳng vào container (`.:/home/src` trong `compose.yaml`), Mage thấy thay đổi ngay. Ngược lại, pipeline tạo trên giao diện Mage cũng được lưu thẳng vào `mage/olist_etl/` để commit.

## 8. Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách khắc phục |
|-----|-------------|----------------|
| `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` | Docker Desktop chưa mở | Mở Docker Desktop, đợi **Engine running** rồi chạy lại lệnh |
| `Bind for 0.0.0.0:5432 failed: port is already allocated` hoặc `ports are not available` (cổng `5432` / `6789`) | Cổng đang bị chương trình khác chiếm – thường là demo Mage của lớp, hoặc PostgreSQL cài sẵn trên Windows | `docker ps` xem container nào chiếm cổng → `docker stop <tên>`. Nếu là PostgreSQL cài trên Windows: tắt service `postgresql-x64-…` trong *Services* |
| `yaml: line …` khi chạy `docker compose` | Thụt lề sai trong `compose.yaml` hoặc `io_config.yaml` | YAML chỉ dùng **dấu cách**, không dùng Tab; so lại thụt lề với bản trên GitHub |
| Đổi mật khẩu trong `.env` rồi nhưng đăng nhập DB báo `password authentication failed` | Postgres chỉ đọc mật khẩu trong `.env` **lúc tạo DB lần đầu** | Cách 1 (giữ dữ liệu): `docker compose exec postgres psql -U olist_user -d olist_dw -c "ALTER USER olist_user PASSWORD 'mật_khẩu_mới';"`. Cách 2 (mất dữ liệu): `docker compose down -v` rồi `docker compose up -d` |
| Pipeline Mage báo không tìm thấy `data/batches/...` | Chưa sinh batch (thư mục batch không lên GitHub) | Chạy mục 6.1 |
| `split_batches.py` kết thúc bằng `CÓ ... KIỂM TRA KHÔNG ĐẠT` | File trong `data/raw/` bị sửa / thiếu, hoặc script bị sửa sai | Xem cột `chi_tiet` của dòng FAIL; khôi phục `data/raw/` bằng `git checkout -- data/raw` rồi chạy lại |
| Sửa file trong `sql/init/` nhưng DB không đổi | Postgres chỉ tự chạy `sql/init/` khi volume còn trống (lần đầu) | Xem mục 5.2 |
| `docker compose logs postgres` có `ERROR` ngay sau dòng `running /docker-entrypoint-initdb.d/...` và container dừng | Script khởi tạo bị lỗi → Postgres dừng giữa chừng | Sửa file SQL bị báo lỗi, rồi `docker compose down -v` và `docker compose up -d` để chạy lại từ đầu |
| Mage hiện project `lab_project` | Đang vào Mage của demo lớp (cùng cổng 6789) | `docker stop lab-mage lab-postgres`, rồi `docker compose up -d` trong repo đồ án |
| Kết quả block Mage hiện `********` | Mage che giá trị trùng biến bí mật trong `.env` | Bình thường, không phải lỗi |
| Power BI báo lỗi chứng chỉ SSL khi kết nối PostgreSQL | Postgres chạy Docker không có chứng chỉ SSL hợp lệ | *File → Options and settings → Data source settings* → chọn nguồn → *Edit Permissions* → bỏ tick **Encrypt connections** |
| DBeaver báo `invalid value for parameter "TimeZone": "Asia/Saigon"` | Java gửi tên múi giờ cũ mà Postgres không nhận | Thêm dòng `-Duser.timezone=Asia/Ho_Chi_Minh` vào cuối `%LOCALAPPDATA%\DBeaver\dbeaver.ini`, mở lại DBeaver |
| dbt báo `No dbt_project.yml found at expected path /home/src/dbt_project.yml` | Container Mage tạo từ `compose.yaml` cũ, chưa có biến `DBT_PROJECT_DIR` | `docker compose up -d` (tự tạo lại container Mage) |
| dbt báo `Could not find profile named 'olist_dw'` (riêng `dbt debug` báo `profiles.yml file [ERROR not found]`) | Chưa có `dbt/profiles.yml` | `Copy-Item dbt\profiles.yml.example dbt\profiles.yml` (mục 6.3) |
| dbt báo `dbt found 1 package(s) specified in packages.yml, but only 0 package(s) installed` | Chưa cài package (thư mục `dbt/dbt_packages/` không lên GitHub) | `docker compose exec mage dbt deps` |
| `dbt build` báo `could not resize shared memory segment … No space left on device` (lúc có lúc không) | Container Postgres tạo trước khi `compose.yaml` có `shm_size: 256mb` – vẫn dùng 64 MB `/dev/shm` mặc định của Docker | `docker compose up -d` (tự tạo lại container, dữ liệu trong volume giữ nguyên); kiểm tra `docker compose exec postgres df -h /dev/shm` ra `256M` |
| Gõ trong **Git Bash**: `mage run /home/src/mage/olist_etl full_load` báo `Pipeline full_load does not exist in repo_path /home/src/C:/Program Files/Git/home/src/...` | Git Bash tự đổi tham số dạng `/home/...` thành đường dẫn Windows trước khi gửi vào container | Chạy lệnh trong **PowerShell**, hoặc thêm `MSYS_NO_PATHCONV=1` trước lệnh: `MSYS_NO_PATHCONV=1 docker compose exec mage mage run /home/src/mage/olist_etl full_load` |
| Pipeline Mage đỏ ở block `dbt_build` / `dbt_build_full` | Bước dbt báo lỗi: model lỗi, dbt test FAIL, hoặc dbt không chạy được (thiếu `profiles.yml` / package, thiếu bộ nhớ dùng chung…) | Đọc `error_message` của lần chạy (`01_pipeline_demo.sql` Q1) hoặc log của block. Lỗi môi trường → sửa theo các dòng dbt ở trên. Test FAIL → `error_message` có tên bảng `dq` chứa dòng vi phạm (`03_dbt_test_demo.sql`), sửa dữ liệu. Xong thì **Run@once** lại: Incremental tự nạp lại đúng batch đó (0 INSERT / 0 UPDATE) rồi chạy dbt |
| `incremental_load` báo `Full Load run_id … đã làm lại staging từ đầu nhưng chưa xong` | Lần Full Load gần nhất lỗi ở bước dbt (hoặc bị ngắt sau khi nạp staging): staging đã làm lại từ đầu nhưng `dds` chưa dựng xong, LSET cũ không còn đúng | Sửa lỗi dbt rồi chạy lại `full_load` ([pipeline_rules.md](pipeline_rules.md) B12) |
| `incremental_load` với `rerun_last = true` báo `Staging đã có batch … không nạp lại batch cũ hơn` | Lần Incremental trước đã nạp staging batch mới hơn nhưng lỗi ở bước dbt | Chạy lại với `rerun_last = false`: pipeline nạp lại đúng batch đó rồi chạy dbt |
