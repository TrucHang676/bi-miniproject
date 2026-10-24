"""Code dùng chung cho 2 pipeline full_load / incremental_load (quy tắc: docs/pipeline_rules.md).

    settings.py     bảng nào, cột nào, khóa chính nào, thứ tự nạp
    db.py           mở kết nối PostgreSQL (đọc biến POSTGRES_* từ .env)
    batch_files.py  đọc manifest.csv và file CSV của batch
    staging.py      đưa dòng vào bảng tạm rồi MERGE vào staging
    etl_log.py      ghi nhật ký etl_log.pipeline_run / table_load / quality_check / dbt_result
    runner.py       nạp trọn 1 batch: gọi các file trên theo đúng thứ tự
    dbt_runner.py   sau khi nạp staging: chạy dbt build dựng dds, ghi etl_log.dbt_result (BS-34)
"""
