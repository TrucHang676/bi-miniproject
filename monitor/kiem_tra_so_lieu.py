"""Đối chiếu số mà dashboard theo dõi ETL hiển thị với SQL ĐỘC LẬP trên bảng gốc (không qua view v_*).

Cách làm: với mỗi tổ hợp bộ lọc và vài lần chạy khác loại, lấy số từ các hàm trong queries.py (đúng nguồn số của app)
rồi tính lại từ etl_log.pipeline_run / table_load / quality_check / dbt_result / dq.rejected_rows và danh sách 10 batch
trong data/batches/manifest.csv. In "x/x số khớp"; thoát mã 1 nếu có số lệch.

Ngữ nghĩa số liệu (khớp với 06_etl_monitor.sql):
  * INSERT / UPDATE / xóa mềm = số ĐÃ COMMIT vào staging (chỉ table_load SUCCESS); lần FAILED bị rollback tính 0,
    số bị hoàn tác nằm riêng (rows_*_rollback);
  * dòng bị loại = đếm thẳng dq.rejected_rows theo run_id (gồm cả file deleted_orders);
  * lượt nạp (cycle_no) chỉ mở khi Full Load có >= 1 bảng table_load SUCCESS;
  * trạng thái dbt ngoài success / pass / warn / skipped là lỗi;
  * thời gian = nạp staging + dbt khởi động (bảng staging cuối -> node dbt đầu) + dbt + phần còn lại của Mage.

Chạy từ gốc repo khi Postgres đang chạy:   py monitor/kiem_tra_so_lieu.py
"""
import csv
import sys
from datetime import date

import pandas as pd

import db
import queries as q

# in tiếng Việt có dấu được cả khi console Windows dùng bảng mã cũ
sys.stdout.reconfigure(encoding="utf-8")
import pandas as _pd; _pd.set_option("future.no_silent_downcasting", True)

KET_QUA = {"khop": 0, "tong": 0}
LECH: list[str] = []


def so(ten: str, app, sql, dung_sai: float = 0.0) -> None:
    """So một số: `app` (số app hiển thị) với `sql` (số tính độc lập)."""
    KET_QUA["tong"] += 1
    ok = (app is None and sql is None) or (
        app is not None and sql is not None and not pd.isna(app) and not pd.isna(sql) and abs(float(app) - float(sql)) <= dung_sai + 1e-9) or (
        app is not None and sql is not None and pd.isna(app) and pd.isna(sql))
    if ok:
        KET_QUA["khop"] += 1
    else:
        LECH.append(f"{ten}: app={app!r} sql={sql!r}")


def v(sql: str, tham_so: dict | None = None):
    kq = db.truy_van(sql, tham_so)
    x = kq.iloc[0, 0]
    return None if pd.isna(x) else x


def danh_sach_batch_manifest() -> list[str]:
    with open(db.GOC_REPO / "data" / "batches" / "manifest.csv", encoding="utf-8", newline="") as f:
        return [r["batch_id"] for r in sorted(csv.DictReader(f), key=lambda r: int(r["seq"]))]


# SQL độc lập: "lượt nạp" = số lần Full Load CÓ ÍT NHẤT 1 BẢNG ĐÃ COMMIT tính tới lần chạy đó (đếm lại từ pipeline_run + table_load)
RAW_RUN = """
    SELECT p.run_id, p.pipeline_name, p.load_type, p.batch_id, p.triggered_by, p.status, p.started_at, p.finished_at, p.cet,
           (SELECT count(*) FROM etl_log.pipeline_run f
             WHERE f.load_type = 'FULL' AND f.run_id <= p.run_id
               AND EXISTS (SELECT 1 FROM etl_log.table_load t WHERE t.run_id = f.run_id AND t.status = 'SUCCESS')) AS luot
    FROM etl_log.pipeline_run p"""
# phân loại trạng thái dbt viết lại độc lập: lỗi = mọi trạng thái ngoài 4 chữ này
DBT_KHONG_LOI_SQL = "('success', 'pass', 'warn', 'skipped')"


def raw_loc(bl: q.BoLoc) -> pd.DataFrame:
    """Các lần chạy thỏa bộ lọc - lọc bằng pandas trên bản đọc thẳng pipeline_run."""
    r = db.truy_van(RAW_RUN)
    if bl.luot is not None:
        r = r[r.luot == bl.luot]
    if bl.pipeline:
        r = r[r.pipeline_name == bl.pipeline]
    if bl.kich_hoat:
        r = r[r.triggered_by == bl.kich_hoat]
    if bl.trang_thai:
        r = r[r.status == bl.trang_thai]
    if bl.tu_ngay:
        r = r[r.started_at.dt.date >= bl.tu_ngay]
    if bl.den_ngay:
        r = r[r.started_at.dt.date <= bl.den_ngay]
    return r


def kiem_bo_loc(ten: str, bl: q.BoLoc, manifest: list[str]) -> None:
    raw = raw_loc(bl)
    ids = raw.run_id.astype(int).tolist()
    in_ids = ",".join(map(str, ids)) if ids else "NULL"
    df = q.lan_chay(bl)
    bay_gio = q.gio_db()
    tien_do = q.tien_do_batch(bl.luot)
    k = q.kpi_trang1(df, tien_do, bay_gio)
    t = f"[{ten}] "

    # ----- Trang 1: 5 thẻ KPI -----
    so(t + "số lần chạy", k["so_lan"], len(raw))
    so(t + "manual", k["so_manual"], (raw.triggered_by == "manual").sum())
    so(t + "schedule", k["so_schedule"], (raw.triggered_by == "schedule").sum())
    ok_, loi_ = (raw.status == "SUCCESS").sum(), (raw.status == "FAILED").sum()
    so(t + "SUCCESS", k["so_success"], ok_)
    so(t + "FAILED", k["so_failed"], loi_)
    so(t + "RUNNING", k["so_running"], (raw.status == "RUNNING").sum())
    so(t + "tỉ lệ thành công", k["ti_le_thanh_cong"], (ok_ / (ok_ + loi_)) if (ok_ + loi_) else None, 1e-9)
    so(t + "lần gần nhất (run_id)", k["gan_nhat"]["run_id"] if k["gan_nhat"] else None, max(ids) if ids else None)
    if ids:
        ids_ok = raw[raw.status == "SUCCESS"].run_id.astype(int).tolist()
        in_ok = ",".join(map(str, ids_ok)) if ids_ok else "NULL"
        so(t + "thời gian TB", k["tb_giay"],
           v(f"SELECT avg(EXTRACT(EPOCH FROM finished_at - started_at)) FROM etl_log.pipeline_run WHERE run_id IN ({in_ok})"), 0.06)
        # từng đoạn của thời gian TB, tính lại từ mốc thời gian gốc: staging, dbt khởi động, dbt, phần còn lại (Mage)
        seg = db.truy_van(f"""
            SELECT p.run_id,
                   EXTRACT(EPOCH FROM p.finished_at - p.started_at)                                  AS tong,
                   EXTRACT(EPOCH FROM tl.t1 - tl.t0)                                                 AS stg,
                   EXTRACT(EPOCH FROM d.t0 - tl.t1)                                                  AS prep,
                   EXTRACT(EPOCH FROM d.t1 - d.t0)                                                   AS dbt
            FROM etl_log.pipeline_run p
            LEFT JOIN (SELECT run_id, min(started_at) t0, max(finished_at) t1 FROM etl_log.table_load GROUP BY 1) tl USING (run_id)
            LEFT JOIN (SELECT run_id, min(started_at) t0, max(finished_at) t1 FROM etl_log.dbt_result GROUP BY 1) d USING (run_id)
            WHERE p.run_id IN ({in_ok})""")
        if len(seg):
            mage = (seg.tong - seg.stg.fillna(0) - seg.prep.fillna(0) - seg.dbt.fillna(0)).clip(lower=0)
            so(t + "nạp staging TB", k["tb_staging"], seg.stg.mean() if seg.stg.notna().any() else None, 0.06)
            so(t + "dbt khởi động TB", k["tb_dbt_prep"], seg.prep.mean() if seg.prep.notna().any() else None, 0.06)
            so(t + "dbt TB", k["tb_dbt"], seg.dbt.mean() if seg.dbt.notna().any() else None, 0.06)
            so(t + "Mage TB", k["tb_mage"], mage.mean(), 0.1)
    # tiến độ batch: đếm từ manifest.csv + các lần SUCCESS của lượt (độc lập với view v_batch_progress)
    r_all = db.truy_van(RAW_RUN)
    luot = bl.luot if bl.luot is not None else int(r_all.luot.max())
    r_luot = r_all[r_all.luot == luot]
    r_ok = r_luot[r_luot.status == "SUCCESS"]
    da_nap = [b for b in manifest if b in set(r_ok.batch_id)]
    so(t + "batch đã nạp", k["batch_da_nap"], len(da_nap))
    so(t + "tổng batch", len(tien_do), len(manifest))
    # "đã nạp hết" = batch cuối của manifest đã nạp (không dựa vào cet rỗng)
    so(t + "đã nạp hết", int(k["da_het"]), int(manifest[-1] in da_nap))
    if len(r_ok):
        cet_cuoi = r_ok.sort_values("run_id").iloc[-1].cet   # LSET hiện tại = cet của lần SUCCESS gần nhất trong lượt
        so(t + "LSET hiện tại", None if pd.isna(k["lset"]) else pd.Timestamp(k["lset"]).value,
           None if pd.isna(cet_cuoi) else pd.Timestamp(cet_cuoi).value)
    for b in manifest:   # lưới 10 ô: số lần thử + số lần lỗi + trạng thái cuối từng batch
        x = r_luot[r_luot.batch_id == b]
        a = tien_do[tien_do.batch_id == b].iloc[0]
        so(t + f"lưới {b} lần thử", int(a.so_lan_thu), len(x))
        so(t + f"lưới {b} lỗi", int(a.so_lan_failed), (x.status == "FAILED").sum())
        so(t + f"lưới {b} trạng thái cuối", 1 if a.trang_thai_cuoi == (x.sort_values("run_id").status.iloc[-1] if len(x) else "PENDING") else 0, 1)

    # ----- Biểu đồ (a),(b),(c) và cột "Dòng nạp": từng lần chạy -----
    if ids:
        tl = db.truy_van(f"""SELECT run_id,
                                    EXTRACT(EPOCH FROM max(finished_at) - min(started_at)) AS s,
                                    COALESCE(sum(rows_inserted) FILTER (WHERE status = 'SUCCESS'), 0) AS i,
                                    COALESCE(sum(rows_updated)  FILTER (WHERE status = 'SUCCESS'), 0) AS u
                             FROM etl_log.table_load WHERE run_id IN ({in_ids}) GROUP BY run_id""").set_index("run_id")
        dbr = db.truy_van(f"""SELECT run_id, EXTRACT(EPOCH FROM max(finished_at) - min(started_at)) AS s
                              FROM etl_log.dbt_result WHERE run_id IN ({in_ids}) GROUP BY run_id""").set_index("run_id")
        dq = db.truy_van(f"SELECT run_id, count(*) AS n FROM dq.rejected_rows WHERE run_id IN ({in_ids}) GROUP BY run_id").set_index("run_id")
        for r in df.itertuples():
            raw_r = raw[raw.run_id == r.run_id].iloc[0]
            dur = None if pd.isna(raw_r.finished_at) else (raw_r.finished_at - raw_r.started_at).total_seconds()
            so(t + f"run {r.run_id} thời lượng", None if pd.isna(r.duration_s) else r.duration_s, dur, 0.06)
            so(t + f"run {r.run_id} staging_s", None if pd.isna(r.staging_s) else r.staging_s,
               tl.s.get(r.run_id) if r.run_id in tl.index else None, 0.06)
            so(t + f"run {r.run_id} dbt_s", None if pd.isna(r.dbt_s) else r.dbt_s,
               dbr.s.get(r.run_id) if r.run_id in dbr.index else None, 0.06)
            so(t + f"run {r.run_id} đã commit INSERT+UPDATE", r.rows_inserted + r.rows_updated,
               (tl.i.get(r.run_id, 0) + tl.u.get(r.run_id, 0)) if r.run_id in tl.index else 0)
            so(t + f"run {r.run_id} dq", r.rows_rejected, int(dq.n.get(r.run_id, 0)) if r.run_id in dq.index else 0)
        # (c) tổng INSERT / UPDATE (đã commit) / dq theo batch
        theo = q.so_dong_theo_batch(df)
        gop = (raw[["run_id", "batch_id"]].merge(tl.reset_index(), on="run_id", how="left")
               .merge(dq.reset_index().rename(columns={"n": "rj"}), on="run_id", how="left").fillna(0)
               .groupby("batch_id")[["i", "u", "rj"]].sum())
        for r in theo.itertuples():
            so(t + f"(c) {r.batch_id} INSERT", r.rows_inserted, gop.i.get(r.batch_id, 0))
            so(t + f"(c) {r.batch_id} UPDATE", r.rows_updated, gop.u.get(r.batch_id, 0))
            so(t + f"(c) {r.batch_id} loại", r.rows_rejected, gop.rj.get(r.batch_id, 0))
        so(t + "(c) tổng INSERT", theo.rows_inserted.sum(), tl.i.sum())
        # lọc chỉ Incremental không được làm mất batch 2018-01 (lỗi A2): mọi batch có lần chạy phải có mặt
        so(t + "(c) số batch", len(theo), raw.batch_id.nunique())

    # ----- Trang 2 -----
    k2 = q.kpi_trang2(df)
    if ids:
        so(t + "check WARN", k2["check_warn"], v(f"SELECT count(*) FROM etl_log.quality_check WHERE status='WARN' AND run_id IN ({in_ids})"))
        so(t + "check FAIL", k2["check_fail"], v(f"SELECT count(*) FROM etl_log.quality_check WHERE status='FAIL' AND run_id IN ({in_ids})"))
        so(t + "dòng bị loại (dq đếm thẳng)", k2["dong_loai"], v(f"SELECT count(*) FROM dq.rejected_rows WHERE run_id IN ({in_ids})"))
        so(t + "dòng bị loại (bảng dq gom)", sum(q.dong_bi_loai(bl).so_dong), v(f"SELECT count(*) FROM dq.rejected_rows WHERE run_id IN ({in_ids})"))
        so(t + "dbt test fail", k2["dbt_test_fail"], v(f"SELECT count(*) FROM etl_log.dbt_result WHERE resource_type='test' AND status NOT IN {DBT_KHONG_LOI_SQL} AND run_id IN ({in_ids})"))
        so(t + "dbt test warn", k2["dbt_test_warn"], v(f"SELECT count(*) FROM etl_log.dbt_result WHERE resource_type='test' AND status='warn' AND run_id IN ({in_ids})"))
        so(t + "dbt test bảng lỗi", len(q.dbt_test_khong_dat(bl)), v(f"SELECT count(*) FROM etl_log.dbt_result WHERE resource_type='test' AND status NOT IN ('pass','success','skipped') AND run_id IN ({in_ids})"))
        so(t + "FAILED do dbt", k2["failed_dbt"], v(f"SELECT count(*) FROM etl_log.pipeline_run WHERE status='FAILED' AND error_message LIKE 'dbt build%%' AND run_id IN ({in_ids})"))
        # bị ngắt xét trước staging (A4); staging = còn lại có table_load FAILED hoặc quality_check FAIL
        so(t + "FAILED do staging", k2["failed_staging"], v(f"""
            SELECT count(*) FROM etl_log.pipeline_run p WHERE status='FAILED'
               AND COALESCE(error_message,'') NOT LIKE 'dbt build%%' AND COALESCE(error_message,'') NOT LIKE 'Bị ngắt giữa chừng%%'
               AND (EXISTS (SELECT 1 FROM etl_log.table_load t WHERE t.run_id=p.run_id AND t.status='FAILED')
                    OR EXISTS (SELECT 1 FROM etl_log.quality_check c WHERE c.run_id=p.run_id AND c.status='FAIL'))
               AND run_id IN ({in_ids})"""))
        so(t + "FAILED khác (gồm bị ngắt)", k2["failed_khac"], v(f"""
            SELECT count(*) FROM etl_log.pipeline_run p WHERE status='FAILED'
               AND (COALESCE(error_message,'') LIKE 'Bị ngắt giữa chừng%%'
                    OR (COALESCE(error_message,'') NOT LIKE 'dbt build%%'
                        AND NOT EXISTS (SELECT 1 FROM etl_log.table_load t WHERE t.run_id=p.run_id AND t.status='FAILED')
                        AND NOT EXISTS (SELECT 1 FROM etl_log.quality_check c WHERE c.run_id=p.run_id AND c.status='FAIL')))
               AND run_id IN ({in_ids})"""))
        # ma trận: mỗi (batch, check) -> trạng thái tệ nhất và tổng dòng vi phạm
        mt = q.ma_tran_chat_luong(bl)
        raw_mt = db.truy_van(f"""
            SELECT p.batch_id, c.check_name, c.status, c.failed_rows
            FROM etl_log.quality_check c JOIN etl_log.pipeline_run p ON p.run_id = c.run_id
            WHERE c.run_id IN ({in_ids})""")
        thu_tu = {"PASS": 1, "WARN": 2, "FAIL": 3}
        for (b, c), g in raw_mt.groupby(["batch_id", "check_name"]):
            tt = max(g.status, key=lambda s: thu_tu[s])
            a = mt[(mt.batch_id == b) & (mt.check_name == c)]
            so(t + f"ma trận {b}/{c} trạng thái", thu_tu[a.status.iloc[0]] if len(a) else None, thu_tu[tt])
            so(t + f"ma trận {b}/{c} dòng", int(a.failed_rows.iloc[0]) if len(a) else None, int(g.failed_rows.sum()))
        so(t + "ma trận số ô", len(mt), raw_mt.groupby(["batch_id", "check_name"]).ngroups)


def kiem_run(run_id: int, nhan: str) -> None:
    r = q.mot_lan_chay(run_id)
    t = f"[run #{run_id} {nhan}] "
    tl = q.table_load_cua(run_id)
    qc = q.quality_check_cua(run_id)
    dbt = q.dbt_node_cua(run_id)
    p = db.truy_van("SELECT * FROM etl_log.pipeline_run WHERE run_id = %(r)s", {"r": run_id}).iloc[0]
    P = {"r": run_id}
    so(t + "status", r.status == p.status, True)
    so(t + "batch", r.batch_id == p.batch_id, True)
    so(t + "bảng nạp", len(tl), v("SELECT count(*) FROM etl_log.table_load WHERE run_id=%(r)s", P))
    so(t + "dòng đọc", r.rows_source, v("SELECT COALESCE(sum(rows_source),0) FROM etl_log.table_load WHERE run_id=%(r)s", P))
    # đã commit = table_load SUCCESS; lần FAILED bị rollback -> 0 ở INSERT / UPDATE, số bị hoàn tác riêng
    so(t + "INSERT đã commit", r.rows_inserted, v("SELECT COALESCE(sum(rows_inserted),0) FROM etl_log.table_load WHERE run_id=%(r)s AND status='SUCCESS'", P))
    so(t + "UPDATE đã commit", r.rows_updated, v("SELECT COALESCE(sum(rows_updated),0) FROM etl_log.table_load WHERE run_id=%(r)s AND status='SUCCESS'", P))
    so(t + "INSERT hoàn tác", r.rows_inserted_rollback, v("SELECT COALESCE(sum(rows_inserted),0) FROM etl_log.table_load WHERE run_id=%(r)s AND status='FAILED'", P))
    so(t + "UPDATE hoàn tác", r.rows_updated_rollback, v("SELECT COALESCE(sum(rows_updated),0) FROM etl_log.table_load WHERE run_id=%(r)s AND status='FAILED'", P))
    so(t + "bị loại (đếm thẳng dq)", r.rows_rejected, v("SELECT count(*) FROM dq.rejected_rows WHERE run_id=%(r)s", P))
    so(t + "xóa mềm", r.rows_deleted, v("SELECT COALESCE(sum(rows_deleted),0) FROM etl_log.table_load WHERE run_id=%(r)s AND status='SUCCESS'", P))
    so(t + "n_check", r.n_check, len(qc))
    so(t + "n_check PASS", r.n_check_pass, v("SELECT count(*) FROM etl_log.quality_check WHERE run_id=%(r)s AND status='PASS'", P))
    so(t + "n_check WARN", r.n_check_warn, v("SELECT count(*) FROM etl_log.quality_check WHERE run_id=%(r)s AND status='WARN'", P))
    so(t + "n_check FAIL", r.n_check_fail, v("SELECT count(*) FROM etl_log.quality_check WHERE run_id=%(r)s AND status='FAIL'", P))
    so(t + "node dbt", r.dbt_n_node, len(dbt))
    so(t + "node dbt đạt", r.dbt_n_ok, v("SELECT count(*) FROM etl_log.dbt_result WHERE run_id=%(r)s AND status IN ('success','pass')", P))
    so(t + "node dbt lỗi", r.dbt_n_fail, v(f"SELECT count(*) FROM etl_log.dbt_result WHERE run_id=%(r)s AND status NOT IN {DBT_KHONG_LOI_SQL}", P))
    so(t + "test dbt lỗi", r.dbt_test_fail, v(f"SELECT count(*) FROM etl_log.dbt_result WHERE run_id=%(r)s AND resource_type='test' AND status NOT IN {DBT_KHONG_LOI_SQL}", P))
    # lượt nạp mới: chỉ Full Load có >= 1 bảng đã commit mới mở lượt
    luot = v("""SELECT count(*) FROM etl_log.pipeline_run f WHERE f.load_type='FULL' AND f.run_id <= %(r)s
                AND EXISTS (SELECT 1 FROM etl_log.table_load t WHERE t.run_id = f.run_id AND t.status = 'SUCCESS')""", P)
    so(t + "lượt nạp", r.cycle_no, luot)
    lan_thu = v("""SELECT count(*) FROM etl_log.pipeline_run p2 WHERE p2.batch_id = %(b)s AND p2.run_id <= %(r)s
                   AND (SELECT count(*) FROM etl_log.pipeline_run f WHERE f.load_type='FULL' AND f.run_id <= p2.run_id
                          AND EXISTS (SELECT 1 FROM etl_log.table_load t WHERE t.run_id = f.run_id AND t.status = 'SUCCESS')) = %(l)s""",
                {"b": p.batch_id, "r": run_id, "l": luot})
    so(t + "lần thử", r.attempt_no, lan_thu)
    # thời gian: các đoạn tính lại từ mốc gốc
    seg = db.truy_van("""
        SELECT EXTRACT(EPOCH FROM p.finished_at - p.started_at) AS tong,
               EXTRACT(EPOCH FROM tl.t1 - tl.t0) AS stg, EXTRACT(EPOCH FROM d.t0 - tl.t1) AS prep, EXTRACT(EPOCH FROM d.t1 - d.t0) AS dbt
        FROM etl_log.pipeline_run p
        LEFT JOIN (SELECT run_id, min(started_at) t0, max(finished_at) t1 FROM etl_log.table_load GROUP BY 1) tl USING (run_id)
        LEFT JOIN (SELECT run_id, min(started_at) t0, max(finished_at) t1 FROM etl_log.dbt_result GROUP BY 1) d USING (run_id)
        WHERE p.run_id = %(r)s""", P).iloc[0]
    for col, mine in (("duration_s", seg.tong), ("staging_s", seg.stg), ("dbt_prep_s", seg.prep), ("dbt_s", seg.dbt)):
        so(t + col, None if pd.isna(r[col]) else r[col], None if pd.isna(mine) else mine, 0.06)
    if pd.notna(seg.tong):
        mage = max(seg.tong - (0 if pd.isna(seg.stg) else seg.stg) - (0 if pd.isna(seg.prep) else seg.prep)
                   - (0 if pd.isna(seg.dbt) else seg.dbt), 0)
        so(t + "mage_s", r.mage_s, mage, 0.1)
    # Gantt: Mage khởi động (nếu > 1 giây) + số bảng staging + (1 nếu có đoạn dbt khởi động) + số loại node dbt có thời gian
    # + Mage ghi log (nếu lần chạy đã kết thúc và còn > 1 giây sau bước cuối) - tính lại độc lập từ mốc thời gian gốc
    gt = q.gantt_cac_buoc(r, tl, dbt, q.gio_db())
    dbt_t = dbt.dropna(subset=["started_at", "finished_at"]) if len(dbt) else dbt
    n_dbt = 0 if dbt.empty else dbt_t.resource_type.nunique()
    co_khoi_dong = int(bool(len(tl) and n_dbt and pd.notna(seg.prep) and seg.prep > 0))
    mage_dau = int(bool(len(tl)) and (tl.started_at.min() - p.started_at).total_seconds() > 1.0)
    moc_cuoi = None
    if len(tl) and not (tl.status == "RUNNING").any() and tl.finished_at.notna().any():
        moc_cuoi = tl.finished_at.max()
    if n_dbt:
        moc_cuoi = dbt_t.finished_at.max() if moc_cuoi is None else max(moc_cuoi, dbt_t.finished_at.max())
    mage_cuoi = int(pd.notna(p.finished_at) and moc_cuoi is not None and (p.finished_at - moc_cuoi).total_seconds() > 1.0)
    so(t + "số bước Gantt", len(gt), mage_dau + len(tl) + co_khoi_dong + n_dbt + mage_cuoi)
    # tổng chiều dài Gantt = thời lượng lần chạy (cộng các đoạn nối tiếp, sai số < 1 giây mỗi đầu nếu đoạn Mage ngắn hơn ngưỡng)
    if pd.notna(p.finished_at) and len(gt):
        dai = (gt.ket_thuc.max() - gt.bat_dau.min()).total_seconds()
        so(t + "độ dài Gantt ≈ thời lượng", dai, (p.finished_at - p.started_at).total_seconds(), 2.1)
    # failed_stage: bị ngắt xét trước staging
    if r.status == "FAILED":
        msg = str(p.error_message or "")
        if msg.startswith("Bị ngắt giữa chừng"):
            mong = "bi_ngat"
        elif msg.startswith("dbt build"):
            mong = "dbt"
        elif (tl.status == "FAILED").any() or (qc.status == "FAIL").any():
            mong = "staging"
        else:
            mong = "khac"
        so(t + "failed_stage", r.failed_stage == mong, True)


def main() -> int:
    manifest = danh_sach_batch_manifest()
    luot_moi = q.luot_moi_nhat()
    lc = q.lua_chon()
    den = lc["den_ngay"]
    to_hop = {
        "lượt mới nhất": q.BoLoc(luot=luot_moi),
        "tất cả lượt": q.BoLoc(),
        "lượt mới nhất + schedule": q.BoLoc(luot=luot_moi, kich_hoat="schedule"),
        "lượt mới nhất + incremental": q.BoLoc(luot=luot_moi, pipeline="incremental_load"),
        "tất cả + FAILED": q.BoLoc(trang_thai="FAILED"),
        "tất cả + full_load": q.BoLoc(pipeline="full_load"),
        "khoảng ngày cuối": q.BoLoc(tu_ngay=den, den_ngay=den) if den else q.BoLoc(),
        "bộ lọc ra rỗng": q.BoLoc(tu_ngay=date(2000, 1, 1), den_ngay=date(2000, 1, 2)),
    }
    for ten, bl in to_hop.items():
        kiem_bo_loc(ten, bl, manifest)
    # các lần chạy khác loại: SUCCESS có WARN, FAILED do dbt, FULL, FAILED do staging (bị rollback), lần có dq nhưng không có trong table_load
    tat = db.truy_van("""SELECT p.run_id, p.status, p.load_type, p.error_message,
                                EXISTS (SELECT 1 FROM etl_log.quality_check c WHERE c.run_id = p.run_id AND c.status = 'WARN') AS co_warn,
                                (SELECT count(*) FROM dq.rejected_rows d WHERE d.run_id = p.run_id)
                                  <> (SELECT COALESCE(sum(rows_rejected), 0) FROM etl_log.table_load t WHERE t.run_id = p.run_id) AS dq_lech
                         FROM etl_log.pipeline_run p ORDER BY run_id DESC""")
    chon = {}
    for r in tat.itertuples():
        if r.status == "SUCCESS" and r.co_warn:
            chon.setdefault("SUCCESS có WARN", r.run_id)
        if r.status == "FAILED" and str(r.error_message).startswith("dbt build"):
            chon.setdefault("FAILED do dbt", r.run_id)
        if r.status == "FAILED" and not str(r.error_message).startswith("dbt build"):
            chon.setdefault("FAILED do staging", r.run_id)
        if r.load_type == "FULL" and r.status == "SUCCESS":
            chon.setdefault("FULL", r.run_id)
        if r.status == "SUCCESS" and r.load_type == "INCREMENTAL" and not r.co_warn:
            chon.setdefault("SUCCESS sạch", r.run_id)
        if r.dq_lech:
            chon.setdefault("dq khác table_load", r.run_id)
    for nhan, rid in chon.items():
        kiem_run(int(rid), nhan)
    print(f"Các lần chạy đã kiểm: {chon}")
    print(f"{KET_QUA['khop']}/{KET_QUA['tong']} số khớp")
    for d in LECH:
        print("LỆCH:", d)
    return 0 if not LECH else 1


if __name__ == "__main__":
    sys.exit(main())
