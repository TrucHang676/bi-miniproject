"""
Chia dữ liệu Olist thành các batch để mô phỏng Full Load + Incremental Load  –  task BS-19.

Cách chạy (từ thư mục bi-miniproject/, ~15 giây):
    docker compose exec mage python scripts/split_batches.py     # không cần cài Python trên Windows
    py scripts/split_batches.py                                   # hoặc Python trên máy (cần pandas)

Đọc data/raw/, ghi ra data/batches/<batch>/<bảng>.csv + manifest.csv (không commit – chạy lại là sinh lại
y hệt từng byte, kể cả giữa Windows và container). Định dạng file: data/batches/README.md.
Quy tắc chia batch: docs/decisions.md D5, D6, D8 (phương án B):
  1. đơn vào batch theo tháng mua; 2. bảng con đi theo đơn, bảng tham chiếu vào FULL;
  3. "ảnh chụp" đơn tại cutoff mỗi batch, đơn cũ có thay đổi được gửi lại; 4. review theo tháng trả lời;
  5. ghi file; 6. đọc lại file, phát lại 10 batch và tự kiểm tra 9 điều (thoát mã 1 nếu có FAIL).
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "batches"

FILES = {  # 8 bảng nạp vào staging (geolocation không nạp)
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Các batch theo thứ tự chạy và mốc cắt (cutoff) của từng batch – D6, D8.
# Batch chỉ chứa những gì đã xảy ra TRƯỚC cutoff của nó; batch cuối không cắt (None).
BATCHES = [
    ("FULL", "2018-01-01"),
    ("2018-01", "2018-02-01"),
    ("2018-02", "2018-03-01"),
    ("2018-03", "2018-04-01"),
    ("2018-04", "2018-05-01"),
    ("2018-05", "2018-06-01"),
    ("2018-06", "2018-07-01"),
    ("2018-07", "2018-08-01"),
    ("2018-08", "2018-09-01"),
    ("2018-09+", None),
]
BATCH_IDS = [b for b, _ in BATCHES]
TRANSACTION_TABLES = ["orders", "order_items", "order_payments", "order_reviews", "customers"]  # mọi batch
REFERENCE_TABLES = ["products", "sellers", "category_translation"]                               # chỉ FULL

PK = {  # khóa chính (D1) – MERGE theo các cột này
    "orders": ["order_id"],
    "order_items": ["order_id", "order_item_id"],
    "order_payments": ["order_id", "payment_sequential"],
    "order_reviews": ["review_id", "order_id"],
    "customers": ["customer_id"],
    "sellers": ["seller_id"],
    "products": ["product_id"],
    "category_translation": ["product_category_name"],
}
FK = [  # khóa ngoại bắt buộc (D2): (bảng con, cột, bảng cha, cột)
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("order_payments", "order_id", "orders", "order_id"),
    ("order_reviews", "order_id", "orders", "order_id"),
]
# Mốc phải xảy ra TRƯỚC cutoff của batch chứa nó (bỏ qua shipping_limit_date, order_estimated_delivery_date:
# là hạn chót / ngày dự kiến, biết ngay lúc mua)
NO_FUTURE = {
    "orders": ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
               "order_delivered_customer_date"],
    "order_reviews": ["review_answer_timestamp"],
}
SEQ = {b: i for i, b in enumerate(BATCH_IDS)}        # thứ tự chạy: FULL = 0 ... 2018-09+ = 9

# Mốc thời gian của đơn có thể "chưa xảy ra" tại cutoff -> bị che (để trống) trong ảnh chụp (D8)
ORDER_EVENTS = ["order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date"]
# Thứ tự vòng đời đơn – ảnh chụp không được vượt quá trạng thái gốc (D8)
STATUS_RANK = {"created": 0, "approved": 1, "invoiced": 2, "processing": 3, "shipped": 4, "delivered": 5}
EXAMPLE_ORDER = "82a35d13f3b95427d47aa11e4afde83b"   # đơn ví dụ trong D8 – in ra để đối chiếu


def load_raw():
    """Đọc 8 file CSV dạng chuỗi nguyên bản (giữ số 0 đầu của zip, ô trống = "")."""
    return {t: pd.read_csv(RAW / f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            for t, f in FILES.items()}


def to_ts(s):
    """Chuỗi -> Timestamp; ô trống -> NaT."""
    return pd.to_datetime(s.where(s != ""))


def batch_of(ts):
    """Batch chứa mốc thời gian ts: batch đầu tiên có cutoff > ts (khoảng nửa mở [LSET, CET) – D4).
    Mốc từ cutoff cuối (2018-09-01) trở đi rơi vào batch cuối."""
    edges = [pd.Timestamp.min] + [pd.Timestamp(c) for _, c in BATCHES[:-1]] + [pd.Timestamp.max]
    return pd.cut(ts, bins=edges, labels=BATCH_IDS, right=False)


def follow_first_batch(T, first_batch):
    """Bảng con đi theo batch đầu tiên của đơn, mỗi dòng gửi đúng 1 lần (D5):
    order_items, order_payments theo order_id; customers theo customer_id (mỗi đơn 1 customer_id).
    Bảng tham chiếu products, sellers, category_translation nạp toàn bộ ở FULL (D3).
    Trả về {bảng: DataFrame các dòng cần gửi, thêm cột batch_id}."""
    od = T["orders"]
    by_order = pd.Series(first_batch.values, index=od.order_id)
    by_customer = pd.Series(first_batch.values, index=od.customer_id)
    sent = {}
    for t, key, lookup in [("order_items", "order_id", by_order),
                           ("order_payments", "order_id", by_order),
                           ("customers", "customer_id", by_customer)]:
        d = T[t].copy()
        d["batch_id"] = d[key].map(lookup)
        if d.batch_id.isna().any():
            sys.exit(f"LỖI {t}: {d.batch_id.isna().sum()} dòng không tìm thấy đơn tương ứng")
        sent[t] = d
    for t in REFERENCE_TABLES:
        sent[t] = T[t].assign(batch_id="FULL")
    return sent


def snapshot(od, events, cutoff):
    """Ảnh chụp toàn bộ đơn tại cutoff (D8 mục 2) – "lúc đó hệ thống biết gì về đơn này?".
    - order_approved_at, order_delivered_carrier_date, order_delivered_customer_date: giữ nếu < cutoff,
      ngược lại để trống (chưa xảy ra).
    - order_status = mốc muộn nhất đã xảy ra; canceled / unavailable giữ từ đầu (nguồn không có ngày hủy);
      đơn gốc kẹt ở invoiced / processing giữ nguyên khi đã duyệt; không vượt quá trạng thái gốc.
    cutoff = None (batch cuối, đối soát): trả về đúng trạng thái gốc."""
    snap = od.copy()
    if cutoff is None:
        return snap
    c = pd.Timestamp(cutoff)
    seen = {col: events[col] < c for col in ORDER_EVENTS}      # ô trống (NaT) < c -> False
    for col in ORDER_EVENTS:
        snap.loc[~seen[col], col] = ""

    orig = od.order_status
    derived = pd.Series(np.select(
        [seen["order_delivered_customer_date"] & (orig == "delivered"),
         seen["order_delivered_carrier_date"],
         seen["order_approved_at"]],
        ["delivered", "shipped", "approved"], default="created"), index=od.index)
    keep_orig = (orig.isin(["canceled", "unavailable"])
                 | (orig.isin(["invoiced", "processing"]) & (derived != "created"))
                 | (derived.map(STATUS_RANK) > orig.map(STATUS_RANK)))
    snap["order_status"] = orig.where(keep_orig, derived)
    return snap


def order_versions(od, first_batch):
    """Các dòng orders gửi ở từng batch (D8 mục 3): đơn MỚI (batch đầu tiên của đơn) + đơn CŨ có ảnh chụp
    khác ảnh chụp ở batch trước (có mốc mới rơi vào tháng này). Cột _new: True = đơn mới, False = gửi lại."""
    events = {col: to_ts(od[col]) for col in ORDER_EVENTS}
    seq = first_batch.map(SEQ)
    compare = ["order_status"] + ORDER_EVENTS
    parts, prev = [], None
    for i, (b, cutoff) in enumerate(BATCHES):
        snap = snapshot(od, events, cutoff)
        is_new = seq == i
        changed = (seq < i) & (snap[compare] != prev[compare]).any(axis=1) if prev is not None else False
        parts.append(snap[is_new | changed].assign(batch_id=b, _new=is_new[is_new | changed]))
        prev = snap
    return pd.concat(parts, ignore_index=True)


def review_batches(T, first_batch):
    """Review gửi ở batch chứa review_answer_timestamp (lúc khách trả lời – D8 mục 4); nếu batch đó sớm hơn
    batch đầu tiên của đơn thì dời về batch đầu tiên của đơn (= batch muộn hơn trong hai batch).
    Mỗi review gửi đúng 1 lần (chỉ INSERT). Cột _order_seq: thứ tự batch đầu tiên của đơn (để thống kê)."""
    rv = T["order_reviews"].copy()
    answer_seq = batch_of(to_ts(rv.review_answer_timestamp)).astype(str).map(SEQ)
    order_seq = rv.order_id.map(pd.Series(first_batch.map(SEQ).values, index=T["orders"].order_id))
    if order_seq.isna().any():
        sys.exit(f"LỖI order_reviews: {order_seq.isna().sum()} review không tìm thấy đơn tương ứng")
    seq = np.maximum(answer_seq, order_seq)
    rv["batch_id"] = seq.map(dict(enumerate(BATCH_IDS)))
    rv["_order_seq"] = order_seq
    rv["_moved"] = answer_seq < order_seq
    return rv


def write_batches(T, sent):
    """Ghi data/batches/<batch_id>/<bảng>.csv + data/batches/manifest.csv.
    - Mỗi batch: đủ 5 file bảng giao dịch (kể cả 0 dòng – chỉ có tiêu đề); FULL thêm 3 file bảng tham chiếu.
    - Cột = cột gốc của CSV + batch_id; giá trị giữ nguyên chuỗi gốc; ô trống = NULL; UTF-8, xuống dòng LF.
    - manifest.csv: 1 dòng / batch theo thứ tự chạy – lset, cet, số dòng từng bảng, số đơn mới / gửi lại.
    Xóa thư mục batch cũ trước khi ghi -> chạy lại luôn ra kết quả y hệt. Trả về DataFrame manifest."""
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (b, cutoff) in enumerate(BATCHES):
        folder = OUT / b
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        tables = TRANSACTION_TABLES + (REFERENCE_TABLES if b == "FULL" else [])
        lset = "" if i == 0 else f"{BATCHES[i - 1][1]} 00:00:00"
        row = {"seq": i + 1, "batch_id": b, "load_type": "FULL" if b == "FULL" else "INCREMENTAL",
               "lset": lset, "cet": f"{cutoff} 00:00:00" if cutoff else ""}
        for t in FILES:
            part = sent[t][sent[t].batch_id == b]
            if t in tables:
                part[list(T[t].columns) + ["batch_id"]].to_csv(
                    folder / f"{t}.csv", index=False, encoding="utf-8", lineterminator="\n")
            row[t] = len(part)
        o = sent["orders"]
        row["orders_new"] = int(((o.batch_id == b) & o._new).sum())
        row["orders_resent"] = row["orders"] - row["orders_new"]
        rows.append(row)
    manifest = pd.DataFrame(rows)
    manifest.to_csv(OUT / "manifest.csv", index=False, encoding="utf-8", lineterminator="\n")
    return manifest


def verify_batches(T, manifest):
    """Đọc LẠI các file trong data/batches/ (như Mage sẽ đọc), phát lại 10 batch theo thứ tự rồi kiểm tra.
    Trả về DataFrame (kiem_tra, ket_qua PASS/FAIL, chi_tiet)."""
    results = []

    def check(name, ok, detail=""):
        results.append({"kiem_tra": name, "ket_qua": "PASS" if ok else "FAIL", "chi_tiet": detail})

    # Đọc lại toàn bộ file, gắn thứ tự batch (_seq)
    B, missing = {}, []
    for t in FILES:
        parts = []
        for b in BATCH_IDS:
            path = OUT / b / f"{t}.csv"
            if path.exists():
                parts.append(pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
                             .assign(_seq=SEQ[b]))
            elif t in TRANSACTION_TABLES or b == "FULL":
                missing.append(f"{b}/{t}.csv")
        B[t] = pd.concat(parts, ignore_index=True)
    check("Đủ file trong mọi thư mục batch", not missing, ", ".join(missing))

    m = manifest.set_index("batch_id")
    bad = [f"{b}/{t}" for t in FILES for b in BATCH_IDS
           if (B[t].batch_id == b).sum() != m.loc[b, t] or (B[t]._seq != B[t].batch_id.map(SEQ)).any()]
    check("Số dòng mỗi file khớp manifest.csv", not bad, ", ".join(bad[:5]))

    # 1 file không được trùng khóa (MERGE sẽ lỗi nếu 1 khóa xuất hiện 2 lần trong cùng nguồn)
    dup = {t: int(d.duplicated(PK[t] + ["_seq"]).sum()) for t, d in B.items()}
    check("Không trùng khóa chính trong cùng 1 file", not any(dup.values()),
          ", ".join(f"{t} {n}" for t, n in dup.items() if n))

    # Bảng ngoài orders: mỗi dòng chỉ gửi 1 lần (D5) -> chỉ INSERT
    resent = {t: int(d.duplicated(PK[t]).sum()) for t, d in B.items() if t != "orders"}
    check("Bảng con / tham chiếu: mỗi dòng chỉ gửi 1 lần", not any(resent.values()),
          ", ".join(f"{t} {n}" for t, n in resent.items() if n))

    # Không biết trước tương lai: mọi mốc trong batch < cutoff của batch đó (batch cuối không cắt)
    cut = pd.Series({SEQ[b]: pd.Timestamp(c) for b, c in BATCHES if c})
    future = []
    for t, cols in NO_FUTURE.items():
        d = B[t]
        c = d._seq.map(cut)
        for col in cols:
            n = int((to_ts(d[col]) >= c).sum())        # NaT / batch cuối (cutoff NaT) -> False
            if n:
                future.append(f"{t}.{col} {n}")
    check("Không batch nào chứa mốc xảy ra sau cutoff của nó", not future, ", ".join(future))

    # Khóa ngoại: dòng con không bao giờ đến trước dòng cha (so batch xuất hiện đầu tiên)
    fk_bad = []
    for child, col, parent, pcol in FK:
        first_parent = B[parent].groupby(pcol)._seq.min()
        parent_seq = B[child][col].map(first_parent)
        n = int((parent_seq.isna() | (parent_seq > B[child]._seq)).sum())
        if n:
            fk_bad.append(f"{child}.{col} {n}")
    check("Khóa ngoại: dòng cha luôn có trước (hoặc cùng batch) dòng con", not fk_bad, ", ".join(fk_bad))

    # Các phiên bản của 1 đơn: trạng thái không đi lùi, mốc đã xuất hiện thì không đổi / không mất
    o = B["orders"].sort_values(["order_id", "_seq"])
    prev = o.groupby("order_id").shift()
    same_order = prev._seq.notna()
    back = same_order & (o.order_status.map(STATUS_RANK) < prev.order_status.map(STATUS_RANK))
    changed = sum(int((same_order & (prev[c] != "") & (o[c] != prev[c])).sum()) for c in ORDER_EVENTS)
    check("orders: trạng thái không đi lùi, mốc đã có không đổi", not back.any() and not changed,
          f"đi lùi {int(back.sum())}, mốc bị đổi {changed}" if back.any() or changed else "")

    # Số INSERT / UPDATE khi phát lại = orders_new / orders_resent trong manifest (đáp án cho etl_log)
    first_seen = ~B["orders"].duplicated("order_id")
    replay = pd.crosstab(B["orders"].batch_id, first_seen).reindex(BATCH_IDS).fillna(0).astype(int)
    ok = (replay[True] == m.orders_new).all() and (replay.get(False, 0) == m.orders_resent).all()
    check("orders: số INSERT / UPDATE khi phát lại khớp manifest", ok)

    # Sau batch cuối: staging (phát lại) phải khớp 100% file gốc – mọi bảng, mọi cột (D8)
    diff = []
    for t, d in B.items():
        final = d.sort_values("_seq").drop_duplicates(PK[t], keep="last")
        cols = list(T[t].columns)
        a = final[cols].sort_values(PK[t]).reset_index(drop=True)
        b = T[t][cols].sort_values(PK[t]).reset_index(drop=True)
        if not a.equals(b):
            diff.append(f"{t} ({len(a):,} vs {len(b):,} dòng)")
    check("Phát lại hết 10 batch = file gốc (mọi bảng, mọi cột)", not diff, ", ".join(diff))

    return pd.DataFrame(results)


def print_counts(sent):
    """In số dòng cần gửi: hàng = batch (theo thứ tự chạy), cột = bảng."""
    tables = [t for t in FILES if t in sent]
    counts = pd.DataFrame({t: sent[t].batch_id.value_counts() for t in tables})
    counts = counts.reindex(BATCH_IDS).fillna(0).astype(int)
    counts.loc["Tổng"] = counts.sum()
    print(counts.to_string())


def h(title):
    print(f"\n=== {title}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    T = load_raw()
    print("Đọc data/raw/:", ", ".join(f"{t} {len(d):,}" for t, d in T.items()))

    # ------------------------------------------------------------ 1. batch đầu tiên của đơn
    od = T["orders"]
    purchase = to_ts(od.order_purchase_timestamp)
    first_batch = batch_of(purchase).astype(str)            # tháng mua (D5)

    h("1. Batch đầu tiên của đơn (so với bảng D5 trong docs/decisions.md)")
    summary = (pd.DataFrame({"batch": first_batch, "purchase": purchase})
               .groupby("batch")
               .agg(don_moi=("purchase", "size"), mua_tu=("purchase", "min"), mua_den=("purchase", "max"))
               .reindex(BATCH_IDS))
    print(summary.to_string())
    print(f"Tổng: {summary.don_moi.sum():,} đơn")

    # ------------------------------------------------------------ 2. bảng con + bảng tham chiếu
    sent = follow_first_batch(T, first_batch)

    h("2. Bảng con + bảng tham chiếu: số dòng gửi ở mỗi batch (so với bảng D5)")
    print_counts(sent)

    # ------------------------------------------------------------ 3. ảnh chụp đơn tại mỗi cutoff (D8)
    sent["orders"] = order_versions(od, first_batch)
    v = sent["orders"]

    h("3. orders: đơn mới (sẽ INSERT) + đơn cũ gửi lại vì có thay đổi (sẽ UPDATE) – D8")
    kinds = pd.crosstab(v.batch_id, v._new.map({True: "don_moi", False: "don_gui_lai"}))
    kinds = kinds.reindex(index=BATCH_IDS, columns=["don_moi", "don_gui_lai"]).fillna(0).astype(int)
    kinds["tong_dong"] = kinds.sum(axis=1)
    kinds.loc["Tổng"] = kinds.sum()
    print(kinds.to_string())

    h("3b. order_status của các dòng orders gửi đi ở mỗi batch")
    print(pd.crosstab(v.batch_id, v.order_status).reindex(BATCH_IDS).fillna(0).astype(int).to_string())

    h(f"3c. Đơn ví dụ {EXAMPLE_ORDER[:8]}... qua các batch (so với bảng ví dụ ở D8)")
    ex = v[v.order_id == EXAMPLE_ORDER]
    print(ex[["batch_id", "_new", "order_status", "order_delivered_carrier_date",
              "order_delivered_customer_date"]].to_string(index=False))

    # ------------------------------------------------------------ 4. review theo tháng khách trả lời
    sent["order_reviews"] = r = review_batches(T, first_batch)

    h("4. order_reviews: review đi theo tháng khách TRẢ LỜI, không theo tháng mua (D8 mục 4)")
    seq = r.batch_id.map(SEQ)
    rv = pd.DataFrame({
        "review": r.batch_id.value_counts(),
        "cua_don_trong_batch": r[seq == r._order_seq].batch_id.value_counts(),
        "cua_don_batch_truoc": r[seq > r._order_seq].batch_id.value_counts(),
        "doi_ve_batch_cua_don": r[r._moved].batch_id.value_counts(),
    }).reindex(BATCH_IDS).fillna(0).astype(int)
    rv.loc["Tổng"] = rv.sum()
    print(rv.to_string())
    print("(doi_ve_batch_cua_don: khách trả lời TRƯỚC tháng mua đơn – dời về batch của đơn để luôn có đơn trước review)")

    h(f"4b. Review của đơn ví dụ {EXAMPLE_ORDER[:8]}...")
    print(r[r.order_id == EXAMPLE_ORDER][["batch_id", "review_score", "review_answer_timestamp"]]
          .to_string(index=False))

    # ------------------------------------------------------------ 5. ghi file
    manifest = write_batches(T, sent)

    h(f"5. Đã ghi {OUT.relative_to(ROOT).as_posix()}/ – nội dung manifest.csv")
    mf = manifest.set_index("batch_id")
    print(mf[["seq", "load_type", "lset", "cet", "orders_new", "orders_resent"]].to_string())
    print()
    print(mf[list(FILES)].rename(columns={"order_items": "items", "order_payments": "payments",
                                          "order_reviews": "reviews", "category_translation": "category"})
          .to_string())
    n_files = sum(1 for _ in OUT.glob("*/*.csv"))
    print(f"{n_files} file CSV trong {len(BATCHES)} thư mục batch + manifest.csv")

    # ------------------------------------------------------------ 6. tự kiểm tra
    checks = verify_batches(T, manifest)

    h("6. Tự kiểm tra: đọc lại file, phát lại 10 batch theo thứ tự (như Mage sẽ chạy)")
    print(checks.to_string(index=False))
    failed = int((checks.ket_qua == "FAIL").sum())
    print(f"\n{'TẤT CẢ ĐẠT' if not failed else f'CÓ {failed} KIỂM TRA KHÔNG ĐẠT'} "
          f"({len(checks) - failed}/{len(checks)} PASS)")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
