-- =====================================================================
-- 01_staging_tables.sql - 8 bảng trong schema staging (Mage nạp từ CSV)
--   * Tên cột giữ NGUYÊN như CSV gốc (kể cả lỗi chính tả *_lenght) - dbt mới đổi tên
--   * Kiểu dữ liệu theo docs/data_dictionary.md, khóa chính theo D1 (docs/decisions.md)
--   * KHÔNG tạo khóa ngoại (D2): Mage nạp từng bảng, FK kiểm tra bằng dbt test
--   * NOT NULL chỉ đặt ở cột khóa / mã và cột luôn có giá trị; cột còn lại để NULL được
--     vì batch mô phỏng (D8) cố ý để trống các mốc thời gian chưa xảy ra
--   * 2 cột kỹ thuật cuối mỗi bảng (D8): _batch_id = batch nạp gần nhất, _loaded_at = lúc nạp
--   * staging.orders có thêm _is_deleted, _deleted_at (xóa mềm) - thêm ở 04_soft_delete.sql
--   * Chạy lại nhiều lần vẫn an toàn (IF NOT EXISTS), không xóa dữ liệu có sẵn
-- =====================================================================


-- ===== Nhóm GIAO DỊCH: nạp theo batch tháng bằng MERGE (D3, D4) =====

-- Đơn hàng - 1 dòng = 1 đơn
CREATE TABLE IF NOT EXISTS staging.orders (
    order_id                       VARCHAR(32)  NOT NULL,
    customer_id                    VARCHAR(32)  NOT NULL,
    order_status                   VARCHAR(20)  NOT NULL,
    order_purchase_timestamp       TIMESTAMP    NOT NULL,   -- watermark chia batch (D4)
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  DATE,                    -- giờ luôn 00:00 -> chỉ giữ ngày
    _batch_id                      VARCHAR(10)  NOT NULL,
    _loaded_at                     TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT pk_orders PRIMARY KEY (order_id)
);

-- Chi tiết đơn - 1 dòng = 1 đơn vị sản phẩm trong 1 đơn
CREATE TABLE IF NOT EXISTS staging.order_items (
    order_id             VARCHAR(32)    NOT NULL,
    order_item_id        INT            NOT NULL,   -- số thứ tự 1..n trong đơn
    product_id           VARCHAR(32)    NOT NULL,
    seller_id            VARCHAR(32)    NOT NULL,
    shipping_limit_date  TIMESTAMP,
    price                NUMERIC(10,2),             -- cơ sở tính doanh thu (BRL)
    freight_value        NUMERIC(10,2),
    _batch_id            VARCHAR(10)    NOT NULL,
    _loaded_at           TIMESTAMP      NOT NULL DEFAULT now(),
    CONSTRAINT pk_order_items PRIMARY KEY (order_id, order_item_id)
);

-- Thanh toán - 1 dòng = 1 lần / phương thức thanh toán của đơn
CREATE TABLE IF NOT EXISTS staging.order_payments (
    order_id              VARCHAR(32)    NOT NULL,
    payment_sequential    INT            NOT NULL,
    payment_type          VARCHAR(20),
    payment_installments  INT,
    payment_value         NUMERIC(10,2),
    _batch_id             VARCHAR(10)    NOT NULL,
    _loaded_at            TIMESTAMP      NOT NULL DEFAULT now(),
    CONSTRAINT pk_order_payments PRIMARY KEY (order_id, payment_sequential)
);

-- Đánh giá - 1 dòng = 1 review cho 1 đơn; review_id KHÔNG duy nhất -> khóa ghép (D1)
CREATE TABLE IF NOT EXISTS staging.order_reviews (
    review_id                VARCHAR(32)  NOT NULL,
    order_id                 VARCHAR(32)  NOT NULL,
    review_score             SMALLINT,               -- 1..5 sao
    review_comment_title     TEXT,
    review_comment_message   TEXT,                   -- có xuống dòng trong ô -> TEXT
    review_creation_date     DATE,
    review_answer_timestamp  TIMESTAMP,              -- quyết định review vào batch nào (D8)
    _batch_id                VARCHAR(10)  NOT NULL,
    _loaded_at               TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT pk_order_reviews PRIMARY KEY (review_id, order_id)
);

-- Khách hàng theo đơn - 1 dòng = 1 customer_id (mỗi đơn 1 mã); khách thật = customer_unique_id (D7)
CREATE TABLE IF NOT EXISTS staging.customers (
    customer_id               VARCHAR(32)   NOT NULL,
    customer_unique_id        VARCHAR(32)   NOT NULL,
    customer_zip_code_prefix  CHAR(5),               -- chuỗi, giữ số 0 đầu (VD 01037)
    customer_city             VARCHAR(100),
    customer_state            CHAR(2),
    _batch_id                 VARCHAR(10)   NOT NULL,
    _loaded_at                TIMESTAMP     NOT NULL DEFAULT now(),
    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);


-- ===== Nhóm THAM CHIẾU: nạp toàn bộ 1 lần ở Full Load (D3) =====

-- Người bán
CREATE TABLE IF NOT EXISTS staging.sellers (
    seller_id               VARCHAR(32)   NOT NULL,
    seller_zip_code_prefix  CHAR(5),                 -- chuỗi, giữ số 0 đầu
    seller_city             VARCHAR(100),
    seller_state            CHAR(2),
    _batch_id               VARCHAR(10)   NOT NULL,
    _loaded_at              TIMESTAMP     NOT NULL DEFAULT now(),
    CONSTRAINT pk_sellers PRIMARY KEY (seller_id)
);

-- Sản phẩm - giữ tên cột sai chính tả của nguồn, dbt stg_products đổi thành *_length
CREATE TABLE IF NOT EXISTS staging.products (
    product_id                  VARCHAR(32)  NOT NULL,
    product_category_name       VARCHAR(60),         -- NULL ở 610 sản phẩm
    product_name_lenght         INT,
    product_description_lenght  INT,
    product_photos_qty          INT,
    product_weight_g            INT,
    product_length_cm           INT,
    product_height_cm           INT,
    product_width_cm            INT,
    _batch_id                   VARCHAR(10)  NOT NULL,
    _loaded_at                  TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT pk_products PRIMARY KEY (product_id)
);

-- Bản dịch danh mục (file product_category_name_translation.csv)
CREATE TABLE IF NOT EXISTS staging.category_translation (
    product_category_name          VARCHAR(60)  NOT NULL,
    product_category_name_english  VARCHAR(60),
    _batch_id                      VARCHAR(10)  NOT NULL,
    _loaded_at                     TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT pk_category_translation PRIMARY KEY (product_category_name)
);
