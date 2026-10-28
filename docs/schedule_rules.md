# Kế hoạch lập lịch ETL – Seminar 3

> **Dành cho người làm phần "lập lịch ETL" của Seminar 3** (hạn 23:00 14/11/2026). Đọc **Phần A** để biết việc cần làm, thứ tự và khi nào coi là xong; mở **Phần B** khi thao tác trong Mage.
> Phạm vi: **chỉ phần lập lịch**. Hai phần còn lại của Seminar 3 (dashboard theo dõi ETL, AI giải thích kết quả) có tài liệu riêng; file này chỉ nói lập lịch để lại dữ liệu gì cho dashboard ETL (B9).
> Code pipeline **không cần sửa** (B7): biến `triggered_by` và cột `etl_log.pipeline_run.triggered_by` đã chừa sẵn từ Seminar 1.
> **[Bắt buộc]** = nhóm đã chốt, muốn làm khác phải bàn lại · **[Gợi ý]** = cách đề xuất, làm khác được nếu ra cùng kết quả · **(cần kiểm chứng)** = hành vi của Mage 0.9.79 chưa thử trên máy nhóm – kiểm thử B8 sẽ trả lời.
> Trạng thái: **kế hoạch, chưa làm**. Cập nhật: 28/10/2026.

---

# Phần A – Nhiệm vụ

## A1. Lập lịch là gì, nằm ở đâu

Tới giờ, mỗi lần nạp 1 batch là **một người bấm** Triggers → Run@once. Lập lịch là **hẹn giờ cho Mage tự bấm**, giống hẹn giờ nồi cơm: tới giờ thì tự chạy, không cần người đứng canh.

Lịch **không** quyết định nạp batch nào. Batch kế tiếp vẫn do LSET trong `etl_log` quyết định, y như lúc chạy tay. Lịch chỉ quyết định **lúc nào** chạy. Vì vậy lỡ một lần chạy (tắt máy, Docker tắt) thì lần sau vẫn nạp đúng batch còn thiếu, không bị nhảy cóc.

```
Bộ hẹn giờ của Mage (scheduler – chạy sẵn trong container olist-mage)
   │  tới giờ theo trigger "incremental_demo" / "incremental_monthly"   ← việc của file này
   ▼
incremental_load:  get_lset → set_cet → extract_load → dbt_build → set_lset     (code có sẵn, không sửa)
   │  ghi pipeline_run với triggered_by = 'schedule'
   ▼
etl_log (pipeline_run, table_load, quality_check, dbt_result)
   │
   ▼
Dashboard theo dõi ETL (Seminar 3 – phần 2) · AI giải thích (phần 3)
```

**Đã có sẵn – không phải làm:**

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| Pipeline `full_load`, `incremental_load` (đã gồm bước dbt) | `mage/olist_etl/` | BS-22, BS-23, BS-34. Một lần chạy mất ~41–63 giây |
| Biến `triggered_by` | `start_full_run.py`, `set_cet.py` | Không truyền thì là `manual`; trigger lịch truyền `schedule` |
| Cột `triggered_by` | `etl_log.pipeline_run` (`sql/init/02_etl_log.sql`) | `CHECK (triggered_by IN ('manual', 'schedule'))` |
| Tự dọn lần chạy kẹt | `etl_log.fail_interrupted_runs` | Lần chạy mới đổi mọi dòng còn `RUNNING` thành `FAILED` – cũng là lý do **cấm chạy chồng** (B6) |
| Tự nạp lại batch lỗi | LSET chỉ tiến khi `SUCCESS` | Lần chạy theo lịch kế tiếp tự nạp lại đúng batch vừa lỗi |

## A2. Việc cần làm và kết quả nộp

| Việc | Kết quả nộp | Quy tắc |
|---|---|---|
| Tạo 2 trigger lịch cho `incremental_load` | `mage/olist_etl/pipelines/incremental_load/triggers.yaml` (cả 2 trigger để `inactive`) | B1 → B4 |
| Kiểm thử | Bảng kết quả T1–T9 ghi vào `mage/README.md` mục "Lập lịch" | B8 |
| Cập nhật tài liệu | `mage/README.md`, `docs/setup_guide.md` mục 6.2, `docs/decisions.md`, `sql/checks/01_pipeline_demo.sql` (thêm Q8), `CLAUDE.md` | B10 |
| Tư liệu cho báo cáo + video | Ảnh chụp (B10) + đoạn demo lập lịch (B11) | B10, B11 |

## A3. Thời gian [Gợi ý]

Seminar 2 (Power BI, hạn **05/11**) đến trước, nên phần này được xếp sao cho không giành thời gian của Seminar 2:

| Khi nào | Việc | Ước lượng |
|---|---|---|
| 29/10 – 04/11, lúc rảnh | Tạo trigger + kiểm thử T1–T9 trên **1 máy** (máy không dùng làm Power BI hôm đó) | 1 buổi (~45 phút là chờ 9 batch chạy) |
| 06/11 – 09/11 | Cập nhật tài liệu, chụp ảnh, viết mục báo cáo | 1 buổi |
| Khi quay video Seminar 3 | Quay đoạn demo B11 | ~1 giờ |

⚠ Trong lúc kiểm thử, `dds` trên máy đó chỉ có một phần dữ liệu (đang nạp dần từng batch). Không refresh Power BI trên máy này cho tới khi chạy xong batch `2018-09+`.

## A4. Thứ tự làm [Gợi ý]

1. Chuẩn bị máy: `git pull`, `docker compose up -d`, kiểm tra bảng ⚠ đầu `CLAUDE.md` đã áp dụng hết.
2. Chạy `full_load` bằng tay để đưa dữ liệu về đầu (T1).
3. Tạo trigger `incremental_demo` (B2, B3) → bật → ngồi xem T2, T3, T5, T6.
4. Tạo trigger `incremental_monthly` (B2) để `inactive` → xem T8.
5. **Save trigger in code** (B4) → kiểm tra file `triggers.yaml` → T7, T9.
6. Ghi kết quả, cập nhật tài liệu (B10), commit.

## A5. Khi nào coi là xong

- `triggers.yaml` đã commit, 2 trigger đều `inactive`, có biến `triggered_by: schedule`.
- T1–T9 đạt (hoặc có ghi lại vì sao khác mong đợi và nhóm đã chốt cách xử lý).
- `etl_log.pipeline_run` có đủ 9 lần `incremental_load` `SUCCESS` với `triggered_by = 'schedule'`, cách nhau ~5 phút → dữ liệu này dùng luôn cho dashboard ETL.
- Tài liệu ở B10 đã cập nhật; đã báo Thanh, Yến (B4 – sau khi pull **không** tự bật trigger).

---

# Phần B – Quy tắc chi tiết

## B1. Lập lịch pipeline nào [Bắt buộc]

| Pipeline | Có lịch? | Vì sao |
|---|---|---|
| `incremental_load` | **Có** | Mỗi lần chạy nạp đúng 1 batch kế tiếp; chạy thừa khi đã hết batch cũng vô hại (B6) |
| `full_load` | **Không** – chỉ chạy tay (Run@once), 1 lần lúc khởi tạo | Full Load `TRUNCATE` staging và `dbt build --full-refresh`. Đặt lịch lặp lại thì mỗi lần tới giờ sẽ xóa staging và kéo Incremental về lại `2018-01` (B8 #9 của [pipeline_rules.md](pipeline_rules.md)) |

## B2. Hai trigger

| Trigger | Bắt buộc? | Lịch (cron) | Ý nghĩa | Trạng thái khi commit |
|---|---|---|---|---|
| `incremental_demo` | **[Bắt buộc]** | `*/5 * * * *` – 5 phút / lần | "Tua nhanh": 5 phút ngoài đời = 1 tháng dữ liệu. Dùng để kiểm thử và quay video | `inactive` |
| `incremental_monthly` | [Gợi ý] | `0 0 1 * *` – 00:00 UTC ngày 1 hằng tháng = **07:00 sáng ngày 1 giờ Việt Nam** | Lịch "thật" nếu hệ thống chạy ở doanh nghiệp: batch chia theo tháng, mốc cắt CET = đầu tháng sau (D4, D8) → đầu tháng mới, tháng trước đã đóng thì nạp. Dùng để trình bày thiết kế trong báo cáo | `inactive` |

**Vì sao 5 phút:** một lần chạy mất tối đa ~63 giây → 5 phút gấp gần 5 lần, đủ an toàn để không chạy chồng. 9 batch ≈ 45 phút. Muốn quay video nhanh hơn thì được giảm xuống **3 phút** (vẫn gấp ~3 lần), **không** giảm dưới 2 phút.

## B3. Cấu hình trigger trong Mage [Bắt buộc]

Mở `incremental_load` → **Triggers** → **New trigger** → **Schedule**. Tên nút ghi theo Mage 0.9.79, chữ có thể hơi khác.

| Mục | Giá trị | Vì sao |
|---|---|---|
| Trigger name | `incremental_demo` (hoặc `incremental_monthly`) | Khớp B2 |
| Frequency | **custom** → cron ở B2 | |
| Start date and time | Lúc bắt đầu kiểm thử (Mage hiểu là **UTC** – B5) | |
| Runtime variables | `triggered_by` = `schedule` · `rerun_last` = `false` | `triggered_by` để dashboard tách lần chạy tay / theo lịch; `rerun_last` ghi rõ để không ai lỡ để `true` (lịch mà chạy lại batch cũ mãi thì không bao giờ tiến) |
| **Skip run if previous run still in progress** | **BẬT** | Chặn chạy chồng (B6). Đây là cài đặt quan trọng nhất |
| Keep running pipeline even if blocks fail | TẮT | Block lỗi thì phải dừng để `set_lset` không chạy |
| Create initial pipeline run if start date is before current execution period | TẮT [Gợi ý] | Tránh vừa bật đã chạy ngay ngoài ý muốn |
| Timeout | Để trống [Gợi ý] | Lần chạy bị Mage cắt giữa chừng sẽ kẹt `RUNNING` tới lần sau; pipeline đã tự dọn được nên không cần thêm |

## B4. Lưu trigger vào code [Bắt buộc]

Trigger tạo trên giao diện chỉ nằm trong DB nội bộ của Mage trên **máy đó** (`mage_data/`, bị `.gitignore`) → máy khác không có, giáo viên chạy lại cũng không có. Vì vậy:

1. Trên trang trigger, bấm **Save trigger in code** → Mage ghi file `mage/olist_etl/pipelines/incremental_load/triggers.yaml`.
2. Mở file kiểm tra: đủ 2 trigger, có `triggered_by: schedule`, có cài đặt bỏ qua khi lần trước đang chạy (`skip_if_previous_running: true`).
3. **Trước khi commit đặt cả 2 trigger `status: inactive`.** Nếu commit `active`, máy nào `git pull` mà đang bật Docker sẽ tự nạp batch → `dds` của bạn đó đổi giữa lúc đang làm Power BI.
4. Bật / tắt khi cần thì làm trên giao diện. Nếu sau đó `git status` thấy `triggers.yaml` đổi chỉ vì `status` → **không commit** phần đó (`git restore` file).

(cần kiểm chứng – T7) Mage đọc lại `triggers.yaml` khi khởi động: có thể restart container làm trigger về lại `inactive`. Nếu đúng vậy thì ghi vào `mage/README.md`: "restart Mage xong phải bật lại trigger".

## B5. Giờ và múi giờ

| Thứ | Múi giờ | Ghi chú |
|---|---|---|
| Lịch cron + Start date của trigger | **UTC** (cần kiểm chứng – T8) | Giờ Việt Nam = UTC + 7. 07:00 VN ngày 1 = 00:00 UTC ngày 1 → `0 0 1 * *` |
| `started_at`, `finished_at` trong `etl_log` | Giờ Việt Nam | DB đặt `Asia/Ho_Chi_Minh` (`00_schemas.sql`) |
| `lset`, `cet` | Thời gian **mô phỏng** của dữ liệu (2018) | Không liên quan giờ chạy |

Trigger 5 phút không bị ảnh hưởng bởi múi giờ.

## B6. Lịch gặp các tình huống – pipeline xử lý thế nào [Bắt buộc đọc]

| # | Tình huống | Điều xảy ra | Người làm gì |
|---|---|---|---|
| 1 | Tới giờ, còn batch chưa nạp | Nạp batch kế tiếp, `pipeline_run.triggered_by = 'schedule'` | Không |
| 2 | Tới giờ, lần trước **đang chạy** | Mage bỏ qua lần này (nhờ cài đặt ở B3). Nếu quên bật: lần mới gọi `fail_interrupted_runs` → đánh `FAILED` **sai** cho lần đang chạy, rồi 2 lần cùng đọc 1 LSET | Kiểm tra B3 đã bật |
| 3 | Tới giờ, **đã nạp hết** batch | `get_lset` trả `DONE` → Mage báo run `completed`, **không** ghi `pipeline_run` | Tắt trigger `incremental_demo` |
| 4 | Lần trước `FAILED` (file lỗi, dbt test FAIL…) | LSET không tiến → lần sau **tự nạp lại đúng batch đó**. Lỗi do dữ liệu thì cứ 5 phút lại `FAILED` 1 lần cho tới khi sửa | Tắt trigger → sửa → bật lại |
| 5 | Full Load lỗi ở bước dbt | Mọi lần Incremental theo lịch báo lỗi "chạy lại full_load" (B12 #5 của [pipeline_rules.md](pipeline_rules.md)) | Tắt trigger → chạy `full_load` tay → bật lại |
| 6 | Máy / Docker tắt lúc tới giờ | Lần đó không chạy. Bật lại thì lần kế tiếp nạp tiếp từ LSET – không mất, không nhảy batch. (cần kiểm chứng) Mage có chạy bù lần bị lỡ không – có bù thì cũng chỉ là nạp batch kế | Không |
| 7 | Container tắt **giữa lúc** đang chạy | Dòng `pipeline_run` kẹt `RUNNING`; staging không dở dang (1 transaction). Lần theo lịch kế tiếp đổi nó thành `FAILED` rồi nạp lại batch đó | Không |
| 8 | Bấm **Run@once** tay trong lúc trigger lịch đang bật | (cần kiểm chứng – T5) Cài đặt "skip" có thể chỉ xét các lần chạy của **cùng** trigger → lần tay và lần theo lịch có thể chạy chồng như #2 | **Không làm.** Muốn chạy tay thì tắt trigger trước |
| 9 | Gõ `dbt` tay trong lúc trigger đang bật | Hai lần dbt cùng dựng `dds` (B12 #8 của [pipeline_rules.md](pipeline_rules.md)) | **Không làm.** Tắt trigger trước |

## B7. Có phải sửa code không

**Không** [Bắt buộc]: `start_full_run` và `set_cet` đã đọc biến `triggered_by`; bảng log đã có cột + `CHECK`. Lập lịch chỉ là cấu hình Mage + 1 file `triggers.yaml`.

Ba điểm nhóm cần chốt (ghi kết quả vào bảng cuối [decisions.md](decisions.md)):

| # | Câu hỏi | Đề xuất | Lý do |
|---|---|---|---|
| 1 | Lần chạy theo lịch mà **không có batch mới** (B6 #3) có ghi vào `etl_log` không? | **Không ghi** (giữ như hiện tại) | Ghi thì phải thêm trạng thái mới (VD `NO_DATA`), sửa `CHECK`, sửa `get_lset` / `set_cet` / `set_lset` và dashboard ETL. Tab **Runs** của Mage vẫn thấy các lần này |
| 2 | Có gửi thông báo khi chạy lỗi (email / Slack – Mage có sẵn `notification_config`)? | **Không làm**, ghi vào "hướng phát triển" trong báo cáo | Cần tài khoản email / Slack; dashboard ETL đã cho thấy lần `FAILED` |
| 3 | Có thêm khóa chống chạy chồng ngay trong code (VD `pg_try_advisory_lock` ở `get_lset`)? | **Chưa**, chỉ dựa vào cài đặt B3 + quy tắc B6 #8, #9 | Nếu T5 cho thấy Run@once tay vẫn chạy chồng được với lần theo lịch thì mới thêm (sửa nhỏ ở `get_lset` + `set_lset`, phải báo Yến vì là block của Yến) |

## B8. Kịch bản kiểm thử – tiêu chí hoàn thành

Làm trên 1 máy, theo thứ tự. Câu truy vấn xem kết quả ở B9.

| # | Kịch bản | Kết quả mong đợi |
|---|---|---|
| T1 | Chạy `full_load` bằng tay (Run@once) | `SUCCESS`, `triggered_by = 'manual'`, batch `FULL`. Đây là cách đưa dữ liệu về đầu, **không** cần xóa DB – log cũ vẫn giữ |
| T2 | Bật `incremental_demo` | Trong ≤ 5 phút tab **Runs** có lần chạy mới; `pipeline_run` thêm dòng batch `2018-01`, `triggered_by = 'schedule'`, `SUCCESS` |
| T3 | Để trigger chạy tiếp ~45 phút | 9 dòng `schedule` `SUCCESS`, batch `2018-01` → `2018-09+` theo đúng thứ tự, `started_at` cách nhau ~5 phút. Số dòng staging khớp B8 #7 của [pipeline_rules.md](pipeline_rules.md); `sql/checks/02_dds_checks.sql` khớp |
| T4 | Để thêm 1–2 lần sau khi hết batch | Mage báo `completed`, log block `get_lset` ghi "đã nạp hết batch", `pipeline_run` **không** thêm dòng. Sau đó tắt trigger |
| T5 | Chống chạy chồng: trong lúc T3, đổi tạm lịch thành `* * * * *` (1 phút – ngắn hơn thời gian chạy) cho 2–3 batch, rồi trả về `*/5` · thêm: bấm Run@once tay trong lúc 1 lần theo lịch đang chạy | Lịch 1 phút: Mage **bỏ qua** các lần trùng; không có dòng `FAILED` "bị ngắt giữa chừng"; không có 2 dòng cùng batch. Run@once tay: ghi lại thực tế xảy ra gì → chốt điểm 3 của B7 |
| T6 | Tự phục hồi sau lỗi: dùng kịch bản #11 ở B12 của [pipeline_rules.md](pipeline_rules.md) (1 dòng `payment_type = pix` ở batch `2018-02`) khi trigger đang bật | Lần theo lịch nạp `2018-02` → `FAILED`, LSET đứng yên; các lần sau vẫn `FAILED` cùng batch. Trả file đúng → lần theo lịch kế tiếp **tự** `SUCCESS` đúng `2018-02` rồi đi tiếp `2018-03` |
| T7 | `docker compose restart mage` khi trigger đang bật | Ghi lại: trigger còn bật hay về `inactive` theo `triggers.yaml` (B4); bật lại thì lịch chạy tiếp đúng LSET |
| T8 | Bật `incremental_monthly` rồi xem "next run" Mage hiển thị, xong tắt ngay | Lần chạy kế = 00:00 UTC ngày 1 tháng tới (= 07:00 VN). Khác thì sửa cron ở B2 và ghi lại Mage dùng múi giờ nào |
| T9 | Máy khác (Thanh hoặc Yến) `git pull` + mở Mage | Thấy 2 trigger, cả 2 `inactive`, **không** tự chạy |

## B9. Câu truy vấn kiểm tra – thêm vào `sql/checks/01_pipeline_demo.sql` thành Q8 [Gợi ý]

```sql
-- Q8. Các lần chạy Incremental gần nhất: chạy tay hay theo lịch, mất bao lâu, cách lần trước bao lâu
SELECT run_id,
       batch_id,
       triggered_by,
       status,
       started_at,
       finished_at - started_at                                AS duration,
       started_at - LAG(started_at) OVER (ORDER BY run_id)     AS gap_from_prev,
       error_message
FROM etl_log.pipeline_run
WHERE pipeline_name = 'incremental_load'
ORDER BY run_id DESC
LIMIT 20;
```

Cùng dữ liệu này là đầu vào cho dashboard theo dõi ETL (phần 2 Seminar 3): số lần chạy theo `triggered_by` / `status`, thời gian chạy từng batch, số dòng INSERT / UPDATE / bị loại (`table_load`), kết quả dbt test (`dbt_result`).

## B10. Cập nhật tài liệu và ảnh cho báo cáo [Bắt buộc]

| File | Sửa gì |
|---|---|
| `mage/README.md` | Đổi mục "Lưu ý khi lập lịch (Seminar 3)" thành mục "Lập lịch": 2 trigger, cài đặt B3, bảng kết quả T1–T9 |
| `docs/setup_guide.md` mục 6.2 | Thêm cách bật / tắt `incremental_demo` thay cho bấm Run@once 9 lần |
| `docs/decisions.md` | 1 dòng chốt: lập lịch `incremental_load` bằng trigger Mage, không lập lịch `full_load`, 3 điểm ở B7 |
| `sql/checks/01_pipeline_demo.sql` | Thêm Q8 (B9) |
| `CLAUDE.md` | Mục "Trạng thái hiện tại" |

Ảnh chụp (lưu `docs/images/schedule/`):

1. Màn hình cấu hình trigger `incremental_demo` (thấy cron, runtime variables, ô "skip").
2. Danh sách trigger của `incremental_load` (2 trigger, trạng thái).
3. Tab **Runs**: chuỗi lần chạy cách nhau 5 phút.
4. Kết quả Q8 trong DBeaver sau T3 (9 dòng `schedule`).
5. Kết quả T6: dòng `FAILED` rồi `SUCCESS` cùng batch `2018-02`.

## B11. Đoạn demo lập lịch trong video [Gợi ý]

1. Chạy Q8 → chỉ ra các lần chạy cũ đều `manual`.
2. Mở trigger `incremental_demo` → giải thích cron 5 phút = "1 tháng dữ liệu", biến `triggered_by`, ô "skip".
3. Bật trigger → (cắt ghép) → tab **Runs** có 2–3 lần chạy tự động.
4. Chạy lại Q8 → dòng mới `triggered_by = schedule`, batch tăng dần, cách nhau ~5 phút.
5. (Nếu còn thời gian) Kịch bản T6: lần theo lịch `FAILED` → sửa file → lần kế tự `SUCCESS`.
6. Tắt trigger.
