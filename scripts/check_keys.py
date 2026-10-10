"""
Kiểm chứng khóa chính, khóa ngoại và phương án chia batch  –  task BS-5.

Cách chạy (từ thư mục bi-miniproject/):
    py scripts/check_keys.py

Chỉ ĐỌC data/raw/ và in kết quả ra màn hình; số liệu dùng cho docs/decisions.md.
Không tạo batch, không ghi file.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
    "geolocation": "olist_geolocation_dataset.csv",
}

# Khóa chính đề xuất (✔ phải unique) và các khóa "trông giống khóa" nhưng không unique (✘)
PK = {
    "orders": ["order_id"],
    "order_items": ["order_id", "order_item_id"],
    "order_payments": ["order_id", "payment_sequential"],
    "order_reviews": ["review_id", "order_id"],
    "customers": ["customer_id"],
    "sellers": ["seller_id"],
    "products": ["product_id"],
    "category_translation": ["product_category_name"],
}
NOT_PK = {
    "order_reviews": [["review_id"], ["order_id"]],
    "customers": [["customer_unique_id"]],
    "order_items": [["order_id"]],
    "geolocation": [["geolocation_zip_code_prefix"], ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"]],
}
FK = [  # (bảng con, cột, bảng cha, cột, bắt buộc?)
    ("orders", "customer_id", "customers", "customer_id", True),
    ("order_items", "order_id", "orders", "order_id", True),
    ("order_items", "product_id", "products", "product_id", True),
    ("order_items", "seller_id", "sellers", "seller_id", True),
    ("order_payments", "order_id", "orders", "order_id", True),
    ("order_reviews", "order_id", "orders", "order_id", True),
    ("products", "product_category_name", "category_translation", "product_category_name", False),
    ("customers", "customer_zip_code_prefix", "geolocation", "geolocation_zip_code_prefix", False),
    ("sellers", "seller_zip_code_prefix", "geolocation", "geolocation_zip_code_prefix", False),
]
FULL_LOAD_END = "2017-12"            # Full Load: mọi đơn mua đến hết tháng này
LAST_BATCH_FROM = "2018-09"          # các tháng từ đây trở đi (rất thưa) gộp vào 1 batch cuối


def h(title):
    print(f"\n=== {title}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    T = {k: pd.read_csv(RAW / f, dtype=str, keep_default_na=False, encoding="utf-8-sig") for k, f in FILES.items()}
    od = T["orders"]
    for c in ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
              "order_delivered_customer_date", "order_estimated_delivery_date"]:
        od[c] = pd.to_datetime(od[c].where(od[c] != ""))
    rv = T["order_reviews"]
    rv["review_answer_timestamp"] = pd.to_datetime(rv.review_answer_timestamp)

    # ------------------------------------------------------------ 1. khóa chính
    h("1. Khóa chính (rows | distinct key | dòng trùng | NULL trong cột khóa)")
    for t, k in PK.items():
        d = T[t]
        dup = int(d.duplicated(k).sum())
        nulls = int((d[k] == "").any(axis=1).sum())
        print(f"{'OK ' if dup == 0 and nulls == 0 else 'FAIL'} {t:22} ({', '.join(k)}): {len(d)} | "
              f"{len(d) - dup} | {dup} | {nulls}")
    for t, ks in NOT_PK.items():
        for k in ks:
            print(f"     không phải khóa: {t}({', '.join(k)}) – dòng trùng {int(T[t].duplicated(k).sum())}")

    h("1b. Khóa ngoại (dòng mồ côi / dòng kiểm tra)")
    for c, cc, p, pc, req in FK:
        s = T[c][cc]
        s = s[s != ""]
        orphan = int((~s.isin(set(T[p][pc]))).sum())
        print(f"{'bắt buộc ' if req else 'mềm     '} {c}.{cc} → {p}.{pc}: {orphan} / {len(s)}")

    # ------------------------------------------------------------ 2-3. watermark
    P = od.order_purchase_timestamp
    h("3. Watermark order_purchase_timestamp")
    print("NULL:", int(P.isna().sum()), "| min:", P.min(), "| max:", P.max())
    ts_dup = P.value_counts()
    print("mốc thời gian dùng chung bởi >1 đơn:", int((ts_dup > 1).sum()), "mốc,", int(ts_dup[ts_dup > 1].sum()), "đơn")
    print("Cột ứng viên khác (NULL):",
          {c: int(od[c].isna().sum()) for c in ["order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date"]})
    print("Bảng nào có cột updated_at / last_modified?",
          [f"{t}.{c}" for t, d in T.items() for c in d.columns if "update" in c or "modif" in c] or "không có")

    # ------------------------------------------------------------ 5. chia batch
    m = P.dt.to_period("M")
    batch = m.astype(str).where(m > pd.Period(FULL_LOAD_END), "FULL")
    batch = batch.where(m < pd.Period(LAST_BATCH_FROM), f"{LAST_BATCH_FROM}+")
    od["batch"] = batch
    order_batch = od.set_index("order_id").batch
    cust_batch = od.set_index("customer_id").batch
    order = ["FULL"] + sorted(b for b in od.batch.unique() if b != "FULL")

    h("4-5. Số dòng theo batch (bảng con đi theo order_id, customers theo customer_id của đơn)")
    rows = pd.DataFrame({
        "orders": od.batch.value_counts(),
        "order_items": T["order_items"].order_id.map(order_batch).value_counts(),
        "order_payments": T["order_payments"].order_id.map(order_batch).value_counts(),
        "order_reviews": rv.order_id.map(order_batch).value_counts(),
        "customers": T["customers"].customer_id.map(cust_batch).value_counts(),
    }).reindex(order).fillna(0).astype(int)
    span = od.groupby("batch").order_purchase_timestamp.agg(["min", "max"]).reindex(order)
    print(pd.concat([span.apply(lambda s: s.dt.strftime("%Y-%m-%d")), rows], axis=1).to_string())
    print("TỔNG:", rows.sum().to_dict())
    print("TỔNG RAW:", {t: len(T[t]) for t in rows.columns})
    for t, c in [("order_items", "order_id"), ("order_payments", "order_id"), ("order_reviews", "order_id")]:
        print(f"{t}: dòng không gán được batch = {int(T[t][c].map(order_batch).isna().sum())}")

    h("4b. review_id dùng chung cho nhiều đơn nằm ở các batch khác nhau")
    rb = rv.assign(b=rv.order_id.map(order_batch))
    multi = rb.groupby("review_id").b.nunique()
    print("review_id có đơn ở >1 batch:", int((multi > 1).sum()))

    h("3b. Dữ liệu 'đến muộn' so với cuối batch (mốc xảy ra SAU ngày cuối của tháng batch)")
    end = (m.dt.to_timestamp(how="end")).dt.normalize() + pd.Timedelta(days=1)   # 00:00 ngày đầu tháng sau
    late = pd.DataFrame({
        "orders": od.batch,
        "approved_after": od.order_approved_at >= end,
        "carrier_after": od.order_delivered_carrier_date >= end,
        "delivered_after": od.order_delivered_customer_date >= end,
    })
    jr = rv.merge(od[["order_id"]].assign(end=end.values, b=od.batch.values), on="order_id")
    jr["answer_after"] = jr.review_answer_timestamp >= jr.end
    g = late.groupby("orders")[["approved_after", "carrier_after", "delivered_after"]].mean().mul(100).round(1)
    g["review_answer_after"] = jr.groupby("b").answer_after.mean().mul(100).round(1)
    print(g.reindex(order).to_string())
    print("Toàn bộ (% đơn):", late[["approved_after", "carrier_after", "delivered_after"]].mean().mul(100).round(1).to_dict(),
          "| review:", round(jr.answer_after.mean() * 100, 1))
    print("delivered_after trong các batch incremental 2018-01..08:",
          round(late[late.orders.str.startswith("2018-0") & (late.orders < "2018-09")].delivered_after.mean() * 100, 1))
    h("3c. Dữ liệu bị cắt cuối kỳ (right-censoring)")
    aug = od[P.dt.to_period("M") == pd.Period("2018-08")]
    daily = aug.groupby(aug.order_purchase_timestamp.dt.day).size()
    print("Số đơn/ngày tháng 2018-08: ngày 1–22 TB", round(daily.loc[1:22].mean()), "| ngày 23–31:", daily.loc[23:].to_dict())
    print("Mốc muộn nhất: carrier", od.order_delivered_carrier_date.max(), "| delivered", od.order_delivered_customer_date.max(),
          "| số đơn giao sau 2018-09-03:", int((od.order_delivered_customer_date >= "2018-09-04").sum()))
    dl = od[(od.order_status == "delivered") & od.order_delivered_customer_date.notna()]
    days_dl = (dl.order_delivered_customer_date - dl.order_purchase_timestamp).dt.total_seconds() / 86400
    print("Thời gian giao TB theo tháng mua:", days_dl.groupby(dl.batch).mean().round(1).reindex(order).to_dict())
    fin = od.order_status.isin(["shipped", "invoiced", "processing", "created", "approved"])
    print("Đơn chưa hoàn tất theo batch:", od[fin].batch.value_counts().reindex(order).fillna(0).astype(int).to_dict())

    # ------------------------------------------------------------ bảng tham chiếu
    h("2. Bảng tham chiếu: thực thể xuất hiện lần đầu ở batch nào")
    it = T["order_items"].assign(b=T["order_items"].order_id.map(order_batch))
    rank = {b: i for i, b in enumerate(order)}
    for col, tbl in [("product_id", "products"), ("seller_id", "sellers")]:
        first = it.assign(r=it.b.map(rank)).groupby(col).r.min().map(dict(enumerate(order)))
        vc = first.value_counts().reindex(order).fillna(0).astype(int)
        print(f"{tbl}: {len(T[tbl])} dòng; lần đầu xuất hiện: FULL {vc['FULL']}, sau Full Load {int(vc.drop('FULL').sum())} "
              f"({vc.drop('FULL').sum() / len(T[tbl]) * 100:.1f}%)")
    print("category_translation:", len(T["category_translation"]), "dòng; geolocation:", len(T["geolocation"]), "dòng")

    # ------------------------------------------------------------ 6. khách hàng
    h("6. Khách hàng")
    cu = T["customers"].merge(od[["customer_id", "order_id", "order_purchase_timestamp", "batch"]], on="customer_id")
    per = cu.groupby("customer_unique_id").order_id.nunique()
    n_u = len(per)
    print("customer_id:", len(T["customers"]), "| customer_unique_id:", n_u,
          "| customer_id/đơn tối đa:", od.customer_id.value_counts().max())
    print("số đơn / khách:", per.value_counts().sort_index().to_dict())
    rep = per[per > 1]
    print(f"khách mua lại (≥2 đơn): {len(rep)} = {len(rep) / n_u * 100:.2f}% khách; "
          f"đơn của họ: {int(rep.sum())} = {rep.sum() / len(od) * 100:.2f}% đơn")
    dl = od.order_status == "delivered"
    per_dl = cu[cu.order_id.isin(od[dl].order_id)].groupby("customer_unique_id").order_id.nunique()
    print(f"chỉ tính đơn delivered: khách mua lại {int((per_dl > 1).sum())} / {len(per_dl)} = {(per_dl > 1).mean() * 100:.2f}%")
    multi_zip = cu.groupby("customer_unique_id").customer_zip_code_prefix.nunique()
    multi_city = cu.groupby("customer_unique_id").customer_city.nunique()
    multi_state = cu.groupby("customer_unique_id").customer_state.nunique()
    print("khách có >1 zip / >1 city / >1 state:", int((multi_zip > 1).sum()), int((multi_city > 1).sum()), int((multi_state > 1).sum()))
    rank = {b: i for i, b in enumerate(order)}
    cu["r"] = cu.batch.map(rank)
    nb = cu.groupby("customer_unique_id").r.nunique()
    print("khách xuất hiện ở >1 batch:", int((nb > 1).sum()))
    first_r = cu.groupby("customer_unique_id").r.min()
    cu["is_new"] = cu.r == cu.customer_unique_id.map(first_r)
    inc = cu[cu.batch != "FULL"]
    ret = inc.groupby("batch").apply(lambda d: int(d.loc[~d.is_new, "customer_unique_id"].nunique()), include_groups=False)
    print("khách quay lại (đã có ở batch trước) theo batch:", ret.reindex(order[1:]).to_dict())
    same_ts = cu.groupby(["customer_unique_id", "order_purchase_timestamp"]).order_id.nunique()
    print("khách đặt >1 đơn cùng 1 thời điểm (giỏ hàng tách đơn):", int((same_ts > 1).sum()))
    # Giỏ hàng nhiều người bán bị tách thành nhiều đơn cách nhau vài giây → gộp đơn cách nhau ≤ 10 phút thành 1 lần mua
    s = cu.sort_values(["customer_unique_id", "order_purchase_timestamp"])
    gap = s.groupby("customer_unique_id").order_purchase_timestamp.diff()
    sessions = (gap.isna() | (gap > pd.Timedelta(minutes=10))).groupby(s.customer_unique_id).sum()
    days = s.groupby("customer_unique_id").order_purchase_timestamp.agg(lambda x: x.dt.date.nunique())
    print(f"khách mua lại theo LẦN MUA (đơn cách nhau > 10 phút): {int((sessions > 1).sum())} = {(sessions > 1).mean() * 100:.2f}%; "
          f"theo NGÀY mua khác nhau: {int((days > 1).sum())} = {(days > 1).mean() * 100:.2f}%")


if __name__ == "__main__":
    main()
