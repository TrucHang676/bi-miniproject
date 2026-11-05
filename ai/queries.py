"""Số liệu cho 12 biểu đồ dashboard (Q1–Q6) và thẻ KPI của 3 trang, lấy thẳng từ dds.

Mỗi hàm tính lại đúng công thức DAX trong powerbi/measures.dax nên số phải khớp Power BI
(đối chiếu bằng ai/kiem_tra_so_lieu.py với bảng nghiệm thu B6 trong powerbi/README.md).
Luôn lọc dim_date.is_analysis_period = TRUE như filter cấp report (01/2017 – 08/2018).
AI chỉ được dùng số do các hàm ở đây trả về, không tự viết SQL.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Callable

import pandas as pd

from db import GOC_REPO, truy_van

# delivery_result của đơn đã giao: mẫu số K6, điều kiện của K7, M4
_DA_GIAO = "('Đúng hạn', 'Trễ hạn')"
THU_TU_MUC_TRE = ["Đúng hạn", "Trễ 1–3 ngày", "Trễ 4–7 ngày", "Trễ 8–14 ngày", "Trễ > 14 ngày"]

# Tên cột -> (nhãn hiển thị, kiểu số). Kiểu: brl | pct | so | diem | ngay | chu
COT = {
    "nam": ("Năm", "chu"),
    "thang": ("Tháng", "chu"),
    "ky": ("Tháng", "chu"),
    "doanh_thu": ("Doanh thu (BRL)", "brl"),
    "doanh_thu_cung_ky": ("Doanh thu cùng kỳ (BRL)", "brl"),
    "tang_truong_cung_ky": ("% so cùng kỳ", "pct"),
    "so_don": ("Số đơn", "so"),
    "gia_tri_don_tb": ("Giá trị đơn TB (BRL)", "brl"),
    "danh_muc": ("Danh mục", "chu"),
    "danh_muc_en": ("Danh mục (gốc)", "chu"),
    "ti_trong": ("% tổng doanh thu", "pct"),
    "vung": ("Vùng", "chu"),
    "bang": ("Bang", "chu"),
    "ten_bang": ("Tên bang", "chu"),
    "don_da_giao": ("Đơn đã giao", "so"),
    "don_tre": ("Đơn giao trễ", "so"),
    "ti_le_tre": ("Tỉ lệ giao trễ", "pct"),
    "ket_qua": ("Kết quả giao", "chu"),
    "muc_tre": ("Mức trễ", "chu"),
    "diem_tb": ("Điểm đánh giá TB (★)", "diem"),
    "so_don_co_danh_gia": ("Đơn có đánh giá", "so"),
    "ban_giao": ("Người bán bàn giao", "chu"),
    "tuyen": ("Tuyến", "chu"),
    "ti_le_ban_giao_tre": ("Tỉ lệ bàn giao trễ", "pct"),
    "van_chuyen_tb": ("Thời gian vận chuyển TB (ngày)", "ngay"),
    "xu_ly_tb": ("Thời gian xử lý TB của người bán (ngày, đặt hàng → bàn giao)", "ngay"),
    "luot_ban_giao_tre": ("Số lượt bàn giao trễ", "so"),
    "nguoi_ban": ("Người bán", "chu"),
    "seller_id": ("Mã người bán", "chu"),
    "can_xu_ly": ("Vượt ngưỡng (M5)", "chu"),
    "canh_bao": ("Vượt ngưỡng", "chu"),
}


# ---------------------------------------------------------------------------
# Bộ lọc
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BoLoc:
    """Bộ lọc giống slicer trên dashboard; None = không lọc."""

    nam: int | None = None
    thang: int | None = None
    vung: str | None = None     # dim_geography.region – nơi nhận hàng (trang 1, 2)
    bang: str | None = None     # dim_geography.state_code (trang 1)
    vung_nb: str | None = None  # dim_seller.seller_region – vùng của người bán (trang 3)
    bang_nb: str | None = None  # dim_seller.seller_state – nơi người bán (trang 3)

    def mo_ta(self) -> str:
        phan = []
        if self.nam:
            phan.append(f"năm {self.nam}")
        if self.thang:
            phan.append(f"tháng {self.thang}")
        if self.vung:
            phan.append(f"vùng {self.vung}")
        if self.bang:
            phan.append(f"bang {self.bang}")
        if self.vung_nb:
            phan.append(f"vùng người bán {self.vung_nb}")
        if self.bang_nb:
            phan.append(f"bang người bán {self.bang_nb}")
        return ", ".join(phan) if phan else "không lọc (toàn kỳ 01/2017 – 08/2018)"


def _loc(bl: BoLoc, *, bo_nam: bool = False, bo_dia_ly: bool = False) -> tuple[str, dict]:
    """Mệnh đề WHERE theo bộ lọc (alias d, g, s của _tu). bo_nam / bo_dia_ly = bỏ lọc đó như ALL() trong DAX."""
    dk, ts = ["d.is_analysis_period"], {}
    if bl.nam is not None and not bo_nam:
        dk.append("d.year = %(nam)s")
        ts["nam"] = bl.nam
    if bl.thang is not None:
        dk.append("d.month = %(thang)s")
        ts["thang"] = bl.thang
    if not bo_dia_ly:
        if bl.vung:
            dk.append("g.region = %(vung)s")
            ts["vung"] = bl.vung
        if bl.bang:
            dk.append("g.state_code = %(bang)s")
            ts["bang"] = bl.bang
    if bl.vung_nb:
        dk.append("s.seller_region = %(vung_nb)s")
        ts["vung_nb"] = bl.vung_nb
    if bl.bang_nb:
        dk.append("s.seller_state = %(bang_nb)s")
        ts["bang_nb"] = bl.bang_nb
    return " AND ".join(dk), ts


def _tu(fact: str) -> str:
    """FROM 1 bảng fact + 3 dimension dùng để lọc (cả 3 fact đều có đủ 3 khóa này)."""
    return f"""dds.{fact} f
        JOIN dds.dim_date d ON d.date_key = f.purchase_date_key
        JOIN dds.dim_geography g ON g.geography_key = f.geography_key
        JOIN dds.dim_seller s ON s.seller_key = f.seller_key"""


_DS = "JOIN dds.dim_delivery_status ds ON ds.delivery_status_key = f.delivery_status_key"
# K6: đếm theo order_id (đơn nhiều người bán chỉ tính 1 lần)
_SO_DA_GIAO = f"COUNT(DISTINCT f.order_id) FILTER (WHERE ds.delivery_result IN {_DA_GIAO})"
_SO_TRE = "COUNT(DISTINCT f.order_id) FILTER (WHERE ds.delivery_result = 'Trễ hạn')"


@dataclass
class KetQua:
    bang: pd.DataFrame
    tom_tat: dict = field(default_factory=dict)


def _rong() -> KetQua:
    return KetQua(pd.DataFrame(), {"ghi_chu": "Không có dữ liệu với bộ lọc này"})


def _ca_cac_thang(bl: BoLoc) -> BoLoc:
    """Biểu đồ theo tháng bỏ lọc Tháng để AI có tháng khác mà so; tháng đang chọn ghi vào tom_tat["thang_dang_xem"]."""
    return replace(bl, thang=None)


def _thang_dang_xem(df: pd.DataFrame, bl: BoLoc, cot: list[str]) -> dict:
    if not bl.thang:
        return {}
    dong = df[df.thang == bl.thang]
    return {"thang_dang_xem": dong[cot].to_dict("records") or f"Không có số liệu tháng {bl.thang}"}


def _ky(df: pd.DataFrame) -> pd.Series:
    return df.thang.astype(int).map("{:02d}".format) + "/" + df.nam.astype(int).astype(str)


@lru_cache
def ten_danh_muc_vi() -> dict[str, str]:
    """Tên danh mục tiếng Việt, lấy từ cột tính dim_product[category_name_vi] trong measures.dax (giữ 1 nguồn duy nhất)."""
    try:
        t = (GOC_REPO / "powerbi" / "measures.dax").read_text(encoding="utf-8")
        khoi = t.split("dim_product[category_name_vi] =", 1)[1].split("// ---", 1)[0]
    except (OSError, IndexError):
        return {}
    return dict(re.findall(r'"([a-z0-9_]+)", "([^"]+)"', khoi))


# ---------------------------------------------------------------------------
# Trang 1 – Tổng quan kinh doanh
# ---------------------------------------------------------------------------
def _cung_ky_ban_hang(bl: BoLoc) -> dict | None:
    """Dòng phụ thẻ K1–K4: 01–08/2018 so với 01–08/2017 trên các tháng đang chọn. None nếu không có cùng kỳ."""
    if bl.nam == 2017 or (bl.thang or 0) > 8:
        return None
    w, ts = _loc(bl, bo_nam=True)
    df = truy_van(f"""
        SELECT d.year AS nam, SUM(f.revenue) AS doanh_thu, COUNT(DISTINCT f.order_id) AS so_don,
               COUNT(DISTINCT f.customer_key) AS so_khach
        FROM {_tu('fact_sales')}
        WHERE {w} AND d.year IN (2017, 2018) AND d.month <= 8
        GROUP BY 1""", ts).set_index("nam")
    if not {2017, 2018} <= set(df.index):
        return None
    df["gia_tri_don_tb"] = df.doanh_thu / df.so_don
    ky = f"tháng {bl.thang:02d}" if bl.thang else "01–08"
    kq = {"ky_so_sanh": f"{ky}/2018 so với {ky}/2017"}
    for cot in ("doanh_thu", "so_don", "gia_tri_don_tb", "so_khach"):
        truoc, nay = df.at[2017, cot], df.at[2018, cot]
        kq[cot] = {"2017": truoc, "2018": nay, "tang_truong": nay / truoc - 1}
    return kq


def doanh_thu_theo_thang(bl: BoLoc) -> KetQua:
    """Q1 (1): doanh thu theo tháng, mỗi năm 1 đường; % so cùng kỳ (M1, M2) chỉ có ở 01–08/2018."""
    # M1 dùng SAMEPERIODLASTYEAR: cần năm trước kể cả khi đang lọc 2018
    w, ts = _loc(_ca_cac_thang(bl), bo_nam=True)
    df = truy_van(f"""
        SELECT d.year AS nam, d.month AS thang, SUM(f.revenue) AS doanh_thu, COUNT(DISTINCT f.order_id) AS so_don
        FROM {_tu('fact_sales')} WHERE {w}
        GROUP BY 1, 2 ORDER BY 1, 2""", ts)
    if df.empty:
        return _rong()
    df["gia_tri_don_tb"] = df.doanh_thu / df.so_don
    nam_truoc = df[df.nam == 2017].set_index("thang").doanh_thu
    df["doanh_thu_cung_ky"] = [
        nam_truoc.get(t, math.nan) if n == 2018 and t <= 8 else math.nan for n, t in zip(df.nam, df.thang)
    ]
    df["tang_truong_cung_ky"] = df.doanh_thu / df.doanh_thu_cung_ky - 1
    if bl.nam is not None:
        df = df[df.nam == bl.nam].reset_index(drop=True)
    if df.empty:
        return _rong()
    df.insert(0, "ky", _ky(df))
    dinh = df.loc[df.doanh_thu.idxmax()]
    return KetQua(df, {
        "thang_doanh_thu_cao_nhat": dinh.ky,
        "doanh_thu_thang_cao_nhat": dinh.doanh_thu,
        "so_cung_ky": _cung_ky_ban_hang(bl) or "Không có cùng kỳ để so (chỉ so được 01–08/2018 với 01–08/2017)",
        **_thang_dang_xem(df, bl, ["ky", "doanh_thu", "so_don", "gia_tri_don_tb", "tang_truong_cung_ky"]),
    })


def so_don_va_aov_theo_thang(bl: BoLoc) -> KetQua:
    """Q1 (2): số đơn (cột) và giá trị đơn TB (đường) theo tháng."""
    kq = doanh_thu_theo_thang(bl)
    if kq.bang.empty:
        return kq
    bang = kq.bang[["ky", "nam", "thang", "so_don", "gia_tri_don_tb", "doanh_thu"]]
    giu = ("so_cung_ky", "thang_dang_xem")
    return KetQua(bang, {k: v for k, v in kq.tom_tat.items() if k in giu})


def top10_danh_muc(bl: BoLoc) -> KetQua:
    """Q2 (1): 10 danh mục doanh thu cao nhất; tỉ trọng = M3 (mẫu số bỏ lọc danh mục và địa lý)."""
    w, ts = _loc(bl)
    w_tong, _ = _loc(bl, bo_dia_ly=True)
    df = truy_van(f"""
        WITH tong AS (SELECT SUM(f.revenue) AS dt FROM {_tu('fact_sales')} WHERE {w_tong})
        SELECT p.category_name_en AS danh_muc_en, SUM(f.revenue) AS doanh_thu, COUNT(DISTINCT f.order_id) AS so_don,
               SUM(f.revenue) / (SELECT dt FROM tong) AS ti_trong
        FROM {_tu('fact_sales')} JOIN dds.dim_product p ON p.product_key = f.product_key
        WHERE {w}
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", ts)
    if df.empty:
        return _rong()
    df.insert(0, "danh_muc", df.danh_muc_en.map(lambda x: ten_danh_muc_vi().get(x, x)))
    return KetQua(df, {"ti_trong_nhom_top10_danh_muc": df.ti_trong.sum()})


def doanh_thu_theo_bang(bl: BoLoc) -> KetQua:
    """Q2 (2): doanh thu và tỉ trọng (M3) theo bang nhận hàng, kèm nhóm top 5 bang (M3b) và theo vùng."""
    w, ts = _loc(bl)
    w_tong, _ = _loc(bl, bo_dia_ly=True)
    df = truy_van(f"""
        WITH tong AS (SELECT SUM(f.revenue) AS dt FROM {_tu('fact_sales')} WHERE {w_tong})
        SELECT g.region AS vung, g.state_code AS bang, g.state_name AS ten_bang,
               SUM(f.revenue) AS doanh_thu, COUNT(DISTINCT f.order_id) AS so_don,
               SUM(f.revenue) / (SELECT dt FROM tong) AS ti_trong
        FROM {_tu('fact_sales')} WHERE {w}
        GROUP BY 1, 2, 3 ORDER BY 4 DESC""", ts)
    if df.empty:
        return _rong()
    vung = (df.groupby("vung", as_index=False)[["doanh_thu", "ti_trong"]].sum()
              .sort_values("doanh_thu", ascending=False))
    return KetQua(df, {
        "ti_trong_nhom_top5_bang": df.head(5).ti_trong.sum(),
        "top5_bang": df.head(5).bang.tolist(),
        "theo_vung": vung.to_dict("records"),
    })


# ---------------------------------------------------------------------------
# Trang 2 – Giao hàng & trải nghiệm khách hàng
# ---------------------------------------------------------------------------
def tre_theo_thang(bl: BoLoc) -> KetQua:
    """Q3 (1): tỉ lệ giao trễ K6 theo tháng, ngưỡng cảnh báo 10%."""
    w, ts = _loc(_ca_cac_thang(bl))
    df = truy_van(f"""
        SELECT d.year AS nam, d.month AS thang, {_SO_DA_GIAO} AS don_da_giao, {_SO_TRE} AS don_tre
        FROM {_tu('fact_delivery')} {_DS} WHERE {w}
        GROUP BY 1, 2 ORDER BY 1, 2""", ts)
    df = df[df.don_da_giao > 0].reset_index(drop=True)
    if df.empty:
        return _rong()
    df["ti_le_tre"] = df.don_tre / df.don_da_giao
    df.insert(0, "ky", _ky(df))
    vuot = df[df.ti_le_tre > 0.10]
    return KetQua(df, {
        "nguong_canh_bao": 0.10,
        "thang_vuot_nguong": vuot[["ky", "ti_le_tre"]].to_dict("records"),
        **_thang_dang_xem(df, bl, ["ky", "ti_le_tre", "don_da_giao", "don_tre"]),
    })


def tre_theo_bang(bl: BoLoc) -> KetQua:
    """Q3 (2): 10 bang nhận hàng có tỉ lệ giao trễ cao nhất."""
    w, ts = _loc(bl)
    df = truy_van(f"""
        SELECT g.state_code AS bang, g.state_name AS ten_bang, g.region AS vung,
               {_SO_DA_GIAO} AS don_da_giao, {_SO_TRE} AS don_tre
        FROM {_tu('fact_delivery')} {_DS} WHERE {w}
        GROUP BY 1, 2, 3""", ts)
    df = df[df.don_da_giao > 0]
    if df.empty:
        return _rong()
    df["ti_le_tre"] = df.don_tre / df.don_da_giao
    df = df.sort_values("ti_le_tre", ascending=False).reset_index(drop=True)
    return KetQua(df.head(10), {
        "nguong_canh_bao": 0.10,
        "so_bang_vuot_nguong": int((df.ti_le_tre > 0.10).sum()),
        "tong_so_bang": len(df),
        "ghi_chu": "Bang ít đơn thì tỉ lệ dao động mạnh, đọc kèm số đơn đã giao",
    })


def _diem_theo_don(bl: BoLoc, **nhom: str) -> tuple[str, dict]:
    """Câu con: 1 dòng / đơn (+ cột nhóm tên=biểu thức), điểm = MAX review_score của đánh giá mới nhất (như K8)."""
    w, ts = _loc(bl)
    chon = "".join(f"{bt} AS {ten}, " for ten, bt in nhom.items())
    gom = "".join(f"{bt}, " for bt in nhom.values())
    return f"""
        SELECT {chon}f.order_id, MAX(f.review_score) AS diem
        FROM {_tu('fact_review')} {_DS}
        WHERE f.is_latest_review AND {w}
        GROUP BY {gom}f.order_id""", ts


def diem_theo_muc_tre(bl: BoLoc) -> KetQua:
    """Q4 (1): điểm đánh giá TB (K8) theo kết quả giao → mức trễ; đường tham chiếu = điểm TB toàn sàn."""
    con, ts = _diem_theo_don(bl, ket_qua="ds.delivery_result", muc_tre="ds.delay_bucket")
    df = truy_van(f"""
        SELECT ket_qua, muc_tre, AVG(diem) AS diem_tb, COUNT(*) AS so_don_co_danh_gia
        FROM ({con}) x WHERE ket_qua IN {_DA_GIAO}
        GROUP BY 1, 2""", ts)
    if df.empty:
        return _rong()
    df["thu_tu"] = df.muc_tre.map({m: i for i, m in enumerate(THU_TU_MUC_TRE)})
    df = df.sort_values("thu_tu").drop(columns="thu_tu").reset_index(drop=True)
    con_tat_ca, _ = _diem_theo_don(bl)
    toan_san = truy_van(f"SELECT AVG(diem) AS v FROM ({con_tat_ca}) x", ts).v.iat[0]
    # mỗi đơn nằm ở đúng 1 mức trễ nên TB có trọng số theo số đơn = TB của cả nhóm kết quả giao
    cap1 = (df.assign(tong=df.diem_tb * df.so_don_co_danh_gia).groupby("ket_qua")[["tong", "so_don_co_danh_gia"]].sum())
    cap1 = (cap1.tong / cap1.so_don_co_danh_gia).to_dict()
    tom_tat = {"diem_tb_toan_san": toan_san, "diem_tb_theo_ket_qua_giao": cap1}
    if {"Đúng hạn", "Trễ hạn"} <= cap1.keys():
        tom_tat["chenh_lech_dung_han_tru_tre_han"] = cap1["Đúng hạn"] - cap1["Trễ hạn"]
    return KetQua(df, tom_tat)


def tre_va_diem_theo_thang(bl: BoLoc) -> KetQua:
    """Q4 (2): tỉ lệ giao trễ (cột) và điểm đánh giá TB (đường) theo tháng."""
    tre = tre_theo_thang(bl).bang
    if tre.empty:
        return _rong()
    con, ts = _diem_theo_don(_ca_cac_thang(bl), nam="d.year", thang="d.month")
    diem = truy_van(f"SELECT nam, thang, AVG(diem) AS diem_tb FROM ({con}) x GROUP BY 1, 2", ts)
    df = tre[["ky", "nam", "thang", "ti_le_tre", "don_da_giao"]].merge(diem, on=["nam", "thang"], how="left")
    tom_tat = {
        "thang_tre_cao_nhat": df.loc[df.ti_le_tre.idxmax(), "ky"],
        "thang_diem_thap_nhat": df.loc[df.diem_tb.idxmin(), "ky"],
        **_thang_dang_xem(df, bl, ["ky", "ti_le_tre", "diem_tb"]),
    }
    if len(df) >= 3:
        tom_tat["he_so_tuong_quan_tre_va_diem"] = df.ti_le_tre.corr(df.diem_tb)
    return KetQua(df, tom_tat)


# ---------------------------------------------------------------------------
# Trang 3 – Người bán & vận chuyển
# ---------------------------------------------------------------------------
def tre_theo_ban_giao(bl: BoLoc) -> KetQua:
    """Q5 (1): tỉ lệ giao trễ K6 theo người bán bàn giao đúng hạn / trễ × tuyến nội bang / liên bang."""
    w, ts = _loc(bl)
    df = truy_van(f"""
        SELECT ds.handover_status AS ban_giao, ds.route_type AS tuyen, {_SO_DA_GIAO} AS don_da_giao, {_SO_TRE} AS don_tre
        FROM {_tu('fact_delivery')} {_DS}
        WHERE {w} AND ds.handover_status IN ('Đúng hạn', 'Trễ hạn') AND ds.route_type IN ('Nội bang', 'Liên bang')
        GROUP BY 1, 2 ORDER BY 1, 2 DESC""", ts)
    if df.empty:
        return _rong()
    df["ti_le_tre"] = df.don_tre / df.don_da_giao
    # gộp mọi tuyến phải đếm lại từ fact: đơn nhiều người bán có thể thuộc 2 tuyến
    tong = truy_van(f"""
        SELECT ds.handover_status AS ban_giao, {_SO_DA_GIAO} AS don_da_giao, {_SO_TRE} AS don_tre
        FROM {_tu('fact_delivery')} {_DS}
        WHERE {w} AND ds.handover_status IN ('Đúng hạn', 'Trễ hạn')
        GROUP BY 1""", ts).set_index("ban_giao")
    tl = (tong.don_tre / tong.don_da_giao).to_dict()
    # kèm số đơn đã đếm lại để AI trích thẳng, không tự cộng 2 tuyến (cộng sẽ đếm trùng đơn nhiều người bán)
    tom_tat = {"ti_le_tre_moi_tuyen": tl, "so_don_moi_tuyen": tong[["don_da_giao", "don_tre"]].to_dict("index")}
    if tl.get("Đúng hạn"):
        tom_tat["ban_giao_tre_gap_so_lan"] = tl.get("Trễ hạn", math.nan) / tl["Đúng hạn"]
    return KetQua(df, tom_tat)


def ban_giao_va_van_chuyen_theo_thang(bl: BoLoc) -> KetQua:
    """Q5 (2): tỉ lệ bàn giao trễ K12 (cột), thời gian xử lý TB và thời gian vận chuyển TB M4 (2 đường) theo tháng,
    kèm số lượt bàn giao trễ (tooltip) và K6. Thời gian xử lý = delivery_days - transit_days (đặt hàng -> bàn giao),
    mỗi đơn 1 lần, đơn đã giao, bỏ đơn bàn giao "Không xác định" – như measure 'Thời gian xử lý TB'."""
    w, ts = _loc(_ca_cac_thang(bl))
    df = truy_van(f"""
        WITH don AS (
            SELECT d.year AS nam, d.month AS thang, f.order_id, MAX(f.transit_days) AS van_chuyen,
                   MAX(f.delivery_days) FILTER (WHERE ds.handover_status IN ('Đúng hạn', 'Trễ hạn'))
                   - MAX(f.transit_days) FILTER (WHERE ds.handover_status IN ('Đúng hạn', 'Trễ hạn')) AS xu_ly
            FROM {_tu('fact_delivery')} {_DS}
            WHERE {w} AND ds.delivery_result IN {_DA_GIAO}
            GROUP BY 1, 2, 3)
        SELECT d.year AS nam, d.month AS thang,
               COUNT(*) FILTER (WHERE ds.handover_status = 'Trễ hạn')::float
                 / NULLIF(COUNT(*) FILTER (WHERE ds.handover_status IN ('Đúng hạn', 'Trễ hạn')), 0) AS ti_le_ban_giao_tre,
               COUNT(*) FILTER (WHERE ds.handover_status = 'Trễ hạn') AS luot_ban_giao_tre,
               (SELECT AVG(v.xu_ly) FROM don v WHERE v.nam = d.year AND v.thang = d.month) AS xu_ly_tb,
               (SELECT AVG(v.van_chuyen) FROM don v WHERE v.nam = d.year AND v.thang = d.month) AS van_chuyen_tb,
               {_SO_DA_GIAO} AS don_da_giao, {_SO_TRE} AS don_tre
        FROM {_tu('fact_delivery')} {_DS} WHERE {w}
        GROUP BY 1, 2 ORDER BY 1, 2""", ts)
    df = df[df.don_da_giao > 0].reset_index(drop=True)
    if df.empty:
        return _rong()
    df["ti_le_tre"] = df.don_tre / df.don_da_giao
    df.insert(0, "ky", _ky(df))
    dot_bien = df.ti_le_tre > 0.10  # tháng đột biến = tháng K6 > 10%, cột tô đỏ trên dashboard
    cot = ["ky", "ti_le_tre", "ti_le_ban_giao_tre", "luot_ban_giao_tre", "xu_ly_tb", "van_chuyen_tb"]
    tom_tat = {"thang_dot_bien_K6_tren_10": df.loc[dot_bien, cot].to_dict("records")}
    if (~dot_bien).any():
        tom_tat["trung_binh_cong_cac_thang_con_lai"] = {
            "ti_le_ban_giao_tre": df.loc[~dot_bien, "ti_le_ban_giao_tre"].mean(),
            "xu_ly_tb": df.loc[~dot_bien, "xu_ly_tb"].mean(),
            "van_chuyen_tb": df.loc[~dot_bien, "van_chuyen_tb"].mean(),
        }
    tom_tat.update(_thang_dang_xem(df, bl, cot))
    return KetQua(df, tom_tat)


def _nguoi_ban(bl: BoLoc) -> pd.DataFrame:
    """Mỗi người bán 1 dòng: số đơn K2, doanh thu K1, điểm K8, bàn giao trễ K12, cờ M5 (cùng ngữ cảnh lọc)."""
    w, ts = _loc(bl)
    df = truy_van(f"""
        WITH ban AS (
            SELECT f.seller_key, SUM(f.revenue) AS doanh_thu, COUNT(DISTINCT f.order_id) AS so_don
            FROM {_tu('fact_sales')} WHERE {w} GROUP BY 1),
        ban_giao AS (
            SELECT f.seller_key,
                   COUNT(*) FILTER (WHERE ds.handover_status = 'Trễ hạn')::float
                     / NULLIF(COUNT(*) FILTER (WHERE ds.handover_status IN ('Đúng hạn', 'Trễ hạn')), 0) AS tl
            FROM {_tu('fact_delivery')} {_DS} WHERE {w} GROUP BY 1),
        diem AS (
            SELECT seller_key, AVG(diem) AS diem_tb FROM (
                SELECT f.seller_key, f.order_id, MAX(f.review_score) AS diem
                FROM {_tu('fact_review')} WHERE f.is_latest_review AND {w} GROUP BY 1, 2) x
            GROUP BY 1)
        SELECT LEFT(sl.seller_id, 6) || ' · ' || UPPER(LEFT(sl.seller_city, 1)) || SUBSTR(sl.seller_city, 2)
                 || ' – ' || sl.seller_state AS nguoi_ban,
               sl.seller_id, b.so_don, b.doanh_thu, dm.diem_tb, bg.tl AS ti_le_ban_giao_tre
        FROM ban b
        JOIN dds.dim_seller sl ON sl.seller_key = b.seller_key
        LEFT JOIN ban_giao bg ON bg.seller_key = b.seller_key
        LEFT JOIN diem dm ON dm.seller_key = b.seller_key
        ORDER BY b.doanh_thu DESC""", ts)
    diem_thap = df.diem_tb.lt(3.5).fillna(False)
    tre = df.ti_le_ban_giao_tre.gt(0.10).fillna(False)
    df["diem_thap"], df["tre"] = diem_thap, tre
    df["can_xu_ly"] = (df.so_don >= 30) & (diem_thap | tre)
    df["canh_bao"] = [
        " · ".join(x for x in (f"Trễ {t:.0%}" if tr else "", f"{so_vn(d, 2)}★" if dt else "") if x)
        for t, d, tr, dt in zip(df.ti_le_ban_giao_tre, df.diem_tb, tre, diem_thap)
    ]
    return df


def _tom_tat_nguoi_ban(df: pd.DataFrame) -> dict:
    nhom30 = df[df.so_don >= 30]
    can = df[df.can_xu_ly]
    tong = df.doanh_thu.sum()
    return {
        "nguong": "≥ 30 đơn và (điểm TB < 3,5 hoặc bàn giao trễ > 10%)",
        "so_nguoi_ban_hoat_dong": len(df),
        "so_nguoi_ban_tu_30_don": len(nhom30),
        "ti_trong_doanh_thu_nhom_tu_30_don": nhom30.doanh_thu.sum() / tong if tong else math.nan,
        "so_nguoi_ban_can_xu_ly": len(can),
        "trong_do_diem_duoi_3_5": int(can.diem_thap.sum()),
        "trong_do_ban_giao_tre_tren_10": int(can.tre.sum()),
        "trong_do_vi_pham_ca_hai": int((can.diem_thap & can.tre).sum()),
        "ti_trong_doanh_thu_nguoi_ban_can_xu_ly": can.doanh_thu.sum() / tong if tong else math.nan,
    }


_COT_NGUOI_BAN = ["nguoi_ban", "so_don", "doanh_thu", "diem_tb", "ti_le_ban_giao_tre", "canh_bao", "seller_id"]


def nguoi_ban_tu_30_don(bl: BoLoc) -> KetQua:
    """Q6 (1): scatter người bán ≥ 30 đơn – X bàn giao trễ, Y điểm TB, cỡ chấm doanh thu, ngưỡng 10% / 3,5."""
    df = _nguoi_ban(bl)
    if df.empty:
        return _rong()
    nhom30 = df[df.so_don >= 30]
    return KetQua(nhom30[_COT_NGUOI_BAN + ["can_xu_ly"]].reset_index(drop=True), _tom_tat_nguoi_ban(df))


def top10_nguoi_ban_can_xu_ly(bl: BoLoc) -> KetQua:
    """Q6 (2): 10 người bán vượt ngưỡng (M5 = 1) có doanh thu lớn nhất; chuột phải → trang Chi tiết người bán."""
    df = _nguoi_ban(bl)
    if df.empty:
        return _rong()
    can = df[df.can_xu_ly]
    top = can.head(10)
    tom_tat = _tom_tat_nguoi_ban(df)
    if len(can):
        tom_tat["ti_trong_cua_top10_trong_doanh_thu_nhom_can_xu_ly"] = top.doanh_thu.sum() / can.doanh_thu.sum()
    return KetQua(top[_COT_NGUOI_BAN].reset_index(drop=True), tom_tat)


# ---------------------------------------------------------------------------
# Thẻ KPI
# ---------------------------------------------------------------------------
def _gia_tri(sql: str, ts: dict) -> pd.Series:
    df = truy_van(sql, ts)
    return df.iloc[0] if len(df) else pd.Series(dtype=float)


def the_kpi(trang: int, bl: BoLoc) -> dict:
    """Số trên hàng thẻ KPI của 1 trang: {mã: {ten, gia_tri, kieu, ghi_chu?}}."""
    w, ts = _loc(bl)
    if trang == 1:
        r = _gia_tri(f"""SELECT SUM(f.revenue) AS k1, COUNT(DISTINCT f.order_id) AS k2, COUNT(DISTINCT f.customer_key) AS k4
                         FROM {_tu('fact_sales')} WHERE {w}""", ts)
        k5 = _gia_tri(f"""SELECT COUNT(*) FILTER (WHERE n >= 2)::float / NULLIF(COUNT(*), 0) AS v FROM (
                              SELECT f.customer_key, COUNT(DISTINCT f.purchase_seq) AS n
                              FROM {_tu('fact_sales')} WHERE {w} GROUP BY 1) x""", ts).v
        ck = _cung_ky_ban_hang(bl)

        def _ghi(cot):
            return f"{ck[cot]['tang_truong']:+.1%} so cùng kỳ ({ck['ky_so_sanh']})" if ck else "Không có cùng kỳ để so"

        return {
            "K1": {"ten": "Doanh thu", "gia_tri": r.k1, "kieu": "brl", "ghi_chu": _ghi("doanh_thu")},
            "K2": {"ten": "Số đơn", "gia_tri": r.k2, "kieu": "so", "ghi_chu": _ghi("so_don")},
            "K3": {"ten": "Giá trị đơn TB", "gia_tri": r.k1 / r.k2 if r.k2 else math.nan, "kieu": "brl",
                   "ghi_chu": _ghi("gia_tri_don_tb")},
            "K4": {"ten": "Số khách hàng", "gia_tri": r.k4, "kieu": "so", "ghi_chu": _ghi("so_khach")},
            "K5": {"ten": "Tỉ lệ khách mua lại", "gia_tri": k5, "kieu": "pct"},
        }
    if trang == 2:
        r = _gia_tri(f"""SELECT {_SO_DA_GIAO} AS da_giao, {_SO_TRE} AS tre FROM {_tu('fact_delivery')} {_DS}
                         WHERE {w}""", ts)
        k7 = _gia_tri(f"""SELECT AVG(ngay) AS v FROM (
                              SELECT f.order_id, MAX(f.delivery_days) AS ngay FROM {_tu('fact_delivery')} {_DS}
                              WHERE {w} AND ds.delivery_result IN {_DA_GIAO} GROUP BY 1) x""", ts).v
        con, _ = _diem_theo_don(bl)
        dg = _gia_tri(f"""SELECT AVG(diem) AS k8, COUNT(*) FILTER (WHERE diem <= 2)::float / NULLIF(COUNT(*), 0) AS k9
                          FROM ({con}) x""", ts)
        return {
            "K6": {"ten": "Tỉ lệ giao trễ", "gia_tri": r.tre / r.da_giao if r.da_giao else math.nan, "kieu": "pct",
                   "ghi_chu": f"{int(r.tre)} / {int(r.da_giao)} đơn đã giao; mục tiêu ≤ 5%, cảnh báo > 10%"},
            "K7": {"ten": "Thời gian giao TB", "gia_tri": k7, "kieu": "ngay"},
            "K8": {"ten": "Điểm đánh giá TB", "gia_tri": dg.k8, "kieu": "diem", "ghi_chu": "mục tiêu ≥ 4,0, cảnh báo < 3,5"},
            "K9": {"ten": "Tỉ lệ đánh giá 1–2★", "gia_tri": dg.k9, "kieu": "pct",
                   "ghi_chu": "mục tiêu ≤ 10%, cảnh báo > 20%"},
        }
    if trang == 3:
        nb = truy_van(f"""SELECT f.seller_key, SUM(f.revenue) AS dt FROM {_tu('fact_sales')} WHERE {w} GROUP BY 1""", ts)
        nb = nb.sort_values("dt", ascending=False)
        n = len(nb)
        so_top = math.ceil(n * 0.1)
        k12 = _gia_tri(f"""SELECT COUNT(*) FILTER (WHERE ds.handover_status = 'Trễ hạn')::float
                                    / NULLIF(COUNT(*) FILTER (WHERE ds.handover_status IN ('Đúng hạn', 'Trễ hạn')), 0) AS v
                             FROM {_tu('fact_delivery')} {_DS} WHERE {w}""", ts).v
        ghi_k10, ck_k10 = "Không có cùng kỳ để so", None
        if bl.nam != 2017 and (bl.thang or 0) <= 8:
            w_ck, ts_ck = _loc(bl, bo_nam=True)
            ck = truy_van(f"""SELECT d.year AS nam, COUNT(DISTINCT f.seller_key) AS n FROM {_tu('fact_sales')}
                              WHERE {w_ck} AND d.year IN (2017, 2018) AND d.month <= 8 GROUP BY 1""", ts_ck)
            ck = dict(zip(ck.nam, ck.n))
            if ck.get(2017) and ck.get(2018):
                ky = f"tháng {bl.thang:02d}" if bl.thang else "01–08"
                ghi_k10 = (f"{ck[2018] / ck[2017] - 1:+.0%} và {ck[2018] - ck[2017]:+d} người bán so cùng kỳ {ky} "
                           f"({ck[2017]} → {ck[2018]})")
                ck_k10 = (ck[2017], ck[2018])
        return {
            "K10": {"ten": "Số người bán hoạt động", "gia_tri": n, "kieu": "so", "ghi_chu": ghi_k10, "ck": ck_k10},
            "K11": {"ten": "Doanh thu TB mỗi người bán", "gia_tri": nb.dt.sum() / n if n else math.nan, "kieu": "brl",
                    "ghi_chu": f"trung vị chỉ {so_vn(nb.dt.median(), 0)} BRL" if n else "",
                    "trung_vi": nb.dt.median() if n else None},
            "K12": {"ten": "Tỉ lệ bàn giao trễ", "gia_tri": k12, "kieu": "pct",
                    "ghi_chu": "mục tiêu ≤ 5%, cảnh báo > 10%"},
            "K13": {"ten": "Tỷ trọng doanh thu top 10% người bán",
                    "gia_tri": nb.dt.head(so_top).sum() / nb.dt.sum() if n else math.nan, "kieu": "pct",
                    "ghi_chu": f"{so_top} / {n} người bán dẫn đầu"},
        }
    raise ValueError(f"Không có trang {trang}")


def _theo_nguong(v, tot: float, xau: float, nho_la_tot: bool, don_vi: str) -> tuple[str, str]:
    """Dòng phụ thẻ theo ngưỡng, cùng chữ với các measure '… so mục tiêu' trong measures.dax."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "Chưa có số liệu", "trung_tinh"
    vuot_xau = v > xau if nho_la_tot else v < xau
    vuot_tot = v > tot if nho_la_tot else v < tot
    f = (lambda x: f"{so_vn(x * 100, 0)}%") if don_vi == "%" else (lambda x: f"{so_vn(x, 1)}★")
    if vuot_xau:
        return f"⚠ {'Vượt' if nho_la_tot else 'Dưới'} ngưỡng cảnh báo {f(xau)}", "xau"
    if vuot_tot:
        return f"⚠ {'Cao' if nho_la_tot else 'Thấp'} hơn mục tiêu {f(tot)}", "canh_bao"
    return f"✓ Đạt mục tiêu (từ {f(tot)} trở {'xuống' if nho_la_tot else 'lên'})", "tot"


def the_powerbi(trang: int, bl: BoLoc) -> list[dict]:
    """Thẻ KPI y như trên dashboard: tiêu đề, số đã định dạng (measure '… (thẻ)'), dòng phụ và kiểu màu dòng phụ.

    Kiểu màu: tang | giam | tot | canh_bao | xau | trung_tinh (app đổi thành màu theo nền thẻ).
    """
    k = the_kpi(trang, bl)

    def ss(cu_moi, dinh_dang_chenh, hau_to, pct_le=0):
        if not cu_moi:
            return "Không có cùng kỳ để so", "trung_tinh"
        truoc, nay = cu_moi
        tang = nay / truoc - 1
        return (f"{'↑' if tang >= 0 else '↓'} {'+' if tang >= 0 else '−'}{so_vn(abs(tang) * 100, pct_le)}% và "
                f"{dinh_dang_chenh(nay - truoc)}{hau_to}", "tang" if tang >= 0 else "giam")

    dau = lambda x, le=0: ("+" if x >= 0 else "−") + so_vn(abs(x), le)
    if trang == 1:
        ck = _cung_ky_ban_hang(bl)
        lay = lambda cot: (ck[cot]["2017"], ck[cot]["2018"]) if ck else None
        return [
            {"ten": "Doanh thu", "so": f"{so_vn(k['K1']['gia_tri'] / 1e6, 2)} tr",
             **dict(zip(("ghi", "kieu"), ss(lay("doanh_thu"), lambda x: dau(x / 1e6, 2), " tr so cùng kỳ")))},
            {"ten": "Số đơn", "so": so_vn(k["K2"]["gia_tri"]),
             **dict(zip(("ghi", "kieu"), ss(lay("so_don"), dau, " đơn")))},
            {"ten": "Giá trị đơn TB", "so": so_vn(k['K3']['gia_tri'], 2),
             **dict(zip(("ghi", "kieu"), ss(lay("gia_tri_don_tb"), lambda x: dau(x, 2), " BRL", pct_le=1)))},
            {"ten": "Số khách hàng", "so": so_vn(k["K4"]["gia_tri"]),
             **dict(zip(("ghi", "kieu"), ss(lay("so_khach"), dau, " khách")))},
            {"ten": "Tỉ lệ khách mua lại", "so": f"{so_vn(k['K5']['gia_tri'] * 100, 2)}%",
             "ghi": f"↓ {so_vn((1 - k['K5']['gia_tri']) * 100, 1)}% chỉ mua 1 lần", "kieu": "giam"},
        ]
    if trang == 2:
        return [
            {"ten": "Tỉ lệ giao trễ", "so": f"{so_vn(k['K6']['gia_tri'] * 100, 1)}%",
             **dict(zip(("ghi", "kieu"), _theo_nguong(k["K6"]["gia_tri"], 0.05, 0.10, True, "%")))},
            {"ten": "Thời gian giao trung bình", "so": f"{so_vn(k['K7']['gia_tri'], 1)} ngày",
             "ghi": "Từ lúc đặt đến khi khách nhận", "kieu": "trung_tinh"},
            {"ten": "Điểm đánh giá trung bình", "so": f"{so_vn(k['K8']['gia_tri'], 2)} ★",
             **dict(zip(("ghi", "kieu"), _theo_nguong(k["K8"]["gia_tri"], 4.0, 3.5, False, "★")))},
            {"ten": "Tỉ lệ đánh giá 1–2 ★", "so": f"{so_vn(k['K9']['gia_tri'] * 100, 1)}%",
             **dict(zip(("ghi", "kieu"), _theo_nguong(k["K9"]["gia_tri"], 0.10, 0.20, True, "%")))},
        ]
    n = k["K10"]["gia_tri"]
    tv = k["K11"].get("trung_vi")
    return [
        {"ten": "Người bán hoạt động", "so": so_vn(n),
         **dict(zip(("ghi", "kieu"), ss(k["K10"].get("ck"), dau, " người bán so cùng kỳ")))},
        {"ten": "Doanh thu TB mỗi người bán", "so": f"{so_vn(k['K11']['gia_tri'])} BRL",
         "ghi": f"Trung vị chỉ {so_vn(tv)} BRL" if tv is not None else "Chưa có doanh thu", "kieu": "giam"},
        {"ten": "Người bán bàn giao trễ", "so": f"{so_vn(k['K12']['gia_tri'] * 100, 1)}%",
         **dict(zip(("ghi", "kieu"), _theo_nguong(k["K12"]["gia_tri"], 0.05, 0.10, True, "%")))},
        {"ten": "Tỉ trọng DT của top 10% người bán", "so": f"{so_vn(k['K13']['gia_tri'] * 100, 1)}%",
         "ghi": f"{so_vn(math.ceil(n * 0.1))} / {so_vn(n)} người bán dẫn đầu", "kieu": "giam"},
    ]


# ---------------------------------------------------------------------------
# Danh mục trang, câu hỏi, biểu đồ
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Trang:
    ten: str
    bo_loc: tuple[str, ...]  # tên trường của BoLoc mà slicer trang đó có


TRANG = {
    1: Trang("Tổng quan kinh doanh", ("nam", "thang", "vung", "bang")),
    2: Trang("Giao hàng & trải nghiệm khách hàng", ("nam", "thang", "vung")),
    3: Trang("Người bán & vận chuyển", ("nam", "thang", "vung_nb", "bang_nb")),
}

CAU_HOI = {
    "Q1": "Doanh thu theo tháng biến động thế nào, 01–08/2018 tăng bao nhiêu % so với cùng kỳ, "
          "và tăng nhờ số đơn hay nhờ giá trị đơn trung bình?",
    "Q2": "10 danh mục và 5 bang nào có doanh thu cao nhất, và chiếm bao nhiêu % tổng doanh thu?",
    "Q3": "Những tháng nào có tỉ lệ giao trễ vượt 10%, và bang nào giao trễ nhiều nhất?",
    "Q4": "Đơn giao trễ bị đánh giá thấp hơn đơn đúng hạn bao nhiêu sao, "
          "và tháng giao trễ tăng thì điểm đánh giá chung có giảm theo không?",
    "Q5": "Người bán bàn giao trễ làm tỉ lệ giao trễ tăng bao nhiêu lần, và các tháng giao trễ đột biến "
          "là do người bán bàn giao chậm hay do vận chuyển kéo dài?",
    "Q6": "Trong người bán có từ 30 đơn, ai có điểm TB < 3,5 hoặc bàn giao trễ > 10%, "
          "và 10 người nào doanh thu lớn nhất cần ưu tiên xử lý?",
}


@dataclass(frozen=True)
class BieuDo:
    ma: str
    trang: int
    cau_hoi: str
    ten: str  # đúng tiêu đề biểu đồ trên dashboard
    ham: Callable[[BoLoc], KetQua]


BIEU_DO = {b.ma: b for b in [
    BieuDo("Q1_1", 1, "Q1", "Doanh thu theo tháng", doanh_thu_theo_thang),
    BieuDo("Q1_2", 1, "Q1", "Số đơn và giá trị đơn trung bình theo tháng", so_don_va_aov_theo_thang),
    BieuDo("Q2_1", 1, "Q2", "Top 10 danh mục theo doanh thu", top10_danh_muc),
    BieuDo("Q2_2", 1, "Q2", "Doanh thu theo bang và vùng", doanh_thu_theo_bang),
    BieuDo("Q3_1", 2, "Q3", "Tỉ lệ giao trễ theo tháng", tre_theo_thang),
    BieuDo("Q3_2", 2, "Q3", "10 bang giao trễ nhiều nhất", tre_theo_bang),
    BieuDo("Q4_1", 2, "Q4", "Điểm đánh giá theo mức trễ", diem_theo_muc_tre),
    BieuDo("Q4_2", 2, "Q4", "Tỉ lệ giao trễ và điểm đánh giá theo tháng", tre_va_diem_theo_thang),
    BieuDo("Q5_1", 3, "Q5", "Tỉ lệ giao trễ theo khâu bàn giao", tre_theo_ban_giao),
    BieuDo("Q5_2", 3, "Q5", "Bàn giao trễ, thời gian xử lý và vận chuyển theo tháng", ban_giao_va_van_chuyen_theo_thang),
    BieuDo("Q6_1", 3, "Q6", "Người bán có ≥ 30 đơn", nguoi_ban_tu_30_don),
    BieuDo("Q6_2", 3, "Q6", "10 người bán cần xử lý trước", top10_nguoi_ban_can_xu_ly),
]}


def bo_loc_cua_trang(trang: int, **gia_tri) -> BoLoc:
    """Chỉ giữ bộ lọc mà trang đó có slicer (VD trang 3 không lọc theo vùng nhận hàng)."""
    return BoLoc(**{k: v for k, v in gia_tri.items() if k in TRANG[trang].bo_loc and v not in (None, "")})


def danh_sach_lua_chon() -> dict[str, list]:
    """Giá trị cho các ô lọc của app."""
    g = truy_van("SELECT DISTINCT region, state_code FROM dds.dim_geography WHERE geography_key <> -1 ORDER BY 1, 2")
    s = truy_van("SELECT DISTINCT seller_region, seller_state FROM dds.dim_seller WHERE seller_key <> -1 ORDER BY 1, 2")
    return {
        "vung": sorted(g.region.unique().tolist()),
        "bang_theo_vung": g.groupby("region").state_code.apply(list).to_dict(),
        "vung_nb": sorted(s.seller_region.unique().tolist()),
        "bang_nb_theo_vung": s.groupby("seller_region").seller_state.apply(list).to_dict(),
        "bang_nb": sorted(s.seller_state.unique().tolist()),
    }


# ---------------------------------------------------------------------------
# Định dạng số và gói dữ liệu gửi AI
# ---------------------------------------------------------------------------
def so_vn(x, le: int = 0) -> str:
    """Số kiểu Việt: 13.449.529,68."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:,.{le}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def dinh_dang(x, kieu: str) -> str:
    if kieu == "brl":
        return so_vn(x, 2)
    if kieu == "pct":
        return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else so_vn(x * 100, 1) + "%"
    if kieu == "so":
        return so_vn(x, 0)
    if kieu == "diem":
        return so_vn(x, 2) + " ★"
    if kieu == "ngay":
        return so_vn(x, 1) + " ngày"
    return "" if x is None else str(x)


def _sach(v, so_le: int = 4):
    """Đổi về kiểu JSON: số numpy -> Python, NaN -> None, làm tròn."""
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, so_le)
    if isinstance(v, dict):
        return {str(k): _sach(x, so_le) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_sach(x, so_le) for x in v]
    return v


def du_lieu_cho_ai(ma: str, bl: BoLoc, kq: KetQua, kpi: dict, toi_da_dong: int = 40) -> dict:
    """Gói đúng số liệu đang hiện trên app để gửi LLM: câu hỏi, bộ lọc, thẻ KPI, kết luận, bảng (tối đa N dòng)."""
    bd = BIEU_DO[ma]
    bang = kq.bang.drop(columns=[c for c in ("nam", "thang", "seller_id", "danh_muc_en") if c in kq.bang], errors="ignore")
    return _sach({
        "trang": f"Trang {bd.trang} – {TRANG[bd.trang].ten}",
        "cau_hoi_nghiep_vu": f"{bd.cau_hoi}. {CAU_HOI[bd.cau_hoi]}",
        "bieu_do": bd.ten,
        "bo_loc": bl.mo_ta(),
        "the_kpi": {k: {"ten": v["ten"], "gia_tri": v["gia_tri"], "ghi_chu": v.get("ghi_chu", "")} for k, v in kpi.items()},
        "so_lieu_ket_luan": kq.tom_tat,
        "don_vi_cot": {c: COT[c][0] for c in bang.columns if c in COT},
        "bang_so_lieu": bang.head(toi_da_dong).to_dict("records"),
        "so_dong_bang": len(bang),
        "ghi_chu": ("Tỉ lệ ghi dạng số thập phân (0,0679 = 6,79%); tiền BRL; điểm 1–5 sao."
                    + (f" Bảng có {len(bang)} dòng, chỉ gửi {toi_da_dong} dòng đầu." if len(bang) > toi_da_dong else "")),
    })
