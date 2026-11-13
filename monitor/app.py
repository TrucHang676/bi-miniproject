"""Theo dõi ETL – dashboard vận hành cho pipeline Mage + dbt của đồ án Olist (BS-54, Seminar 3).

Đọc nhật ký etl_log (pipeline_run, table_load, quality_check, dbt_result) và dq.rejected_rows qua các view
trong sql/init/06_etl_monitor.sql. Ba trang:
  1. Tổng quan vận hành  - thẻ KPI, cảnh báo, dòng thời gian các lần chạy, thời gian từng khâu, số dòng theo batch,
                           lưới 10 batch, bảng 20 lần chạy gần nhất (nút Xem chi tiết ở cuối mỗi dòng)
  2. Chất lượng dữ liệu  - ma trận batch x phép kiểm tra, dòng bị loại (dq), dbt test không đạt
  3. Chi tiết một lần chạy - Gantt các bước, bảng nạp từng bảng, kiểm tra chất lượng, kết quả dbt

Giao diện theo phong cách dashboard Power BI của nhóm (theme Olist Lime Soft). Chỉ ĐỌC dữ liệu, không ghi gì.
Chạy từ gốc repo khi Postgres đang chạy:   streamlit run monitor/app.py --server.port 8502
Link thẳng tới 1 lần chạy:  http://localhost:8502/?run_id=99
"""
import html
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st
import streamlit.components.v1 as components

import queries as q
from PIL import Image, ImageDraw


def _favicon() -> Image.Image:
    """Icon tab trình duyệt = logo ở thanh trên (ô vuông bo góc xanh chanh, 3 cột đen tăng dần).

    Vẽ ở 256px theo đúng tỉ lệ logo CSS (.lg 28px: bo 9px, cột rộng 3px cách 2px, cao 6 / 10 / 14px, cách đáy 7px)
    rồi thu nhỏ về 64px cho mép mịn. Vẽ bằng code nên không cần thêm file ảnh vào repo.
    """
    n, k = 256, 256 / 28
    anh = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ve = ImageDraw.Draw(anh)
    ve.rounded_rectangle((0, 0, n - 1, n - 1), radius=round(9 * k), fill="#E2FA2C")
    rong, cach, day = 3 * k, 2 * k, n - 7 * k
    x = (n - (3 * rong + 2 * cach)) / 2
    for cao in (6, 10, 14):
        ve.rounded_rectangle((x, day - cao * k, x + rong, day), radius=round(1 * k), fill="#121316")
        x += rong + cach
    return anh.resize((64, 64), Image.LANCZOS)


st.set_page_config(page_title="Theo dõi ETL – Olist BI", page_icon=_favicon(), layout="wide", initial_sidebar_state="expanded")

# Bảng màu theo mockup / theme Olist Lime Soft (powerbi/theme_olist.json)
NEN, THE, DEN, CHU2, XAM = "#E9EBEF", "#FFFFFF", "#121316", "#4A4E57", "#8B9099"
KE, LUOI, NHAT = "#E2E5EA", "#EEF0F3", "#F0F2F6"
CHANH, CHANH_BAR, TIM, TIM_DAM, TIM_NHAT = "#E2FA2C", "#C8E62A", "#A9B8F8", "#6F80EC", "#DCE2FD"
DO, XANH, VANG = "#EF6F61", "#1D5E12", "#F6C343"
MAU_TT = {"SUCCESS": CHANH_BAR, "FAILED": DO, "RUNNING": TIM_DAM, "PENDING": "#D5D8DE"}
# chip: (nền, chữ)
CHIP = {"SUCCESS": ("#EAF7B2", XANH), "PASS": ("#EAF7B2", XANH), "success": ("#EAF7B2", XANH), "pass": ("#EAF7B2", XANH),
        "FAILED": ("#FDE3E0", "#B8382B"), "FAIL": ("#FDE3E0", "#B8382B"), "fail": ("#FDE3E0", "#B8382B"),
        "error": ("#FDE3E0", "#B8382B"), "RUNNING": ("#E4E8FD", "#3A47C4"),
        "WARN": ("#FDF1CC", "#8A6100"), "warn": ("#FDF1CC", "#8A6100"),
        "PENDING": (NHAT, XAM), "skipped": (NHAT, XAM)}
TAT_CA = "Tất cả"
TEN_TRANG = {1: "Tổng quan vận hành", 2: "Chất lượng dữ liệu", 3: "Chi tiết một lần chạy"}
TEN_CHECK = {"file_exists": ("Có đủ<br>file", "Có đủ file"), "columns_match": ("Đủ<br>cột", "Đủ cột"),
             "batch_id_match": ("Đúng<br>batch", "Đúng batch"), "not_null_key": ("Khóa không<br>rỗng", "Khóa không rỗng"),
             "duplicate_key": ("Khóa không<br>trùng", "Khóa không trùng"), "type_cast": ("Ép kiểu<br>được", "Ép kiểu được"),
             "row_count_match": ("Khớp số<br>dòng", "Khớp số dòng"), "in_window": ("Trong<br>khoảng", "Trong khoảng"),
             "key_exists": ("Đơn<br>tồn tại", "Đơn tồn tại")}


# ---------------------------------------------------------------------------
# Định dạng kiểu Việt Nam
# ---------------------------------------------------------------------------
def so_vn(x, nd: int = 0) -> str:
    """1234567.5 -> '1.234.567,5' (nd chữ số thập phân); rỗng -> '–'."""
    if x is None or pd.isna(x):
        return "–"
    return f"{x:,.{nd}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def phan_tram(x, nd: int = 1) -> str:
    return "–" if x is None or pd.isna(x) else so_vn(x * 100, nd) + "%"


def thoi_luong(giay) -> str:
    """48,2 -> '48 giây'; 125 -> '2 phút 05 giây'; 3700 -> '1 giờ 02 phút'."""
    if giay is None or pd.isna(giay):
        return "–"
    g = float(giay)
    if g < 10:
        return f"{so_vn(g, 1)} giây"
    g = int(round(g))
    if g < 60:
        return f"{g} giây"
    if g < 3600:
        return f"{g // 60} phút {g % 60:02d} giây"
    return f"{g // 3600} giờ {(g % 3600) // 60:02d} phút"


def cach_day(giay, truoc: bool = True) -> str:
    """Khoảng thời gian tính tới bây giờ: '7 ngày 16 giờ trước' (truoc=False: bỏ chữ 'trước', dùng dưới nhãn 'Cách đây')."""
    if giay is None or pd.isna(giay):
        return "–"
    if giay < 5:
        return "vừa xong"
    duoi = " trước" if truoc else ""
    if giay >= 86400:
        return f"{int(giay // 86400)} ngày {int(giay % 86400 // 3600)} giờ{duoi}"
    if giay >= 3600:
        return f"{int(giay // 3600)} giờ {int(giay % 3600 // 60):02d} phút{duoi}"
    return thoi_luong(giay) + duoi


def gio(ts, day_du: bool = True) -> str:
    if ts is None or pd.isna(ts):
        return "–"
    return pd.Timestamp(ts).strftime("%d/%m/%Y %H:%M:%S" if day_du else "%H:%M:%S")


def so_cot(serie) -> list[str]:
    """Cột số -> chuỗi kiểu VN; NULL (cột bị pandas đổi thành float) -> '–', số nguyên không có phần thập phân."""
    return [so_vn(v) for v in serie]


def esc(x) -> str:
    return html.escape("" if x is None or (not isinstance(x, str) and pd.isna(x)) else str(x))


def rut_gon(x, n: int = 90) -> str:
    t = " ".join(str(x or "").split())
    return t if len(t) <= n else t[:n - 1] + "…"


def chip(trang_thai: str, chu_hien: str | None = None) -> str:
    nen, chu = CHIP.get(trang_thai, (NHAT, CHU2))
    return f'<span class="chip" style="background:{nen};color:{chu}">{esc(chu_hien or trang_thai)}</span>'


def chip_dbt(trang_thai: str, chu_hien: str | None = None) -> str:
    """Chip trạng thái dbt: success / pass xanh, warn vàng, skipped xám, còn lại (fail, error, chữ lạ) đỏ."""
    s = str(trang_thai)
    ma = s if s in ("success", "pass", "warn", "skipped") else "error"
    return chip(ma, chu_hien or s)


def lop_0(x) -> str:
    """Ô số trong bảng: giá trị 0 tô xám nhạt (C6) để số khác 0 nổi lên."""
    return " z" if x is not None and not pd.isna(x) and float(x) == 0 else ""


def ten_test_ngan(ten: str) -> str:
    """Tên dbt test rút gọn = phần trước dấu '__' đầu tiên (bỏ danh sách giá trị dbt nối vào cuối tên)."""
    return str(ten).split("__")[0]


def tom_tat_model(msg) -> str:
    """Lỗi 1 node dbt -> 1 câu: 'relation "x" does not exist' thành 'Không tìm thấy bảng x';
    lỗi khác lấy dòng cuối có chữ của thông báo, cắt 120 ký tự."""
    import re
    m = str(msg or "")
    k = re.search(r'relation "([^"]+)" does not exist', m)
    if k:
        return f"Không tìm thấy bảng {k.group(1)}"
    dong = [d.strip() for d in m.splitlines() if d.strip()]
    return rut_gon(dong[-1] if dong else "", 120)


def tom_tat_loi(r) -> str:
    """Cột Lỗi của bảng 20 lần chạy (T1.6): tóm tắt từ cột có sẵn của v_run (failed_stage, dbt_test_fail, dbt_model_error)."""
    if r.status != "FAILED":
        return ""
    if r.failed_stage == "dbt":
        phan = []
        if r.dbt_model_error:
            phan.append(f"{so_vn(r.dbt_model_error)} model lỗi")
        if r.dbt_test_fail:
            phan.append(f"{so_vn(r.dbt_test_fail)} test không đạt")
        return "Khâu dbt: " + (", ".join(phan) if phan else "dbt không chạy được")
    return {"staging": "Khâu nạp staging lỗi", "bi_ngat": "Bị ngắt giữa chừng"}.get(r.failed_stage, "Lỗi khác")


# ---------------------------------------------------------------------------
# Dữ liệu (cache ngắn để vừa mới vừa nhẹ DB)
# ---------------------------------------------------------------------------
TTL = 10


@st.cache_data(ttl=TTL, show_spinner=False)
def _lua_chon():
    return q.lua_chon()


@st.cache_data(ttl=TTL, show_spinner=False)
def _lan_chay(bl):
    return q.lan_chay(bl)


@st.cache_data(ttl=TTL, show_spinner=False)
def _tien_do(luot):
    return q.tien_do_batch(luot)


@st.cache_data(ttl=TTL, show_spinner=False)
def _gio_db():
    return q.gio_db()


@st.cache_data(ttl=TTL, show_spinner=False)
def _so_dong_batch(bl):
    return q.so_dong_theo_batch(_lan_chay(bl))


@st.cache_data(ttl=TTL, show_spinner=False)
def _ma_tran(bl):
    return q.ma_tran_chat_luong(bl)


@st.cache_data(ttl=TTL, show_spinner=False)
def _dong_loai(bl):
    return q.dong_bi_loai(bl)


@st.cache_data(ttl=TTL, show_spinner=False)
def _mau_loai(bl):
    return q.mau_dong_bi_loai(bl)


@st.cache_data(ttl=TTL, show_spinner=False)
def _dbt_loi(bl):
    return q.dbt_test_khong_dat(bl)


@st.cache_data(ttl=TTL, show_spinner=False)
def _ds_run():
    return q.danh_sach_run()


@st.cache_data(ttl=TTL, show_spinner=False)
def _chi_tiet(run_id):
    return q.mot_lan_chay(run_id), q.table_load_cua(run_id), q.quality_check_cua(run_id), q.dbt_node_cua(run_id)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def _css() -> None:
    st.markdown(f"""<style>
    .stApp, .stApp p, .stApp div, .stApp label, .stApp button, .stApp input, .stApp li, .stApp td, .stApp th,
    .stApp span:not([data-testid="stIconMaterial"]) {{ font-family: "Segoe UI Variable Display", "Segoe UI", system-ui,
        -apple-system, "Helvetica Neue", Arial, sans-serif; }}
    [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: {NEN}; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    /* ẩn nút Deploy + menu ba chấm của Streamlit (chay_monitor.bat đã bật --client.toolbarMode minimal; CSS này để chạy
       thiếu cờ cũng không hiện). KHÔNG ẩn cả stToolbar: nút mở lại thanh bên (stExpandSidebarButton) nằm trong đó. */
    [data-testid="stDeployButton"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
    [data-testid="stDecoration"] {{ display: none !important; }}
    /* Thanh trên dính ở đỉnh khi cuộn (top = đúng vị trí lúc chưa cuộn nên không nhảy); lớp bóng nền phía trên che phần
       nội dung cuộn qua khe giữa thanh và mép màn hình. */
    [data-testid="stElementContainer"]:has(.appbar) {{ position: sticky; top: 32px; z-index: 50; }}
    /* Thanh bên ẩn: Streamlit đặt nút mở lại (stExpandSidebarButton) cố định ở góc trên trái, lơ lửng ngoài bố cục.
       Đưa nút vào trong thanh trên, trước logo (thanh trên chừa 48px bên trái); vì thanh trên dính ở đỉnh nên nút và
       thanh luôn đi cùng nhau. Vị trí: thanh trên bắt đầu ở top 32 / left 20, cao 50 -> nút 34px ở top 40 / left 31. */
    [data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) .appbar {{ padding-left: 56px; }}
    [data-testid="stExpandSidebarButton"] {{ position: fixed !important; top: 40px; left: 31px; z-index: 1000;
        width: 34px; height: 34px; border-radius: 10px; background: {NHAT}; color: {DEN}; display: flex;
        align-items: center; justify-content: center; }}
    [data-testid="stExpandSidebarButton"]:hover {{ background: {KE}; }}
    .block-container {{ padding: 1rem 1.2rem 1.5rem; max-width: 100%; }}
    [data-testid="stSidebar"] {{ background: {THE}; border-right: 1px solid {KE}; }}
    .stApp button [data-testid="stMarkdownContainer"], .stApp button p {{ font-size: inherit !important; color: inherit; }}

    /* ---------- thanh bên (S1): bỏ hàng riêng của nút thu gọn «, đưa nút lên góc trên phải cùng hàng với logo ---------- */
    [data-testid="stSidebarContent"] {{ position: relative; }}
    [data-testid="stSidebarHeader"] {{ position: absolute !important; top: 14px; right: 12px; height: 40px !important;
        padding: 0 !important; margin: 0 !important; z-index: 5; display: flex; align-items: center; width: auto !important; }}
    [data-testid="stSidebarHeader"] [data-testid="stLogoSpacer"] {{ display: none; }}
    [data-testid="stSidebarCollapseButton"] {{ display: flex !important; visibility: visible !important; opacity: 1 !important; }}
    [data-testid="stSidebarCollapseButton"] button {{ width: 30px; height: 30px; border-radius: 9px; }}
    [data-testid="stSidebarCollapseButton"] button:hover {{ background: {NHAT}; }}
    [data-testid="stSidebarUserContent"] {{ padding-top: 14px !important; }}
    .sb_dau {{ display: flex; align-items: center; gap: 10px; height: 40px; margin: 0 40px 12px 2px; }}
    .sb_ten .a {{ font-size: 11px; color: {XAM}; line-height: 1.1; }}
    .sb_ten .b {{ font-size: 14.5px; font-weight: 700; color: {DEN}; line-height: 1.25; }}
    .lg {{ width: 28px; height: 28px; border-radius: 9px; background: {CHANH}; display: flex; align-items: flex-end;
        justify-content: center; gap: 2px; padding-bottom: 7px; box-sizing: border-box; flex: none; }}
    .lg i {{ display: block; width: 3px; background: {DEN}; border-radius: 1px; }}
    .sb_dau .lg {{ width: 30px; height: 30px; padding-bottom: 8px; }}
    .sb_muc {{ font-size: 10px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: {XAM}; margin: 14px 0 6px 6px; }}
    [class*="st-key-nut_trang_"] button {{ justify-content: flex-start; text-align: left; border-radius: 12px; min-height: 40px;
        padding: 0 12px; border: none; background: transparent; color: {CHU2}; font-size: 13px; box-shadow: none; }}
    [class*="st-key-nut_trang_"] button > div {{ justify-content: flex-start; width: 100%; }}
    [class*="st-key-nut_trang_"] button:hover {{ background: {NHAT}; color: {DEN}; }}
    [class*="st-key-nut_trang_"] button[kind="primary"] {{ background: {DEN}; color: #fff; font-weight: 600; }}
    [class*="st-key-nut_trang_"] button[kind="primary"] [data-testid="stIconMaterial"] {{ color: {CHANH}; }}
    [data-testid="stSidebar"] label p {{ font-size: 11.5px; font-weight: 500; color: {CHU2}; }}
    [data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-testid="stDateInputField"] {{
        background: {NHAT}; border: 1px solid transparent; border-radius: 12px; font-size: 12.5px; min-height: 36px; }}
    [data-testid="stSidebar"] .stButton button {{ padding: 0 8px; font-size: 12px; white-space: nowrap; min-height: 36px; border-radius: 12px; }}
    .pillc code {{ color: {CHU2}; background: none; font-size: 11.5px; padding: 0; }}
    /* S3: ghi chú cuối thanh bên chỉ là chữ nhỏ xám, có đường kẻ mảnh phía trên */
    .sb_ghi {{ font-size: 11px; line-height: 1.55; color: {XAM}; margin-top: 14px; padding-top: 14px; border-top: 1px solid {KE}; }}

    /* ---------- thanh trên ---------- */
    .appbar {{ background: {THE}; border-radius: 16px;
        box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05), 0 -16px 0 16px {NEN};
        display: flex; align-items: center; justify-content: space-between; padding: 8px 10px 8px 14px; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-size: 15px; color: {DEN}; }}
    .brand b {{ font-weight: 700; }} .brand .sep {{ color: #B6BAC2; }} .brand .pg {{ font-weight: 600; }}
    .bar_r {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .pillc {{ height: 34px; border-radius: 999px; background: {NHAT}; display: inline-flex; align-items: center; gap: 8px;
        padding: 0 14px; font-size: 12.5px; color: {CHU2}; white-space: nowrap; }}
    .pillc b {{ color: {DEN}; font-weight: 600; }}
    .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
    .dot.bat {{ background: {XANH}; box-shadow: 0 0 0 3px rgba(29,94,18,.18); }} .dot.tat {{ background: #B6BAC2; }}

    /* ---------- thẻ KPI (C2): số lớn + hàng ô nhỏ có nhãn ở đáy thẻ ---------- */
    .hang_kpi {{ display: grid; gap: 12px; margin-bottom: 12px; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); }}
    .kc {{ border-radius: 18px; padding: 13px 15px 11px; min-height: 120px; box-sizing: border-box; display: flex; flex-direction: column;
        background: {THE}; color: {DEN}; box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05); min-width: 0; }}
    .kc.chanh {{ background: {CHANH}; }} .kc.tim {{ background: {TIM}; }} .kc.den {{ background: {DEN}; color: #fff; }}
    .kc .lab {{ font-size: 12px; color: {XAM}; }}
    .kc.chanh .lab, .kc.tim .lab {{ color: {CHU2}; }} .kc.den .lab {{ color: rgba(255,255,255,.7); }}
    .kc .so {{ font-size: clamp(20px, 1.9vw, 26px); font-weight: 700; letter-spacing: -.015em; line-height: 1.2; margin: 3px 0 10px;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-variant-numeric: tabular-nums; }}
    .kc .so small {{ font-size: 12.5px; font-weight: 600; margin-left: 5px; color: {CHU2}; letter-spacing: 0; }}
    .kc.den .so small {{ color: rgba(255,255,255,.75); }}
    .kc .so.xau {{ color: #D9483B; }} .kc .so.tot {{ color: {XANH}; }}
    .kc .chia {{ display: flex; gap: 16px; margin: 3px 0 10px; flex-wrap: nowrap; overflow: hidden; }}
    .kc .chia .n {{ font-size: clamp(18px, 1.75vw, 26px); white-space: nowrap; font-weight: 700; letter-spacing: -.015em; line-height: 1.2; font-variant-numeric: tabular-nums; }}
    .kc .chia .l {{ font-size: 11px; color: {CHU2}; margin-top: 1px; }}
    .kc .day {{ margin-top: auto; padding-top: 8px; border-top: 1px solid rgba(18,19,22,.10); display: flex; gap: 6px 14px; flex-wrap: wrap; }}
    .kc.den .day {{ border-top-color: rgba(255,255,255,.14); }}
    .mini .l {{ font-size: 10.5px; color: {CHU2}; line-height: 1.3; white-space: nowrap; }}
    .kc.chanh .mini .l, .kc.tim .mini .l {{ color: rgba(18,19,22,.62); }}
    .kc.den .mini .l {{ color: rgba(255,255,255,.62); }}
    .mini .v {{ font-size: 13px; font-weight: 700; line-height: 1.35; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    .mini .v.xau {{ color: #D9483B; }} .kc.den .mini .v.xau {{ color: #FF9B8F; }}
    .kc .chu_day {{ font-size: 11.5px; font-weight: 600; color: {CHU2}; line-height: 1.35; }}
    .kc.den .chu_day {{ color: rgba(255,255,255,.85); }}
    .kc .chu_day.xau {{ color: #D9483B; }}
    .tien {{ height: 6px; border-radius: 999px; background: {NHAT}; overflow: hidden; margin: 3px 0 7px; }}
    .tien i {{ display: block; height: 100%; background: {CHANH_BAR}; border-radius: 999px; }}

    /* ---------- thẻ trắng ---------- */
    [class*="st-key-the_"] {{ background: {THE}; border-radius: 20px; padding: 14px 16px 12px;
        box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05); }}
    /* C3: các thẻ đặt cạnh nhau trong một hàng (st.columns) luôn cao bằng nhau: cột giãn hết chiều cao hàng, thẻ cuối
       của mỗi cột giãn phần còn lại (cột trái của trang 3 xếp chồng 2 thẻ thì thẻ dưới giãn). */
    [data-testid="stHorizontalBlock"]:has([class*="st-key-the_"]) > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ height: 100%; }}
    [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-the_"]):last-child {{ flex: 1 1 auto; }}
    [data-testid="stColumn"] [class*="st-key-the_"] {{ height: 100%; }}
    /* nội dung cần chiếm hết phần còn lại của thẻ (khung trống căn giữa, bảng có dòng tổng kết ở đáy) */
    [class*="st-key-the_"] > [data-testid="stElementContainer"]:has(.gian) {{ flex: 1 1 auto; display: flex; flex-direction: column; }}
    [class*="st-key-the_"] > [data-testid="stElementContainer"]:has(.gian) > [data-testid="stMarkdown"],
    [class*="st-key-the_"] > [data-testid="stElementContainer"]:has(.gian) [data-testid="stMarkdown"] div:has(.gian) {{
        flex: 1 1 auto; display: flex; flex-direction: column; }}
    .gian {{ flex: 1 1 auto; display: flex; flex-direction: column; }}
    .tt {{ font-size: 13.5px; font-weight: 600; color: {DEN}; margin: 0; }}
    .tp {{ font-size: 11.5px; color: {XAM}; margin: 2px 0 6px; line-height: 1.45; }}
    /* C4: chú thích (legend) tự vẽ, 1 hàng ngay dưới tiêu đề phụ */
    .chu_giai {{ display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11.5px; color: {CHU2}; margin: 0 0 2px; }}
    .chu_giai span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .chu_giai i {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
    .chu_giai i.tron {{ border-radius: 50%; background: {DEN}; width: 7px; height: 7px; }}
    .chu_giai i.thoi {{ background: {DEN}; width: 7px; height: 7px; transform: rotate(45deg); border-radius: 1px; }}
    .chu_giai .v {{ font-weight: 700; color: {DEN}; margin-left: 2px; font-variant-numeric: tabular-nums; }}
    .nhom_hd {{ display: flex; align-items: center; gap: 10px; margin: 14px 0 8px; }}
    .nhom_hd .tag {{ font-size: 11px; font-weight: 700; background: {CHANH}; color: {DEN}; border-radius: 999px; padding: 0 10px; line-height: 20px; }}
    .nhom_hd h3 {{ margin: 0; font-size: 15px; font-weight: 600; color: {DEN}; padding: 0; }}

    /* ---------- cảnh báo ---------- */
    .cb {{ display: flex; gap: 10px; align-items: flex-start; border-radius: 14px; padding: 10px 14px; margin-bottom: 8px;
        font-size: 12.5px; line-height: 1.5; }}
    .cb.do {{ background: #FDE3E0; color: #8E2A20; }} .cb.vang {{ background: #FDF1CC; color: #7A5600; }}
    .cb.ok {{ background: #EAF7B2; color: {XANH}; }}
    .cb b {{ white-space: nowrap; }}

    /* ---------- chip, lưới batch (T1.5: 2 cột x 5 hàng) ---------- */
    .chip {{ display: inline-block; border-radius: 999px; padding: 2px 9px; font-size: 10.5px; font-weight: 700; letter-spacing: .02em; white-space: nowrap; }}
    .luoi_batch {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .o_batch {{ border-radius: 14px; padding: 8px 12px 8px 13px; min-height: 64px; box-sizing: border-box; display: flex; flex-direction: column;
        justify-content: space-between; border: 1.5px solid transparent; }}
    .o_batch .b {{ font-size: 13px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; gap: 6px; }}
    .o_batch .m {{ font-size: 11.5px; line-height: 1.45; color: {CHU2}; margin-top: 3px; font-variant-numeric: tabular-nums; }}
    .o_batch.SUCCESS {{ background: #F3FBC9; border-color: {CHANH_BAR}; }}
    .o_batch.FAILED {{ background: #FDE3E0; border-color: {DO}; }}
    .o_batch.RUNNING {{ background: #E4E8FD; border-color: {TIM_DAM}; }}
    .o_batch.PENDING {{ background: {NHAT}; border-color: {KE}; color: {XAM}; }}
    .o_batch.PENDING .b {{ color: {XAM}; }}

    /* ---------- bảng HTML (bảng dòng bị loại, dbt, table_load...) ---------- */
    .bang_wrap {{ overflow-x: auto; }}
    /* Streamlit tô viền cả 4 cạnh + nền cho thẻ table trong markdown -> bỏ, chỉ giữ đường kẻ ngang */
    .stApp table.bang {{ width: 100%; border-collapse: collapse; border: none !important; margin: 0; display: table; }}
    .stApp table.bang th, .stApp table.bang td {{ border: none !important; border-bottom: 1px solid {KE} !important; }}
    .stApp table.bang tbody tr:last-child td {{ border-bottom: none !important; }}
    .stApp table.bang thead tr, .stApp table.bang tbody tr {{ background: none !important; }}
    .bang th {{ font-size: 11.5px; color: {XAM}; font-weight: 500; text-align: left; padding: 7px 8px; border-bottom: 1px solid {KE};
        white-space: nowrap; background: none; }}
    .bang td {{ font-size: 12.5px; color: {DEN}; padding: 0 8px; height: 34px; border-bottom: 1px solid {KE}; white-space: nowrap;
        border-left: none; border-right: none; }}
    .bang tr {{ border: none; }}
    .bang tbody tr:last-child td {{ border-bottom: 0; }}
    .bang tbody tr:hover td {{ background: #F6F7F9; }}
    .bang .r {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .bang td.z, .o_bang.z {{ color: #B6BAC2; }}
    .bang td.go {{ white-space: normal; padding-top: 7px; padding-bottom: 7px; height: auto; }}
    .mono {{ font-family: "Cascadia Mono", Consolas, monospace; font-size: 11.5px; }}
    .cat {{ display: inline-block; overflow: hidden; text-overflow: ellipsis; vertical-align: middle; white-space: nowrap; }}
    .kv_wrap {{ display: flex; flex-wrap: wrap; gap: 4px; min-width: 380px; max-width: 560px; }}
    .kv {{ background: {NHAT}; border-radius: 6px; padding: 1px 7px; font-family: "Cascadia Mono", Consolas, monospace; font-size: 11px; color: {CHU2}; }}
    .kv.loi {{ background: #FDE3E0; color: #B8382B; font-weight: 700; }}
    .thanh_so {{ display: inline-flex; align-items: center; gap: 8px; justify-content: flex-end; width: 100%; }}
    .thanh_so i {{ display: inline-block; height: 8px; border-radius: 3px; background: {TIM}; }}
    .tong_ket {{ margin-top: auto; padding-top: 10px; border-top: 1px solid {KE}; font-size: 12px; color: {CHU2}; }}
    .tong_ket b {{ color: {DEN}; }}

    /* ---------- ma trận HTML (trang 3, T3.7): cùng kiểu ô với ma trận trang 2 ---------- */
    .mt {{ display: grid; gap: 3px; align-items: center; margin-top: 4px; }}
    .mt .hd {{ font-size: 11px; color: {CHU2}; text-align: center; padding: 0 2px 4px; line-height: 1.25; }}
    .mt .rh {{ font-size: 11.5px; color: {CHU2}; text-align: right; padding-right: 8px; white-space: nowrap; }}
    .mt .o {{ height: 34px; display: flex; align-items: center; justify-content: center; font-size: 11px; color: {DEN}; cursor: default; }}
    .mt .o.PASS {{ background: #DDF08A; }} .mt .o.WARN {{ background: {VANG}; }} .mt .o.FAIL {{ background: {DO}; }}
    .mt .o.NA {{ background: {NHAT}; }}

    /* ---------- trống dữ liệu (C3) ---------- */
    .trong {{ flex: 1 1 auto; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
        color: {CHU2}; font-size: 12.5px; text-align: center; min-height: 110px; }}
    .trong .ic {{ width: 34px; height: 34px; border-radius: 50%; background: #EAF7B2; display: flex; align-items: center; justify-content: center; }}
    .trong_dong {{ display: flex; align-items: center; gap: 10px; background: #F6F7F9; border-radius: 12px; padding: 10px 12px;
        font-size: 12.5px; color: {CHU2}; }}
    .trong .ic.xam, .trong_dong .ic.xam {{ background: {NHAT}; }}
    .ic.xam i {{ display: block; width: 8px; height: 2px; border-radius: 1px; background: {XAM}; }}
    .trong_dong .ic.xam {{ background: {KE}; }}
    .trong_dong .ic {{ width: 22px; height: 22px; border-radius: 50%; background: #EAF7B2; display: flex; align-items: center;
        justify-content: center; flex: none; }}

    /* ---------- trang chi tiết ---------- */
    .dau_tieu {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
    .dau_tieu .so_run {{ font-size: 21px; font-weight: 700; letter-spacing: -.01em; }}
    .dau_tieu .chip {{ font-size: 11px; padding: 3px 10px; }}
    .dau_run {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px 20px; }}
    .dau_run .k {{ font-size: 11.5px; color: {XAM}; }}
    .dau_run .v {{ font-size: 14px; font-weight: 600; color: {DEN}; margin-top: 2px; word-break: break-word; font-variant-numeric: tabular-nums; }}
    .hop_loi {{ background: #FDE3E0; color: #7E2419; border-radius: 12px; padding: 11px 14px; font-size: 12.5px; line-height: 1.55;
        margin-top: 14px; word-break: break-word; }}
    .hop_loi .tom {{ font-size: 13px; font-weight: 700; margin: 0 0 4px; }}
    .hop_loi ul {{ margin: 0; padding-left: 18px; }}
    .hop_loi li {{ margin: 1px 0; font-size: 12.5px; }}
    .hop_loi li .mono {{ font-weight: 600; }}
    .hop_loi details {{ margin-top: 6px; }}
    .hop_loi summary {{ cursor: pointer; font-size: 12px; font-weight: 600; color: #8E2A20; list-style: none; }}
    .hop_loi summary::-webkit-details-marker {{ display: none; }}
    .hop_loi summary::after {{ content: " ›"; }}
    .hop_loi details[open] summary::after {{ content: " ⌄"; }}
    .hop_loi .goc {{ margin-top: 6px; background: rgba(255,255,255,.55); border-radius: 8px; padding: 8px 10px; font-size: 11.5px;
        line-height: 1.5; color: #8E2A20; }}
    .hop_ghi {{ background: {NHAT}; color: {CHU2}; border-radius: 12px; padding: 10px 14px; font-size: 12.5px; line-height: 1.55; }}
    .ds_loi {{ display: flex; flex-direction: column; gap: 8px; }}
    .mot_loi {{ border-left: 3px solid {DO}; background: #F6F7F9; border-radius: 0 10px 10px 0; padding: 8px 12px; font-size: 12.5px;
        line-height: 1.5; word-break: break-word; }}
    .mot_loi.canh {{ border-left-color: {VANG}; }}
    .mot_loi .mono {{ color: {CHU2}; }}
    [data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
    [class*="st-key-the_dau_run"] {{ padding: 16px; }}
    /* Streamlit đặt margin-bottom: -16px cho mọi khối markdown (để bù lề dưới của thẻ <p>). Khung thông báo tự vẽ
       không có <p> nên bị bù sai: khung tràn khỏi đáy thẻ trắng hoặc dính sát mép dưới. Trả lề về 0 cho các khối này. */
    [data-testid="stMarkdownContainer"]:has(> .hop_ghi), [data-testid="stMarkdownContainer"]:has(> .hop_loi),
    [data-testid="stMarkdownContainer"]:has(> .cb), [data-testid="stMarkdownContainer"]:has(> .dau_run),
    [data-testid="stMarkdownContainer"]:has(> .gian), [data-testid="stMarkdownContainer"]:has(> .trong_dong),
    [data-testid="stMarkdownContainer"]:has(> .bang_wrap), [data-testid="stMarkdownContainer"]:has(> .mt),
    [data-testid="stMarkdownContainer"]:has(> .luoi_batch), [data-testid="stMarkdownContainer"]:has(> .chu_giai) {{ margin-bottom: 0; }}
    /* ---------- bảng 20 lần chạy (hàng st.columns + nút Chi tiết) ---------- */
    .st-key-bang_run {{ background: {THE}; border-radius: 20px; padding: 6px 14px 8px; gap: 0 !important; overflow-x: auto;
        box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05); }}
    /* bảng hẹp hơn ~905px thì cột bị ép cắt chữ -> giữ độ rộng tối thiểu, màn hình hẹp thì cuộn ngang trong thẻ */
    .st-key-bang_run > * {{ min-width: 905px; }}
    /* cột 11 (Lỗi, căn trái) đứng sau cột số căn phải (Test lỗi) -> đệm trái để chữ không dính số */
    .st-key-bang_run [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(11) {{ padding-left: 14px; }}
    [data-testid="stMain"] .st-key-bang_run [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 6px;
        padding: 4px 6px; border-bottom: 1px solid {KE}; min-height: 40px; }}
    [data-testid="stMain"] .st-key-bang_run [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
        min-width: 0 !important; overflow: hidden; }}
    .st-key-bang_run [data-testid="stHorizontalBlock"]:hover {{ background: #F6F7F9; border-radius: 10px; }}
    .st-key-bang_run [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; }}
    .o_bang {{ font-size: 12.5px; color: {DEN}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.4; }}
    .o_bang.phai {{ text-align: right; font-variant-numeric: tabular-nums; }}
    /* tiêu đề cột: thiếu chỗ thì xuống dòng thay vì cắt "…" (font mỗi máy rộng hẹp khác nhau một chút) */
    .o_bang.tieu {{ font-size: 11.5px; color: {XAM}; font-weight: 500; cursor: default; white-space: normal;
        overflow: visible; line-height: 1.25; overflow-wrap: normal; word-break: keep-all; }}
    .o_bang.loi {{ color: #B8382B; font-size: 12.5px; cursor: help; }}
    .o_bang .chip {{ font-size: 10.5px; padding: 2px 8px; }}
    [class*="st-key-xem_"] {{ display: flex; justify-content: flex-end; }}
    [class*="st-key-xem_"] button {{ min-height: 28px; height: 28px; padding: 0 12px; border-radius: 999px; border: none;
        background: {NHAT}; color: {DEN}; font-size: 12px; font-weight: 600; white-space: nowrap; }}
    [class*="st-key-xem_"] button:hover {{ background: {CHANH}; color: {DEN}; }}
    [class*="st-key-xem_"] button p {{ white-space: nowrap; }}
    /* màn hình hẹp (<= 1000px): các cặp thẻ đặt cạnh nhau xếp thành 1 cột cho bảng / biểu đồ đủ rộng */
    @media (max-width: 1000px) {{
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width: 100% !important; }}
        .dau_run {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    </style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Thành phần giao diện dùng chung
# ---------------------------------------------------------------------------
ICON_OK = ('<span class="ic"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D5E12" stroke-width="3" '
           'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg></span>')
ICON_OK_NHO = ('<span class="ic"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#1D5E12" stroke-width="3.5" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg></span>')


def mini(nhan: str, gia_tri: str, lop: str = "") -> str:
    """Ô nhỏ ở đáy thẻ KPI (C2): nhãn nhỏ ở trên, số đậm ở dưới."""
    return f'<div class="mini"><div class="l">{esc(nhan)}</div><div class="v {lop}">{gia_tri}</div></div>'


def chu_day(noi_dung: str, lop: str = "") -> str:
    """Đáy thẻ KPI chỉ có 1 câu (VD 'Đã commit', 'dbt báo lỗi sau khi staging đã nạp xong')."""
    return f'<div class="chu_day {lop}">{noi_dung}</div>'


def the_kpi(ten: str, so: str, day: str, kieu: str = "trang", don_vi: str = "", mau_so: str = "") -> str:
    """Thẻ KPI: nhãn, số lớn (+ đơn vị / phần nhỏ cạnh số), đáy thẻ = các ô mini() hoặc chu_day()."""
    dv = f"<small>{don_vi}</small>" if don_vi else ""
    return (f'<div class="kc {kieu}"><div class="lab">{esc(ten)}</div>'
            f'<div class="so {mau_so}">{so}{dv}</div><div class="day">{day}</div></div>')


def the_chia(ten: str, cap: list[tuple[str, str]], day: str, kieu: str = "trang") -> str:
    """Thẻ KPI có 2 số lớn đứng riêng, mỗi số một nhãn bên dưới (T3.4: Thêm mới 746, Cập nhật 67)."""
    so = "".join(f'<div><div class="n">{v}</div><div class="l">{esc(n)}</div></div>' for n, v in cap)
    return (f'<div class="kc {kieu}"><div class="lab">{esc(ten)}</div><div class="chia">{so}</div>'
            f'<div class="day">{day}</div></div>')


def hang_kpi(cac_the: list[str]) -> None:
    st.markdown('<div class="hang_kpi">' + "".join(cac_the) + "</div>", unsafe_allow_html=True)


def tieu_de(ma: str, noi_dung: str) -> None:
    st.markdown(f'<div class="nhom_hd"><span class="tag">{esc(ma)}</span><h3>{esc(noi_dung)}</h3></div>', unsafe_allow_html=True)


def chu_giai(muc: list[tuple]) -> str:
    """Chú thích (C4) 1 hàng: mỗi mục (tên, màu) hoặc (tên, màu, giá trị in đậm); màu 'tron' / 'thoi' = ký hiệu chạy tay / theo lịch."""
    o = []
    for m in muc:
        ten, mau = m[0], m[1]
        ky = f'<i class="{mau}"></i>' if mau in ("tron", "thoi") else f'<i style="background:{mau}"></i>'
        gt = f'<span class="v">{m[2]}</span>' if len(m) > 2 and m[2] else ""
        o.append(f"<span>{ky}{esc(ten)}{gt}</span>")
    return '<div class="chu_giai">' + "".join(o) + "</div>"


def the_ve(key: str, tieu: str, phu: str = "", cg: str = ""):
    """Mở một thẻ trắng (container) có tiêu đề, tiêu đề phụ (1 câu) và chú thích; trả về container để vẽ vào."""
    c = st.container(key=f"the_{key}")
    c.markdown(f'<div class="tt">{esc(tieu)}</div>' + (f'<div class="tp">{phu}</div>' if phu else "") + cg,
               unsafe_allow_html=True)
    return c


def khung_plotly(fig: go.Figure, cao: int = 300, **tuy_chon) -> go.Figure:
    """Khung chung của mọi biểu đồ: không legend của Plotly (chú thích vẽ bằng HTML ngay dưới tiêu đề phụ - C4),
    không chữ trục (đơn vị ghi ở tiêu đề phụ - C5), cột bo góc 3px."""
    fig.update_layout(height=cao, margin=dict(l=6, r=6, t=6, b=6), paper_bgcolor="rgba(0,0,0,0)", separators=",.",
                      font=dict(family="Segoe UI, Arial, sans-serif", size=11, color=CHU2), showlegend=False,
                      barcornerradius=3,
                      hoverlabel=dict(bgcolor=DEN, bordercolor=DEN, font=dict(color="#fff", size=12)),
                      **{"plot_bgcolor": "rgba(0,0,0,0)", **tuy_chon})
    fig.update_xaxes(gridcolor=LUOI, linecolor=KE, zeroline=False, tickfont=dict(color=XAM), title=None, automargin=True)
    fig.update_yaxes(gridcolor=LUOI, linecolor=KE, zeroline=False, tickfont=dict(color=XAM), title=None, automargin=True)
    return fig


def ve(c, fig: go.Figure, key: str) -> None:
    c.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def trong(c, thong_bao: str, ok: bool = True) -> None:
    """Thẻ không có dữ liệu, thẻ nằm cạnh thẻ khác: biểu tượng + câu thông báo căn giữa thẻ (C3, class .trong).
    ok=True: ✓ xanh (không có lỗi nào); ok=False: chấm xám (chưa có dữ liệu, không phải tin tốt hay xấu)."""
    ic = ICON_OK if ok else '<span class="ic xam"><i></i></span>'
    c.markdown(f'<div class="gian"><div class="trong">{ic}<span>{thong_bao}</span></div></div>', unsafe_allow_html=True)


def trong_dong(c, thong_bao: str, ok: bool = True) -> None:
    """Thẻ không có dữ liệu, thẻ chiếm cả hàng: dạng 1 dòng (C3, class .trong_dong). ok như trong()."""
    ic = ICON_OK_NHO if ok else '<span class="ic xam"><i></i></span>'
    c.markdown(f'<div class="trong_dong">{ic}<span>{thong_bao}</span></div>', unsafe_allow_html=True)


def bang_html(cot: list[tuple[str, str]], hang: list[list[tuple[str, str]]], lop_bang: str = "") -> str:
    """Bảng HTML gọn: cot = [(tiêu đề, lớp th)], hang = [[(nội dung html, lớp td), ...]]. Lớp 'r' = căn phải, 'z' = số 0 xám."""
    th = "".join(f'<th class="{l}">{esc(t)}</th>' for t, l in cot)
    tb = "".join("<tr>" + "".join(f'<td class="{l}">{v}</td>' for v, l in h) + "</tr>" for h in hang)
    return f'<div class="bang_wrap"><table class="bang {lop_bang}"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


def o_so(x, nd: int = 0) -> tuple[str, str]:
    """Ô số căn phải của bang_html; 0 tô xám (C6)."""
    return so_vn(x, nd), "r" + lop_0(x)


# ---------------------------------------------------------------------------
# Thanh trên + thanh bên
# ---------------------------------------------------------------------------
def _thanh_tren(trang: int, bay_gio: pd.Timestamp) -> None:
    lich = q.doc_lich()
    if not lich:
        pill_lich = '<span class="pillc"><span class="dot tat"></span>Lịch: không đọc được triggers.yaml</span>'
    else:
        dang_bat = [t for t in lich if t["bat"]]
        if dang_bat:
            pill_lich = "".join(
                f'<span class="pillc"><span class="dot bat"></span>Lịch <b>{esc(t["ten"])}</b> đang bật, '
                f'<code style="background:none;padding:0">{esc(t["cron"])}</code></span>' for t in dang_bat)
        else:
            pill_lich = '<span class="pillc"><span class="dot tat"></span>Lịch: <b>tắt</b> (chỉ chạy tay)</span>'
    st.markdown(
        f'<div class="appbar"><div class="brand"><span class="lg"><i style="height:6px"></i><i style="height:10px"></i>'
        f'<i style="height:14px"></i></span><b>Olist BI</b><span class="sep">/</span><span>Theo dõi ETL</span>'
        f'<span class="sep">/</span><span class="pg">{esc(TEN_TRANG[trang])}</span></div>'
        f'<div class="bar_r">{pill_lich}<span class="pillc">Cập nhật lúc <b>{bay_gio.strftime("%H:%M:%S")}</b> '
        f'ngày {bay_gio.strftime("%d/%m/%Y")}</span></div></div>', unsafe_allow_html=True)


def _doi_trang(t: int) -> None:
    st.session_state.trang = t
    st.session_state.cuon_len = True   # đổi trang thì cuộn lên đầu trang (C12)


def _dat_lai() -> None:
    st.session_state.f_luot = -1
    for k in ("f_pipeline", "f_kich_hoat", "f_trang_thai"):
        st.session_state[k] = TAT_CA
    st.session_state.f_ngay = ()


# S1, S2: logo cùng hàng với nút thu gọn « (nút do Streamlit vẽ, CSS đưa lên góc trên phải); tên viết 2 dòng
LOGO_THANH_BEN = ('<div class="sb_dau"><span class="lg"><i style="height:6px"></i><i style="height:10px"></i>'
                  '<i style="height:14px"></i></span><div class="sb_ten"><div class="a">Olist BI</div>'
                  '<div class="b">Theo dõi ETL</div></div></div>')


def _thanh_ben(lc: dict) -> q.BoLoc:
    sb = st.sidebar
    sb.markdown(LOGO_THANH_BEN, unsafe_allow_html=True)
    sb.markdown('<div class="sb_muc">Trang</div>', unsafe_allow_html=True)
    for t, ten, icon in zip((1, 2, 3), ("Tổng quan vận hành", "Chất lượng dữ liệu", "Chi tiết một lần chạy"),
                            (":material/monitor_heart:", ":material/fact_check:", ":material/manage_search:")):
        sb.button(ten, icon=icon, key=f"nut_trang_{t}", width="stretch",
                  type="primary" if st.session_state.trang == t else "secondary", on_click=_doi_trang, args=(t,))

    sb.markdown('<div class="sb_muc">Bộ lọc</div>', unsafe_allow_html=True)
    luot_df = lc["luot"]
    moi_nhat = int(luot_df.cycle_no.max()) if len(luot_df) else None
    mo_ta = {int(r.cycle_no): (f"Lượt {int(r.cycle_no)}, từ {pd.Timestamp(r.bat_dau):%d/%m %H:%M}, {int(r.so_lan)} lần"
                               if r.cycle_no > 0 else f"Trước Full Load đầu tiên, {int(r.so_lan)} lần")
             for r in luot_df.itertuples()}
    tuy_chon = [-1, None] + list(mo_ta)
    st.session_state.setdefault("f_luot", -1)
    if st.session_state.f_luot not in tuy_chon:
        st.session_state.f_luot = -1

    def nhan_luot(v):
        if v == -1:
            return f"Lượt mới nhất ({'lượt ' + str(moi_nhat) if moi_nhat is not None else 'chưa có'})"
        return TAT_CA if v is None else mo_ta[v]

    luot = sb.selectbox("Lượt nạp (mỗi Full Load mở 1 lượt)", tuy_chon, format_func=nhan_luot, key="f_luot")
    if luot == -1:
        luot = moi_nhat
    st.session_state.setdefault("f_pipeline", TAT_CA)
    ds_pl = [TAT_CA] + lc["pipeline"]
    if st.session_state.f_pipeline not in ds_pl:
        st.session_state.f_pipeline = TAT_CA
    pipeline = sb.selectbox("Pipeline", ds_pl, key="f_pipeline")
    st.session_state.setdefault("f_kich_hoat", TAT_CA)
    kich_hoat = sb.selectbox("Kích hoạt", [TAT_CA, *q.KICH_HOAT], key="f_kich_hoat",
                             format_func=lambda v: {"manual": "manual (chạy tay)", "schedule": "schedule (theo lịch)"}.get(v, v))
    st.session_state.setdefault("f_trang_thai", TAT_CA)
    trang_thai = sb.selectbox("Trạng thái", [TAT_CA, *q.TRANG_THAI], key="f_trang_thai")
    st.session_state.setdefault("f_ngay", ())
    kwargs = {}
    if lc["tu_ngay"] and lc["den_ngay"]:
        kwargs = dict(min_value=lc["tu_ngay"], max_value=max(lc["den_ngay"], date.today()))
    ngay = sb.date_input("Khoảng ngày chạy", key="f_ngay", format="DD/MM/YYYY", **kwargs)
    tu_ngay = den_ngay = None
    if isinstance(ngay, (tuple, list)) and len(ngay) == 2:
        tu_ngay, den_ngay = ngay
    elif isinstance(ngay, date):
        tu_ngay = den_ngay = ngay

    c1, c2 = sb.columns(2)
    if c1.button("Làm mới", icon=":material/refresh:", width="stretch", key="lam_moi"):
        st.cache_data.clear()
        st.rerun()
    c2.button("Đặt lại", icon=":material/restart_alt:", width="stretch", key="dat_lai", on_click=_dat_lai)
    sb.toggle("Tự làm mới 30 giây", key="tu_lam_moi")
    sb.markdown('<div class="sb_ghi">Lần chạy theo lịch khi đã nạp hết batch không ghi vào etl_log nên không xuất hiện '
                'ở đây. Giờ hiển thị là giờ Việt Nam.</div>', unsafe_allow_html=True)
    return q.BoLoc(luot=luot, pipeline=None if pipeline == TAT_CA else pipeline,
                   kich_hoat=None if kich_hoat == TAT_CA else kich_hoat,
                   trang_thai=None if trang_thai == TAT_CA else trang_thai, tu_ngay=tu_ngay, den_ngay=den_ngay)


# ---------------------------------------------------------------------------
# Trang 1 - Tổng quan vận hành
# ---------------------------------------------------------------------------
def _hien_canh_bao(bl: q.BoLoc, bay_gio: pd.Timestamp) -> None:
    tat_ca = _lan_chay(q.BoLoc())
    tien_do = _tien_do(None)
    cb = q.canh_bao(tat_ca, tien_do, q.doc_lich(), bay_gio)
    if not cb:
        return
    st.markdown("".join(f'<div class="cb {m}"><b>{"Cần xử lý" if m == "do" else "Chú ý"}</b><span>{esc(n)}</span></div>'
                        for m, n in cb), unsafe_allow_html=True)


NGUONG_NGHI_PHUT = 20    # khoảng trống giữa 2 đợt chạy dài hơn mức này thì cắt khỏi trục thời gian
LE_NGHI_PHUT = 3         # giữ lại ngần này phút hai đầu mỗi khoảng cắt để thanh đầu / cuối đợt không sát mép


def _khoang_nghi(df: pd.DataFrame, bay_gio: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Các khoảng trống (> NGUONG_NGHI_PHUT) giữa các lần chạy, tính từ chính dữ liệu: mỗi phần tử là (từ, đến) cần cắt bỏ
    khỏi trục thời gian. Chỉ có 1 lần chạy, hoặc các lần chạy sát nhau -> danh sách rỗng."""
    bd = df.started_at.sort_values().reset_index(drop=True)
    kt = df.finished_at.fillna(bay_gio)[df.started_at.sort_values().index].reset_index(drop=True)
    cac, cuoi = [], None   # cuoi = mốc kết thúc muộn nhất của các lần chạy đã xét (các lần chạy có thể chồng nhau)
    le = pd.Timedelta(minutes=LE_NGHI_PHUT)
    for b, k in zip(bd, kt):
        if cuoi is not None and (b - cuoi) > pd.Timedelta(minutes=NGUONG_NGHI_PHUT):
            cac.append((cuoi + le, b - le))
        cuoi = k if cuoi is None else max(cuoi, k)
    return cac


def _nghi_txt(giay: float, day_du: bool = True) -> str:
    """Khoảng nghỉ -> chữ ngắn: 'nghỉ 45 phút', 'nghỉ 4 giờ', 'nghỉ 2 ngày' (day_du=False: bỏ chữ 'nghỉ' cho gọn khi có nhiều khoảng)."""
    tien_to = "nghỉ " if day_du else ""
    if giay >= 86400:
        return f"{tien_to}{round(giay / 86400)} ngày"
    if giay >= 3600:
        return f"{tien_to}{round(giay / 3600)} giờ"
    return f"{tien_to}{round(giay / 60)} phút"


def _nhan_truc(d0: pd.Timestamp, d1: pd.Timestamp, nghi: list, muc_tieu: int = 5, mot_ngay: bool = False) -> tuple[list, list]:
    """Nhãn trục tự tính khi có cắt khoảng nghỉ: mỗi đoạn nhìn thấy có ít nhất 1 nhãn, số nhãn tỉ lệ với độ dài đoạn.
    Trả về (tickvals, ticktext); ticktext kiểu VN 'HH:MM', kèm dòng 'dd/mm/yyyy' ở nhãn đầu và mỗi khi sang ngày khác
    (nhãn ngắn nên không chồng nhau); không có 2 nhãn trùng giờ trùng ngày. mot_ngay=True: mọi lần chạy cùng một ngày
    (ngày đã ghi ở tiêu đề phụ) nên nhãn chỉ ghi giờ."""
    moc = [d0] + [x for b, k in nghi for x in (b, k)] + [d1]
    doan = [(moc[i], moc[i + 1]) for i in range(0, len(moc), 2)]
    tong = max(sum((k - b).total_seconds() for b, k in doan), 1.0)
    nhieu = len(doan) >= 4   # nhiều đoạn (VD "Tất cả" lượt): mỗi đoạn 1 nhãn, ngày viết ngắn dd/mm cho khỏi chồng nhau
    vals, texts, da_co, ngay_truoc = [], [], set(), None
    for b, k in doan:
        n = 1 if nhieu else max(1, round(muc_tieu * (k - b).total_seconds() / tong))
        for i in range(n):
            t = (b + (k - b) * ((i + 0.5) / n)).floor("min")
            khoa = t.strftime("%Y-%m-%d %H:%M")
            if khoa in da_co:
                continue
            da_co.add(khoa)
            ngay = t.strftime("%d/%m" if nhieu else "%d/%m/%Y")
            vals.append(t)
            texts.append(t.strftime("%H:%M") + (f"<br>{ngay}" if ngay != ngay_truoc and not mot_ngay else ""))
            ngay_truoc = ngay
    return vals, texts


def _mot_ngay(df: pd.DataFrame, bay_gio: pd.Timestamp) -> bool:
    """Mọi lần chạy (kể cả lần đang chạy) bắt đầu và kết thúc trong cùng một ngày."""
    kt = df.finished_at.fillna(bay_gio)
    return df.started_at.min().date() == kt.max().date()


def _bieu_do_dong_thoi_gian(df: pd.DataFrame, batches: list[str]):
    """(a) mỗi lần chạy = 1 thanh nằm đúng lúc chạy, hàng = batch; chấm tròn = chạy tay, thoi = theo lịch.
    Khoảng nghỉ dài giữa các đợt chạy bị cắt khỏi trục (rangebreaks); chỗ cắt có vạch đứt kèm chú thích 'nghỉ 4 giờ'.
    Mọi lần chạy cùng một ngày thì trục chỉ ghi giờ (ngày ghi ở tiêu đề phụ - T1.2)."""
    fig = go.Figure()
    bay_gio = _gio_db()
    ket_thuc = df.finished_at.fillna(bay_gio)
    nghi = _khoang_nghi(df, bay_gio)
    mot_ngay = _mot_ngay(df, bay_gio)
    nhip = (ket_thuc.max() - df.started_at.min()).total_seconds() - sum((k - b).total_seconds() for b, k in nghi)
    nhip = max(nhip, 60)   # độ dài trục sau khi đã cắt khoảng nghỉ
    rong_toi_thieu = nhip / 140   # lần chạy quá ngắn so với khoảng thời gian đang xem vẫn nhìn thấy được
    thoi_gian = (ket_thuc - df.started_at).dt.total_seconds().clip(lower=1)
    for tt in q.TRANG_THAI:
        d = df[df.status == tt]
        if d.empty:
            continue
        fig.add_trace(go.Bar(
            y=d.batch_id, x=[max(v, rong_toi_thieu) * 1000 for v in thoi_gian[d.index]], base=d.started_at, orientation="h",
            name=tt, marker=dict(color=MAU_TT[tt], line=dict(width=0)), width=0.5,
            customdata=list(zip(d.run_id, d.pipeline_name, d.triggered_by, [thoi_luong(v) for v in thoi_gian[d.index]],
                                [rut_gon(e, 80) for e in d.error_message.fillna("")])),
            hovertemplate="<b>#%{customdata[0]}, batch %{y}</b><br>" + tt + ", %{customdata[2]}, %{customdata[1]}<br>"
                          "Chạy %{customdata[3]}<br>%{customdata[4]}<extra></extra>"))
    for kich, ky_hieu in (("manual", "circle"), ("schedule", "diamond")):
        d = df[df.triggered_by == kich]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            y=d.batch_id, x=d.started_at, mode="markers",
            marker=dict(symbol=ky_hieu, size=8, color=DEN, line=dict(color="#fff", width=1.5)), hoverinfo="skip"))
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=batches, autorange="reversed")
    cau_hinh = dict(type="date", tickformat="%H:%M" if mot_ngay else "%H:%M<br>%d/%m/%Y")
    if nghi:
        vals, texts = _nhan_truc(df.started_at.min(), ket_thuc.max(), nghi, mot_ngay=mot_ngay)
        cau_hinh.update(rangebreaks=[dict(bounds=[b.isoformat(), k.isoformat()]) for b, k in nghi],
                        tickmode="array", tickvals=vals, ticktext=texts, tickangle=0)
        for b, k in nghi:   # vạch đứt ở chỗ cắt + chú thích độ dài khoảng nghỉ thật (cộng lại phần lề đã giữ)
            thuc = (k - b).total_seconds() + 2 * LE_NGHI_PHUT * 60
            fig.add_shape(type="line", x0=b, x1=b, y0=0, y1=1, xref="x", yref="paper",
                          line=dict(color=XAM, width=1.2, dash="dot"))
            fig.add_annotation(x=b, y=0.98, xref="x", yref="paper", text=_nghi_txt(thuc, len(nghi) <= 3), showarrow=False, yanchor="top",
                               xanchor="left", xshift=3, textangle=-90, font=dict(size=10, color=XAM))
    fig.update_xaxes(**cau_hinh)
    fig.update_layout(barmode="overlay")
    return khung_plotly(fig, 310)


MAU_MAGE = "#C9CDD4"


def _bieu_do_thoi_gian_tung_lan(df: pd.DataFrame):
    """(b) mỗi lần chạy 1 cột chồng: nạp staging / dbt khởi động / dbt build / Mage (đang chạy tính tới bây giờ).
    Lần FAILED: số run trên trục ngang tô đỏ đậm (T1.3); lần đang chạy tô tím đậm."""
    d = df.tail(40).copy()
    stg, prep, dbt, mage = (d.staging_s.fillna(0), d.dbt_prep_s.fillna(0), d.dbt_s.fillna(0), d.mage_s.fillna(0))
    # đang ở khâu dbt (chưa có kết quả dbt): phần "còn lại" thực ra là dbt đang chạy
    dang_dbt = (d.status == "RUNNING") & (d.phase == "dbt")
    dbt = dbt.where(~dang_dbt, mage)
    mage = mage.where(~dang_dbt, 0)
    nhan = [f"#{r}" for r in d.run_id]
    tick = [f'<span style="color:#B8382B"><b>#{r.run_id}</b></span>' if r.status == "FAILED" else
            f'<span style="color:#3A47C4"><b>#{r.run_id}</b></span>' if r.status == "RUNNING" else f"#{r.run_id}"
            for r in d.itertuples()]
    fig = go.Figure()
    for ten, gt, mau in (("Nạp staging", stg, CHANH_BAR), ("dbt khởi động", prep, TIM_NHAT), ("dbt build", dbt, TIM_DAM),
                         ("Mage", mage, MAU_MAGE)):
        fig.add_trace(go.Bar(x=nhan, y=gt, name=ten, marker=dict(color=mau, line=dict(color="#fff", width=1)),
                             customdata=d.status, hovertemplate="%{x}, %{customdata}<br>" + ten + ": %{y:.1f} giây<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.32)
    fig.update_xaxes(type="category", tickmode="array", tickvals=nhan, ticktext=tick, showgrid=False,
                     tickangle=0 if len(nhan) * max(map(len, nhan), default=0) <= 40 else None)   # vừa chỗ thì nằm ngang
    fig.update_yaxes(rangemode="tozero")
    return khung_plotly(fig, 310)


def _bieu_do_so_dong(theo_batch: pd.DataFrame):
    """(c) INSERT / UPDATE đã commit theo batch (cột chồng) + số dòng bị loại vào dq (nhãn đỏ ngay trên cột). Full Load vẽ riêng ngoài."""
    d = theo_batch[theo_batch.batch_id != q.FULL_BATCH]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=d.batch_id, y=d.rows_inserted, name="INSERT", marker_color=CHANH_BAR,
                         hovertemplate="Batch %{x}<br>INSERT: %{y:,}<extra></extra>"))
    fig.add_trace(go.Bar(x=d.batch_id, y=d.rows_updated, name="UPDATE", marker_color=TIM,
                         hovertemplate="Batch %{x}<br>UPDATE: %{y:,}<extra></extra>"))
    cao = float((d.rows_inserted + d.rows_updated).max()) if len(d) else 0.0
    for r in d[d.rows_rejected > 0].itertuples():
        fig.add_annotation(x=r.batch_id, y=float(r.rows_inserted + r.rows_updated), yshift=12, showarrow=False,
                           text=f"{so_vn(r.rows_rejected)} bị loại", font=dict(color=DO, size=11))
    fig.update_layout(barmode="stack", bargap=0.42, yaxis=dict(tickformat=",d", range=[0, max(cao * 1.12, 1)]))
    fig.update_xaxes(type="category", showgrid=False)
    return khung_plotly(fig, 372)


def _luoi_batch(tien_do: pd.DataFrame) -> str:
    """Tiến độ 10 batch: giữ kiểu ô (nền + viền theo trạng thái, chip góc phải), xếp 2 cột x 5 hàng (T1.5)."""
    o = []
    for r in tien_do.itertuples():
        # lần chạy gần nhất đang RUNNING thì hiện RUNNING; đã nạp thành công (da_nap) thì ưu tiên SUCCESS dù trong lượt
        # còn một lần lỗi đã rollback (N4, VD Full Load lỗi); chưa nạp được thì theo trạng thái lần gần nhất
        if r.trang_thai_cuoi == "RUNNING":
            tt = "RUNNING"
        elif r.da_nap:
            tt = "SUCCESS"
        else:
            tt = r.trang_thai_cuoi if r.trang_thai_cuoi in ("FAILED", "PENDING") else "PENDING"
        dong1 = ("chưa nạp" if tt == "PENDING" else
                 f"xong {gio(r.xong_luc, False)}" if tt == "SUCCESS" else
                 "đang chạy…" if tt == "RUNNING" else "lần cuối bị lỗi")
        dong2 = "" if not r.so_lan_thu else (f"{r.so_lan_thu} lần thử, {r.so_lan_failed} lỗi" if r.so_lan_failed
                                             else f"{r.so_lan_thu} lần thử")
        o.append(f'<div class="o_batch {tt}"><div class="b"><span>{esc(r.batch_id)}</span>{chip(tt)}</div>'
                 f'<div class="m">{dong1}{"<br>" + dong2 if dong2 else ""}</div></div>')
    return '<div class="luoi_batch">' + "".join(o) + "</div>"


def _the_kpi_trang1(k: dict) -> list[str]:
    """5 thẻ KPI trang 1 theo T1.1: dòng phụ tách thành các ô nhỏ có nhãn."""
    gn = k["gan_nhat"]
    t1 = the_kpi("Số lần chạy", so_vn(k["so_lan"]),
                 mini("Chạy tay", so_vn(k["so_manual"])) + mini("Theo lịch", so_vn(k["so_schedule"])), "chanh")
    t2 = the_kpi("Tỉ lệ thành công", phan_tram(k["ti_le_thanh_cong"]),
                 mini("SUCCESS", so_vn(k["so_success"])) + mini("FAILED", so_vn(k["so_failed"]))
                 + (mini("Đang chạy", so_vn(k["so_running"])) if k["so_running"] else ""), "tim")
    if gn:
        t3 = the_kpi("Lần chạy gần nhất", esc(gn["status"]),
                     mini("Batch", esc(gn["batch_id"])) + mini("Cách đây", esc(cach_day(gn["giay_truoc"], truoc=False))),
                     "trang", don_vi=f'#{gn["run_id"]}', mau_so="xau" if gn["status"] == "FAILED" else "")
    else:
        t3 = the_kpi("Lần chạy gần nhất", "–", chu_day("Chưa có lần chạy nào"), "trang")
    # tiến độ batch ("đã nạp hết" dựa vào batch cuối 2018-09+ đã nạp, không dựa vào cet)
    if k["da_het"]:
        lset = "Đã nạp hết batch"
    elif k["lset"] is not None and pd.notna(k["lset"]):
        lset = f'LSET hiện tại: {pd.Timestamp(k["lset"]):%d/%m/%Y}'
    else:
        lset = "Chưa nạp batch nào" if not k["batch_da_nap"] else "LSET: –"
    ti_le = k["batch_da_nap"] / k["batch_tong"] * 100 if k["batch_tong"] else 0
    t4 = the_kpi("Tiến độ batch", f'{k["batch_da_nap"]}/{k["batch_tong"]}',
                 f'<div style="width:100%"><div class="tien"><i style="width:{ti_le:.0f}%"></i></div>{chu_day(esc(lset))}</div>',
                 "trang", don_vi="batch")
    # thời gian trung bình (chỉ các lần SUCCESS): dbt = dbt khởi động + dbt build (biểu đồ bên dưới vẫn tách 4 khâu)
    if k["tb_giay"] is not None:
        def g(*x):
            x = [v for v in x if v is not None]
            return so_vn(sum(x), 1) if x else "–"
        t5 = the_kpi("Thời gian chạy TB", so_vn(k["tb_giay"], 1),
                     mini("Staging", g(k["tb_staging"])) + mini("dbt", g(k["tb_dbt_prep"], k["tb_dbt"])) + mini("Mage", g(k["tb_mage"])),
                     "den", don_vi="giây")
    else:
        t5 = the_kpi("Thời gian chạy TB", "–", chu_day("Chưa có lần SUCCESS"), "den")
    return [t1, t2, t3, t4, t5]


def trang_tong_quan(bl: q.BoLoc, bay_gio: pd.Timestamp) -> None:
    df = _lan_chay(bl)
    tien_do = _tien_do(bl.luot)
    _hien_canh_bao(bl, bay_gio)
    if df.empty:
        st.markdown('<div class="hop_ghi">Không có lần chạy nào khớp bộ lọc (hoặc <b>etl_log</b> còn trống). '
                    'Hãy nới bộ lọc ở thanh bên hoặc chạy pipeline <b>full_load</b> trước.</div>', unsafe_allow_html=True)
    hang_kpi(_the_kpi_trang1(q.kpi_trang1(df, tien_do, bay_gio)))
    if df.empty:
        return

    batches = tien_do.batch_id.tolist()
    c1, c2 = st.columns([3, 2])
    with c1:
        kt = df.finished_at.fillna(bay_gio)
        d0, d1 = df.started_at.min(), kt.max()
        ngay = f"Ngày {d0:%d/%m/%Y}." if _mot_ngay(df, bay_gio) else f"Từ {d0:%d/%m/%Y} đến {d1:%d/%m/%Y}."
        phu_a = f"{ngay} Mỗi thanh là một lần chạy; nhiều thanh trên cùng một hàng là batch phải chạy lại"
        phu_a += "; vạch đứt là chỗ bỏ bớt khoảng nghỉ dài." if _khoang_nghi(df, bay_gio) else "."
        co_tt = [tt for tt in q.TRANG_THAI if (df.status == tt).any()]
        co_kh = [(t, k) for t, k in (("Chạy tay", "manual"), ("Theo lịch", "schedule")) if (df.triggered_by == k).any()]
        cg = chu_giai([(tt, MAU_TT[tt]) for tt in co_tt]
                      + [(t, "tron" if k == "manual" else "thoi") for t, k in co_kh])
        c = the_ve("dong_thoi_gian", "Các lần chạy theo thời gian", phu_a, cg)
        ve(c, _bieu_do_dong_thoi_gian(df, batches), "bd_dong_thoi_gian")
    with c2:
        phu_b = "Đơn vị: giây. Số lần chạy màu đỏ là lần chạy FAILED"
        phu_b += ", màu tím là lần đang chạy." if (df.tail(40).status == "RUNNING").any() else "."
        cg = chu_giai([("Nạp staging", CHANH_BAR), ("dbt khởi động", TIM_NHAT), ("dbt build", TIM_DAM), ("Mage", MAU_MAGE)])
        c = the_ve("thoi_gian_lan", "Thời gian chạy từng lần", phu_b, cg)
        ve(c, _bieu_do_thoi_gian_tung_lan(df), "bd_thoi_gian_lan")
    c3, c4 = st.columns([3, 2])
    theo_batch = _so_dong_batch(bl)
    with c3:
        full = theo_batch[theo_batch.batch_id == q.FULL_BATCH]
        co_incr = bool(len(theo_batch) and (theo_batch.batch_id != q.FULL_BATCH).any())
        phu_c = "Số dòng đã commit vào staging"
        if len(full) and full.rows_inserted.sum() > 0:
            phu_c += (f". Batch {q.FULL_BATCH} ({so_vn(full.rows_inserted.sum())} dòng) không vẽ để các batch khác dễ so sánh."
                      if co_incr else f"; batch {q.FULL_BATCH} nạp {so_vn(full.rows_inserted.sum())} dòng.")
        else:
            phu_c += "."
        if bl.luot is None:
            phu_c += " Đang xem tất cả lượt nạp nên mỗi cột cộng dồn nhiều lượt."
        muc = [("INSERT (thêm mới)", CHANH_BAR), ("UPDATE (cập nhật)", TIM)]
        if co_incr and (theo_batch[theo_batch.batch_id != q.FULL_BATCH].rows_rejected > 0).any():
            muc.append(("Số dòng bị loại vào dq (chữ đỏ trên cột)", DO))
        c = the_ve("so_dong", "Số dòng nạp theo batch", phu_c, chu_giai(muc) if co_incr else "")
        if co_incr:
            ve(c, _bieu_do_so_dong(theo_batch), "bd_so_dong")
        else:
            trong(c, "Chưa có batch Incremental nào trong bộ lọc này.", ok=False)
    with c4:
        c = the_ve("luoi_batch", "Tiến độ 10 batch", "Của lượt nạp đang chọn, không phụ thuộc bộ lọc trạng thái và kích hoạt.")
        c.markdown(_luoi_batch(tien_do), unsafe_allow_html=True)

    tieu_de("20 lần gần nhất", "Danh sách lần chạy")
    _bang_lan_chay(df.sort_values("run_id", ascending=False).head(20).reset_index(drop=True))


# Bảng 20 lần chạy dựng bằng hàng st.columns (không dùng st.dataframe) để mỗi dòng có nút "Chi tiết ›" thật:
# bấm là sang trang 3 trong cùng phiên (giữ bộ lọc); ô Lỗi ghi tóm tắt, rê chuột vào thấy thông báo đầy đủ (thuộc tính title).
# (tiêu đề cột, tỉ lệ độ rộng, căn phải, chú thích khi rê chuột vào tiêu đề)
COT_BANG_RUN = [
    ("Run", .45, False, ""), ("Pipeline", 1.25, False, "Tên pipeline bỏ đuôi _load: full / incremental"),
    ("Batch", .85, False, ""), ("Kích hoạt", .9, False, ""), ("Trạng thái", 1.05, False, ""),
    ("Bắt đầu", 1.4, False, ""), ("Thời lượng", 1.4, True, ""),
    ("Dòng nạp", .9, True, "INSERT + UPDATE ĐÃ COMMIT vào staging (lần FAILED bị hoàn tác tính 0)"),
    ("WARN", .6, True, "Số phép kiểm tra chất lượng WARN"), ("Test lỗi", .7, True, "Số dbt test fail / error"),
    ("Lỗi", 2.6, False, "Tóm tắt lỗi; rê chuột vào ô để xem thông báo đầy đủ, trang chi tiết có thông báo nguyên văn"),
    ("", 1.3, False, "")]


def _xem_chi_tiet(run_id: int) -> None:
    st.session_state.run_chon = run_id
    st.session_state.trang = 3
    st.session_state.cuon_len = True   # sang trang 3 thì cuộn lên đầu trang


def _bang_lan_chay(g: pd.DataFrame) -> None:
    khung = st.container(key="bang_run")
    rong = [c[1] for c in COT_BANG_RUN]
    for cot, (ten, _, phai, goi_y) in zip(khung.columns(rong, gap="small", vertical_alignment="center"), COT_BANG_RUN):
        cot.markdown(f'<div class="o_bang tieu{" phai" if phai else ""}" title="{esc(goi_y)}">{esc(ten)}</div>',
                     unsafe_allow_html=True)
    for r in g.itertuples():
        loi_day_du = " ".join(str(r.error_message).split()) if pd.notna(r.error_message) else ""
        dang_chay = pd.isna(r.duration_s)
        dong = r.rows_inserted + r.rows_updated
        o = [(f"<b>{r.run_id}</b>", ""), (esc(str(r.pipeline_name).replace("_load", "")), ""), (esc(r.batch_id), ""),
             (esc(r.triggered_by), ""), (chip(r.status), ""), (pd.Timestamp(r.started_at).strftime("%d/%m %H:%M:%S"), ""),
             (thoi_luong(r.elapsed_s if dang_chay else r.duration_s) + ("…" if dang_chay else ""), "phai"),
             (so_vn(dong), "phai" + lop_0(dong)), (so_vn(r.n_check_warn), "phai" + lop_0(r.n_check_warn)),
             (so_vn(r.dbt_test_fail), "phai" + lop_0(r.dbt_test_fail))]
        hang = khung.columns(rong, gap="small", vertical_alignment="center")
        for cot, (noi_dung, lop) in zip(hang, o):
            cot.markdown(f'<div class="o_bang {lop}">{noi_dung}</div>', unsafe_allow_html=True)
        tom = tom_tat_loi(r) or (rut_gon(loi_day_du, 60) if loi_day_du else "")
        hang[-2].markdown(f'<div class="o_bang loi" title="{esc(loi_day_du)}">{esc(tom)}</div>', unsafe_allow_html=True)
        # không dùng on_click: khi bật "Tự làm mới" trang nằm trong st.fragment, callback chỉ chạy lại fragment (vẫn
        # trang cũ) -> bấm xong gọi st.rerun() để chạy lại cả app với trang mới
        if hang[-1].button("Chi tiết ›", key=f"xem_{r.run_id}"):
            _xem_chi_tiet(int(r.run_id))
            st.rerun()


# ---------------------------------------------------------------------------
# Trang 2 - Chất lượng dữ liệu
# ---------------------------------------------------------------------------
def _bieu_do_ma_tran(mt: pd.DataFrame, batches: list[str]):
    cot = [c for c in q.THU_TU_CHECK if c in set(mt.check_name)] or list(q.THU_TU_CHECK[:7])
    hang = [b for b in batches if b in set(mt.batch_id)]
    ma = {"PASS": 0, "WARN": 1, "FAIL": 2}
    z, text, hover = [], [], []
    tra = {(r.batch_id, r.check_name): r for r in mt.itertuples()}
    for b in hang:
        zz, tt, hh = [], [], []
        for c in cot:
            r = tra.get((b, c))
            if r is None:
                zz.append(None); tt.append(""); hh.append(f"{b}, {TEN_CHECK[c][1]}<br>chưa có dữ liệu")
            else:
                zz.append(ma[r.status])
                # WARN / FAIL chỉ kèm số dòng khi có dòng vi phạm (VD row_count_match WARN không có dòng nào bị loại)
                tt.append(r.status if r.status == "PASS" or not r.failed_rows else f"{r.status} {so_vn(r.failed_rows)}")
                hh.append(f"{b}, {TEN_CHECK[c][1]}<br>{r.status}, {so_vn(r.failed_rows)} dòng vi phạm, {r.so_phep} phép đã chạy"
                          + (f"<br>bảng {r.bang_loi}" if r.bang_loi else ""))
        z.append(zz); text.append(tt); hover.append(hh)
    fig = go.Figure(go.Heatmap(
        z=z, x=[TEN_CHECK[c][1] for c in cot], y=hang, text=text, texttemplate="%{text}", hovertext=hover,
        hovertemplate="%{hovertext}<extra></extra>", xgap=3, ygap=3, showscale=False, zmin=0, zmax=2,
        colorscale=[[0, "#DDF08A"], [0.333, "#DDF08A"], [0.334, VANG], [0.666, VANG], [0.667, DO], [1, DO]],
        textfont=dict(size=11, color=DEN)))
    fig.update_yaxes(autorange="reversed", type="category", showgrid=False)
    fig.update_xaxes(side="top", type="category", tickangle=0, tickfont=dict(size=11, color=CHU2), showgrid=False)
    return khung_plotly(fig, max(260, 36 * len(hang) + 90), plot_bgcolor=NHAT)


def _bieu_do_dbt_theo_lan(df: pd.DataFrame):
    d = df[df.dbt_n_node > 0].tail(40)
    nhan = [f"#{r}" for r in d.run_id]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=nhan, y=d.dbt_test_fail, name="Test FAIL hoặc ERROR", marker_color=DO,
                         hovertemplate="%{x}<br>Test FAIL hoặc ERROR: %{y}<extra></extra>"))
    if d.dbt_test_warn.sum():
        fig.add_trace(go.Bar(x=nhan, y=d.dbt_test_warn, name="Test WARN", marker_color=VANG,
                             hovertemplate="%{x}<br>Test WARN: %{y}<extra></extra>"))
    cao = float((d.dbt_test_fail + d.dbt_test_warn).max()) if len(d) else 1.0
    fig.update_layout(barmode="stack", bargap=0.62)
    fig.update_xaxes(type="category", tickangle=0 if len(nhan) * max(map(len, nhan), default=0) <= 40 else None, showgrid=False)
    fig.update_yaxes(dtick=1, rangemode="tozero", range=[0, cao + 0.4])
    return khung_plotly(fig, 220)


def _cot_gay_loai(reason, cac_cot) -> set:
    """Cột làm dòng bị loại (T2.5): tên cột đứng đầu `reason` (VD 'order_id rỗng', 'payment_value = "abc" không hợp lệ…');
    lý do trùng khóa 'khóa (a=…, b=…) lặp…' thì là các cột khóa. Không xác định được -> rỗng (không tô)."""
    import re
    r = str(reason or "").strip()
    dau = r.split(" ")[0] if r else ""
    if dau in cac_cot:
        return {dau}
    if r.startswith("khóa ("):
        return {c for c in re.findall(r"(\w+)=", r) if c in cac_cot}
    return set()


def _o_noi_dung_dong(row_json, reason) -> str:
    """row_data (JSONB) -> các ô nhỏ 'tên cột: giá trị'; rỗng ghi (trống); ô của cột làm dòng bị loại tô đỏ."""
    import json
    du_lieu = row_json if isinstance(row_json, dict) else (json.loads(row_json) if row_json else {})
    loi = _cot_gay_loai(reason, set(du_lieu))
    o = [f'<span class="kv{" loi" if c in loi else ""}">{esc(c)}: '
         f'{"(trống)" if v is None or str(v) == "" else esc(v)}</span>' for c, v in du_lieu.items()]
    return '<div class="kv_wrap">' + "".join(o) + "</div>"


def _ten_check(c: str) -> str:
    """Tên phép kiểm tra tiếng Việt như tiêu đề cột ma trận, rê chuột thấy tên gốc."""
    return f'<span title="{esc(c)}">{esc(TEN_CHECK[c][1] if c in TEN_CHECK else c)}</span>'


def _the_kpi_trang2(df: pd.DataFrame) -> list[str]:
    if df.empty:
        rong = chu_day("Chưa có dữ liệu")
        return [the_kpi("Phép kiểm tra WARN / FAIL", "–", rong, "chanh"), the_kpi("Dòng bị loại vào dq", "–", rong, "tim"),
                the_kpi("dbt test không đạt", "–", rong), the_kpi("Lần FAILED do dbt", "–", rong),
                the_kpi("Lần FAILED do nạp staging", "–", rong, "den")]
    k = q.kpi_trang2(df)
    return [
        the_kpi("Phép kiểm tra WARN / FAIL", so_vn(k["check_warn"] + k["check_fail"]),
                mini("WARN", so_vn(k["check_warn"])) + mini("FAIL", so_vn(k["check_fail"])) + mini("Khâu", "Mage"), "chanh"),
        the_kpi("Dòng bị loại vào dq", so_vn(k["dong_loai"]), mini("Lưu tại", "dq.rejected_rows"), "tim"),
        the_kpi("dbt test không đạt", so_vn(k["dbt_test_fail"]), mini("Test WARN", so_vn(k["dbt_test_warn"])), "trang",
                mau_so="xau" if k["dbt_test_fail"] else ""),
        the_kpi("Lần FAILED do dbt", so_vn(k["failed_dbt"]), chu_day("dbt báo lỗi sau khi staging đã nạp xong"), "trang",
                mau_so="xau" if k["failed_dbt"] else ""),
        the_kpi("Lần FAILED do nạp staging", so_vn(k["failed_staging"]), mini("Bị ngắt hoặc khác", so_vn(k["failed_khac"])), "den")]


def trang_chat_luong(bl: q.BoLoc, bay_gio: pd.Timestamp) -> None:
    df = _lan_chay(bl)
    if df.empty:
        st.markdown('<div class="hop_ghi">Không có lần chạy nào khớp bộ lọc (hoặc <b>etl_log</b> còn trống). Nới bộ lọc ở thanh bên.</div>',
                    unsafe_allow_html=True)
        hang_kpi(_the_kpi_trang2(df))
        return
    hang_kpi(_the_kpi_trang2(df))
    batches = _tien_do(bl.luot).batch_id.tolist()

    tieu_de("Mage", "Kiểm tra chất lượng khi nạp staging")
    c = the_ve("ma_tran", "Batch × phép kiểm tra",
               "Màu = kết quả tệ nhất trong các lần chạy đã lọc: xanh PASS; vàng WARN (loại dòng, vẫn nạp); "
               "đỏ FAIL (dừng cả batch). Ô xám: chưa có dữ liệu.")
    mt = _ma_tran(bl)
    if mt.empty:
        trong_dong(c, "Chưa có kết quả kiểm tra chất lượng nào trong bộ lọc này.", ok=False)
    else:
        ve(c, _bieu_do_ma_tran(mt, batches), "bd_ma_tran")

    c1, c2 = st.columns([4, 3])
    with c1:
        c = the_ve("dong_loai", "Dòng bị loại theo bảng và lý do", "Gom từ dq.rejected_rows của các lần chạy đã lọc.")
        dl = _dong_loai(bl)
        if dl.empty:
            trong(c, "Không có dòng nào bị loại trong các lần chạy đã lọc.")
        else:
            lon = max(int(dl.so_dong.max()), 1)
            hang = [[(esc(r.table_name), ""), (_ten_check(r.check_name), ""),
                     (f'<span class="cat" style="max-width:150px" title="{esc(r.reason)}">{esc(r.reason)}</span>', ""),
                     (f'<span class="thanh_so"><i style="width:{max(6, r.so_dong / lon * 60):.0f}px"></i>'
                      f'<b>{so_vn(r.so_dong)}</b></span>', "r")] for r in dl.itertuples()]
            so_lan = int((df.rows_rejected > 0).sum())
            c.markdown('<div class="gian">' + bang_html([("Bảng", ""), ("Phép kiểm tra", ""), ("Lý do", ""), ("Số dòng", "r")], hang)
                       + f'<div class="tong_ket">Tổng <b>{so_vn(dl.so_dong.sum())}</b> dòng bị loại, '
                         f'<b>{so_vn(dl.table_name.nunique())}</b> bảng, <b>{so_vn(so_lan)}</b> lần chạy.</div></div>',
                       unsafe_allow_html=True)
    with c2:
        d = df[df.dbt_n_node > 0]
        co_bd = not d.empty and (d.dbt_test_fail + d.dbt_test_warn).sum() > 0
        muc = [("Test FAIL hoặc ERROR", DO)] + ([("Test WARN", VANG)] if co_bd and d.dbt_test_warn.sum() else [])
        c = the_ve("dbt_lan", "dbt test không đạt theo lần chạy",
                   "Mỗi cột là một lần chạy có chạy dbt; không có cột nghĩa là mọi test đều đạt.", chu_giai(muc) if co_bd else "")
        if d.empty:
            trong(c, "Chưa có lần chạy nào có kết quả dbt trong bộ lọc này.", ok=False)
        elif not co_bd:
            trong(c, f"{so_vn(len(d))} lần chạy có dbt, mọi test đều đạt.")
        else:
            ve(c, _bieu_do_dbt_theo_lan(df), "bd_dbt_lan")

    tieu_de("Dòng lỗi", "Chi tiết dòng lỗi")
    c = the_ve("mau_loai", "Mẫu dòng bị loại (dq.rejected_rows)",
               "Tối đa 50 dòng mới nhất. Ô tô đỏ trong cột “Nội dung dòng” là cột làm dòng bị loại.")
    ml = _mau_loai(bl)
    if ml.empty:
        trong_dong(c, "Không có dòng bị loại.")
    else:
        hang = [[(f"<b>{r.run_id}</b>", ""), (esc(r.table_name), ""), (_ten_check(r.check_name), ""), o_so(r.source_row),
                 (f'<span class="cat" style="max-width:180px" title="{esc(r.reason)}">{esc(r.reason)}</span>', ""),
                 (_o_noi_dung_dong(r.row_json, r.reason), "go"), (gio(r.rejected_at), "")] for r in ml.itertuples()]
        c.markdown(bang_html([("Run", ""), ("Bảng", ""), ("Phép kiểm tra", ""), ("Bản ghi số", "r"), ("Lý do", ""),
                              ("Nội dung dòng", ""), ("Lúc loại", "")], hang), unsafe_allow_html=True)

    c = the_ve("dbt_loi", "Danh sách dbt test không đạt",
               "Dòng vi phạm nằm trong bảng ở cột cuối; rê chuột để xem tên đầy đủ của test và bảng.")
    dt = _dbt_loi(bl)
    if dt.empty:
        trong_dong(c, "Không có dbt test nào fail, error hoặc warn trong bộ lọc này.")
    else:
        hang = [[(f"<b>{r.run_id}</b>", ""), (esc(r.batch_id), ""), (esc(r.triggered_by), ""),
                 (f'<span class="mono cat" style="max-width:420px" title="{esc(r.node_name)}">{esc(ten_test_ngan(r.node_name))}</span>', ""),
                 (chip_dbt(r.status, str(r.status).upper()), ""), o_so(r.failures),
                 (f'<span class="mono cat" style="max-width:240px" title="{esc(r.relation_name)}">{esc(r.relation_name)}</span>', "")]
                for r in dt.itertuples()]
        c.markdown(bang_html([("Run", ""), ("Batch", ""), ("Kích hoạt", ""), ("Test", ""), ("Trạng thái", ""),
                              ("Dòng vi phạm", "r"), ("Bảng chứa dòng lỗi", "")], hang), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Trang 3 - Chi tiết một lần chạy
# ---------------------------------------------------------------------------
MAU_KHAU = {"Mage": MAU_MAGE, "Nạp staging": CHANH_BAR, "dbt khởi động": TIM_NHAT, "dbt build": TIM}
# bước thời gian đẹp (mili giây) để chọn dtick của trục Gantt: không bao giờ lặp nhãn giờ khi lần chạy chỉ dài vài giây
BUOC_DTICK = (100, 200, 500, 1000, 2000, 5000, 10000, 15000, 30000, 60000, 120000, 300000, 600000)
KHAU_LOI = {"dbt": "dbt", "staging": "nạp staging", "bi_ngat": "bị ngắt", "khac": "khác"}


def _dtick_gantt(buoc: pd.DataFrame) -> tuple[int, str]:
    """Chọn dtick (ms) sao cho trục có khoảng 6-8 nhãn; dưới 1 giây thì nhãn có phần mili giây."""
    tong_ms = max((buoc.ket_thuc.max() - buoc.bat_dau.min()).total_seconds() * 1000, 1.0)
    dtick = next((d for d in BUOC_DTICK if tong_ms / d <= 8), BUOC_DTICK[-1])
    return dtick, ("%H:%M:%S.%L" if dtick < 1000 else "%H:%M:%S")


def _ten_buoc(b: str) -> str:
    """Tên hàng Gantt ngắn (T3.5): 'staging.customers' -> 'customers', 'Mage (ghi log)' -> 'Mage ghi log'."""
    return (str(b).replace("staging.", "").replace(" / parse", "")
            .replace("Mage (khởi động)", "Mage khởi động").replace("Mage (ghi log)", "Mage ghi log"))


def _bieu_do_gantt(buoc: pd.DataFrame):
    buoc = buoc.assign(buoc=buoc.buoc.map(_ten_buoc))
    fig = go.Figure()
    for khau in ("Mage", "Nạp staging", "dbt khởi động", "dbt build"):
        d = buoc[buoc.khau == khau]
        if d.empty:
            continue
        mau = [MAU_TT["FAILED"] if t == "FAILED" else MAU_TT["RUNNING"] if t == "RUNNING" else MAU_KHAU[khau] for t in d.trang_thai]
        giay = (d.ket_thuc - d.bat_dau).dt.total_seconds().clip(lower=0.2)
        fig.add_trace(go.Bar(y=d.buoc, x=giay * 1000, base=d.bat_dau, orientation="h", name=khau, marker_color=mau, width=0.58,
                             customdata=[[khau, thoi_luong(v), t] for v, t in zip(giay, d.trang_thai)],
                             hovertemplate="<b>%{y}</b><br>%{customdata[0]}, %{customdata[2]}<br>%{customdata[1]}<extra></extra>"))
    dtick, dinh_dang = _dtick_gantt(buoc)
    fig.update_yaxes(type="category", autorange="reversed", categoryorder="array", categoryarray=buoc.buoc.tolist())
    fig.update_xaxes(type="date", tickformat=dinh_dang, dtick=dtick)
    fig.update_layout(barmode="overlay")
    return khung_plotly(fig, max(200, 24 * len(buoc) + 50))


def _vao_staging(t: str) -> str:
    return {"SUCCESS": "Có", "FAILED": "Không, đã hoàn tác", "RUNNING": "Đang nạp"}.get(t, t)


def _rel_ngan(rel, n: int) -> str:
    """Tên bảng dq cắt ngắn, rê chuột thấy tên đầy đủ."""
    r = str(rel or "")
    hien = r if len(r) <= n else r[:n] + "…"
    return f'<span class="mono" title="{esc(r)}">{esc(hien)}</span>'


def _khung_loi(run, tl: pd.DataFrame, dbt: pd.DataFrame) -> str:
    """Khung lỗi 3 tầng (T3.3): (1) 1 câu tóm tắt từ số trong v_run; (2) mỗi node dbt / bảng staging lỗi 1 dòng, tối đa 3;
    (3) thông báo gốc thu trong <details>, bấm mới mở."""
    dong, nhan_goc = [], "Xem thông báo gốc của dbt"
    if run.failed_stage == "dbt":
        phan = []
        if run.dbt_model_error:
            phan.append(f"{so_vn(run.dbt_model_error)} model lỗi")
        if run.dbt_test_fail:
            phan.append(f"{so_vn(run.dbt_test_fail)} test không đạt")
        if run.dbt_n_skipped:
            phan.append(f"{so_vn(run.dbt_n_skipped)} node bị bỏ qua")
        dat = f" ({so_vn(run.dbt_n_ok)}/{so_vn(run.dbt_n_node)} node đạt)" if run.dbt_n_node else ""
        tom = f"dbt build lỗi: {', '.join(phan) if phan else 'dbt không chạy được'}{dat}."
        xau = dbt[dbt.status.map(q.la_loi_dbt)] if len(dbt) else dbt
        for x in xau.itertuples():
            ten = f'<span class="mono" title="{esc(x.node_name)}">{esc(ten_test_ngan(x.node_name))}</span>'
            if x.resource_type == "test" and pd.notna(x.failures):
                dong.append(f"{ten}: {so_vn(x.failures)} dòng vi phạm, xem bảng {_rel_ngan(x.relation_name, 32)}")
            else:
                dong.append(f"{ten}: {esc(tom_tat_model(x.message))}")
    elif run.failed_stage == "staging":
        # bảng gây lỗi = bảng FAILED có lỗi thật; các bảng đã MERGE xong chỉ bị hoàn tác theo ("Đã hoàn tác (rollback)…")
        loi = tl[tl.status == "FAILED"] if len(tl) else tl
        that = loi[~loi.error_message.fillna("").str.startswith("Đã hoàn tác")] if len(loi) else loi
        loi = that if len(that) else loi
        bang = ", ".join(loi.table_name) if len(loi) else ""
        tom = (f"Nạp staging lỗi ở bảng {bang}" if bang else "Nạp staging lỗi") + "; cả batch đã hoàn tác (rollback)."
        dong = [f'<span class="mono">{esc(t.table_name)}</span>: {esc(rut_gon(t.error_message, 120))}'
                for t in loi.itertuples() if pd.notna(t.error_message)]
        nhan_goc = "Xem thông báo lỗi gốc"
    elif run.failed_stage == "bi_ngat":
        tom = "Lần chạy bị ngắt giữa chừng (container tắt hoặc pipeline dừng đột ngột)."
        nhan_goc = "Xem thông báo lỗi gốc"
    else:
        tom = "Lần chạy bị lỗi."
        nhan_goc = "Xem thông báo lỗi gốc"
    them = f"<li>và {len(dong) - 3} lỗi khác</li>" if len(dong) > 3 else ""
    ds = ("<ul>" + "".join(f"<li>{d}</li>" for d in dong[:3]) + them + "</ul>") if dong else ""
    return (f'<div class="hop_loi"><p class="tom">{esc(tom)}</p>{ds}'
            f'<details><summary>{nhan_goc}</summary><div class="goc mono">{esc(run.error_message)}</div></details></div>')


def _ma_tran_run(qc: pd.DataFrame, tl: pd.DataFrame) -> str:
    """Ma trận bảng x phép kiểm tra của 1 lần chạy (T3.7), cùng kiểu ô với ma trận trang 2; rê chuột thấy số dòng vi phạm + detail."""
    thu_tu_bang = list(dict.fromkeys(list(tl.table_name) + list(qc.table_name)))
    bang = [b for b in thu_tu_bang if b in set(qc.table_name)]
    cot = [c for c in q.THU_TU_CHECK if c in set(qc.check_name)] + sorted(set(qc.check_name) - set(q.THU_TU_CHECK))
    tra = {(r.table_name, r.check_name): r for r in qc.itertuples()}
    h = "<div></div>" + "".join(f'<div class="hd">{esc(TEN_CHECK[c][1] if c in TEN_CHECK else c)}</div>' for c in cot)
    for b in bang:
        h += f'<div class="rh">{esc(b)}</div>'
        for c in cot:
            r = tra.get((b, c))
            if r is None:
                h += '<div class="o NA" title="Không có phép kiểm tra này"></div>'
                continue
            chu = r.status if r.status == "PASS" or not r.failed_rows else f"{r.status} {so_vn(r.failed_rows)}"
            goi_y = (f"{b}, {TEN_CHECK[c][1] if c in TEN_CHECK else c}: {r.status}, {so_vn(r.failed_rows)} dòng vi phạm"
                     + (f". {r.detail}" if pd.notna(r.detail) and r.detail else ""))
            h += f'<div class="o {esc(r.status)}" title="{esc(goi_y)}">{esc(chu)}</div>'
    return f'<div class="mt" style="grid-template-columns:auto repeat({len(cot)}, minmax(0,1fr))">{h}</div>'


def _dau_lan_chay(run, tl, dbt, bay_gio) -> str:
    """Thẻ thông tin lần chạy (T3.2): mỗi ô một thông tin, lưới 4 cột x 3 hàng; kèm khung lỗi 3 tầng nếu có lỗi."""
    kt = run.finished_at
    thoi_gian = thoi_luong(run.duration_s) if pd.notna(run.duration_s) else f"Đang chạy {thoi_luong(run.elapsed_s)}"
    lset = "Từ đầu dữ liệu" if pd.isna(run.lset) else f"{pd.Timestamp(run.lset):%d/%m/%Y}"
    cet = "Hết dữ liệu (batch cuối)" if pd.isna(run.cet) else f"{pd.Timestamp(run.cet):%d/%m/%Y}"
    khau_dang = {"staging": "nạp staging", "dbt": "dbt", "ghi_log": "ghi log"}
    tieu = (f'<div class="dau_tieu"><span class="so_run">Lần chạy #{run.run_id}</span>{chip(run.status)}'
            + (f'<span class="chip" style="background:#FDE3E0;color:#B8382B;font-weight:600;letter-spacing:0">'
               f'Lỗi ở khâu {esc(KHAU_LOI.get(run.failed_stage, run.failed_stage))}</span>' if run.status == "FAILED" else "")
            + (f'<span class="chip" style="background:#E4E8FD;color:#3A47C4;font-weight:600;letter-spacing:0">'
               f'Đang ở khâu {esc(khau_dang.get(run.phase, run.phase))}</span>' if run.status == "RUNNING" and run.phase else "")
            + (f'<span class="chip" style="background:#FDE3E0;color:#B8382B">Nghi kẹt &gt; {q.PHUT_KET} phút</span>' if run.is_stuck else "")
            + "</div>")
    o = [("Pipeline", esc(run.pipeline_name)), ("Batch", esc(run.batch_id)), ("Loại nạp", esc(run.load_type)),
         ("Kích hoạt", esc(run.triggered_by)), ("Lượt nạp", so_vn(run.cycle_no)), ("Lần thử của batch", so_vn(run.attempt_no)),
         ("LSET (thời gian mô phỏng)", lset), ("CET (thời gian mô phỏng)", cet),
         ("Bắt đầu", gio(run.started_at)), ("Kết thúc", gio(kt) if pd.notna(kt) else "Chưa kết thúc"),
         ("Thời lượng", thoi_gian),
         ("Khâu gây lỗi", esc(KHAU_LOI.get(run.failed_stage, run.failed_stage)) if run.status == "FAILED" else "Không có")]
    luoi = '<div class="dau_run">' + "".join(f'<div><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in o) + "</div>"
    loi = _khung_loi(run, tl, dbt) if pd.notna(run.error_message) and run.error_message else ""
    return tieu + luoi + loi


def _the_kpi_trang3(run) -> list[str]:
    """5 thẻ KPI trang 3 (T3.4)."""
    rollback = int(run.rows_inserted_rollback + run.rows_updated_rollback)
    t1 = the_kpi("Dòng đọc từ file", so_vn(run.rows_source),
                 mini("Số bảng, đã hoàn tác" if run.n_bang_loi else "Số bảng staging được nạp", so_vn(run.n_bang)), "chanh")
    t2 = the_chia("Dòng đã vào staging", [("Thêm mới", so_vn(run.rows_inserted)), ("Cập nhật", so_vn(run.rows_updated))],
                  chu_day(f"Đã hoàn tác {so_vn(run.rows_inserted_rollback)} thêm mới, "
                          f"{so_vn(run.rows_updated_rollback)} cập nhật", "xau") if rollback
                  else chu_day("Đã commit"), "tim")
    t3 = the_chia("Dòng bị loại và xóa mềm", [("Bị loại vào dq", so_vn(run.rows_rejected)), ("Đơn xóa mềm", so_vn(run.rows_deleted))],
                  chu_day("Bị loại lưu ở dq.rejected_rows"))
    t4 = the_kpi("Kiểm tra chất lượng", f"{so_vn(run.n_check_pass)}/{so_vn(run.n_check)}",
                 mini("PASS", so_vn(run.n_check_pass)) + mini("WARN", so_vn(run.n_check_warn))
                 + mini("FAIL", so_vn(run.n_check_fail), "xau" if run.n_check_fail else ""))
    t5 = the_kpi("Node dbt", f"{so_vn(run.dbt_n_ok)}/{so_vn(run.dbt_n_node)}",
                 mini("Đạt", so_vn(run.dbt_n_ok)) + mini("Lỗi", so_vn(run.dbt_n_fail), "xau" if run.dbt_n_fail else "")
                 + mini("Bỏ qua", so_vn(run.dbt_n_skipped)), "den")
    return [t1, t2, t3, t4, t5]


def _dong_dbt_xau(x) -> str:
    """1 node dbt lỗi / cảnh báo trong thẻ 'Test hoặc model lỗi, cảnh báo' (T3.8)."""
    ten = f'<span class="mono" title="{esc(x.node_name)}">{esc(ten_test_ngan(x.node_name))}</span>'
    if x.resource_type == "test" and pd.notna(x.failures):
        chi_tiet = f"{so_vn(x.failures)} dòng vi phạm, xem bảng {_rel_ngan(x.relation_name, 40)}"
    else:
        chi_tiet = esc(tom_tat_model(x.message))
    canh = " canh" if x.status == "warn" else ""
    return (f'<div class="mot_loi{canh}" title="{esc(x.message)}"><b>{esc(x.resource_type)}</b> {chip_dbt(x.status)} '
            f'{ten}<br>{chi_tiet}</div>')


def trang_chi_tiet(bay_gio: pd.Timestamp) -> None:
    ds = _ds_run()
    if ds.empty:
        st.markdown('<div class="hop_ghi">etl_log đang trống, chưa có lần chạy nào để xem. Chạy pipeline <b>full_load</b> trước.</div>',
                    unsafe_allow_html=True)
        return
    ids = ds.run_id.astype(int).tolist()
    rc = st.session_state.get("run_chon")
    if rc not in ids:
        if rc is not None:   # VD ?run_id=9999: báo rõ rồi mới về lần chạy gần nhất
            st.warning(f"Không tìm thấy lần chạy #{rc}. Đang hiện lần chạy gần nhất (#{ids[0]}).")
        st.session_state.run_chon = ids[0]
    nhan = {int(r.run_id): f"#{r.run_id}, batch {r.batch_id}, {r.triggered_by}, {r.status}, {gio(r.started_at)}"
            for r in ds.itertuples()}
    run_id = st.selectbox("Chọn lần chạy", ids, format_func=lambda v: nhan[v], key="run_chon")
    st.query_params["run_id"] = str(run_id)
    run, tl, qc, dbt = _chi_tiet(run_id)
    if run is None:
        st.warning(f"Không tìm thấy lần chạy #{run_id}.")
        return

    st.container(key="the_dau_run").markdown(_dau_lan_chay(run, tl, dbt, bay_gio), unsafe_allow_html=True)
    hang_kpi(_the_kpi_trang3(run))

    # thông báo cho lần chạy thiếu dữ liệu
    if run.status == "RUNNING":
        st.markdown('<div class="hop_ghi">Lần chạy đang diễn ra: bảng và kết quả dbt sẽ hiện dần khi từng bước xong '
                    '(bật “Tự làm mới 30 giây” ở thanh bên để theo dõi). Kết quả dbt chỉ được ghi một lần khi dbt build xong.</div>',
                    unsafe_allow_html=True)
    if tl.empty:
        st.markdown('<div class="hop_ghi" style="margin-top:8px">Chưa có bảng nào được ghi nhận nạp trong lần chạy này '
                    '(dừng ngay khi vừa bắt đầu hoặc lỗi trước bước nạp).</div>', unsafe_allow_html=True)
    if dbt.empty and run.status == "SUCCESS":
        st.markdown('<div class="hop_ghi" style="margin-top:8px">Lần chạy này không có kết quả dbt: chạy trước khi pipeline được nối với dbt '
                    '(BS-34) hoặc bước dbt bị bỏ qua.</div>', unsafe_allow_html=True)
    elif dbt.empty and run.status == "FAILED":
        st.markdown('<div class="hop_ghi" style="margin-top:8px">Lần chạy này không có kết quả dbt: pipeline dừng trước khi dbt chạy '
                    '(lỗi ở khâu nạp staging) hoặc dbt không chạy được; xem thông báo lỗi ở trên.</div>', unsafe_allow_html=True)

    tieu_de("Các bước", "Dòng thời gian từng bước")
    buoc = q.gantt_cac_buoc(run, tl, dbt, bay_gio)
    dang_dbt = run.status == "RUNNING" and run.phase == "dbt"   # dbt_result chỉ có khi dbt build xong
    def giay(x):
        return f"{so_vn(x, 1)} giây" if x is not None and pd.notna(x) else "–"
    muc = [("Mage", MAU_MAGE, "–" if dang_dbt else giay(run.mage_s)), ("Nạp staging", CHANH_BAR, giay(run.staging_s)),
           ("dbt khởi động", TIM_NHAT, giay(run.dbt_prep_s)),
           ("dbt build", TIM, f"đang chạy {thoi_luong(run.mage_s)}" if dang_dbt else giay(run.dbt_s)), ("Bước lỗi", DO)]
    if run.status == "RUNNING":
        muc.append(("Đang chạy", TIM_DAM))
    c = the_ve("gantt", "Các bước của lần chạy", "Thanh đỏ là bước bị lỗi; rê chuột vào thanh để xem thời gian.", chu_giai(muc))
    if buoc.empty:
        trong_dong(c, "Chưa có bước nào để vẽ.", ok=False)
    else:
        ve(c, _bieu_do_gantt(buoc), "bd_gantt")

    tieu_de("Bảng", "Nạp staging (table_load)")
    c = the_ve("table_load", "Kết quả nạp từng bảng")
    if tl.empty:
        trong_dong(c, "Không có dòng table_load.", ok=False)
    else:
        co_loi = (tl.status == "FAILED").any()
        if co_loi:
            c.markdown('<div class="hop_loi" style="margin:0 0 6px">Lần chạy này bị lỗi ở khâu nạp: cả batch đã được <b>hoàn tác (rollback)</b>. '
                       'Số thêm mới và cập nhật bên dưới là số đã xử lý trước khi lỗi, <b>không nằm trong staging</b>.</div>',
                       unsafe_allow_html=True)
        cot = [("Bảng", ""), ("Dòng đọc", "r"), ("Thêm mới", "r"), ("Cập nhật", "r"), ("Bị loại", "r"), ("Xóa mềm", "r"),
               ("Bắt đầu", ""), ("Xong", ""), ("Trạng thái", ""), ("Vào staging", "")] + ([("Lỗi", "")] if co_loi else [])
        hang = []
        for t in tl.itertuples():
            h = [(esc(t.table_name), ""), o_so(t.rows_source), o_so(t.rows_inserted), o_so(t.rows_updated), o_so(t.rows_rejected),
                 o_so(t.rows_deleted), (gio(t.started_at, False), ""), (gio(t.finished_at, False), ""), (chip(t.status), ""),
                 (_vao_staging(t.status), "")]
            if co_loi:
                e = t.error_message if pd.notna(t.error_message) else ""
                h.append((f'<span class="cat" style="max-width:200px;color:#B8382B" title="{esc(e)}">{esc(e)}</span>', ""))
            hang.append(h)
        c.markdown(bang_html(cot, hang), unsafe_allow_html=True)
    if qc.empty:
        c = the_ve("quality", "Kiểm tra chất lượng (quality_check)")
        trong_dong(c, "Lần chạy này không có phép kiểm tra chất lượng nào được ghi.", ok=False)
    else:
        c = the_ve("quality", "Kiểm tra chất lượng (quality_check)",
                   f"{so_vn(run.n_check)} phép kiểm tra: {so_vn(run.n_check_pass)} PASS, {so_vn(run.n_check_warn)} WARN, "
                   f"{so_vn(run.n_check_fail)} FAIL. Rê chuột vào ô để xem chi tiết.")
        c.markdown(_ma_tran_run(qc, tl), unsafe_allow_html=True)

    tieu_de("dbt", "Kết quả dbt build")
    if dbt.empty:
        trong_dong(st, "Chưa có kết quả dbt cho lần chạy này.", ok=False)
        return
    c1, c2 = st.columns([2, 3])
    with c1:
        c = the_ve("dbt_dem", "Số node theo loại và trạng thái")
        dem = dbt.groupby(["resource_type", "status"]).size().reset_index(name="so_node")
        c.markdown(bang_html([("Loại", ""), ("Trạng thái", ""), ("Số node", "r")],
                             [[(esc(r.resource_type), ""), (chip_dbt(r.status), ""), o_so(r.so_node)] for r in dem.itertuples()]),
                   unsafe_allow_html=True)
        xau = dbt[dbt.status.map(lambda s: s == "warn" or q.la_loi_dbt(s))]
        c = the_ve("dbt_test_loi", "Test hoặc model lỗi, cảnh báo", "Dòng vi phạm của test nằm trong bảng thuộc schema dq.")
        if xau.empty:
            trong(c, "Không có node nào lỗi hoặc cảnh báo.")
        else:
            c.markdown('<div class="ds_loi">' + "".join(_dong_dbt_xau(x) for x in xau.itertuples()) + "</div>",
                       unsafe_allow_html=True)
    with c2:
        c = the_ve("dbt_cham", "10 model và seed chạy lâu nhất")
        md = dbt[dbt.resource_type.isin(["model", "seed"])].sort_values("execution_time", ascending=False).head(10)
        hang = [[(esc(r.node_name), ""), (esc(r.resource_type), ""), o_so(r.execution_time, 2), o_so(r.rows_affected),
                 (f'<span class="mono" style="color:{CHU2}">{esc(r.relation_name)}</span>', "")] for r in md.itertuples()]
        c.markdown(bang_html([("Node", ""), ("Loại", ""), ("Giây", "r"), ("Số dòng", "r"), ("Bảng đích", "")], hang),
                   unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Khung chính
# ---------------------------------------------------------------------------
def _doc_url() -> None:
    """Lần đầu mở: ?run_id=99 -> thẳng trang chi tiết lần chạy đó."""
    if st.session_state.get("da_doc_url"):
        return
    st.session_state.da_doc_url = True
    r = st.query_params.get("run_id", "")
    if r.isdigit():
        st.session_state.run_chon = int(r)
        st.session_state.trang = 3


def _cuon_len_dau() -> None:
    """Đổi trang (nút thanh bên hoặc nút Xem chi tiết ở bảng 20 lần): cuộn khung nội dung về đầu trang.
    Script có số thứ tự riêng mỗi lần (nếu giống hệt lần trước thì Streamlit không nạp lại iframe nên không chạy)
    và cuộn lặp vài lần vì nội dung trang mới còn đang dựng nên chiều cao đổi."""
    if st.session_state.pop("cuon_len", False):
        st.session_state.cuon_so = st.session_state.get("cuon_so", 0) + 1
        components.html(
            f"<script>/* lần {st.session_state.cuon_so} */ const d = window.parent.document;"
            "const len = () => { for (const sel of ['[data-testid=\"stMain\"]', 'section.main', '.main']) {"
            " const e = d.querySelector(sel); if (e) e.scrollTo({top: 0}); } };"
            "len(); [100, 300, 700, 1500].forEach(t => setTimeout(len, t));</script>", height=0)


def _noi_dung(trang: int, bl: q.BoLoc) -> None:
    """Phần thay đổi theo dữ liệu - chạy lại riêng (st.fragment) mỗi 30 giây khi bật tự làm mới."""
    try:
        bay_gio = _gio_db()
        if trang != 3 and "run_id" in st.query_params:
            del st.query_params["run_id"]   # rời trang 3 thì bỏ run_id khỏi URL
        _thanh_tren(trang, bay_gio)
        if trang == 1:
            trang_tong_quan(bl, bay_gio)
        elif trang == 2:
            trang_chat_luong(bl, bay_gio)
        else:
            trang_chi_tiet(bay_gio)
        # gọi SAU nội dung: khung iframe cao 0 của lệnh cuộn vẫn chiếm 1 khoảng gap 16px; đặt trước thanh trên thì đẩy
        # thanh trên xuống, lệch khỏi nút mở thanh bên (nút này Streamlit đặt cố định ở góc trên trái)
        _cuon_len_dau()
    except psycopg.OperationalError:
        _bao_loi_ket_noi()
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
        st.error("Chưa tạo các view theo dõi ETL (hoặc bảng log thiếu cột). Chạy: "
                 "`docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/init/06_etl_monitor.sql` "
                 "(thiếu bảng dbt_result thì chạy `05_dbt_log.sql` trước).")


def _bao_loi_ket_noi() -> None:
    st.error("Không kết nối được Postgres. Mở Docker Desktop rồi chạy `docker compose up -d` ở thư mục repo "
             "(đợi vài giây cho container `olist-postgres` báo healthy), sau đó tải lại trang (F5).")


_css()
_doc_url()
st.session_state.setdefault("trang", 1)
try:
    lc = _lua_chon()
except psycopg.OperationalError:
    st.sidebar.markdown(LOGO_THANH_BEN, unsafe_allow_html=True)
    _bao_loi_ket_noi()
    st.stop()
except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
    st.error("Chưa tạo bảng log hoặc view theo dõi ETL. Chạy `sql/init/02_etl_log.sql` … `06_etl_monitor.sql` "
             "(xem monitor/README.md).")
    st.stop()
bo_loc = _thanh_ben(lc)
if st.session_state.get("tu_lam_moi"):
    st.fragment(_noi_dung, run_every=30)(st.session_state.trang, bo_loc)
else:
    _noi_dung(st.session_state.trang, bo_loc)
