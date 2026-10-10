"""
Khảo sát dữ liệu (profiling) cho 9 file CSV Olist trong data/raw/  –  task BS-4.

Cách chạy (từ thư mục bi-miniproject/):
    py scripts/profile_olist.py

Kết quả: ghi đè docs/data_profiling.md (file sinh tự động – không sửa tay).
Script chỉ ĐỌC dữ liệu gốc, không sửa file nào trong data/raw/.

Nguyên tắc: mọi file được đọc dưới dạng chuỗi (dtype=str) để thấy đúng giá trị gốc
(khoảng trắng, số 0 đầu, định dạng ngày...). Ô rỗng "" được coi là NULL.
"""
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "data_profiling.md"

# Tên bảng -> (file, khóa chính dự kiến, {cột: kiểu nghiệp vụ})
# Kiểu nghiệp vụ: id (mã hash 32 ký tự hex), zip, city, state, enum, category, text, int, float, datetime
TABLES = {
    "orders": ("olist_orders_dataset.csv", ["order_id"], {
        "order_id": "id", "customer_id": "id", "order_status": "enum",
        "order_purchase_timestamp": "datetime", "order_approved_at": "datetime",
        "order_delivered_carrier_date": "datetime", "order_delivered_customer_date": "datetime",
        "order_estimated_delivery_date": "datetime"}),
    "order_items": ("olist_order_items_dataset.csv", ["order_id", "order_item_id"], {
        "order_id": "id", "order_item_id": "int", "product_id": "id", "seller_id": "id",
        "shipping_limit_date": "datetime", "price": "float", "freight_value": "float"}),
    "order_payments": ("olist_order_payments_dataset.csv", ["order_id", "payment_sequential"], {
        "order_id": "id", "payment_sequential": "int", "payment_type": "enum",
        "payment_installments": "int", "payment_value": "float"}),
    "order_reviews": ("olist_order_reviews_dataset.csv", ["review_id"], {
        "review_id": "id", "order_id": "id", "review_score": "int", "review_comment_title": "text",
        "review_comment_message": "text", "review_creation_date": "datetime",
        "review_answer_timestamp": "datetime"}),
    "customers": ("olist_customers_dataset.csv", ["customer_id"], {
        "customer_id": "id", "customer_unique_id": "id", "customer_zip_code_prefix": "zip",
        "customer_city": "city", "customer_state": "state"}),
    "sellers": ("olist_sellers_dataset.csv", ["seller_id"], {
        "seller_id": "id", "seller_zip_code_prefix": "zip", "seller_city": "city", "seller_state": "state"}),
    "products": ("olist_products_dataset.csv", ["product_id"], {
        "product_id": "id", "product_category_name": "category", "product_name_lenght": "int",
        "product_description_lenght": "int", "product_photos_qty": "int", "product_weight_g": "int",
        "product_length_cm": "int", "product_height_cm": "int", "product_width_cm": "int"}),
    "category_translation": ("product_category_name_translation.csv", ["product_category_name"], {
        "product_category_name": "category", "product_category_name_english": "category"}),
    "geolocation": ("olist_geolocation_dataset.csv", None, {
        "geolocation_zip_code_prefix": "zip", "geolocation_lat": "float", "geolocation_lng": "float",
        "geolocation_city": "city", "geolocation_state": "state"}),
}

UF = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
NULL_LIKE = {"na", "n/a", "null", "none", "nan", "-", "?"}
MOJIBAKE = r"Ã[\u0080-¿]|Â[\u0080-¿]|�|[a-z][£¢¤¥¦§¨©¬®¯±²³µ¶·¸¹¼½¾][a-z]"  # bỏ ° vì "n°s", "2° vez" là cách viết hợp lệ
DT_RE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
DT_FMT = "%Y-%m-%d %H:%M:%S"
# Khung tọa độ Brazil (gồm cả quần đảo Fernando de Noronha ~ -32.4 lng)
BR_LAT, BR_LNG = (-34.0, 5.5), (-74.5, -32.0)
TREND_FROM, TREND_TO = "2017-01", "2018-08"


# ---------------------------------------------------------------- tiện ích định dạng
def vn(x, d=0):
    """Số kiểu Việt Nam: 12.345,67"""
    if pd.isna(x):
        return "–"
    return f"{x:,.{d}f}".translate(str.maketrans(",.", ".,"))


def pct(a, b, d=2):
    return vn(a / b * 100, d) + "%" if b else "–"


def cell(x, maxlen=45):
    x = str(x).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return x if len(x) <= maxlen else x[:maxlen] + "…"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def fold(x):
    """Bỏ dấu + viết thường + gộp khoảng trắng – dùng để phát hiện cùng một tên viết nhiều kiểu."""
    x = "".join(c for c in unicodedata.normalize("NFKD", x) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", x.lower()).strip()


def dt(s):
    return pd.to_datetime(s.where(s != ""), format=DT_FMT, errors="coerce")


def num(s):
    return pd.to_numeric(s.where(s != ""), errors="coerce")


# ---------------------------------------------------------------- profiling 1 cột
def profile_column(s, kind):
    vc = s.value_counts()                      # tính trên giá trị khác nhau cho nhanh
    u = pd.Series(vc.index, dtype="object").astype(str)
    w = vc.to_numpy()
    nonnull = u != ""

    def cnt(m):
        return int(w[(nonnull & m).to_numpy()].sum())

    def ex(m, k=3):
        return ", ".join(f"`{cell(v, 30)}`" for v in u[nonnull & m].head(k))

    p = {"kind": kind, "null": int(w[(~nonnull).to_numpy()].sum()), "distinct": int(nonnull.sum()),
         "example": next((v for v in s if v != ""), ""), "issues": []}

    def flag(m, msg, key=None):
        c = cnt(m)
        if c:
            p["issues"].append(f"{vn(c)} dòng {msg} (vd {ex(m)})")
        if key:
            p[key] = c
        return c

    flag(u != u.str.strip(), "có khoảng trắng đầu/cuối", "ws")
    flag(u.str.contains("  ", regex=False), "có 2 khoảng trắng liền nhau")
    flag(u.str.strip().str.lower().isin(NULL_LIKE), "là chuỗi giả-NULL (NA, null, -...)")

    if kind == "id":
        flag(~u.str.fullmatch(r"[0-9a-f]{32}"), "không phải mã hash 32 ký tự hex")
    elif kind == "zip":
        flag(~u.str.fullmatch(r"\d{5}"), "không đủ 5 chữ số")
        flag(u.str.startswith("0"), "bắt đầu bằng số 0 (mất số 0 nếu ép kiểu số)", "lead0")
    elif kind == "state":
        flag(~u.isin(UF), "không phải mã bang hợp lệ")
    elif kind in ("int", "float"):
        n = pd.to_numeric(u.where(nonnull), errors="coerce")
        flag(n.isna(), "không phải số")
        if kind == "int":
            flag(n.notna() & (n % 1 != 0), "có phần thập phân")
        v = num(s).dropna()
        p["num"] = dict(min=v.min(), p50=v.median(), p99=v.quantile(0.99), max=v.max(),
                        neg=int((v < 0).sum()), zero=int((v == 0).sum()))
    elif kind == "datetime":
        parsed = pd.to_datetime(u.where(nonnull), format=DT_FMT, errors="coerce")
        bad = flag(~u.str.fullmatch(DT_RE) | parsed.isna(), "sai định dạng YYYY-MM-DD HH:MM:SS")
        ok = parsed.notna()
        midnight = ok & (parsed.dt.hour == 0) & (parsed.dt.minute == 0) & (parsed.dt.second == 0)
        p["dt"] = dict(min=parsed[ok].min(), max=parsed[ok].max(), bad=bad,
                       midnight=cnt(midnight), ok=cnt(ok))

    if kind in ("city", "category", "enum", "text"):
        if kind != "text":
            flag(u != u.str.lower(), "có chữ hoa (phần còn lại viết thường)", "upper")
        flag(u.map(lambda x: unicodedata.normalize("NFC", x) != x),
             "chứa dấu tổ hợp tách rời (Unicode chưa chuẩn hóa NFC)", "nfc")
        # "NÃO" là chữ hợp lệ; mojibake là Ã/Â + ký tự Latin-1 (vd "Ã£") hoặc ký hiệu kẹp giữa 2 chữ (vd "sa£o")
        flag(u.str.contains(MOJIBAKE), "lỗi encoding (mojibake)", "mojibake")
    if kind == "category":
        flag(~u.str.fullmatch(r"[a-z0-9_]+"), "không theo dạng snake_case")
    if kind == "city":
        flag(u.str.contains(r"[^\x00-\x7f]"), "viết có dấu (đa số viết không dấu)", "accent")
        folded = u.map(fold)
        flag(folded.str.contains(r"[^a-z '\-]"), "chứa ký tự lạ (số, dấu câu...)", "odd")
        key = folded.str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
        g = pd.DataFrame({"raw": u, "w": w, "key": key})[nonnull.to_numpy()]
        multi = g[g.groupby("key")["raw"].transform("size") > 1]
        p["variants"] = (0, 0)
        if len(multi):
            dominant = multi.groupby("key").w.max().sum()
            minor = int(multi.w.sum() - dominant)
            top = multi.groupby("key").w.sum().sort_values(ascending=False).head(2).index
            exs = "; ".join(" / ".join(f"`{r}`" for r in multi[multi.key == k].raw.head(4)) for k in top)
            p["variants"] = (multi.key.nunique(), minor)
            p["issues"].append(f"{vn(multi.key.nunique())} tên có nhiều cách viết (dấu/không dấu, gạch nối...); "
                               f"{vn(minor)} dòng không theo cách viết phổ biến nhất (vd {exs})")
    if kind == "text":
        flag(u.str.contains(r"[\r\n]"), "chứa ký tự xuống dòng bên trong ô", "newline")
        L = s[s != ""].str.len()
        if len(L):
            p["issues"].append(f"độ dài TB {vn(L.mean())}, tối đa {vn(L.max())} ký tự")
    return p


# ---------------------------------------------------------------- đọc & profiling từng bảng
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    T, P, INFO = {}, {}, {}
    for name, (fname, pk, cols) in TABLES.items():
        path = RAW / fname
        print(f"Đang đọc {fname} ...")
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        default_types = pd.read_csv(path, encoding="utf-8-sig", low_memory=False).dtypes.astype(str)
        with open(path, "rb") as f:
            bom = f.read(3) == b"\xef\xbb\xbf"
        T[name] = df
        P[name] = {}
        for c in df.columns:
            p = profile_column(df[c], cols.get(c, "text"))
            p["pandas"] = default_types[c]
            if p["kind"] == "zip" and p.get("lead0") and default_types[c] != "object":
                p["issues"].insert(0, f"pandas tự đọc thành {default_types[c]} → mất số 0 đầu ở "
                                      f"{vn(p['lead0'])} dòng")
            P[name][c] = p
        info = dict(file=fname, rows=len(df), cols=df.shape[1], mb=path.stat().st_size / 2**20, bom=bom,
                    dup_rows=int(df.duplicated().sum()), pk=pk,
                    missing=[c for c in cols if c not in df.columns],
                    extra=[c for c in df.columns if c not in cols])
        if pk:
            d = df.duplicated(pk, keep=False)
            info["pk_dup_rows"] = int(d.sum())
            info["pk_dup_keys"] = int(df[d].drop_duplicates(pk).shape[0])
        INFO[name] = info

    M = {}            # các con số dùng cho mục "Vấn đề cần làm sạch"
    X = {k: [] for k in TABLES}   # kiểm tra nghiệp vụ riêng từng bảng (bullet)

    # ---- kiểu dữ liệu đúng để phân tích
    od = T["orders"].copy()
    for c in [c for c, k in TABLES["orders"][2].items() if k == "datetime"]:
        od[c] = dt(od[c])
    it = T["order_items"].copy()
    it["price"], it["freight_value"] = num(it.price), num(it.freight_value)
    it["order_item_id"] = num(it.order_item_id)
    it["shipping_limit_date"] = dt(it.shipping_limit_date)
    pa = T["order_payments"].copy()
    for c in ["payment_sequential", "payment_installments", "payment_value"]:
        pa[c] = num(pa[c])
    rv = T["order_reviews"].copy()
    rv["review_score"] = num(rv.review_score)
    rv["review_creation_date"], rv["review_answer_timestamp"] = dt(rv.review_creation_date), dt(rv.review_answer_timestamp)
    cu, se, pr, tr = T["customers"], T["sellers"], T["products"].copy(), T["category_translation"]
    ge = T["geolocation"].copy()
    ge["lat"], ge["lng"] = num(ge.geolocation_lat), num(ge.geolocation_lng)
    n_od = len(od)

    # ---- orders
    st = od.order_status.value_counts()
    X["orders"].append("Phân bố `order_status`: " + ", ".join(f"{k} {vn(v)} ({pct(v, n_od)})" for k, v in st.items()))
    M["cust_per_order_max"] = int(od.customer_id.value_counts().max())
    X["orders"].append(f"Mỗi `customer_id` xuất hiện tối đa {M['cust_per_order_max']} đơn → customer_id là mã khách "
                       f"*theo từng đơn*, không phải mã khách thật.")

    # ---- order_items
    ipo = it.groupby("order_id").size()
    M["orders_multi_item"] = int((ipo > 1).sum())
    X["order_items"].append("Số item mỗi đơn: " + ", ".join(f"{k} item: {vn(v)} đơn" for k, v in ipo.value_counts().sort_index().head(6).items())
                            + f"; tối đa {ipo.max()} item/đơn.")
    gap = it.groupby("order_id").order_item_id.agg(["max", "size"])
    M["item_seq_gap"] = int((gap["max"] != gap["size"]).sum())
    X["order_items"].append(f"`order_item_id` đánh số liên tục 1..n trong mỗi đơn: {vn(M['item_seq_gap'])} đơn bị đứt quãng.")
    M["orders_multi_seller"] = int((it.groupby("order_id").seller_id.nunique() > 1).sum())
    X["order_items"].append(f"Đơn có nhiều người bán: {vn(M['orders_multi_seller'])}.")
    M["freight_zero"] = int((it.freight_value == 0).sum())
    M["freight_gt_price"] = int((it.freight_value > it.price).sum())
    X["order_items"].append(f"`freight_value = 0` (miễn phí ship): {vn(M['freight_zero'])} dòng; phí ship > giá sản phẩm: "
                            f"{vn(M['freight_gt_price'])} dòng ({pct(M['freight_gt_price'], len(it))}).")
    p99 = it.price.quantile(0.99)
    X["order_items"].append(f"Giá > p99 ({vn(p99, 2)} BRL): {vn(int((it.price > p99).sum()))} dòng – giá trị lớn nhưng hợp lý "
                            f"(đồ điện tử, nội thất), không phải lỗi.")
    j = it.merge(od[["order_id", "order_purchase_timestamp"]], on="order_id")
    M["ship_limit_before_purchase"] = int((j.shipping_limit_date < j.order_purchase_timestamp).sum())
    X["order_items"].append(f"`shipping_limit_date` < ngày mua: {vn(M['ship_limit_before_purchase'])} dòng.")

    # ---- order_payments
    n_pa = len(pa)
    X["order_payments"].append("Phân bố `payment_type`: " + ", ".join(f"{k} {vn(v)} ({pct(v, n_pa)})" for k, v in pa.payment_type.value_counts().items()))
    M["pay_not_defined"] = int((pa.payment_type == "not_defined").sum())
    M["pay_value_zero"] = int((pa.payment_value == 0).sum())
    M["pay_inst_zero"] = int((pa.payment_installments == 0).sum())
    M["pay_inst_noncc"] = int(((pa.payment_installments > 1) & (pa.payment_type != "credit_card")).sum())
    X["order_payments"].append(f"`payment_value = 0`: {vn(M['pay_value_zero'])} dòng (loại: "
                               + ", ".join(f"{k} {v}" for k, v in pa[pa.payment_value == 0].payment_type.value_counts().items())
                               + f"); `payment_installments = 0`: {vn(M['pay_inst_zero'])}; trả góp >1 kỳ nhưng không phải thẻ tín dụng: {vn(M['pay_inst_noncc'])}.")
    ppo = pa.groupby("order_id").size()
    M["orders_multi_pay"] = int((ppo > 1).sum())
    sq = pa.groupby("order_id").payment_sequential.agg(["max", "size"])
    M["pay_seq_gap"] = int((sq["max"] != sq["size"]).sum())
    X["order_payments"].append(f"Đơn có >1 dòng thanh toán: {vn(M['orders_multi_pay'])}; `payment_sequential` bị đứt quãng: {vn(M['pay_seq_gap'])} đơn.")
    tot = pd.concat([(it.price + it.freight_value).groupby(it.order_id).sum().rename("items"),
                     pa.groupby("order_id").payment_value.sum().rename("paid")], axis=1).dropna()
    M["pay_mismatch"] = int(((tot["items"] - tot.paid).abs() > 1).sum())
    M["pay_mismatch_base"] = len(tot)
    X["order_payments"].append(f"Tổng thanh toán lệch tổng (price + freight) quá 1 BRL: {vn(M['pay_mismatch'])} / {vn(len(tot))} đơn "
                               f"(tổng price {vn(it.price.sum())} + freight {vn(it.freight_value.sum())} = {vn(it.price.sum() + it.freight_value.sum())} "
                               f"vs tổng payment {vn(pa.payment_value.sum())} BRL).")

    # ---- order_reviews
    n_rv = len(rv)
    X["order_reviews"].append("Phân bố `review_score`: " + ", ".join(f"{int(k)}★ {vn(v)} ({pct(v, n_rv, 1)})" for k, v in rv.review_score.value_counts().sort_index().items()))
    M["review_score_bad"] = int((~rv.review_score.isin([1, 2, 3, 4, 5])).sum())
    rid = rv.groupby("review_id").order_id.nunique()
    M["review_id_multi_order"] = int((rid > 1).sum())
    M["review_dup_ids"] = INFO["order_reviews"]["pk_dup_keys"]
    M["review_dup_rows"] = INFO["order_reviews"]["pk_dup_rows"]
    M["review_pair_dup"] = int(rv.duplicated(["review_id", "order_id"]).sum())
    rpo = rv.groupby("order_id").size()
    M["orders_multi_review"] = int((rpo > 1).sum())
    X["order_reviews"].append(f"`review_id` trùng: {vn(M['review_dup_ids'])} mã ({vn(M['review_dup_rows'])} dòng); "
                              f"1 review_id gắn với nhiều đơn khác nhau: {vn(M['review_id_multi_order'])} mã; "
                              f"cặp (review_id, order_id) trùng: {vn(M['review_pair_dup'])} → khóa thật là (review_id, order_id).")
    # Vì sao 1 review_id gắn nhiều đơn: so khách, nội dung review, thời điểm mua và người bán của các đơn đó
    dup = (rv[rv.review_id.isin(rid[rid > 1].index)]
           .merge(od[["order_id", "customer_id", "order_purchase_timestamp"]], on="order_id")
           .merge(cu[["customer_id", "customer_unique_id"]], on="customer_id"))
    dup["sellers"] = dup.order_id.map(it.groupby("order_id").seller_id.agg(frozenset))
    g = dup.groupby("review_id")
    n_dup = len(g)
    same_answer = (g[["customer_unique_id", "review_score", "review_comment_message", "review_creation_date",
                      "review_answer_timestamp"]].nunique() == 1).all(axis=1)
    span = g.order_purchase_timestamp.agg(lambda s: (s.max() - s.min()).total_seconds())
    multi_seller = g.sellers.agg(lambda x: len(frozenset().union(*x.dropna())) > 1)
    M["rdup_same_answer"], M["rdup_1min"] = int(same_answer.sum()), int((span <= 60).sum())
    M["rdup_multi_seller"], M["rdup_over_1day"] = int(multi_seller.sum()), int((span > 86400).sum())
    X["order_reviews"].append(
        f"Phân tích {vn(n_dup)} review_id gắn nhiều đơn: cùng 1 khách & cùng điểm, bình luận, ngày tạo, ngày trả lời: "
        f"{vn(M['rdup_same_answer'])}/{vn(n_dup)}; các đơn đặt cách nhau ≤ 1 phút: {vn(M['rdup_1min'])}; "
        f"các đơn do người bán khác nhau giao: {vn(M['rdup_multi_seller'])}; cách nhau > 1 ngày: {vn(M['rdup_over_1day'])} "
        f"(xa nhất {vn(span.max() / 86400)} ngày). → Suy luận: giỏ hàng nhiều người bán bị tách thành nhiều đơn nhưng khách chỉ nhận "
        f"**1 khảo sát cho cả lần mua**, câu trả lời được chép sang mọi đơn. Không phải lỗi nhập liệu (mô tả Kaggle không nói rõ điều này).")
    X["order_reviews"].append(f"Đơn có >1 review: {vn(M['orders_multi_review'])}.")
    j = rv.merge(od[["order_id", "order_purchase_timestamp"]], on="order_id")
    M["review_before_purchase"] = int((j.review_creation_date < j.order_purchase_timestamp.dt.normalize()).sum())
    M["answer_before_creation"] = int((rv.review_answer_timestamp < rv.review_creation_date).sum())
    X["order_reviews"].append(f"Review tạo trước ngày mua: {vn(M['review_before_purchase'])}; trả lời trước khi tạo review: {vn(M['answer_before_creation'])}.")
    X["order_reviews"].append(f"Có tiêu đề: {pct((rv.review_comment_title != '').sum(), n_rv, 1)}; có nội dung bình luận: "
                              f"{pct((rv.review_comment_message != '').sum(), n_rv, 1)} (tiếng Bồ Đào Nha).")

    # ---- customers
    M["cust_unique"] = cu.customer_unique_id.nunique()
    per_u = cu.groupby("customer_unique_id").customer_id.size()
    M["cust_repeat"] = int((per_u > 1).sum())
    M["cust_multi_zip"] = int((cu.groupby("customer_unique_id").customer_zip_code_prefix.nunique() > 1).sum())
    X["customers"].append(f"`customer_unique_id` khác nhau: {vn(M['cust_unique'])} (so với {vn(len(cu))} customer_id); "
                          f"khách mua ≥2 lần: {vn(M['cust_repeat'])} ({pct(M['cust_repeat'], M['cust_unique'])}).")
    X["customers"].append(f"Khách (unique_id) có nhiều zip khác nhau giữa các đơn (chuyển địa chỉ): {vn(M['cust_multi_zip'])} → cần quyết định SCD.")
    X["customers"].append("Top 5 bang: " + ", ".join(f"{k} {pct(v, len(cu), 1)}" for k, v in cu.customer_state.value_counts().head(5).items()))

    # ---- sellers
    X["sellers"].append("Top 5 bang: " + ", ".join(f"{k} {pct(v, len(se), 1)}" for k, v in se.seller_state.value_counts().head(5).items()))

    # ---- products
    pc = pr.product_category_name == ""
    M["prod_no_cat"] = int(pc.sum())
    same = (pr.loc[pc, ["product_name_lenght", "product_description_lenght", "product_photos_qty"]] == "").all(axis=1).sum()
    X["products"].append(f"Sản phẩm thiếu danh mục: {vn(M['prod_no_cat'])}; trong đó {vn(same)} dòng cũng thiếu luôn name/description/photos (thiếu cùng lúc).")
    dims = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
    for c in dims:
        pr[c] = num(pr[c])
    M["prod_dim_zero"] = int((pr[dims] == 0).any(axis=1).sum())
    M["prod_dim_null"] = int(pr[dims].isna().any(axis=1).sum())
    X["products"].append(f"Sản phẩm có khối lượng/kích thước = 0: {vn(M['prod_dim_zero'])}; thiếu khối lượng/kích thước: {vn(M['prod_dim_null'])}.")
    X["products"].append("Tên cột gốc sai chính tả: `product_name_lenght`, `product_description_lenght` (đúng: *length*).")
    M["n_categories"] = pr.loc[~pc, "product_category_name"].nunique()
    M["cat_no_translation"] = sorted(set(pr.loc[~pc, "product_category_name"]) - set(tr.product_category_name))
    M["cat_no_translation_rows"] = int(pr.product_category_name.isin(M["cat_no_translation"]).sum())
    X["products"].append(f"Số danh mục: {M['n_categories']}; danh mục không có bản dịch tiếng Anh: "
                         + ", ".join(f"`{c}`" for c in M["cat_no_translation"]) + f" ({vn(M['cat_no_translation_rows'])} sản phẩm).")

    # ---- geolocation
    zc = ge.groupby("geolocation_zip_code_prefix").size()
    M["geo_zip"] = len(zc)
    M["geo_dup_rows"] = INFO["geolocation"]["dup_rows"]
    X["geolocation"].append(f"Không có khóa: {vn(len(ge))} dòng cho {vn(len(zc))} zip → trung bình {vn(zc.mean(), 1)}, trung vị {vn(zc.median())}, "
                            f"tối đa {vn(zc.max())} dòng/zip. Dòng trùng hoàn toàn: {vn(M['geo_dup_rows'])} ({pct(M['geo_dup_rows'], len(ge))}).")
    out_bbox = ~ge.lat.between(*BR_LAT) | ~ge.lng.between(*BR_LNG)
    M["geo_out_bbox"] = int(out_bbox.sum())
    X["geolocation"].append(f"Tọa độ nằm ngoài lãnh thổ Brazil: {vn(M['geo_out_bbox'])} dòng "
                            f"(vd zip " + ", ".join(ge[out_bbox].geolocation_zip_code_prefix.head(3)) + ").")
    M["geo_multi_state"] = int((ge.groupby("geolocation_zip_code_prefix").geolocation_state.nunique() > 1).sum())
    ge["city_key"] = ge.geolocation_city.map(fold)
    M["geo_multi_city"] = int((ge.groupby("geolocation_zip_code_prefix").city_key.nunique() > 1).sum())
    X["geolocation"].append(f"Zip gắn với >1 bang: {vn(M['geo_multi_state'])}; zip gắn với >1 thành phố (sau khi bỏ dấu): {vn(M['geo_multi_city'])}.")

    # ---------------------------------------------------------------- toàn vẹn tham chiếu
    RI = [("orders", "customer_id", "customers", "customer_id"),
          ("order_items", "order_id", "orders", "order_id"),
          ("order_items", "product_id", "products", "product_id"),
          ("order_items", "seller_id", "sellers", "seller_id"),
          ("order_payments", "order_id", "orders", "order_id"),
          ("order_reviews", "order_id", "orders", "order_id"),
          ("products", "product_category_name", "category_translation", "product_category_name"),
          ("customers", "customer_zip_code_prefix", "geolocation", "geolocation_zip_code_prefix"),
          ("sellers", "seller_zip_code_prefix", "geolocation", "geolocation_zip_code_prefix")]
    ri_rows = []
    for c, cc, p, pcol in RI:
        s = T[c][cc]
        s = s[s != ""]
        orphan = ~s.isin(set(T[p][pcol]))
        M[f"orphan_{c}_{cc}"] = int(orphan.sum())
        ri_rows.append([f"`{c}.{cc}`", f"`{p}.{pcol}`", vn(len(s)), vn(int(orphan.sum())),
                        vn(s[orphan].nunique()), pct(orphan.sum(), len(s)),
                        ", ".join(f"`{cell(v, 20)}`" for v in s[orphan].unique()[:2]) or "–"])
    COVER = [("customers", "customer_id", "orders", "customer_id", "Khách hàng không có đơn"),
             ("orders", "order_id", "order_items", "order_id", "Đơn không có sản phẩm"),
             ("orders", "order_id", "order_payments", "order_id", "Đơn không có thanh toán"),
             ("orders", "order_id", "order_reviews", "order_id", "Đơn không có review"),
             ("products", "product_id", "order_items", "product_id", "Sản phẩm chưa từng bán"),
             ("sellers", "seller_id", "order_items", "seller_id", "Người bán chưa từng bán"),
             ("category_translation", "product_category_name", "products", "product_category_name", "Bản dịch danh mục không dùng tới")]
    cover_rows = []
    for p, pcol, c, cc, label in COVER:
        miss = ~T[p][pcol].isin(set(T[c][cc]))
        M[f"cover_{p}_{c}"] = int(miss.sum())
        extra = ""
        if p == "orders":
            extra = ", ".join(f"{k} {v}" for k, v in T["orders"][miss].order_status.value_counts().head(4).items())
        cover_rows.append([label, f"`{p}` ∉ `{c}`", vn(int(miss.sum())), pct(miss.sum(), len(miss)), extra or "–"])

    # ---------------------------------------------------------------- logic ngày trong orders
    P_, A, C, D, E = (od.order_purchase_timestamp, od.order_approved_at, od.order_delivered_carrier_date,
                      od.order_delivered_customer_date, od.order_estimated_delivery_date)
    dl = od.order_status == "delivered"
    days = (D - P_).dt.total_seconds() / 86400
    # estimated chỉ có phần ngày (00:00:00) → so theo ngày; so timestamp sẽ tính nhầm đơn giao đúng ngày dự kiến là trễ
    late = dl & D.notna() & (D.dt.normalize() > E)
    late_ts = dl & D.notna() & (D > E)
    n_dl = int(dl.sum())
    # (nhãn, điều kiện, chỉ xét đơn delivered?) – kiểm tra chỉ xét đơn delivered thì có thêm % trên đơn delivered
    DATE_CHECKS = [
        ("Duyệt đơn trước khi mua (`approved_at` < `purchase`)", A < P_, False),
        ("Giao cho vận chuyển trước khi mua (`carrier` < `purchase`)", C < P_, False),
        ("Giao cho vận chuyển trước khi duyệt (`carrier` < `approved_at`)", C < A, False),
        ("Khách nhận hàng trước khi mua (`delivered_customer` < `purchase`)", D < P_, False),
        ("Khách nhận hàng trước khi giao vận chuyển (`delivered_customer` < `carrier`)", D < C, False),
        ("Ngày dự kiến trước ngày mua (`estimated` < `purchase`)", E < P_.dt.normalize(), False),
        ("Trạng thái khác `delivered` nhưng CÓ `delivered_customer_date`", ~dl & D.notna(), False),
        ("Trạng thái `delivered` nhưng thiếu `delivered_customer_date`", dl & D.isna(), True),
        ("Trạng thái `delivered` nhưng thiếu `delivered_carrier_date`", dl & C.isna(), True),
        ("Trạng thái `delivered` nhưng thiếu `approved_at`", dl & A.isna(), True),
        ("Đơn delivered có thời gian giao > 60 ngày", dl & (days > 60), True),
        ("**Giao trễ**: ngày nhận > ngày dự kiến (so theo ngày)", late, True),
    ]
    date_rows = []
    for label, m, deliv_only in DATE_CHECKS:
        m = m.fillna(False)
        by = ", ".join(f"{k} {v}" for k, v in od[m].order_status.value_counts().head(3).items())
        date_rows.append([label, vn(int(m.sum())), pct(m.sum(), n_od),
                          pct(m.sum(), n_dl) if deliv_only else "–", by or "–"])
    M["date_carrier_before_purchase"] = int((C < P_).sum())
    M["date_delivered_no_date"] = int((dl & D.isna()).sum())
    M["date_nondelivered_with_date"] = int((~dl & D.notna()).sum())
    M["date_delivered_before_carrier"] = int((D < C).sum())
    M["date_carrier_before_approved"] = int((C < A).sum())
    M["late_rate"] = late.sum() / n_dl * 100
    M["late_rate_ts"] = late_ts.sum() / n_dl * 100
    dd = days[dl & D.notna()]

    # ---- hạn chế snapshot: thông tin xảy ra sau tháng mua (batch theo tháng mua sẽ chứa "thông tin tương lai")
    pm = P_.dt.to_period("M")
    after = lambda s: int((s.dt.to_period("M") > pm).sum())
    M["snap_approved_later"], M["snap_carrier_later"], M["snap_delivered_later"] = after(A), after(C), after(D)
    jr = rv.merge(od[["order_id", "order_purchase_timestamp"]], on="order_id")
    M["snap_review_later"] = int((jr.review_answer_timestamp.dt.to_period("M")
                                  > jr.order_purchase_timestamp.dt.to_period("M")).sum())
    M["snap_n_review"] = len(jr)
    open_st = ["shipped", "invoiced", "processing", "created", "approved"]
    op = od.order_status.isin(open_st)
    M["snap_open"] = int(op.sum())
    M["snap_open_old"] = int((op & (P_ < P_.max() - pd.Timedelta(days=90))).sum())
    M["snap_max_ts"] = max(P_.max(), A.max(), C.max(), D.max(), rv.review_answer_timestamp.max())
    null_matrix = od.assign(a=A.isna(), c=C.isna(), d=D.isna()).groupby("order_status").agg(
        don=("order_id", "size"), a=("a", "sum"), c=("c", "sum"), d=("d", "sum")).sort_values("don", ascending=False)

    # ---------------------------------------------------------------- đơn theo tháng
    month = P_.dt.to_period("M")
    rng = pd.period_range(month.min(), month.max(), freq="M")
    mc = pd.DataFrame({"all": month.value_counts(), "deliv": month[dl].value_counts(),
                       "cancel": month[od.order_status.isin(["canceled", "unavailable"])].value_counts()}
                      ).reindex(rng, fill_value=0).fillna(0).astype(int)
    peak = mc["all"].max()
    mc["cum"] = mc["all"].cumsum() / mc["all"].sum() * 100
    sparse = [str(m) for m, v in mc["all"].items() if v < 0.05 * peak]
    M["sparse_months"] = sparse
    in_trend = mc.loc[pd.Period(TREND_FROM):pd.Period(TREND_TO), "all"].sum()

    # ---------------------------------------------------------------- danh sách vấn đề
    zip_lead0 = sum(P[t][c].get("lead0", 0) for t, c in [("customers", "customer_zip_code_prefix"),
                    ("sellers", "seller_zip_code_prefix"), ("geolocation", "geolocation_zip_code_prefix")])
    city_cols = [("customers", "customer_city"), ("sellers", "seller_city"), ("geolocation", "geolocation_city")]
    city_variant = ", ".join(f"{t}: {vn(P[t][c]['variants'][0])} tên / {vn(P[t][c]['variants'][1])} dòng" for t, c in city_cols)
    city_extra = {"có chữ hoa": "upper", "ký tự lạ (số, dấu câu)": "odd", "lỗi encoding": "mojibake",
                  "dấu tổ hợp chưa chuẩn hóa NFC": "nfc", "khoảng trắng đầu/cuối": "ws"}
    city_extra = "; ".join(f"{lbl}: {vn(n)} dòng" for lbl, key in city_extra.items()
                           if (n := sum(P[t][c].get(key, 0) for t, c in city_cols)))
    rv_txt = [P["order_reviews"][c] for c in ["review_comment_title", "review_comment_message"]]
    date_only = [(c, p["dt"]) for t in TABLES for c, p in P[t].items()
                 if p.get("dt") and p["dt"]["ok"] and p["dt"]["midnight"] / p["dt"]["ok"] >= 0.99]
    ISSUES = []

    def issue(level, title, evidence, fix):
        ISSUES.append((level, title, evidence, fix))

    issue(1, "Nhân dòng (fan-out) khi JOIN bảng con vào orders",
          f"{vn(M['orders_multi_item'])} đơn có >1 item, {vn(M['orders_multi_pay'])} đơn có >1 dòng thanh toán, "
          f"{vn(M['orders_multi_review'])} đơn có >1 review",
          "Fact chính ở grain *1 item / 1 đơn*; gom payments & reviews về 1 dòng/đơn trước khi join; "
          "doanh thu tính từ order_items, không SUM sau khi join items × payments.")
    issue(1, "`customer_id` không phải khách hàng thật",
          f"{vn(len(cu))} customer_id nhưng chỉ {vn(M['cust_unique'])} customer_unique_id; mỗi customer_id chỉ có {M['cust_per_order_max']} đơn",
          "`dim_customer` dựng theo `customer_unique_id`; nếu không, tỉ lệ khách quay lại luôn = 0%.")
    issue(1, "Dữ liệu đầu/cuối kỳ rất thưa, có tháng trống",
          "Tháng < 5% tháng cao nhất: " + ", ".join(f"{m} ({mc.loc[pd.Period(m), 'all']})" for m in sparse),
          f"Phân tích xu hướng trong {TREND_FROM} → {TREND_TO} (giữ {pct(in_trend, n_od, 1)} số đơn); ghi rõ giới hạn này trên dashboard.")
    issue(1, "`review_id` không duy nhất",
          f"{vn(M['review_dup_ids'])} review_id lặp ({vn(M['review_dup_rows'])} dòng); {vn(M['review_id_multi_order'])} review_id gắn với nhiều đơn. "
          f"{vn(M['rdup_same_answer'])} trường hợp là cùng 1 câu trả lời của cùng 1 khách chép sang nhiều đơn; "
          f"{vn(M['rdup_1min'])} trường hợp các đơn đặt cách nhau ≤ 1 phút – 1 khảo sát cho cả giỏ hàng bị tách đơn",
          "Khóa `fact_review` = (review_id, order_id); không đặt PK/unique test chỉ trên review_id. "
          "KPI *số lượt đánh giá* dùng COUNT(DISTINCT review_id); KPI điểm theo đơn/người bán giữ 1 dòng/đơn.")
    issue(1, "Mã zip mất số 0 đầu nếu đọc kiểu số",
          f"{vn(zip_lead0)} dòng zip bắt đầu bằng 0 (customers + sellers + geolocation); pandas mặc định đọc thành int64",
          "Ép kiểu CHAR(5) ngay từ staging (Mage dtype=str); join zip bằng chuỗi.")
    issue(1, "geolocation trùng lặp & nhiều tọa độ cho 1 zip",
          f"{vn(M['geo_dup_rows'])} dòng trùng hoàn toàn; {vn(len(ge))} dòng cho {vn(M['geo_zip'])} zip; "
          f"{vn(M['geo_multi_state'])} zip thuộc >1 bang",
          "Không join trực tiếp; gom 1 dòng/zip (trung bình lat/lng, bang/thành phố phổ biến nhất).")
    issue(2, "Ngày tháng trong orders mâu thuẫn với trạng thái",
          f"`delivered` thiếu ngày nhận: {M['date_delivered_no_date']}; khác delivered nhưng có ngày nhận: {M['date_nondelivered_with_date']}; "
          f"giao vận chuyển trước khi mua: {M['date_carrier_before_purchase']}; giao vận chuyển trước khi duyệt: {vn(M['date_carrier_before_approved'])}; "
          f"nhận hàng trước khi giao vận chuyển: {M['date_delivered_before_carrier']}",
          "Gắn cờ `is_date_valid` ở staging/dbt, loại các dòng này khỏi KPI thời gian giao & tỉ lệ trễ; thêm dbt test.")
    issue(2, "Đơn thiếu dữ liệu ở bảng con",
          f"Không có item: {M['cover_orders_order_items']}; không có thanh toán: {M['cover_orders_order_payments']}; "
          f"không có review: {M['cover_orders_order_reviews']}",
          "Dùng LEFT JOIN; KPI điểm review chỉ tính trên đơn có review; đơn không item không vào fact_order_item.")
    issue(2, "Sản phẩm thiếu danh mục / danh mục thiếu bản dịch",
          f"{vn(M['prod_no_cat'])} sản phẩm không có danh mục; {len(M['cat_no_translation'])} danh mục không có bản dịch "
          f"({', '.join(M['cat_no_translation'])})",
          "Gán `unknown`; bổ sung bản dịch bằng dbt seed.")
    issue(2, "Tổng thanh toán ≠ tổng tiền hàng + phí ship",
          f"{vn(M['pay_mismatch'])} / {vn(M['pay_mismatch_base'])} đơn lệch > 1 BRL (lãi trả góp, voucher...)",
          "KPI doanh thu lấy từ order_items; payment chỉ dùng phân tích phương thức thanh toán.")
    issue(2, "Tên thành phố nhiều cách viết",
          f"{city_variant}; {city_extra}",
          "Lưu NVARCHAR; chuẩn hóa ở dbt: bỏ dấu (`COLLATE Latin1_General_CI_AI` hoặc TRANSLATE), LOWER, TRIM, gộp khoảng trắng; "
          "ưu tiên phân tích theo bang.")
    issue(2, "Khách thay đổi địa chỉ giữa các đơn",
          f"{vn(M['cust_multi_zip'])} customer_unique_id có >1 zip",
          "Chọn SCD: type 1 (lấy địa chỉ đơn gần nhất) hoặc lưu địa chỉ theo đơn trong fact.")
    issue(2, "Zip của khách/người bán không có trong geolocation",
          f"customers: {vn(M['orphan_customers_customer_zip_code_prefix'])} dòng; sellers: {vn(M['orphan_sellers_seller_zip_code_prefix'])} dòng",
          "LEFT JOIN, tọa độ để NULL; bản đồ vẽ theo bang thay vì điểm.")
    issue(2, "Giá trị thanh toán bất thường",
          f"payment_value = 0: {M['pay_value_zero']}; payment_type = not_defined: {M['pay_not_defined']}; installments = 0: {M['pay_inst_zero']}",
          "Map `not_defined` → `unknown`; installments 0 → 1; giữ lại nhưng gắn cờ.")
    issue(3, "Tọa độ ngoài lãnh thổ Brazil", f"{vn(M['geo_out_bbox'])} dòng geolocation",
          "Loại khi gom tọa độ theo zip.")
    issue(3, "Kích thước/khối lượng sản phẩm = 0 hoặc thiếu",
          f"= 0: {M['prod_dim_zero']} sản phẩm; thiếu: {M['prod_dim_null']} sản phẩm", "Đổi 0 → NULL; không dùng cho KPI chính.")
    issue(3, "Tên cột sai chính tả", "`product_name_lenght`, `product_description_lenght`", "Đổi tên ở model stg_products.")
    issue(3, "Bình luận review có xuống dòng bên trong ô",
          f"{vn(P['order_reviews']['review_comment_message'].get('newline', 0))} dòng; file có {vn(sum(1 for _ in open(RAW / TABLES['order_reviews'][0], encoding='utf-8')))} dòng vật lý cho {vn(n_rv)} bản ghi",
          "Nạp bằng CSV parser chuẩn (pandas, hoặc `BULK INSERT ... WITH (FORMAT = 'CSV', CODEPAGE = '65001')`), "
          "không đọc theo từng dòng; cột đích NVARCHAR(MAX).")
    issue(3, "Cột ngày chỉ chứa phần ngày (giờ = 00:00:00)",
          "; ".join(f"`{c}` ({pct(d['midnight'], d['ok'], 1)})" for c, d in date_only)
          + ". Phần còn lại là 01:00:00 ngày 2017-10-15 – ngày Brazil chuyển giờ mùa hè (không tồn tại mốc 00:00)",
          "Ép kiểu DATE thay vì DATETIME2; so sánh với ngày dự kiến theo ngày, không theo giờ.")
    issue(3, "Review có ngày bất thường",
          f"Review tạo trước ngày mua: {M['review_before_purchase']}",
          "Gắn cờ, không dùng cho KPI thời gian phản hồi review.")
    issue(3, "Nội dung review có khoảng trắng thừa / giá trị giả-NULL",
          f"Khoảng trắng đầu/cuối: {vn(sum(p.get('ws', 0) for p in rv_txt))} dòng; giá trị như `?`, `-`, `N/a` thay cho rỗng",
          "TRIM và đổi chuỗi giả-NULL thành NULL ở stg_order_reviews (phục vụ phần AI phân tích bình luận).")
    issue(3, "`payment_sequential` không liên tục trong đơn", f"{vn(M['pay_seq_gap'])} đơn",
          "Không dùng payment_sequential để đếm số lần thanh toán; đếm số dòng.")
    bom_files = [i["file"] for i in INFO.values() if i["bom"]]
    if bom_files:
        issue(3, "File có BOM UTF-8", ", ".join(bom_files), "Đọc bằng encoding `utf-8-sig`, nếu không tên cột đầu bị dính ký tự lạ.")

    # ---------------------------------------------------------------- ghi markdown
    L = ["# Khảo sát dữ liệu (Data Profiling) – Olist", "",
         f"> File sinh tự động bởi `scripts/profile_olist.py` lúc {datetime.now():%d/%m/%Y %H:%M}. **Không sửa tay** – sửa script rồi chạy lại.",
         "> Toàn bộ file được đọc dạng chuỗi; ô rỗng = NULL. Số liệu ở đây là dữ liệu gốc, chưa làm sạch.", "",
         "## 1. Tổng quan", ""]
    L += table(["Bảng", "File", "Số dòng", "Số cột", "Dung lượng (MB)", "Dòng trùng hoàn toàn", "Khóa chính dự kiến", "Dòng trùng khóa"],
               [[f"`{n}`", i["file"], vn(i["rows"]), i["cols"], vn(i["mb"], 1), vn(i["dup_rows"]),
                 ", ".join(i["pk"]) if i["pk"] else "(không có)",
                 f"{vn(i['pk_dup_rows'])} dòng / {vn(i['pk_dup_keys'])} mã" if i["pk"] else "–"] for n, i in INFO.items()])
    for k, (name, i) in enumerate(INFO.items(), start=2):
        L += [f"## {k}. Bảng `{name}`", "", f"File `{i['file']}` – {vn(i['rows'])} dòng × {i['cols']} cột"
              + (" – **có BOM UTF-8**" if i["bom"] else "") + ".", ""]
        if i["missing"] or i["extra"]:
            L += [f"⚠️ Cột thiếu: {i['missing']}; cột lạ: {i['extra']}", ""]
        L += ["**Thống kê theo cột**", ""]
        L += table(["Cột", "Kiểu nghiệp vụ", "Kiểu pandas mặc định", "% NULL", "Số giá trị khác nhau", "Ví dụ", "Vấn đề phát hiện"],
                   [[f"`{c}`", p["kind"], p["pandas"], pct(p["null"], i["rows"]), vn(p["distinct"]), f"`{cell(p['example'], 35)}`",
                     "<br>".join(cell(x, 400) for x in p["issues"]) or "–"] for c, p in P[name].items()])
        dts = [(c, p["dt"]) for c, p in P[name].items() if "dt" in p]
        if dts:
            L += ["**Cột ngày giờ**", ""]
            L += table(["Cột", "Min", "Max", "Sai định dạng", "% giá trị có giờ = 00:00:00"],
                       [[f"`{c}`", d["min"], d["max"], vn(d["bad"]), pct(d["midnight"], d["ok"], 1)] for c, d in dts])
        nums = [(c, p["num"]) for c, p in P[name].items() if "num" in p]
        if nums:
            L += ["**Cột số**", ""]
            L += table(["Cột", "Min", "Trung vị", "p99", "Max", "Số âm", "Bằng 0"],
                       [[f"`{c}`", vn(d["min"], 2), vn(d["p50"], 2), vn(d["p99"], 2), vn(d["max"], 2), vn(d["neg"]), vn(d["zero"])] for c, d in nums])
        if X[name]:
            L += ["**Kiểm tra nghiệp vụ**", ""] + [f"- {x}" for x in X[name]] + [""]

    k = len(INFO) + 2
    L += [f"## {k}. Toàn vẹn tham chiếu", "", "**Dòng mồ côi** (giá trị ở bảng con không tìm thấy ở bảng cha):", ""]
    L += table(["Bảng con", "Bảng cha", "Số dòng kiểm tra", "Dòng mồ côi", "Giá trị mồ côi khác nhau", "%", "Ví dụ"], ri_rows)
    L += ["**Độ phủ** (bản ghi cha không có bản ghi con):", ""]
    L += table(["Kiểm tra", "Điều kiện", "Số dòng", "%", "Theo trạng thái đơn"], cover_rows)

    k += 1
    L += [f"## {k}. Logic ngày trong `orders`", ""]
    L += table(["Kiểm tra", "Số đơn", f"% trên tổng đơn (n = {vn(n_od)})", f"% trên đơn delivered (n = {vn(n_dl)})",
                "Trạng thái đơn chiếm nhiều nhất"], date_rows)
    L += [f"Hai cột % khác mẫu số: VD giao trễ = {vn(int(late.sum()))} đơn là {pct(late.sum(), n_od)} *tổng đơn* "
          f"nhưng {pct(late.sum(), n_dl)} *đơn delivered*. "
          "**KPI tỉ lệ giao trễ dùng mẫu số là đơn delivered.** Cột thứ hai chỉ điền cho kiểm tra giới hạn trong đơn delivered.", "",
          f"- Thời gian giao (đơn delivered có ngày nhận): TB {vn(dd.mean(), 1)} ngày, trung vị {vn(dd.median(), 1)}, "
          f"p95 {vn(dd.quantile(.95), 1)}, max {vn(dd.max(), 1)} ngày.",
          f"- Tỉ lệ giao trễ (so theo ngày, trên {vn(n_dl)} đơn delivered): **{vn(M['late_rate'], 2)}%**. Nếu so cả giờ (cách nhiều notebook Kaggle dùng) "
          f"sẽ ra {vn(M['late_rate_ts'], 2)}% – sai, vì `order_estimated_delivery_date` luôn là 00:00:00 nên đơn giao đúng ngày dự kiến bị tính là trễ.", "",
          "**Ma trận NULL theo trạng thái đơn** (số đơn thiếu từng mốc thời gian):", ""]
    L += table(["order_status", "Số đơn", "Thiếu approved_at", "Thiếu delivered_carrier", "Thiếu delivered_customer"],
               [[s, vn(r.don), vn(r.a), vn(r.c), vn(r.d)] for s, r in null_matrix.iterrows()])

    k += 1
    L += [f"## {k}. Số đơn theo tháng (`order_purchase_timestamp`)", "",
          "Dùng để quyết định chia batch cho Incremental Load. Tháng đánh dấu ⚠️ có số đơn < 5% tháng cao nhất.", ""]
    L += table(["Tháng", "Tổng đơn", "Delivered", "Canceled + unavailable", "% lũy kế", "Ghi chú"],
               [[str(m), vn(r["all"]), vn(r.deliv), vn(r.cancel), vn(r.cum, 1) + "%",
                 "⚠️ trống" if r["all"] == 0 else ("⚠️ thưa" if str(m) in sparse else ("cao nhất" if r["all"] == peak else ""))]
                for m, r in mc.iterrows()])
    L += [f"- Khoảng {TREND_FROM} → {TREND_TO}: {vn(in_trend)} đơn ({pct(in_trend, n_od, 1)}).", ""]

    k += 1
    L += [f"## {k}. Vấn đề cần làm sạch (xếp theo mức độ ảnh hưởng)", "",
          "- **Cao**: làm sai KPI chính, sai khóa hoặc sai kết quả JOIN nếu không xử lý.",
          "- **Trung bình**: ảnh hưởng một nhóm phân tích cụ thể.",
          "- **Thấp**: ít dòng, hoặc chỉ cần lưu ý khi nạp dữ liệu.", ""]
    names = {1: "Cao", 2: "Trung bình", 3: "Thấp"}
    L += table(["#", "Mức độ", "Vấn đề", "Bằng chứng", "Đề xuất xử lý"],
               [[n, names[lv], t, ev, fx] for n, (lv, t, ev, fx) in enumerate(sorted(ISSUES, key=lambda x: x[0]), start=1)])

    k += 1
    L += [f"## {k}. Hạn chế khi mô phỏng incremental", "",
          f"Dataset là **ảnh chụp cuối kỳ** (mốc thời gian muộn nhất trong dữ liệu: {M['snap_max_ts']}): mỗi đơn chỉ có 1 dòng mang "
          "trạng thái *cuối cùng*, không có lịch sử thay đổi. Vì vậy `order_status` và các mốc giao hàng là trạng thái **tại lúc chụp**, "
          "không phải tại thời điểm mua. Khi chia batch theo tháng mua (mục 13), mỗi batch đã chứa sẵn thông tin chỉ có được về sau:", ""]
    L += table(["Thông tin", "Số dòng xảy ra ở tháng SAU tháng mua", "%"],
               [["`order_approved_at`", vn(M["snap_approved_later"]), pct(M["snap_approved_later"], n_od, 1)],
                ["`order_delivered_carrier_date`", vn(M["snap_carrier_later"]), pct(M["snap_carrier_later"], n_od, 1)],
                ["`order_delivered_customer_date`", vn(M["snap_delivered_later"]), pct(M["snap_delivered_later"], n_od, 1)],
                ["`review_answer_timestamp` (order_reviews)", vn(M["snap_review_later"]), pct(M["snap_review_later"], M["snap_n_review"], 1)]])
    L += [f"- Đơn chưa hoàn tất (`{'`, `'.join(open_st)}`): {vn(M['snap_open'])} đơn; trong đó {vn(M['snap_open_old'])} đơn mua trước ngày mua cuối cùng "
          f"({P_.max():%Y-%m-%d}) hơn 90 ngày → không phải \"đang xử lý\" mà là bị kẹt ở trạng thái đó tại lúc chụp.",
          "",
          "**Hệ quả**",
          "- Chia batch theo tháng mua chỉ mô phỏng được **thêm đơn mới (insert-only)**: đơn đã nạp không bao giờ được batch sau cập nhật "
          "trạng thái, nên không thể hiện được upsert / thay đổi trạng thái trên dữ liệu gốc.",
          "- KPI tính tại một batch giữa kỳ (VD tỉ lệ giao trễ của tháng mới nhất) đã \"biết trước\" kết quả giao → đầy đủ hơn thực tế ở thời điểm đó.",
          "- Không phân tích được thời gian đơn nằm ở từng trạng thái (không có lịch sử trạng thái).",
          "",
          "**Hướng xử lý (nhóm chọn 1)**",
          "1. *Đơn giản*: chấp nhận incremental = thêm đơn mới theo tháng mua, ghi rõ hạn chế này trong báo cáo.",
          "2. *Mô phỏng cập nhật*: khi tạo batch tháng T, ẩn các mốc xảy ra sau cuối tháng T (để NULL, lùi `order_status` về trạng thái "
          "tương ứng, VD `shipped`); batch sau gửi lại các đơn đó với thông tin mới → pipeline phải MERGE theo `order_id`. "
          "Trạng thái lùi lại là suy diễn, cần ghi rõ đây là dữ liệu mô phỏng.", ""]

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\nĐã ghi {OUT.relative_to(ROOT)} ({len(ISSUES)} vấn đề).")


if __name__ == "__main__":
    main()
