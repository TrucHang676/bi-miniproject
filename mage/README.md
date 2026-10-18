# Mage.ai – Data Ingestion

> Project Mage nằm ở `mage/olist_etl/` (Mage 0.9.79 chạy trong container `olist-mage` – cách bật: [docs/setup_guide.md](../docs/setup_guide.md)).
> Kết nối Postgres khai báo trong `olist_etl/io_config.yaml`, đọc giá trị từ `.env` qua `{{ env_var('...') }}`.

## Pipelines

| Pipeline | Loại | Mô tả | Nguồn → Đích |
|----------|------|-------|--------------|
| `[tên]_full_load` | Full Load | | `data/raw/` → `staging.[...]` |
| `[tên]_incremental_load` | Incremental | | `data/batches/` → `staging.[...]` |

## Các block

| Block | Loại | Chức năng |
|-------|------|-----------|
|       | Data loader | Đọc file nguồn |
|       | Transformer | Kiểm tra cấu trúc & chất lượng |
|       | Data exporter | Ghi vào staging |
|       | Data exporter | Ghi log (`etl_log`) |

## Kiểm tra chất lượng cơ bản
- [ ] Đúng số cột / tên cột
- [ ] Kiểu dữ liệu
- [ ] Null ở cột bắt buộc
- [ ] Trùng khóa

## Cơ chế Incremental
[Mô tả: dựa trên cột nào (watermark / batch_id), xử lý trùng lặp thế nào (upsert / skip).]

## Ghi log
[Mô tả bảng log: run_id, pipeline, thời gian bắt đầu/kết thúc, trạng thái, số dòng, lỗi.]
