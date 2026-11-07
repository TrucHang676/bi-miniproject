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


def cach_day(giay) -> str:
    if giay is None or pd.isna(giay):
        return "–"
    if giay < 5:
        return "vừa xong"
    if giay >= 86400:
        return f"{int(giay // 86400)} ngày {int(giay % 86400 // 3600)} giờ trước"
    return thoi_luong(giay) + " trước"


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


def chip(trang_thai: str) -> str:
    nen, chu = CHIP.get(trang_thai, (NHAT, CHU2))
    return f'<span class="chip" style="background:{nen};color:{chu}">{esc(trang_thai)}</span>'


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
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding-top: .4rem; }}
    .stApp button [data-testid="stMarkdownContainer"], .stApp button p {{ font-size: inherit !important; color: inherit; }}

    /* ---------- thanh bên ---------- */
    .sb_logo {{ display: flex; align-items: center; gap: 10px; font-size: 14.5px; font-weight: 700; color: {DEN}; margin: 0 0 14px 4px; }}
    .lg {{ width: 28px; height: 28px; border-radius: 9px; background: {CHANH}; display: flex; align-items: flex-end;
        justify-content: center; gap: 2px; padding-bottom: 7px; box-sizing: border-box; flex: none; }}
    .lg i {{ display: block; width: 3px; background: {DEN}; border-radius: 1px; }}
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
    .sb_ghi {{ font-size: 11px; line-height: 1.5; color: {XAM}; background: {TIM_NHAT}; border-radius: 12px; padding: 10px 12px;
        margin-top: 14px; }}

    /* ---------- thanh trên ---------- */
    .appbar {{ background: {THE}; border-radius: 16px;
        box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05), 0 -16px 0 16px {NEN};
        display: flex; align-items: center; justify-content: space-between; padding: 8px 10px 8px 14px; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-size: 15px; color: {DEN}; }}
    .brand b {{ font-weight: 700; }} .brand .sep {{ color: {XAM}; }} .brand .pg {{ font-weight: 600; }}
    .bar_r {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .pillc {{ height: 34px; border-radius: 999px; background: {NHAT}; display: inline-flex; align-items: center; gap: 8px;
        padding: 0 14px; font-size: 12.5px; color: {CHU2}; white-space: nowrap; }}
    .pillc b {{ color: {DEN}; font-weight: 600; }}
    .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
    .dot.bat {{ background: {XANH}; box-shadow: 0 0 0 3px rgba(29,94,18,.18); }} .dot.tat {{ background: #B6BAC2; }}

    /* ---------- thẻ KPI ---------- */
    .hang_kpi {{ display: grid; gap: 12px; margin-bottom: 12px; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); }}
    .kc {{ border-radius: 18px; padding: 13px 16px 11px; min-height: 112px; box-sizing: border-box; display: flex; flex-direction: column;
        justify-content: space-between; background: {THE}; color: {DEN}; box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05); }}
    .kc.chanh {{ background: {CHANH}; }} .kc.tim {{ background: {TIM}; }} .kc.den {{ background: {DEN}; color: #fff; }}
    .kc .lab {{ font-size: 12px; color: {XAM}; }}
    .kc.chanh .lab, .kc.tim .lab {{ color: {CHU2}; }} .kc.den .lab {{ color: rgba(255,255,255,.7); }}
    .kc .so {{ font-size: clamp(18px, 1.7vw, 24px); font-weight: 700; letter-spacing: -.015em; line-height: 1.25; margin: 2px 0;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .kc .so small {{ font-size: 12px; font-weight: 600; margin-left: 4px; color: {CHU2}; letter-spacing: 0; white-space: nowrap; }}
    .kc.den .so small {{ color: rgba(255,255,255,.8); }}
    .kc .ghi {{ font-size: 11.5px; font-weight: 600; line-height: 1.35; padding-top: 7px; border-top: 1px solid rgba(18,19,22,.10); color: {CHU2}; }}
    .kc.den .ghi {{ border-top-color: rgba(255,255,255,.14); color: rgba(255,255,255,.85); }}
    .kc .ghi.tot {{ color: {XANH}; }} .kc .ghi.xau {{ color: #D9483B; }} .kc.den .ghi.xau {{ color: #FF9B8F; }}
    .kc .so.xau {{ color: #D9483B; }} .kc .so.tot {{ color: {XANH}; }}

    /* ---------- thẻ biểu đồ ---------- */
    [class*="st-key-the_"] {{ background: {THE}; border-radius: 20px; padding: 14px 16px 10px;
        box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05); }}
    .tt {{ font-size: 13.5px; font-weight: 600; color: {DEN}; margin: 0 0 2px; }}
    .tp {{ font-size: 11.5px; color: {XAM}; margin: 0 0 6px; line-height: 1.4; }}
    .nhom_hd {{ display: flex; align-items: center; gap: 10px; margin: 14px 0 8px; }}
    .nhom_hd .tag {{ font-size: 11px; font-weight: 700; background: {CHANH}; color: {DEN}; border-radius: 999px; padding: 0 10px; line-height: 20px; }}
    .nhom_hd h3 {{ margin: 0; font-size: 15px; font-weight: 600; color: {DEN}; padding: 0; }}

    /* ---------- cảnh báo ---------- */
    .cb {{ display: flex; gap: 10px; align-items: flex-start; border-radius: 14px; padding: 10px 14px; margin-bottom: 8px;
        font-size: 12.5px; line-height: 1.5; }}
    .cb.do {{ background: #FDE3E0; color: #8E2A20; }} .cb.vang {{ background: #FDF1CC; color: #7A5600; }}
    .cb.ok {{ background: #EAF7B2; color: {XANH}; }}
    .cb b {{ white-space: nowrap; }}

    /* ---------- chip, lưới batch ---------- */
    .chip {{ display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 11px; font-weight: 700; letter-spacing: .02em; }}
    .luoi_batch {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; padding-bottom: 16px; }}
    .o_batch {{ border-radius: 14px; padding: 7px 11px; min-height: 64px; box-sizing: border-box; display: flex; flex-direction: column;
        justify-content: space-between; border: 1.5px solid transparent; }}
    .o_batch .b {{ font-size: 13px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; gap: 4px; flex-wrap: wrap; }}
    .o_batch .m {{ font-size: 10.5px; line-height: 1.4; color: {CHU2}; }}
    .o_batch.SUCCESS {{ background: #F3FBC9; border-color: {CHANH_BAR}; }}
    .o_batch.FAILED {{ background: #FDE3E0; border-color: {DO}; }}
    .o_batch.RUNNING {{ background: #E4E8FD; border-color: {TIM_DAM}; }}
    .o_batch.PENDING {{ background: {NHAT}; border-color: {KE}; color: {XAM}; }}
    .o_batch.PENDING .b {{ color: {XAM}; }}

    /* ---------- trang chi tiết ---------- */
    .dau_run {{ padding-bottom: 4px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px 18px; }}
    .dau_run .k {{ font-size: 10.5px; color: {XAM}; text-transform: uppercase; letter-spacing: .06em; }}
    .dau_run .v {{ font-size: 14px; font-weight: 600; color: {DEN}; margin-top: 2px; word-break: break-word; }}
    .hop_loi {{ background: #FDE3E0; color: #8E2A20; border-radius: 12px; padding: 10px 14px; font-size: 12.5px; line-height: 1.55;
        margin-top: 10px; word-break: break-word; }}
    .hop_ghi {{ background: {NHAT}; color: {CHU2}; border-radius: 12px; padding: 10px 14px; font-size: 12.5px; line-height: 1.55; }}
    [data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
    [class*="st-key-the_dau_run"] {{ padding: 16px; }}
    /* Streamlit đặt margin-bottom: -16px cho mọi khối markdown (để bù lề dưới của thẻ <p>). Khung thông báo tự vẽ
       không có <p> nên bị bù sai: khung tràn khỏi đáy thẻ trắng hoặc dính sát mép dưới. Trả lề về 0 cho các khối này. */
    [data-testid="stMarkdownContainer"]:has(> .hop_ghi), [data-testid="stMarkdownContainer"]:has(> .hop_loi),
    [data-testid="stMarkdownContainer"]:has(> .cb), [data-testid="stMarkdownContainer"]:has(> .dau_run) {{ margin-bottom: 0; }}
    /* khung thông báo là phần tử cuối của thẻ trắng: lề dưới bằng lề hai bên (thẻ có padding dưới 10px, hai bên 16px) */
    [class*="st-key-the_"] .hop_ghi:last-child, [class*="st-key-the_"] .hop_loi:last-child {{ margin-bottom: 6px; }}
    [class*="st-key-the_dau_run"] .hop_loi:last-child {{ margin-bottom: 0; }}
    /* ---------- bảng 20 lần chạy (hàng st.columns + nút Xem chi tiết) ---------- */
    .st-key-bang_run {{ background: {THE}; border-radius: 20px; padding: 6px 14px 8px; gap: 0 !important; overflow-x: auto;
        box-shadow: 0 1px 2px rgba(18,19,22,.03), 0 8px 24px rgba(18,19,22,.05); }}
    /* bảng hẹp hơn ~900px thì cột bị ép cắt chữ -> giữ độ rộng tối thiểu, màn hình hẹp thì cuộn ngang trong thẻ
       (màn hình 1280px có thanh bên: bảng rộng ~900px, vừa khít) */
    .st-key-bang_run > * {{ min-width: 900px; }}
    /* cột 11 (Lỗi, căn trái) đứng sau cột số căn phải (Test lỗi) -> đệm trái để chữ không dính số */
    .st-key-bang_run [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(11) {{ padding-left: 14px; }}
    [data-testid="stMain"] .st-key-bang_run [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 8px;
        padding: 6px 6px; border-bottom: 1px solid {KE}; min-height: 44px; }}
    [data-testid="stMain"] .st-key-bang_run [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
        min-width: 0 !important; overflow: hidden; }}
    .st-key-bang_run [data-testid="stHorizontalBlock"]:hover {{ background: {NHAT}; border-radius: 10px; }}
    .st-key-bang_run [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; }}
    .o_bang {{ font-size: 12.5px; color: {DEN}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.4; }}
    .o_bang.phai {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .o_bang.giua {{ text-align: center; }}
    /* tiêu đề cột: thiếu chỗ thì xuống dòng thay vì cắt "…" (font mỗi máy rộng hẹp khác nhau một chút) */
    .o_bang.tieu {{ font-size: 12px; color: {XAM}; font-weight: 500; cursor: default; white-space: normal;
        overflow: visible; line-height: 1.25; overflow-wrap: normal; word-break: keep-all; }}
    .o_bang.loi {{ color: #8E2A20; font-size: 12.5px; cursor: help; }}
    .o_bang .chip {{ font-size: 10.5px; padding: 2px 8px; }}
    [class*="st-key-xem_"] button {{ min-height: 30px; height: 30px; padding: 0 12px; border-radius: 999px; border: none;
        background: {NHAT}; color: {DEN}; font-size: 12px; font-weight: 600; white-space: nowrap; width: 100%; }}
    [class*="st-key-xem_"] button:hover {{ background: {CHANH}; color: {DEN}; }}
    [class*="st-key-xem_"] button p {{ white-space: nowrap; }}
    /* màn hình hẹp (<= 1000px): các cặp thẻ đặt cạnh nhau xếp thành 1 cột cho bảng / biểu đồ đủ rộng */
    @media (max-width: 1000px) {{
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width: 100% !important; }}
    }}
    </style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Thành phần giao diện dùng chung
# ---------------------------------------------------------------------------
def the_kpi(ten: str, so: str, ghi: str, kieu: str = "trang", don_vi: str = "", mau_so: str = "", mau_ghi: str = "") -> str:
    dv = f"<small>{esc(don_vi)}</small>" if don_vi else ""
    return (f'<div class="kc {kieu}"><div class="lab">{esc(ten)}</div>'
            f'<div class="so {mau_so}">{so}{dv}</div><div class="ghi {mau_ghi}">{ghi}</div></div>')


def hang_kpi(cac_the: list[str]) -> None:
    st.markdown('<div class="hang_kpi">' + "".join(cac_the) + "</div>", unsafe_allow_html=True)


def tieu_de(ma: str, noi_dung: str) -> None:
    st.markdown(f'<div class="nhom_hd"><span class="tag">{esc(ma)}</span><h3>{esc(noi_dung)}</h3></div>', unsafe_allow_html=True)


def the_ve(key: str, tieu: str, phu: str = ""):
    """Mở một thẻ trắng (container) có tiêu đề; trả về container để vẽ vào."""
    c = st.container(key=f"the_{key}")
    c.markdown(f'<div class="tt">{esc(tieu)}</div>' + (f'<div class="tp">{phu}</div>' if phu else ""), unsafe_allow_html=True)
    return c


def khung_plotly(fig: go.Figure, cao: int = 300, **tuy_chon) -> go.Figure:
    fig.update_layout(height=cao, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)", separators=",.",
                      font=dict(family="Segoe UI, Arial, sans-serif", size=11, color=CHU2),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(size=11),
                                  bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor=DEN, font=dict(color="#fff", size=12)), **{"plot_bgcolor": "rgba(0,0,0,0)", **tuy_chon})
    fig.update_xaxes(gridcolor=LUOI, linecolor=KE, zeroline=False, tickfont=dict(color=XAM))
    fig.update_yaxes(gridcolor=LUOI, linecolor=KE, zeroline=False, tickfont=dict(color=XAM))
    return fig


def ve(c, fig: go.Figure, key: str) -> None:
    c.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def trong(c, thong_bao: str) -> None:
    c.markdown(f'<div class="hop_ghi">{esc(thong_bao)}</div>', unsafe_allow_html=True)


def to_mau_trang_thai(v, dbt: bool = False):
    nen, chu = CHIP.get(v, (None, None))
    if nen is None and dbt and q.la_loi_dbt(str(v).lower()):
        nen, chu = CHIP["FAILED"]   # trạng thái dbt lạ = lỗi
    return f"background-color:{nen};color:{chu};font-weight:700;text-align:center" if nen else ""


def style_bang(df: pd.DataFrame, cot_tt: list[str], dbt: bool = False):
    """Tô màu chip cho các cột trạng thái (dbt=True: trạng thái dbt lạ tô như lỗi).
    pandas >=2.1 dùng Styler.map, bản cũ dùng applymap."""
    s = df.style
    ap = s.map if hasattr(s, "map") else s.applymap
    return ap(lambda v: to_mau_trang_thai(v, dbt), subset=cot_tt) if cot_tt else s


def mau_thanh(bang: pd.DataFrame, cot: str = "status") -> list[str]:
    return [MAU_TT.get(s, "#D5D8DE") for s in bang[cot]]


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
                f'<span class="pillc"><span class="dot bat"></span>Lịch <b>{esc(t["ten"])}</b> đang bật · '
                f'<code style="background:none;padding:0">{esc(t["cron"])}</code></span>' for t in dang_bat)
        else:
            pill_lich = '<span class="pillc"><span class="dot tat"></span>Lịch: <b>tắt</b> (chỉ chạy tay)</span>'
    st.markdown(
        f'<div class="appbar"><div class="brand"><span class="lg"><i style="height:6px"></i><i style="height:10px"></i>'
        f'<i style="height:14px"></i></span><b>Olist BI</b><span class="sep">·</span><span>Theo dõi ETL</span>'
        f'<span class="sep">/</span><span class="pg">{esc(TEN_TRANG[trang])}</span></div>'
        f'<div class="bar_r">{pill_lich}<span class="pillc">Cập nhật lúc <b>{bay_gio.strftime("%H:%M:%S")}</b> '
        f'· {bay_gio.strftime("%d/%m/%Y")}</span></div></div>', unsafe_allow_html=True)


def _doi_trang(t: int) -> None:
    st.session_state.trang = t
    st.session_state.cuon_len = True   # đổi trang thì cuộn lên đầu trang (C12)


def _dat_lai() -> None:
    st.session_state.f_luot = -1
    for k in ("f_pipeline", "f_kich_hoat", "f_trang_thai"):
        st.session_state[k] = TAT_CA
    st.session_state.f_ngay = ()


def _thanh_ben(lc: dict) -> q.BoLoc:
    sb = st.sidebar
    sb.markdown('<div class="sb_logo"><span class="lg"><i style="height:6px"></i><i style="height:10px"></i>'
                '<i style="height:14px"></i></span>Olist BI · Theo dõi ETL</div>', unsafe_allow_html=True)
    sb.markdown('<div class="sb_muc">Trang</div>', unsafe_allow_html=True)
    for t, ten, icon in zip((1, 2, 3), ("Tổng quan vận hành", "Chất lượng dữ liệu", "Chi tiết một lần chạy"),
                            (":material/monitor_heart:", ":material/fact_check:", ":material/manage_search:")):
        sb.button(ten, icon=icon, key=f"nut_trang_{t}", width="stretch",
                  type="primary" if st.session_state.trang == t else "secondary", on_click=_doi_trang, args=(t,))

    sb.markdown('<div class="sb_muc">Bộ lọc</div>', unsafe_allow_html=True)
    luot_df = lc["luot"]
    moi_nhat = int(luot_df.cycle_no.max()) if len(luot_df) else None
    mo_ta = {int(r.cycle_no): (f"Lượt {int(r.cycle_no)} · từ {pd.Timestamp(r.bat_dau):%d/%m %H:%M} · {int(r.so_lan)} lần"
                               if r.cycle_no > 0 else f"Trước Full Load đầu tiên · {int(r.so_lan)} lần")
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
    sb.markdown('<div class="sb_ghi">Lần chạy theo lịch khi đã nạp hết batch <b>không</b> ghi vào etl_log '
                '(decisions.md 05/11/2026) nên không xuất hiện ở đây. Giờ hiển thị là giờ Việt Nam.</div>',
                unsafe_allow_html=True)
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


def _nhan_truc(d0: pd.Timestamp, d1: pd.Timestamp, nghi: list, muc_tieu: int = 5) -> tuple[list, list]:
    """Nhãn trục tự tính khi có cắt khoảng nghỉ: mỗi đoạn nhìn thấy có ít nhất 1 nhãn, số nhãn tỉ lệ với độ dài đoạn.
    Trả về (tickvals, ticktext); ticktext kiểu VN 'HH:MM', kèm dòng 'dd/mm/yyyy' ở nhãn đầu và mỗi khi sang ngày khác
    (nhãn ngắn nên không chồng nhau); không có 2 nhãn trùng giờ trùng ngày."""
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
            texts.append(t.strftime("%H:%M") + (f"<br>{ngay}" if ngay != ngay_truoc else ""))
            ngay_truoc = ngay
    return vals, texts


def _bieu_do_dong_thoi_gian(df: pd.DataFrame, batches: list[str]):
    """(a) mỗi lần chạy = 1 thanh nằm đúng lúc chạy, hàng = batch; chấm tròn = chạy tay, thoi = theo lịch.
    Khoảng nghỉ dài giữa các đợt chạy bị cắt khỏi trục (rangebreaks); chỗ cắt có vạch đứt kèm chú thích 'nghỉ 4 giờ'."""
    fig = go.Figure()
    bay_gio = _gio_db()
    ket_thuc = df.finished_at.fillna(bay_gio)
    nghi = _khoang_nghi(df, bay_gio)
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
            name=tt, marker=dict(color=MAU_TT[tt], line=dict(width=0)), width=0.55,
            customdata=list(zip(d.run_id, d.pipeline_name, d.triggered_by, [thoi_luong(v) for v in thoi_gian[d.index]],
                                [rut_gon(e, 80) for e in d.error_message.fillna("")])),
            hovertemplate="<b>#%{customdata[0]} · %{y}</b><br>%{customdata[1]} · %{customdata[2]}<br>"
                          "Chạy %{customdata[3]}<br>%{customdata[4]}<extra>" + tt + "</extra>"))
    for kich, ky_hieu, ten in (("manual", "circle", "Chạy tay"), ("schedule", "diamond", "Theo lịch")):
        d = df[df.triggered_by == kich]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            y=d.batch_id, x=d.started_at, mode="markers", name=ten,
            marker=dict(symbol=ky_hieu, size=9, color=DEN, line=dict(color="#fff", width=1.5)),
            hoverinfo="skip"))
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=batches, autorange="reversed", title=None)
    cau_hinh = dict(type="date", title=None, tickformat="%H:%M<br>%d/%m/%Y")
    if nghi:
        vals, texts = _nhan_truc(df.started_at.min(), ket_thuc.max(), nghi)
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
    return khung_plotly(fig, 350)


def _bieu_do_thoi_gian_tung_lan(df: pd.DataFrame):
    """(b) mỗi lần chạy 1 cột chồng: nạp staging / dbt khởi động / dbt build / Mage (đang chạy tính tới bây giờ)."""
    d = df.tail(40).copy()
    stg, prep, dbt, mage = (d.staging_s.fillna(0), d.dbt_prep_s.fillna(0), d.dbt_s.fillna(0), d.mage_s.fillna(0))
    # đang ở khâu dbt (chưa có kết quả dbt): phần "còn lại" thực ra là dbt đang chạy
    dang_dbt = (d.status == "RUNNING") & (d.phase == "dbt")
    dbt = dbt.where(~dang_dbt, mage)
    mage = mage.where(~dang_dbt, 0)
    tong = stg + prep + dbt + mage
    nhan = [f"#{r}" for r in d.run_id]
    fig = go.Figure()
    for ten, gt, mau in (("Nạp staging", stg, CHANH_BAR), ("dbt khởi động / parse", prep, TIM_NHAT), ("dbt build", dbt, TIM),
                         ("Mage (khởi động block, ghi log)", mage, "#D5D8DE")):
        fig.add_trace(go.Bar(x=nhan, y=gt, name=ten, marker_color=mau, hovertemplate="%{x} · " + ten + ": %{y:.1f} giây<extra></extra>"))
    cao_nhat = max(float(tong.max()), 1.0)
    loi = d[d.status == "FAILED"]
    if len(loi):
        fig.add_trace(go.Scatter(x=[f"#{r}" for r in loi.run_id], y=(tong[loi.index] + cao_nhat * 0.06), mode="markers",
                                 name="FAILED", marker=dict(symbol="x", size=9, color=DO, line=dict(width=2)), hoverinfo="skip"))
    dang = d[d.status == "RUNNING"]
    if len(dang):
        fig.add_trace(go.Scatter(x=[f"#{r}" for r in dang.run_id], y=(tong[dang.index] + cao_nhat * 0.06), mode="markers",
                                 name="RUNNING", marker=dict(symbol="circle-open", size=10, color=TIM_DAM, line=dict(width=2)),
                                 hoverinfo="skip"))
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(type="category", title=None)
    fig.update_yaxes(title="giây")
    return khung_plotly(fig, 330)


def _bieu_do_so_dong(theo_batch: pd.DataFrame):
    """(c) INSERT / UPDATE đã commit theo batch (cột chồng) + số dòng bị loại vào dq (nhãn đỏ ngay trên cột). Full Load vẽ riêng ngoài."""
    d = theo_batch[theo_batch.batch_id != q.FULL_BATCH]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=d.batch_id, y=d.rows_inserted, name="INSERT (thêm mới)", marker_color=CHANH_BAR,
                         hovertemplate="%{x} · INSERT: %{y:,}<extra></extra>"))
    fig.add_trace(go.Bar(x=d.batch_id, y=d.rows_updated, name="UPDATE (cập nhật)", marker_color=TIM,
                         hovertemplate="%{x} · UPDATE: %{y:,}<extra></extra>"))
    cao = float((d.rows_inserted + d.rows_updated).max()) if len(d) else 0.0
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Số dòng bị loại vào dq (chữ đỏ trên cột)",
                             marker=dict(color=DO, symbol="square", size=9), hoverinfo="skip"))
    for r in d[d.rows_rejected > 0].itertuples():
        fig.add_annotation(x=r.batch_id, y=float(r.rows_inserted + r.rows_updated), yshift=12, showarrow=False,
                           text=f"{so_vn(r.rows_rejected)} bị loại", font=dict(color=DO, size=11))
    fig.update_layout(barmode="stack", bargap=0.3, yaxis=dict(title="số dòng", tickformat=",", range=[0, max(cao * 1.15, 1)]))
    fig.update_xaxes(type="category", title=None)
    return khung_plotly(fig, 330)


def _luoi_batch(tien_do: pd.DataFrame) -> str:
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
        dong2 = ("chưa nạp" if tt == "PENDING" else
                 f"xong {gio(r.xong_luc, False)}" if tt == "SUCCESS" else
                 "đang chạy…" if tt == "RUNNING" else "lần cuối bị lỗi")
        thu = (f"{r.so_lan_thu} lần thử" + (f" · {r.so_lan_failed} lỗi" if r.so_lan_failed else "")) if r.so_lan_thu else "–"
        o.append(f'<div class="o_batch {tt}"><div class="b"><span>{esc(r.batch_id)}</span>{chip(tt)}</div>'
                 f'<div class="m">{dong2}<br>{thu}</div></div>')
    return '<div class="luoi_batch">' + "".join(o) + "</div>"


def trang_tong_quan(bl: q.BoLoc, bay_gio: pd.Timestamp) -> None:
    df = _lan_chay(bl)
    tien_do = _tien_do(bl.luot)
    _hien_canh_bao(bl, bay_gio)
    if df.empty:
        st.markdown('<div class="hop_ghi">Không có lần chạy nào khớp bộ lọc (hoặc <b>etl_log</b> còn trống). '
                    'Hãy nới bộ lọc ở thanh bên hoặc chạy pipeline <b>full_load</b> trước.</div>', unsafe_allow_html=True)
    k = q.kpi_trang1(df, tien_do, bay_gio)
    gn = k["gan_nhat"]
    # thẻ 1: số lần chạy
    t1 = the_kpi("Số lần chạy", so_vn(k["so_lan"]),
                 f'{so_vn(k["so_manual"])} chạy tay · {so_vn(k["so_schedule"])} theo lịch', "chanh")
    # thẻ 2: tỉ lệ thành công
    t2 = the_kpi("Tỉ lệ thành công", phan_tram(k["ti_le_thanh_cong"]),
                 f'{so_vn(k["so_success"])} SUCCESS · {so_vn(k["so_failed"])} FAILED' +
                 (f' · {so_vn(k["so_running"])} đang chạy' if k["so_running"] else ""), "tim")
    # thẻ 3: lần chạy gần nhất
    if gn:
        mau3 = "xau" if gn["status"] == "FAILED" else ""
        t3 = the_kpi("Lần chạy gần nhất", esc(gn["status"]),
                     f'#{gn["run_id"]} · batch {esc(gn["batch_id"])} · {esc(gn["triggered_by"])} · {esc(cach_day(gn["giay_truoc"]))}',
                     "trang", mau_so=mau3)
    else:
        t3 = the_kpi("Lần chạy gần nhất", "–", "chưa có lần chạy nào", "trang")
    # thẻ 4: tiến độ batch ("đã nạp hết" dựa vào batch cuối 2018-09+ đã nạp, không dựa vào cet)
    if k["da_het"]:
        lset = "đã nạp hết batch"
    elif k["lset"] is not None and pd.notna(k["lset"]):
        lset = f'LSET hiện tại: {pd.Timestamp(k["lset"]):%d/%m/%Y}'
    else:
        lset = "chưa nạp batch nào" if not k["batch_da_nap"] else "LSET: –"
    t4 = the_kpi("Tiến độ batch", f'{k["batch_da_nap"]}/{k["batch_tong"]}', esc(lset), "trang", don_vi="batch")
    # thẻ 5: thời gian trung bình (chỉ các lần SUCCESS), tách từng đoạn
    if k["tb_giay"] is not None:
        def g(x):
            return so_vn(x, 1) if x is not None else "–"
        t5 = the_kpi("Thời gian chạy TB", so_vn(k["tb_giay"], 1),
                     f'staging {g(k["tb_staging"])} · dbt khởi động {g(k["tb_dbt_prep"])} · dbt {g(k["tb_dbt"])} · Mage {g(k["tb_mage"])} giây',
                     "den", don_vi="giây")
    else:
        t5 = the_kpi("Thời gian chạy TB", "–", "chưa có lần SUCCESS", "den")
    hang_kpi([t1, t2, t3, t4, t5])

    if df.empty:
        return
    batches = tien_do.batch_id.tolist()
    c1, c2 = st.columns([3, 2])
    with c1:
        phu_a = "Mỗi thanh là một lần chạy (dài = thời gian chạy). Chấm tròn: chạy tay · thoi: theo lịch. Cùng một hàng bị lỗi nhiều lần = chạy lại cùng batch."
        if _khoang_nghi(df, bay_gio):
            phu_a += f" Trục thời gian đã bỏ các khoảng nghỉ dài hơn {NGUONG_NGHI_PHUT} phút giữa các đợt chạy."
        c = the_ve("dong_thoi_gian", "Các lần chạy theo thời gian", phu_a)
        ve(c, _bieu_do_dong_thoi_gian(df, batches), "bd_dong_thoi_gian")
    with c2:
        c = the_ve("thoi_gian_lan", "Thời gian chạy từng lần", "Cột chồng: nạp staging · dbt khởi động · dbt build · Mage. Dấu ✕ = FAILED.")
        ve(c, _bieu_do_thoi_gian_tung_lan(df), "bd_thoi_gian_lan")
    c3, c4 = st.columns([3, 2])
    theo_batch = _so_dong_batch(bl)
    with c3:
        phu_c = "INSERT / UPDATE đã commit vào staging của 5 bảng giao dịch (cột); lần FAILED bị hoàn tác tính 0. Chữ đỏ = số dòng bị loại vào dq."
        if bl.luot is None:
            phu_c += " Đang chọn “Tất cả” lượt nạp nên mỗi cột là tổng của nhiều lượt."
        c = the_ve("so_dong", "Số dòng nạp theo batch", phu_c)
        co_incr = len(theo_batch) and (theo_batch.batch_id != q.FULL_BATCH).any()
        if co_incr:
            ve(c, _bieu_do_so_dong(theo_batch), "bd_so_dong")
        else:
            trong(c, "Chưa có batch Incremental nào trong bộ lọc này.")
        full = theo_batch[theo_batch.batch_id == q.FULL_BATCH]
        if len(full) and full.rows_inserted.sum() > 0:
            c.caption(f"Batch {q.FULL_BATCH} nạp {so_vn(full.rows_inserted.sum())} dòng INSERT"
                      + (", không vẽ để các batch còn lại nhìn rõ." if co_incr else "."))
    with c4:
        c = the_ve("luoi_batch", "Tiến độ 10 batch", "Của lượt nạp đang chọn (không phụ thuộc bộ lọc trạng thái / kích hoạt).")
        c.markdown(_luoi_batch(tien_do), unsafe_allow_html=True)

    tieu_de("20 lần gần nhất", "Danh sách lần chạy")
    _bang_lan_chay(df.sort_values("run_id", ascending=False).head(20).reset_index(drop=True))


# Bảng 20 lần chạy dựng bằng hàng st.columns (không dùng st.dataframe) để mỗi dòng có nút "Xem chi tiết" thật:
# bấm là sang trang 3 trong cùng phiên (giữ bộ lọc), ô Lỗi dài thì "…" và rê chuột vào thấy đủ (thuộc tính title).
# (tiêu đề cột, tỉ lệ độ rộng, căn phải, chú thích khi rê chuột vào tiêu đề)
COT_BANG_RUN = [
    ("Run", .5, False, ""), ("Pipeline", 1.15, False, "Tên pipeline bỏ đuôi _load: full / incremental"),
    ("Batch", .9, False, ""), ("Kích hoạt", .9, False, ""), ("Trạng thái", 1.2, False, ""),
    ("Bắt đầu", 1.4, False, ""), ("Thời lượng", 1.35, False, ""),
    ("Dòng nạp", 1.0, True, "INSERT + UPDATE ĐÃ COMMIT vào staging (lần FAILED bị hoàn tác tính 0)"),
    ("WARN", .7, True, "Số phép kiểm tra chất lượng WARN"), ("Test lỗi", .75, True, "Số dbt test fail / error"),
    ("Lỗi", 2.1, False, "Rê chuột vào ô lỗi để xem đầy đủ; trang chi tiết có thông báo lỗi nguyên văn"), ("", 1.35, False, "")]


def _xem_chi_tiet(run_id: int) -> None:
    st.session_state.run_chon = run_id
    st.session_state.trang = 3
    st.session_state.cuon_len = True   # sang trang 3 thì cuộn lên đầu trang


def _bang_lan_chay(g: pd.DataFrame) -> None:
    khung = st.container(key="bang_run")
    rong = [c[1] for c in COT_BANG_RUN]
    for cot, (ten, _, phai, goi_y) in zip(khung.columns(rong, gap="small", vertical_alignment="center"), COT_BANG_RUN):
        can = " phai" if phai else (" giua" if ten == "Lỗi" else "")   # cột Lỗi rộng nhất: tiêu đề căn giữa cho cân
        cot.markdown(f'<div class="o_bang tieu{can}" title="{esc(goi_y)}">{esc(ten)}</div>',
                     unsafe_allow_html=True)
    for r in g.itertuples():
        loi = " ".join(str(r.error_message).split()) if pd.notna(r.error_message) else ""
        dang_chay = pd.isna(r.duration_s)
        o = [(str(r.run_id), ""), (esc(str(r.pipeline_name).replace("_load", "")), ""), (esc(r.batch_id), ""),
             (esc(r.triggered_by), ""), (chip(r.status), ""), (pd.Timestamp(r.started_at).strftime("%d/%m %H:%M:%S"), ""),
             (thoi_luong(r.elapsed_s if dang_chay else r.duration_s) + ("…" if dang_chay else ""), ""),
             (so_vn(r.rows_inserted + r.rows_updated), "phai"), (so_vn(r.n_check_warn), "phai"),
             (so_vn(r.dbt_test_fail), "phai")]
        hang = khung.columns(rong, gap="small", vertical_alignment="center")
        for cot, (noi_dung, lop) in zip(hang, o):
            cot.markdown(f'<div class="o_bang {lop}">{noi_dung}</div>', unsafe_allow_html=True)
        hang[-2].markdown(f'<div class="o_bang loi" title="{esc(loi)}">{esc(loi)}</div>', unsafe_allow_html=True)
        # không dùng on_click: khi bật "Tự làm mới" trang nằm trong st.fragment, callback chỉ chạy lại fragment (vẫn
        # trang cũ) -> bấm xong gọi st.rerun() để chạy lại cả app với trang mới
        if hang[-1].button("Xem chi tiết", key=f"xem_{r.run_id}"):
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
                zz.append(None); tt.append(""); hh.append(f"{b} · {TEN_CHECK[c][1]}<br>không có dữ liệu")
            else:
                zz.append(ma[r.status])
                # WARN / FAIL chỉ kèm số dòng khi có dòng vi phạm (VD row_count_match WARN không có dòng nào bị loại)
                tt.append(r.status if r.status == "PASS" or not r.failed_rows else f"{r.status} · {so_vn(r.failed_rows)}")
                hh.append(f"{b} · {TEN_CHECK[c][1]}<br>{r.status}, {so_vn(r.failed_rows)} dòng vi phạm, {r.so_phep} phép đã chạy"
                          + (f"<br>bảng: {r.bang_loi}" if r.bang_loi else ""))
        z.append(zz); text.append(tt); hover.append(hh)
    fig = go.Figure(go.Heatmap(
        z=z, x=[TEN_CHECK[c][1] for c in cot], y=hang, text=text, texttemplate="%{text}", hovertext=hover,
        hovertemplate="%{hovertext}<extra></extra>", xgap=3, ygap=3, showscale=False, zmin=0, zmax=2,
        colorscale=[[0, "#DDF08A"], [0.333, "#DDF08A"], [0.334, VANG], [0.666, VANG], [0.667, DO], [1, DO]],
        textfont=dict(size=11, color=DEN)))
    fig.update_yaxes(autorange="reversed", type="category")
    fig.update_xaxes(side="top", type="category", tickangle=0, tickfont=dict(size=11, color=CHU2))
    return khung_plotly(fig, max(260, 36 * len(hang) + 90), plot_bgcolor=NHAT)


def _bieu_do_dbt_theo_lan(df: pd.DataFrame):
    d = df[df.dbt_n_node > 0].tail(40)
    nhan = [f"#{r}" for r in d.run_id]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=nhan, y=d.dbt_test_fail, name="Test FAIL / ERROR", marker_color=DO,
                         hovertemplate="%{x} · fail: %{y}<extra></extra>"))
    fig.add_trace(go.Bar(x=nhan, y=d.dbt_test_warn, name="Test WARN", marker_color=VANG,
                         hovertemplate="%{x} · warn: %{y}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.3)
    fig.update_xaxes(type="category", title=None)
    fig.update_yaxes(title="số test", dtick=1, rangemode="tozero")
    return khung_plotly(fig, 280)


def trang_chat_luong(bl: q.BoLoc, bay_gio: pd.Timestamp) -> None:
    df = _lan_chay(bl)
    if df.empty:
        st.markdown('<div class="hop_ghi">Không có lần chạy nào khớp bộ lọc (hoặc <b>etl_log</b> còn trống). Nới bộ lọc ở thanh bên.</div>',
                    unsafe_allow_html=True)
        hang_kpi([the_kpi("Phép kiểm tra WARN / FAIL", "–", "chưa có dữ liệu", "chanh"),
                  the_kpi("Dòng bị loại vào dq", "–", "chưa có dữ liệu", "tim"),
                  the_kpi("dbt test không đạt", "–", "chưa có dữ liệu", "trang"),
                  the_kpi("Lần FAILED do dbt", "–", "chưa có dữ liệu", "trang"),
                  the_kpi("Lần FAILED do nạp staging", "–", "chưa có dữ liệu", "den")])
        return
    k = q.kpi_trang2(df)
    n_loi = k["check_warn"] + k["check_fail"]
    hang_kpi([
        the_kpi("Phép kiểm tra WARN / FAIL", so_vn(n_loi), f'{so_vn(k["check_warn"])} WARN · {so_vn(k["check_fail"])} FAIL (Mage)', "chanh"),
        the_kpi("Dòng bị loại vào dq", so_vn(k["dong_loai"]), "không nạp được vào staging, nội dung nằm ở dq.rejected_rows", "tim"),
        the_kpi("dbt test không đạt", so_vn(k["dbt_test_fail"]), f'{so_vn(k["dbt_test_warn"])} test WARN thêm', "trang",
                mau_so="xau" if k["dbt_test_fail"] else ""),
        the_kpi("Lần FAILED do dbt", so_vn(k["failed_dbt"]), "dbt build báo lỗi sau khi staging đã nạp xong", "trang",
                mau_so="xau" if k["failed_dbt"] else ""),
        the_kpi("Lần FAILED do nạp staging", so_vn(k["failed_staging"]),
                f'file thiếu cột, sai batch… · bị ngắt / khác: {so_vn(k["failed_khac"])}', "den")])
    batches = _tien_do(bl.luot).batch_id.tolist()

    tieu_de("Mage", "Kiểm tra chất lượng khi nạp staging")
    c = the_ve("ma_tran", "Batch × phép kiểm tra",
               "Màu = kết quả tệ nhất trong các lần chạy đã lọc: xanh PASS · vàng WARN (loại dòng, vẫn nạp) · đỏ FAIL (dừng cả batch). Ô xám: chưa có dữ liệu.")
    mt = _ma_tran(bl)
    if mt.empty:
        trong(c, "Chưa có kết quả kiểm tra chất lượng nào trong bộ lọc này.")
    else:
        ve(c, _bieu_do_ma_tran(mt, batches), "bd_ma_tran")

    c1, c2 = st.columns([4, 3])
    with c1:
        c = the_ve("dong_loai", "Dòng bị loại theo bảng và lý do", "Gom từ dq.rejected_rows của các lần chạy đã lọc.")
        dl = _dong_loai(bl)
        if dl.empty:
            trong(c, "Không có dòng nào bị loại trong bộ lọc này.")
        else:
            c.dataframe(pd.DataFrame({"Bảng": dl.table_name, "Phép kiểm tra": dl.check_name, "Lý do": dl.reason,
                                      "Số dòng": so_cot(dl.so_dong)}),
                        hide_index=True, width="stretch",
                        column_config={"Bảng": st.column_config.TextColumn(width=105), "Phép kiểm tra": st.column_config.TextColumn(width=110),
                                       "Lý do": st.column_config.TextColumn(width=140),
                                       "Số dòng": st.column_config.TextColumn(width=65)})
    with c2:
        c = the_ve("dbt_lan", "dbt test không đạt theo lần chạy", "Mỗi cột là một lần chạy có chạy dbt. Không có cột nào = mọi test đạt.")
        d = df[df.dbt_n_node > 0]
        if d.empty:
            trong(c, "Chưa có lần chạy nào có kết quả dbt trong bộ lọc này.")
        elif (d.dbt_test_fail + d.dbt_test_warn).sum() == 0:
            trong(c, f"{so_vn(len(d))} lần chạy có dbt, mọi test đều đạt.")
        else:
            ve(c, _bieu_do_dbt_theo_lan(df), "bd_dbt_lan")

    tieu_de("Dòng lỗi", "Chi tiết dòng lỗi")
    c = the_ve("mau_loai", "Mẫu dòng bị loại (dq.rejected_rows)", "Tối đa 50 dòng mới nhất; row_data cắt ngắn 200 ký tự.")
    ml = _mau_loai(bl)
    if ml.empty:
        trong(c, "Không có dòng bị loại.")
    else:
        c.dataframe(pd.DataFrame({"Run": ml.run_id, "Bảng": ml.table_name, "Phép kiểm tra": ml.check_name,
                                  "Bản ghi số": so_cot(ml.source_row), "Lý do": ml.reason, "Nội dung dòng": ml.row_data,
                                  "Lúc loại": [gio(t) for t in ml.rejected_at]}), hide_index=True, width="stretch")
    c = the_ve("dbt_loi", "Danh sách dbt test không đạt",
               "relation_name = bảng trong schema dq chứa các dòng vi phạm (SELECT * FROM … để xem).")
    dt = _dbt_loi(bl)
    if dt.empty:
        trong(c, "Không có dbt test nào fail / error / warn trong bộ lọc này.")
    else:
        c.dataframe(style_bang(pd.DataFrame({"Run": dt.run_id, "Batch": dt.batch_id, "Kích hoạt": dt.triggered_by,
                                             "Test": dt.node_name, "Trạng thái": dt.status.str.upper(),
                                             "Dòng vi phạm": so_cot(dt.failures), "Bảng chứa dòng lỗi": dt.relation_name,
                                             "Thông báo": dt.message}), ["Trạng thái"], dbt=True), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Trang 3 - Chi tiết một lần chạy
# ---------------------------------------------------------------------------
MAU_KHAU = {"Mage": "#D5D8DE", "Nạp staging": CHANH_BAR, "dbt khởi động": TIM_NHAT, "dbt build": TIM}
# bước thời gian đẹp (mili giây) để chọn dtick của trục Gantt: không bao giờ lặp nhãn giờ khi lần chạy chỉ dài vài giây
BUOC_DTICK = (100, 200, 500, 1000, 2000, 5000, 10000, 15000, 30000, 60000, 120000, 300000, 600000)


def _dtick_gantt(buoc: pd.DataFrame) -> tuple[int, str]:
    """Chọn dtick (ms) sao cho trục có khoảng 6-8 nhãn; dưới 1 giây thì nhãn có phần mili giây."""
    tong_ms = max((buoc.ket_thuc.max() - buoc.bat_dau.min()).total_seconds() * 1000, 1.0)
    dtick = next((d for d in BUOC_DTICK if tong_ms / d <= 8), BUOC_DTICK[-1])
    return dtick, ("%H:%M:%S.%L" if dtick < 1000 else "%H:%M:%S")


def _bieu_do_gantt(buoc: pd.DataFrame):
    fig = go.Figure()
    for khau in ("Mage", "Nạp staging", "dbt khởi động", "dbt build"):
        d = buoc[buoc.khau == khau]
        if d.empty:
            continue
        mau = [MAU_TT["FAILED"] if t == "FAILED" else MAU_TT["RUNNING"] if t == "RUNNING" else MAU_KHAU[khau] for t in d.trang_thai]
        giay = (d.ket_thuc - d.bat_dau).dt.total_seconds().clip(lower=0.2)
        fig.add_trace(go.Bar(y=d.buoc, x=giay * 1000, base=d.bat_dau, orientation="h", name=khau, marker_color=mau, width=0.6,
                             customdata=[[thoi_luong(v), t] for v, t in zip(giay, d.trang_thai)],
                             hovertemplate="<b>%{y}</b><br>%{customdata[1]} · %{customdata[0]}<extra></extra>"))
    dtick, dinh_dang = _dtick_gantt(buoc)
    fig.update_yaxes(type="category", autorange="reversed", categoryorder="array", categoryarray=buoc.buoc.tolist(), title=None)
    fig.update_xaxes(type="date", title=None, tickformat=dinh_dang, dtick=dtick)
    fig.update_layout(barmode="overlay", showlegend=True)
    return khung_plotly(fig, max(220, 28 * len(buoc) + 60))


def _vao_staging(t: str) -> str:
    return {"SUCCESS": "có", "FAILED": "không – đã hoàn tác (rollback)", "RUNNING": "đang nạp"}.get(t, t)


def trang_chi_tiet(bay_gio: pd.Timestamp) -> None:
    ds = _ds_run()
    if ds.empty:
        st.markdown('<div class="hop_ghi">etl_log đang trống – chưa có lần chạy nào để xem. Chạy pipeline <b>full_load</b> trước.</div>',
                    unsafe_allow_html=True)
        return
    ids = ds.run_id.astype(int).tolist()
    rc = st.session_state.get("run_chon")
    if rc not in ids:
        if rc is not None:   # VD ?run_id=9999: báo rõ rồi mới về lần chạy gần nhất
            st.warning(f"Không tìm thấy lần chạy #{rc}. Đang hiện lần chạy gần nhất (#{ids[0]}).")
        st.session_state.run_chon = ids[0]
    nhan = {int(r.run_id): f"#{r.run_id} · {r.batch_id} · {r.triggered_by} · {r.status} · {gio(r.started_at)}" for r in ds.itertuples()}
    run_id = st.selectbox("Chọn lần chạy", ids, format_func=lambda v: nhan[v], key="run_chon")
    st.query_params["run_id"] = str(run_id)
    run, tl, qc, dbt = _chi_tiet(run_id)
    if run is None:
        st.warning(f"Không tìm thấy lần chạy #{run_id}.")
        return

    kt = run.finished_at
    mo_ta_thoi_gian = (thoi_luong(run.duration_s) if pd.notna(run.duration_s)
                       else f"đang chạy {thoi_luong(run.elapsed_s)}")
    lset = "từ đầu dữ liệu" if pd.isna(run.lset) else f"{pd.Timestamp(run.lset):%d/%m/%Y}"
    cet = "hết dữ liệu (batch cuối)" if pd.isna(run.cet) else f"{pd.Timestamp(run.cet):%d/%m/%Y}"
    # đang ở khâu dbt: dbt_result chỉ được ghi khi dbt build xong nên chưa biết thời gian từng đoạn
    dang_dbt = run.status == "RUNNING" and run.phase == "dbt"
    dbt_txt = f"đang chạy ({thoi_luong(run.mage_s)})" if dang_dbt else thoi_luong(run.dbt_s)
    mage_txt = "–" if dang_dbt else thoi_luong(run.mage_s)
    khau_loi = {"dbt": "dbt", "staging": "nạp staging", "bi_ngat": "bị ngắt", "khac": "khác"}
    khau_dang = {"staging": "nạp staging", "dbt": "dbt", "ghi_log": "ghi log"}
    c = st.container(key="the_dau_run")
    c.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;flex-wrap:wrap"><span style="font-size:22px;font-weight:700">'
        f'Lần chạy #{run.run_id}</span><span style="font-size:15px">{chip(run.status)}</span>'
        + (f'<span class="chip" style="background:#FDE3E0;color:#B8382B">lỗi ở khâu {esc(khau_loi.get(run.failed_stage, run.failed_stage))}</span>'
           if run.status == "FAILED" else "")
        + (f'<span class="chip" style="background:#E4E8FD;color:#3A47C4">đang ở khâu {esc(khau_dang.get(run.phase, run.phase))}</span>'
           if run.status == "RUNNING" and run.phase else "")
        + (f'<span class="chip" style="background:#FDE3E0;color:#B8382B">nghi kẹt &gt; {q.PHUT_KET} phút</span>' if run.is_stuck else "")
        + '</div><div class="dau_run">'
        f'<div><div class="k">Pipeline</div><div class="v">{esc(run.pipeline_name)}</div></div>'
        f'<div><div class="k">Batch · loại nạp</div><div class="v">{esc(run.batch_id)} · {esc(run.load_type)}</div></div>'
        f'<div><div class="k">LSET → CET (thời gian mô phỏng)</div><div class="v">{lset} → {cet}</div></div>'
        f'<div><div class="k">Kích hoạt · lượt nạp · lần thử</div><div class="v">{esc(run.triggered_by)} · lượt {run.cycle_no} · lần {run.attempt_no}</div></div>'
        f'<div><div class="k">Bắt đầu</div><div class="v">{gio(run.started_at)}</div></div>'
        f'<div><div class="k">Kết thúc</div><div class="v">{gio(kt) if pd.notna(kt) else "chưa kết thúc"}</div></div>'
        f'<div><div class="k">Thời lượng</div><div class="v">{mo_ta_thoi_gian}</div></div>'
        f'<div><div class="k">Nạp staging · dbt khởi động · dbt · Mage</div><div class="v">'
        f'{thoi_luong(run.staging_s)} · {thoi_luong(run.dbt_prep_s)} · {dbt_txt} · {mage_txt}</div></div></div>'
        + (f'<div class="hop_loi"><b>Thông báo lỗi đầy đủ:</b><br>{esc(run.error_message)}</div>' if pd.notna(run.error_message) and run.error_message else ""),
        unsafe_allow_html=True)

    rollback = int(run.rows_inserted_rollback + run.rows_updated_rollback)
    hang_kpi([
        the_kpi("Dòng đọc từ file", so_vn(run.rows_source), (f"{so_vn(run.n_bang)} bảng – đã hoàn tác" if run.n_bang_loi else f"{so_vn(run.n_bang)} bảng staging được nạp"), "chanh"),
        the_kpi("INSERT · UPDATE (đã vào staging)", f"{so_vn(run.rows_inserted)} · {so_vn(run.rows_updated)}",
                (f"đã hoàn tác (rollback) {so_vn(run.rows_inserted_rollback)} · {so_vn(run.rows_updated_rollback)} – KHÔNG vào staging"
                 if rollback else "dòng thêm mới · dòng cập nhật, đã commit"), "tim"),
        the_kpi("Bị loại · xóa mềm", f"{so_vn(run.rows_rejected)} · {so_vn(run.rows_deleted)}", "vào dq.rejected_rows · đơn bị đánh dấu xóa", "trang"),
        the_kpi("Kiểm tra chất lượng", f"{so_vn(run.n_check_pass)}/{so_vn(run.n_check)}", f"PASS · {so_vn(run.n_check_warn)} WARN · {so_vn(run.n_check_fail)} FAIL", "trang"),
        the_kpi("Node dbt", f"{so_vn(run.dbt_n_ok)}/{so_vn(run.dbt_n_node)}", f"đạt · {so_vn(run.dbt_n_fail)} lỗi · {so_vn(run.dbt_n_skipped)} bỏ qua", "den")])

    # thông báo cho lần chạy thiếu dữ liệu
    if run.status == "RUNNING":
        st.markdown('<div class="hop_ghi">Lần chạy đang diễn ra – bảng và kết quả dbt sẽ hiện dần khi từng bước xong '
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
                    '(lỗi ở khâu nạp staging) hoặc dbt không chạy được – xem thông báo lỗi ở trên.</div>', unsafe_allow_html=True)

    tieu_de("Các bước", "Dòng thời gian từng bước")
    buoc = q.gantt_cac_buoc(run, tl, dbt, bay_gio)
    c = the_ve("gantt", "Gantt: Mage khởi động, nạp từng bảng staging, dbt, Mage ghi log",
               "Xám = Mage (khởi động block, ghi log) · xanh chanh = nạp staging · tím nhạt = dbt khởi động / parse project · tím = dbt build · đỏ = bước lỗi · tím đậm = đang chạy.")
    if buoc.empty:
        trong(c, "Chưa có bước nào để vẽ.")
    else:
        ve(c, _bieu_do_gantt(buoc), "bd_gantt")

    tieu_de("Bảng", "Nạp staging (table_load)")
    c = the_ve("table_load", "Kết quả nạp từng bảng")
    if tl.empty:
        trong(c, "Không có dòng table_load.")
    else:
        if (tl.status == "FAILED").any():
            c.markdown('<div class="hop_loi" style="margin:0">Lần chạy này bị lỗi ở khâu nạp: cả batch đã được <b>hoàn tác (rollback)</b>. '
                       'Số INSERT / UPDATE bên dưới là số đã xử lý trước khi lỗi, <b>KHÔNG nằm trong staging</b>.</div>', unsafe_allow_html=True)
        c.dataframe(style_bang(pd.DataFrame({
            "Bảng": tl.table_name, "Dòng đọc": so_cot(tl.rows_source), "INSERT": so_cot(tl.rows_inserted),
            "UPDATE": so_cot(tl.rows_updated), "Bị loại": so_cot(tl.rows_rejected), "Xóa mềm": so_cot(tl.rows_deleted),
            "Bắt đầu": [gio(t, False) for t in tl.started_at], "Xong": [gio(t, False) for t in tl.finished_at],
            "Trạng thái": tl.status, "Vào staging": [_vao_staging(t) for t in tl.status],
            "Lỗi": [rut_gon(e, 140) for e in tl.error_message.fillna("")]}), ["Trạng thái"]),
            hide_index=True, width="stretch")
    c = the_ve("quality", "Kiểm tra chất lượng (quality_check)")
    if qc.empty:
        trong(c, "Lần chạy này không có phép kiểm tra chất lượng nào được ghi.")
    else:
        c.dataframe(style_bang(pd.DataFrame({
            "Bảng": qc.table_name, "Phép kiểm tra": qc.check_name, "Trạng thái": qc.status, "Dòng vi phạm": so_cot(qc.failed_rows),
            "Chi tiết": qc.detail.fillna("")}), ["Trạng thái"]), hide_index=True, width="stretch", height=min(420, 38 + 35 * len(qc)))

    tieu_de("dbt", "Kết quả dbt build")
    if dbt.empty:
        trong(st, "Chưa có kết quả dbt cho lần chạy này.")
        return
    c1, c2 = st.columns([2, 3])
    with c1:
        c = the_ve("dbt_dem", "Số node theo loại và trạng thái")
        dem = dbt.groupby(["resource_type", "status"]).size().reset_index(name="so_node")
        c.dataframe(style_bang(pd.DataFrame({"Loại": dem.resource_type, "Trạng thái": dem.status, "Số node": so_cot(dem.so_node)}),
                               ["Trạng thái"], dbt=True), hide_index=True, width="stretch")
    with c2:
        c = the_ve("dbt_cham", "10 model / seed chạy lâu nhất")
        md = dbt[dbt.resource_type.isin(["model", "seed"])].sort_values("execution_time", ascending=False).head(10)
        c.dataframe(pd.DataFrame({"Node": md.node_name, "Loại": md.resource_type, "Giây": [so_vn(v, 2) for v in md.execution_time],
                                  "Số dòng": so_cot(md.rows_affected), "Bảng đích": md.relation_name}), hide_index=True, width="stretch")
    xau = dbt[dbt.status.map(lambda s: s == "warn" or q.la_loi_dbt(s))]
    c = the_ve("dbt_test_loi", "Test / model lỗi hoặc cảnh báo", "Test fail: relation_name là bảng trong schema dq chứa dòng vi phạm.")
    if xau.empty:
        trong(c, "Không có node nào fail / error / warn.")
    else:
        c.dataframe(style_bang(pd.DataFrame({"Loại": xau.resource_type, "Node": xau.node_name, "Trạng thái": xau.status.str.upper(),
                                             "Dòng vi phạm": so_cot(xau.failures), "Bảng chứa dòng lỗi": xau.relation_name,
                                             "Thông báo": xau.message}), ["Trạng thái"], dbt=True), hide_index=True, width="stretch")


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
    st.sidebar.markdown('<div class="sb_logo"><span class="lg"><i style="height:6px"></i><i style="height:10px"></i>'
                        '<i style="height:14px"></i></span>Olist BI · Theo dõi ETL</div>', unsafe_allow_html=True)
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
