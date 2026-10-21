from olist_etl.utils.runner import load_batch

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer


@transformer
def load_full_batch(run_info, *args, **kwargs):
    """Full Load - bước 2: làm lại staging từ đầu bằng batch FULL.

    TRUNCATE 8 bảng staging rồi nạp 8 file theo thứ tự
    products, sellers, category_translation -> customers -> orders -> order_items, order_payments -> order_reviews.
    Cả bước là 1 transaction: lỗi thì staging trở về như trước khi chạy, lần chạy ghi FAILED.
    Trả về kết quả từng bảng (etl_log.table_load) để xem ngay trong Mage.
    """
    run = run_info.iloc[0]
    return load_batch(int(run['run_id']), run['batch_id'], run['load_type'], truncate_first=True)
