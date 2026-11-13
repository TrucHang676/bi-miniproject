"""Mọi câu SQL và phép tính số liệu của dashboard theo dõi ETL (BS-54). app.py chỉ vẽ, không có SQL.

Nguồn dữ liệu: view etl_log.v_run, v_batch_progress, v_quality_issue (sql/init/06_etl_monitor.sql),
các bảng etl_log.table_load / quality_check / dbt_result và dq.rejected_rows. Không có số cứng
(trừ danh sách trạng thái); 10 batch chuẩn lấy từ chính view v_batch_progress.

Hàm `kpi_*` nhận DataFrame và trả về dict số THÔ -> app định dạng, kiem_tra_so_lieu.py đối chiếu với SQL độc lập.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

import db

# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------
TRANG_THAI = ("SUCCESS", "FAILED", "RUNNING")
KICH_HOAT = ("manual", "schedule")
# Một lần chạy bình thường 40 - 70 giây; RUNNING quá ngưỡng này là nghi kẹt (cũng là ngưỡng của view v_run.is_stuck)
PHUT_KET = 15
# Thứ tự hiển thị 7 phép kiểm tra nạp staging (pipeline_rules.md B4.2) + 2 phép của file xóa đơn (B6)
THU_TU_CHECK = ("file_exists", "columns_match", "batch_id_match", "not_null_key", "duplicate_key",
                "type_cast", "row_count_match", "in_window", "key_exists")
FULL_BATCH = "FULL"      # batch của Full Load (hàng đầu trong manifest)
# Trạng thái dbt: ngoài các nhóm dưới đây (VD 'error', 'fail', hoặc chữ lạ của bản dbt sau) đều tính là LỖI
DBT_OK = ("success", "pass")
DBT_CANH_BAO = ("warn",)
DBT_BO_QUA = ("skipped",)
DBT_KHONG_LOI = DBT_OK + DBT_CANH_BAO + DBT_BO_QUA
FILE_LICH = db.GOC_REPO / "mage" / "olist_etl" / "pipelines" / "incremental_load" / "triggers.yaml"


@dataclass(frozen=True)
class BoLoc:
    """Bộ lọc ở thanh bên. None = không lọc theo tiêu chí đó. `luot` là số thứ tự lượt nạp (cycle_no)."""
    luot: int | None = None
    pipeline: str | None = None
    kich_hoat: str | None = None
    trang_thai: str | None = None
    tu_ngay: date | None = None
    den_ngay: date | None = None


def _dieu_kien(bl: BoLoc, bi_danh: str = "r") -> tuple[str, dict]:
    """Ghép mệnh đề WHERE trên v_run (bí danh `bi_danh`) + tham số có tên."""
    ds, tham_so = ["TRUE"], {}
    if bl.luot is not None:
        ds.append(f"{bi_danh}.cycle_no = %(luot)s")
        tham_so["luot"] = bl.luot
    if bl.pipeline:
        ds.append(f"{bi_danh}.pipeline_name = %(pipeline)s")
        tham_so["pipeline"] = bl.pipeline
    if bl.kich_hoat:
        ds.append(f"{bi_danh}.triggered_by = %(kich_hoat)s")
        tham_so["kich_hoat"] = bl.kich_hoat
    if bl.trang_thai:
        ds.append(f"{bi_danh}.status = %(trang_thai)s")
        tham_so["trang_thai"] = bl.trang_thai
    if bl.tu_ngay:
        ds.append(f"{bi_danh}.started_at::date >= %(tu_ngay)s")
        tham_so["tu_ngay"] = bl.tu_ngay
    if bl.den_ngay:
        ds.append(f"{bi_danh}.started_at::date <= %(den_ngay)s")
        tham_so["den_ngay"] = bl.den_ngay
    return " AND ".join(ds), tham_so


def la_loi_dbt(trang_thai) -> bool:
    """Trạng thái dbt có tính là lỗi không (trạng thái lạ = lỗi)."""
    return str(trang_thai) not in DBT_KHONG_LOI


def _run_trong_loc(bl: BoLoc) -> tuple[str, dict]:
    """Mệnh đề `run_id IN (các lần chạy thỏa bộ lọc)` để nối vào truy vấn trên bảng con."""
    dk, tham_so = _dieu_kien(bl, "r")
    return f"run_id IN (SELECT r.run_id FROM etl_log.v_run r WHERE {dk})", tham_so


# ---------------------------------------------------------------------------
# Thông tin chung
# ---------------------------------------------------------------------------
def gio_db() -> pd.Timestamp:
    """Giờ hiện tại theo DB (giờ Việt Nam) - dùng tính 'cách đây bao lâu' để khớp với cột log."""
    return pd.Timestamp(db.truy_van("SELECT localtimestamp AS t").iloc[0, 0])


def lua_chon() -> dict:
    """Các giá trị cho bộ lọc: lượt nạp (mới nhất trước), pipeline, khoảng ngày chạy."""
    luot = db.truy_van("""
        SELECT cycle_no, min(started_at) AS bat_dau, count(*)::int AS so_lan
        FROM etl_log.v_run GROUP BY cycle_no ORDER BY cycle_no DESC""")
    pl = db.truy_van("SELECT DISTINCT pipeline_name FROM etl_log.pipeline_run ORDER BY 1")
    ngay = db.truy_van("SELECT min(started_at)::date AS tu, max(started_at)::date AS den FROM etl_log.pipeline_run")
    tu, den = ngay.iloc[0, 0], ngay.iloc[0, 1]
    return {"luot": luot, "pipeline": pl.pipeline_name.tolist(),
            "tu_ngay": None if pd.isna(tu) else tu, "den_ngay": None if pd.isna(den) else den}


def luot_moi_nhat() -> int | None:
    kq = db.truy_van("SELECT max(cycle_no) AS c FROM etl_log.v_run").iloc[0, 0]
    return None if pd.isna(kq) else int(kq)


def doc_lich() -> list[dict]:
    """Đọc triggers.yaml (Mage ghi ngược trạng thái bật/tắt trên giao diện vào file này). Lỗi/thiếu file -> []."""
    try:
        import yaml
        du_lieu = yaml.safe_load(Path(FILE_LICH).read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    ds = []
    for t in du_lieu.get("triggers", []) or []:
        cron = str(t.get("schedule_interval", ""))
        ds.append({"ten": t.get("name", "?"), "cron": cron, "bat": t.get("status") == "active",
                   "phut": chu_ky_phut(cron), "bat_luc": _gio_vn(t.get("last_enabled_at"))})
    return ds


def _gio_vn(x) -> pd.Timestamp | None:
    """Mốc giờ trong triggers.yaml (Mage ghi theo UTC) -> giờ Việt Nam không múi giờ, cùng kiểu với cột log. Rỗng -> None."""
    if x is None or x == "":
        return None
    ts = pd.Timestamp(x)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    return ts.tz_convert("Asia/Ho_Chi_Minh").tz_localize(None)


def chu_ky_phut(cron: str) -> int | None:
    """Chu kỳ (phút) của cron dạng `*/n * * * *`; dạng khác (VD hằng tháng) -> None."""
    phan = cron.split()
    if len(phan) == 5 and phan[0].startswith("*/") and phan[0][2:].isdigit() and phan[1:] == ["*"] * 4:
        return int(phan[0][2:])
    if cron.strip() == "* * * * *":
        return 1
    return None


# ---------------------------------------------------------------------------
# Trang 1 - Tổng quan vận hành
# ---------------------------------------------------------------------------
def lan_chay(bl: BoLoc) -> pd.DataFrame:
    """Các lần chạy thỏa bộ lọc (từ view v_run), cũ -> mới."""
    dk, tham_so = _dieu_kien(bl, "r")
    df = db.truy_van(f"SELECT * FROM etl_log.v_run r WHERE {dk} ORDER BY r.run_id", tham_so)
    # cột toàn NULL (VD chưa lần nào kết thúc) về kiểu object -> ép lại để phép tính thời gian / số không lỗi
    for c in ("duration_s", "elapsed_s", "staging_s", "dbt_prep_s", "dbt_s", "mage_s", "gap_from_prev_s"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("started_at", "finished_at", "lset", "cet"):
        df[c] = pd.to_datetime(df[c])
    return df


def tien_do_batch(luot: int | None) -> pd.DataFrame:
    """10 batch chuẩn x 1 lượt nạp (None = mới nhất): lấy thẳng từ view v_batch_progress (nguồn duy nhất)."""
    return db.truy_van("""
        SELECT seq, batch_id, so_lan_thu, so_lan_failed, da_nap, trang_thai_cuoi,
               run_id_success, run_id_cuoi, xong_luc, kich_hoat, lset, cet
        FROM etl_log.v_batch_progress
        WHERE cycle_no = COALESCE(%(luot)s, (SELECT max(cycle_no) FROM etl_log.v_batch_progress))
        ORDER BY seq""", {"luot": luot})


def danh_sach_batch() -> pd.DataFrame:
    """Danh sách 10 batch chuẩn theo thứ tự nạp (seq, batch_id)."""
    return db.truy_van("SELECT DISTINCT seq, batch_id FROM etl_log.v_batch_progress ORDER BY seq")


def kpi_trang1(df: pd.DataFrame, tien_do: pd.DataFrame, bay_gio: pd.Timestamp) -> dict:
    """5 thẻ KPI trang 1. `df` = các lần chạy đã lọc, `tien_do` = tien_do_batch(lượt)."""
    n = len(df)
    thanh_cong = int((df.status == "SUCCESS").sum())
    loi = int((df.status == "FAILED").sum())
    dang_chay = int((df.status == "RUNNING").sum())
    xong = thanh_cong + loi
    kq = {
        "so_lan": n,
        "so_manual": int((df.triggered_by == "manual").sum()),
        "so_schedule": int((df.triggered_by == "schedule").sum()),
        "so_success": thanh_cong, "so_failed": loi, "so_running": dang_chay,
        "ti_le_thanh_cong": (thanh_cong / xong) if xong else None,
        "gan_nhat": None,
        "batch_da_nap": int(tien_do.da_nap.sum()), "batch_tong": len(tien_do),
        # "đã nạp hết" = batch cuối của manifest (2018-09+) đã nạp, không dựa vào cet rỗng
        "da_het": bool(len(tien_do) and tien_do.iloc[-1].da_nap), "lset": None,
        "tb_giay": None, "tb_staging": None, "tb_dbt_prep": None, "tb_dbt": None, "tb_mage": None,
    }
    if n:
        cuoi = df.iloc[-1]
        moc = cuoi.finished_at if pd.notna(cuoi.finished_at) else cuoi.started_at
        kq["gan_nhat"] = {"run_id": int(cuoi.run_id), "status": cuoi.status, "batch_id": cuoi.batch_id,
                          "triggered_by": cuoi.triggered_by, "bat_dau": cuoi.started_at,
                          "giay_truoc": max(0.0, (bay_gio - moc).total_seconds())}
    ok = df[df.status == "SUCCESS"]
    if len(ok):
        def tb(cot):
            return None if ok[cot].dropna().empty else float(ok[cot].mean())
        kq["tb_giay"] = float(ok.duration_s.mean())
        kq["tb_staging"], kq["tb_dbt_prep"], kq["tb_dbt"], kq["tb_mage"] = tb("staging_s"), tb("dbt_prep_s"), tb("dbt_s"), tb("mage_s")
    da = tien_do[tien_do.run_id_success.notna()]
    if len(da):
        # LSET hiện tại = mốc cắt (cet) của lần SUCCESS gần nhất trong lượt (NaT = batch cuối, không cắt)
        kq["lset"] = da.sort_values("run_id_success").iloc[-1].cet
    return kq


def canh_bao(tat_ca: pd.DataFrame, tien_do: pd.DataFrame, lich: list[dict], bay_gio: pd.Timestamp) -> list[tuple[str, str]]:
    """Danh sách cảnh báo (mức, nội dung) - luôn tính trên TOÀN BỘ log, không phụ thuộc bộ lọc.
    mức: 'do' (cần xử lý) hoặc 'vang' (chú ý)."""
    kq: list[tuple[str, str]] = []
    if tat_ca.empty:
        return kq
    for _, r in tat_ca[tat_ca.is_stuck.fillna(False)].iterrows():
        kq.append(("do", f"Lần chạy #{r.run_id} ({r.batch_id}) đang ở RUNNING đã {int(r.elapsed_s // 60)} phút "
                         f"(quá {PHUT_KET} phút) - nghi pipeline chết giữa chừng."))
    cuoi = tat_ca.iloc[-1]
    if cuoi.status == "FAILED":
        msg = " ".join(str(cuoi.error_message or "").split())
        kq.append(("do", f"Lần chạy gần nhất #{cuoi.run_id} ({cuoi.batch_id}) bị FAILED: "
                         f"{msg[:220]}{'…' if len(msg) > 220 else ''}"))
    luot = tat_ca[tat_ca.cycle_no == tat_ca.cycle_no.max()]
    for batch, nhom in luot.groupby("batch_id", sort=False):
        trang_thai = [x for x in nhom.sort_values("run_id").status if x != "RUNNING"]  # bỏ lần đang chạy dở
        lien_tiep = 0
        for s in reversed(trang_thai):
            if s != "FAILED":
                break
            lien_tiep += 1
        if lien_tiep >= 2:
            kq.append(("do", f"Batch {batch} đã FAILED {lien_tiep} lần liên tiếp - cần xem lỗi, sửa nguồn rồi chạy lại."))
    # Lịch bật mà lâu không có lần chạy theo lịch: chỉ cảnh báo khi còn batch chưa nạp
    # (nạp hết rồi thì lịch chạy mà không ghi log là đúng thiết kế - decisions.md 05/11/2026).
    # Mốc tính: lần schedule gần nhất hoặc lúc bật lịch (last_enabled_at trong triggers.yaml), lấy mốc muộn hơn.
    # Chưa từng có lần schedule và triggers.yaml không có last_enabled_at -> không có mốc nên bỏ qua.
    con_batch = not bool(len(tien_do) and tien_do.iloc[-1].da_nap)
    ds = tat_ca[tat_ca.triggered_by == "schedule"]
    lan_cuoi = ds.started_at.max() if len(ds) else None
    for t in lich:
        if not (t["bat"] and t["phut"] and con_batch):
            continue
        moc = [m for m in (lan_cuoi, t.get("bat_luc")) if m is not None and not pd.isna(m)]
        if not moc:
            continue
        moc = max(moc)
        tre = (bay_gio - moc).total_seconds() / 60
        if tre > 3 * t["phut"]:
            kq.append(("vang", f"Lịch {t['ten']} đang bật (mỗi {t['phut']} phút) nhưng "
                               + ("chưa có lần chạy theo lịch nào" if lan_cuoi is None else "lần chạy theo lịch gần nhất")
                               + f" kể từ mốc {pd.Timestamp(moc):%H:%M %d/%m} (cách đây {int(tre)} phút, > 3 chu kỳ) - kiểm tra Docker / Mage."))
    return kq


def so_dong_theo_batch(df: pd.DataFrame) -> pd.DataFrame:
    """INSERT / UPDATE (đã commit vào staging) / bị loại (dq) gom theo batch, theo thứ tự batch chuẩn. Lần FAILED bị rollback đóng góp 0."""
    g = (df.groupby("batch_id")[["rows_inserted", "rows_updated", "rows_rejected"]].sum().reset_index())
    return danh_sach_batch().merge(g, on="batch_id", how="inner").sort_values("seq")


# ---------------------------------------------------------------------------
# Trang 2 - Chất lượng dữ liệu
# ---------------------------------------------------------------------------
def kpi_trang2(df: pd.DataFrame) -> dict:
    return {
        "check_warn": int(df.n_check_warn.sum()), "check_fail": int(df.n_check_fail.sum()),
        "dong_loai": int(df.rows_rejected.sum()),
        "dbt_test_fail": int(df.dbt_test_fail.sum()), "dbt_test_warn": int(df.dbt_test_warn.sum()),
        "failed_dbt": int(((df.status == "FAILED") & (df.failed_stage == "dbt")).sum()),
        "failed_staging": int(((df.status == "FAILED") & (df.failed_stage == "staging")).sum()),
        "failed_khac": int(((df.status == "FAILED") & ~df.failed_stage.isin(["dbt", "staging"])).sum()),
    }


def ma_tran_chat_luong(bl: BoLoc) -> pd.DataFrame:
    """Batch x phép kiểm tra: trạng thái tệ nhất (FAIL > WARN > PASS) trong các lần chạy thỏa bộ lọc."""
    dk, tham_so = _run_trong_loc(bl)
    return db.truy_van(f"""
        SELECT r.batch_id, q.check_name,
               CASE max(CASE q.status WHEN 'FAIL' THEN 3 WHEN 'WARN' THEN 2 ELSE 1 END)
                    WHEN 3 THEN 'FAIL' WHEN 2 THEN 'WARN' ELSE 'PASS' END    AS status,
               COALESCE(sum(q.failed_rows), 0)::int                           AS failed_rows,
               count(*)::int                                                   AS so_phep,
               string_agg(DISTINCT q.table_name, ', ') FILTER (WHERE q.status <> 'PASS') AS bang_loi
        FROM etl_log.quality_check q
        JOIN etl_log.v_run r ON r.run_id = q.run_id
        WHERE q.{dk}
        GROUP BY r.batch_id, q.check_name""", tham_so)


def dong_bi_loai(bl: BoLoc) -> pd.DataFrame:
    """Dòng bị Mage loại (dq.rejected_rows) gom theo bảng, phép kiểm tra, lý do."""
    dk, tham_so = _run_trong_loc(bl)
    return db.truy_van(f"""
        SELECT table_name, check_name, COALESCE(reason, '(không ghi lý do)') AS reason, count(*)::int AS so_dong
        FROM dq.rejected_rows WHERE {dk}
        GROUP BY 1, 2, 3 ORDER BY so_dong DESC, table_name""", tham_so)


def mau_dong_bi_loai(bl: BoLoc, gioi_han: int = 50) -> pd.DataFrame:
    """Mẫu dòng bị loại. row_data = chuỗi cắt 200 ký tự (như cũ); row_json = nguyên dòng (JSONB -> dict) để app tách
    thành từng ô 'cột: giá trị' (chỉ thêm cột hiển thị, không đổi số liệu)."""
    dk, tham_so = _run_trong_loc(bl)
    tham_so["gh"] = gioi_han
    return db.truy_van(f"""
        SELECT run_id, table_name, check_name, source_row, reason,
               left(row_data::text, 200) AS row_data, row_data AS row_json, rejected_at
        FROM dq.rejected_rows WHERE {dk}
        ORDER BY run_id DESC, rejected_id LIMIT %(gh)s""", tham_so)


def dbt_test_khong_dat(bl: BoLoc) -> pd.DataFrame:
    """dbt test fail / error / warn trong các lần chạy thỏa bộ lọc (relation_name = bảng dq chứa dòng vi phạm)."""
    dk, tham_so = _run_trong_loc(bl)
    return db.truy_van(f"""
        SELECT d.run_id, r.batch_id, r.triggered_by, d.node_name, d.status, d.failures, d.relation_name, d.message
        FROM etl_log.dbt_result d JOIN etl_log.v_run r ON r.run_id = d.run_id
        WHERE d.resource_type = 'test' AND d.status NOT IN ('pass', 'success', 'skipped') AND d.{dk}
        ORDER BY d.run_id DESC, d.node_name""", tham_so)


# ---------------------------------------------------------------------------
# Trang 3 - Chi tiết một lần chạy
# ---------------------------------------------------------------------------
def danh_sach_run() -> pd.DataFrame:
    return db.truy_van("""SELECT run_id, pipeline_name, batch_id, triggered_by, status, started_at
                          FROM etl_log.v_run ORDER BY run_id DESC""")


def mot_lan_chay(run_id: int) -> pd.Series | None:
    kq = db.truy_van("SELECT * FROM etl_log.v_run WHERE run_id = %(r)s", {"r": run_id})
    return None if kq.empty else kq.iloc[0]


def table_load_cua(run_id: int) -> pd.DataFrame:
    return db.truy_van("""
        SELECT table_name, rows_source, rows_inserted, rows_updated, rows_rejected, rows_deleted,
               started_at, finished_at, status, error_message
        FROM etl_log.table_load WHERE run_id = %(r)s ORDER BY started_at, table_name""", {"r": run_id})


def quality_check_cua(run_id: int) -> pd.DataFrame:
    return db.truy_van("""
        SELECT table_name, check_name, status, failed_rows, detail, checked_at
        FROM etl_log.quality_check WHERE run_id = %(r)s
        ORDER BY CASE status WHEN 'FAIL' THEN 1 WHEN 'WARN' THEN 2 ELSE 3 END, checked_at, table_name, check_name""", {"r": run_id})


def dbt_node_cua(run_id: int) -> pd.DataFrame:
    return db.truy_van("""
        SELECT resource_type, node_name, relation_name, status, rows_affected, failures,
               execution_time, started_at, finished_at, message
        FROM etl_log.dbt_result WHERE run_id = %(r)s ORDER BY started_at NULLS LAST, node_name""", {"r": run_id})


NGUONG_MAGE_GIAY = 1.0   # đoạn Mage đầu / cuối ngắn hơn mức này thì không vẽ thanh riêng


def gantt_cac_buoc(run: pd.Series, tl: pd.DataFrame, dbt: pd.DataFrame, bay_gio: pd.Timestamp) -> pd.DataFrame:
    """Các bước của 1 lần chạy để vẽ Gantt, theo thứ tự thời gian: Mage khởi động (từ lúc lần chạy bắt đầu tới bảng staging đầu tiên),
    từng bảng staging, đoạn dbt khởi động / parse, dbt gộp theo seed / model / test, Mage ghi log (từ bước cuối tới lúc lần chạy kết thúc).
    Nhờ vậy tổng chiều dài Gantt bằng "Thời lượng". Trạng thái dbt lạ (ngoài success / pass / warn / skipped) tô như lỗi."""
    dong = []
    cuoi_run = run.finished_at if pd.notna(run.finished_at) else bay_gio
    if len(tl) and pd.notna(tl.started_at.min()) and (tl.started_at.min() - run.started_at).total_seconds() > NGUONG_MAGE_GIAY:
        dong.append(("Mage", "Mage (khởi động)", run.started_at, tl.started_at.min(), "SUCCESS"))
    for _, t in tl.iterrows():
        dong.append(("Nạp staging", f"staging.{t.table_name}", t.started_at,
                     t.finished_at if pd.notna(t.finished_at) else cuoi_run, t.status))
    cuoi_stg = tl.finished_at.max() if len(tl) and tl.finished_at.notna().any() else None
    cuoi_stg = None if cuoi_stg is None or pd.isna(cuoi_stg) or (tl.status == "RUNNING").any() else cuoi_stg
    moc_cuoi = cuoi_stg   # mốc kết thúc muộn nhất của các bước đã vẽ
    if len(dbt):
        bd_dbt = dbt.started_at.min()
        if cuoi_stg is not None and pd.notna(bd_dbt) and bd_dbt > cuoi_stg:
            dong.append(("dbt khởi động", "dbt khởi động / parse", cuoi_stg, bd_dbt, "SUCCESS"))
        for loai, nhom in dbt.groupby("resource_type", sort=False):
            bd, kt = nhom.started_at.min(), nhom.finished_at.max()
            if pd.isna(bd) or pd.isna(kt):
                continue
            xau = bool(nhom.status.map(la_loi_dbt).any())
            dong.append(("dbt build", f"dbt {loai} ({len(nhom)})", bd, kt, "FAILED" if xau else "SUCCESS"))
            moc_cuoi = kt if moc_cuoi is None else max(moc_cuoi, kt)
    elif run.status == "RUNNING" and cuoi_stg is not None and len(tl) and (tl.status == "SUCCESS").all():
        # staging đã commit, dbt đang chạy và chưa ghi kết quả (dbt_result chỉ được ghi khi dbt build xong)
        dong.append(("dbt build", "dbt đang chạy (chưa có kết quả)", cuoi_stg, bay_gio, "RUNNING"))
    if pd.notna(run.finished_at) and moc_cuoi is not None and (run.finished_at - moc_cuoi).total_seconds() > NGUONG_MAGE_GIAY:
        dong.append(("Mage", "Mage (ghi log)", moc_cuoi, run.finished_at, "SUCCESS"))
    return pd.DataFrame(dong, columns=["khau", "buoc", "bat_dau", "ket_thuc", "trang_thai"])
