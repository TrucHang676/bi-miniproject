"""Cấu hình dùng chung: vị trí batch, cột và khóa chính của từng bảng, thứ tự nạp.

Kiểu dữ liệu KHÔNG khai báo ở đây: đọc thẳng từ bảng staging trong DB (sql/init/01_staging_tables.sql)
để chỉ có một nơi quy định kiểu.
"""
import os

# Repo được gắn vào container Mage tại /home/src (compose.yaml) -> batch nằm ở /home/src/data/batches
BATCH_DIR = os.getenv('OLIST_BATCH_DIR', '/home/src/data/batches')
MANIFEST_PATH = os.path.join(BATCH_DIR, 'manifest.csv')

STAGING_SCHEMA = 'staging'

# Cột trong file batch = cột CSV gốc, đúng thứ tự (data/batches/README.md mục 4).
# Cột batch_id ở cuối mỗi file không ghi ở đây: lúc nạp nó thành cột _batch_id.
# key = khóa chính (D1) = các cột MERGE ... ON.
TABLES = {
    'orders': {
        'columns': ['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp',
                    'order_approved_at', 'order_delivered_carrier_date',
                    'order_delivered_customer_date', 'order_estimated_delivery_date'],
        'key': ['order_id'],
    },
    'order_items': {
        'columns': ['order_id', 'order_item_id', 'product_id', 'seller_id',
                    'shipping_limit_date', 'price', 'freight_value'],
        'key': ['order_id', 'order_item_id'],
    },
    'order_payments': {
        'columns': ['order_id', 'payment_sequential', 'payment_type',
                    'payment_installments', 'payment_value'],
        'key': ['order_id', 'payment_sequential'],
    },
    'order_reviews': {
        'columns': ['review_id', 'order_id', 'review_score', 'review_comment_title',
                    'review_comment_message', 'review_creation_date', 'review_answer_timestamp'],
        'key': ['review_id', 'order_id'],
    },
    'customers': {
        'columns': ['customer_id', 'customer_unique_id', 'customer_zip_code_prefix',
                    'customer_city', 'customer_state'],
        'key': ['customer_id'],
    },
    'sellers': {
        'columns': ['seller_id', 'seller_zip_code_prefix', 'seller_city', 'seller_state'],
        'key': ['seller_id'],
    },
    'products': {
        'columns': ['product_id', 'product_category_name', 'product_name_lenght',
                    'product_description_lenght', 'product_photos_qty', 'product_weight_g',
                    'product_length_cm', 'product_height_cm', 'product_width_cm'],
        'key': ['product_id'],
    },
    'category_translation': {
        'columns': ['product_category_name', 'product_category_name_english'],
        'key': ['product_category_name'],
    },
}

# Thứ tự nạp trong 1 batch (D5, pipeline_rules.md B3): bảng cha trước bảng con
REFERENCE_TABLES = ['products', 'sellers', 'category_translation']          # chỉ có ở batch FULL (D3)
TRANSACTION_TABLES = ['customers', 'orders', 'order_items', 'order_payments', 'order_reviews']


def tables_for(load_type):
    """Danh sách bảng (= danh sách file) của 1 batch, theo thứ tự nạp."""
    if load_type == 'FULL':
        return REFERENCE_TABLES + TRANSACTION_TABLES
    return list(TRANSACTION_TABLES)
