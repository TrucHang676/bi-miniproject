"""Hỏi AI về dashboard Olist – app Streamlit đi kèm Power BI; giao diện theo bản thiết kế "Thiết kế lại giao diện AI chatbot".

Thanh bên: chọn trang + bộ lọc (giống slicer). Phần chính: header, hàng thẻ KPI, 4 biểu đồ của trang (lấy thẳng từ dds
bằng queries.py). Khung Trợ lý AI bên phải: hỏi về 1 biểu đồ (nút "Hỏi AI" trên thẻ biểu đồ), cả trang hoặc cả dashboard;
tóm tắt / giải thích / chat. Số trong câu trả lời được kiểm lại với dữ liệu (kiem_so.py), mỗi lần hỏi lưu log vào ai/outputs/.
Cần GEMINI_API_KEY (và GROQ_API_KEY dự phòng) trong .env – xem llm.py.

Chạy từ gốc repo khi Postgres đang chạy:   streamlit run ai/app.py
Robot "Hỏi AI" trong Power BI mở link dạng:  http://localhost:8501/?bieu_do=Q5_2&nam=2018&thang=3
Tham số link: bieu_do (Q1_1 … Q6_2), nam, thang, vung, bang, bang_nb – thiếu tham số nào thì không lọc theo đó.
"""
import html
from datetime import datetime

import plotly.express as px
import plotly.graph_objects as go
import psycopg
import streamlit as st
from plotly.subplots import make_subplots

import kiem_so
import llm
import queries as q

st.set_page_config(page_title="Hỏi AI – Olist BI", page_icon="💬", layout="wide", initial_sidebar_state="expanded")

# Bảng màu theo dashboard Power BI (theme Olist_Lime_Soft)
NEN, THE, DEN, CHANH, TIM, TIM_DAM = "#F3F5F8", "#FFFFFF", "#121316", "#E2FA2C", "#A9B8F8", "#6F80EC"
DO, XAM, XAM_NHAT, LUOI = "#EF6F61", "#8B9099", "#F0F2F6", "#E6E8EC"
TANG, GIAM = "#1D5E12", "#D9483B"
# màu thẻ KPI theo thứ tự trên dashboard: chanh, tím, trắng (…), đen
MAU_KPI = {5: [CHANH, TIM, THE, THE, DEN], 4: [CHANH, TIM, THE, DEN]}
TAT_CA = "Tất cả"
THEO_THANG = ("Q1_1", "Q1_2", "Q3_1", "Q4_2", "Q5_2")


# ---------------------------------------------------------------------------
# Dữ liệu (cache)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def _so_lieu(ma: str, bl: q.BoLoc):
    kq = q.BIEU_DO[ma].ham(bl)
    return kq.bang, kq.tom_tat


@st.cache_data(ttl=600, show_spinner=False)
def _kpi(trang: int, bl: q.BoLoc):
    return q.the_kpi(trang, bl)


@st.cache_data(ttl=600, show_spinner=False)
def _the_pbi(trang: int, bl: q.BoLoc):
    return q.the_powerbi(trang, bl)


@st.cache_data(ttl=600, show_spinner="Đang gom số liệu cả trang…")
def _goi_trang(trang: int, bl: q.BoLoc):
    return llm.goi_so_lieu_trang(trang, bl)


@st.cache_data(ttl=600, show_spinner="Đang gom số liệu cả dashboard…")
def _goi_tat_ca(nam, thang):
    return llm.goi_so_lieu_tat_ca(nam, thang)


@st.cache_data(ttl=3600, show_spinner=False)
def _lua_chon():
    return q.danh_sach_lua_chon()


# ---------------------------------------------------------------------------
# Giao diện chung (CSS)
# ---------------------------------------------------------------------------
def _css(ma_chon: str, dang_hoi_bieu_do: bool, mo_ai: bool) -> None:
    """Giao diện theo bản thiết kế 'Thiết kế lại giao diện AI chatbot' (Figma Make): nền xám xanh, thẻ viền mảnh,
    nút 'Hỏi AI' dạng viên thuốc, khung Trợ lý AI header tối nhuộm tím + điểm nhấn xanh chanh."""
    the_chon = f".st-key-the_{ma_chon}" if dang_hoi_bieu_do else ".khong_co"
    nut_chon = f".st-key-hoi_{ma_chon}" if dang_hoi_bieu_do else ".khong_co"
    # Khung Trợ lý AI là popup trượt ra bên phải: ẩn khi đóng, khi đóng hiện nút nổi "Trợ lý AI" ở góc dưới
    popup = """.st-key-khung_ai {{ display: flex !important; }} .st-key-mo_tro_ly {{ display: none !important; }}"""         if mo_ai else """.st-key-khung_ai {{ display: none !important; }}"""
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');
    .stApp, .stApp p, .stApp div, .stApp label, .stApp button, .stApp input, .stApp textarea, .stApp li,
    .stApp span:not([data-testid="stIconMaterial"]) {{ font-family: 'Be Vietnam Pro', -apple-system, sans-serif; }}
    [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: {NEN}; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .stApp button [data-testid="stMarkdownContainer"], .stApp button p {{ font-size: inherit !important;
        font-weight: inherit; color: inherit; }}
    .block-container {{ padding: 1rem 1.1rem 1rem; max-width: 100%; }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 9999px; }}

    /* ---------- thanh bên ---------- */
    [data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid rgba(226,232,240,.8); }}
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding-top: .3rem; }}
    .sb_logo {{ display: flex; align-items: center; gap: 10px; font-size: 14.5px; font-weight: 700; color: #0f172a;
        margin: 0 0 18px 4px; letter-spacing: -.01em; }}
    .sb_muc {{ font-size: 10.5px; font-weight: 700; letter-spacing: .08em; color: #94a3b8; margin: 16px 0 6px 6px; }}
    [class*="st-key-nut_trang_"] button {{ justify-content: flex-start; text-align: left; border-radius: 12px;
        min-height: 40px; padding: 8px 12px; border: none; background: transparent; color: #475569; font-size: 12px;
        font-weight: 500; box-shadow: none; }}
    [class*="st-key-nut_trang_"] button > div, [class*="st-key-nut_trang_"] button [data-testid="stMarkdownContainer"] {{
        justify-content: flex-start; width: 100%; text-align: left; }}
    [class*="st-key-nut_trang_"] button:hover {{ background: #f1f5f9; color: #0f172a; }}
    [class*="st-key-nut_trang_"] button[kind="primary"] {{ background: #18181b; color: #fff; font-weight: 600; }}
    .st-key-nut_trang_1 [data-testid="stIconMaterial"] {{ color: #818cf8; }}
    .st-key-nut_trang_2 [data-testid="stIconMaterial"] {{ color: #f59e0b; }}
    .st-key-nut_trang_3 [data-testid="stIconMaterial"] {{ color: #ec4899; }}
    [data-testid="stSidebar"] label p {{ font-size: 11.5px; font-weight: 500; color: #334155; }}
    [data-testid="stSidebar"] [data-baseweb="select"] > div {{ background: rgba(241,245,249,.9); border: 1px solid transparent;
        border-radius: 12px; font-size: 12px; min-height: 36px; }}
    .st-key-dat_lai button {{ border: none; background: transparent; color: #4f46e5; font-size: 10.5px; font-weight: 600;
        padding: 0; min-height: 0; }}

    /* ---------- header + thẻ KPI ---------- */
    .olist_header {{ background: #fff; border-radius: 16px; border: 1px solid rgba(226,232,240,.8); display: flex;
        align-items: center; padding: 10px 16px; gap: 10px; margin-bottom: 12px; }}
    .olist_logo {{ width: 24px; height: 24px; border-radius: 6px; background: #d4f828; display: flex;
        align-items: flex-end; justify-content: center; gap: 2px; padding-bottom: 6px; box-sizing: border-box; }}
    .olist_logo i {{ display: block; width: 2.5px; background: #020617; border-radius: 1px; }}
    .sb_logo .olist_logo {{ width: 28px; height: 28px; border-radius: 8px; border: 1px solid rgba(15,23,42,.1); }}
    .olist_ten {{ font-size: 15px; font-weight: 700; color: #0f172a; }}
    .olist_ngay {{ margin-left: auto; display: inline-flex; align-items: center; gap: 6px; background: #f1f5f9;
        border: 1px solid rgba(226,232,240,.7); border-radius: 999px; padding: 6px 12px; font-weight: 600;
        font-size: 12px; color: #334155; }}
    .olist_ngay b {{ color: #4f46e5; }}
    .hang_kpi {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .the_kpi {{ border-radius: 16px; padding: 12px 16px; min-height: 104px; box-sizing: border-box; border: 1px solid;
        display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
    .the_kpi .ten {{ font-size: 11.5px; opacity: .8; font-weight: 500; }}
    .the_kpi .so {{ font-size: 22px; font-weight: 800; letter-spacing: -.02em; line-height: 1.2; margin: 4px 0; }}
    .the_kpi .ghi {{ font-size: 10.5px; font-weight: 600; line-height: 1.35; }}

    /* ---------- thẻ biểu đồ ---------- */
    [class*="st-key-the_"] {{ background: #fff; border-radius: 16px; border: 1px solid rgba(226,232,240,.8);
        padding: 16px 18px 8px; box-shadow: 0 2px 10px -4px rgba(15,23,42,.04); transition: all .2s; }}
    [class*="st-key-the_"]:hover {{ border-color: #cbd5e1; }}
    {the_chon} {{ border-color: rgba(15,23,42,.2); box-shadow: 0 0 0 2px #d4f828, 0 10px 30px -10px rgba(15,23,42,.1); }}
    .tieu_de_the {{ font-weight: 700; font-size: 14px; color: #0f172a; margin: 0; line-height: 1.3; }}
    .phu_the {{ font-size: 11.5px; color: #64748b; margin: 2px 0 0; }}
    [class*="st-key-hoi_"] {{ display: flex; justify-content: flex-end; }}
    [class*="st-key-hoi_"] .stButton {{ width: auto; max-width: 100%; }}
    [class*="st-key-hoi_"] button {{ border-radius: 999px; min-height: 28px; padding: 3px 11px; font-size: 11.5px;
        font-weight: 600; background: rgba(241,245,249,.9); color: #334155; border: 1px solid rgba(226,232,240,.8);
        white-space: nowrap; transition: all .2s; max-width: 100%; }}
    [class*="st-key-hoi_"] button:hover {{ background: #0f172a; color: #fff; border-color: #0f172a; }}
    [class*="st-key-hoi_"] [data-testid="stIconMaterial"] {{ color: #6366f1; }}
    {nut_chon} button {{ background: #0f172a; color: #d9f938; border-color: #0f172a;
        box-shadow: 0 4px 14px rgba(15,23,42,.18), 0 0 0 2px rgba(217,249,56,.5); }}
    {nut_chon} [data-testid="stIconMaterial"] {{ color: #d9f938; animation: nhay 1.4s ease-in-out infinite; }}
    @keyframes nhay {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}

    /* ---------- khung Trợ lý AI ---------- */
    .st-key-khung_ai {{ background: #fff; border: 1px solid rgba(226,232,240,.9); border-radius: 16px; overflow: hidden;
        box-shadow: 0 24px 60px -12px rgba(15,23,42,.35); gap: 0 !important; position: fixed; top: 14px; right: 18px;
        bottom: 14px; width: min(470px, 42vw); z-index: 999990; overflow-y: auto; overflow-x: hidden;
        animation: truot_vao .28s cubic-bezier(.2,.8,.2,1); }}
    @keyframes truot_vao {{ from {{ transform: translateX(40px); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
    {popup.replace("{{", "{").replace("}}", "}")}
    .st-key-dong_ai button {{ background: transparent; border: none; color: #cbd5e1; min-height: 30px; padding: 4px 6px; }}
    .st-key-dong_ai button:hover {{ background: rgba(239,68,68,.2); color: #fff; }}
    .st-key-mo_tro_ly {{ position: fixed; right: 22px; bottom: 22px; z-index: 999980; }}
    .st-key-mo_tro_ly button {{ background: #0f172a; color: #d9f938; border: none; border-radius: 999px; padding: 10px 18px;
        font-size: 13px; font-weight: 700; box-shadow: 0 10px 30px -6px rgba(15,23,42,.45), 0 0 0 3px rgba(217,249,56,.35); }}
    .st-key-mo_tro_ly button:hover {{ background: #1e1b4b; color: #d9f938; }}
    .st-key-ai_dau {{ background: linear-gradient(135deg, #0f172a 0%, #0f172a 55%, #1e1b4b 100%); padding: 14px 16px 12px;
        position: relative; overflow: hidden; gap: .55rem !important; }}
    .st-key-ai_dau::before {{ content: ""; position: absolute; right: -32px; top: -32px; width: 112px; height: 112px;
        border-radius: 50%; background: rgba(217,249,56,.15); filter: blur(18px); pointer-events: none; }}
    .ai_ten {{ display: flex; align-items: center; gap: 10px; }}
    .ai_bieu_tuong {{ width: 32px; height: 32px; border-radius: 12px; background: #d9f938; color: #020617; display: flex;
        align-items: center; justify-content: center; font-size: 16px; box-shadow: 0 0 16px rgba(217,249,56,.4); flex-shrink: 0; }}
    .ai_ten h2 {{ font-size: 14px !important; font-weight: 700; color: #fff !important; margin: 0 !important; padding: 0 !important; }}
    .ai_ten p {{ font-size: 11px; color: #cbd5e1; margin: 1px 0 0; }}
    .ai_huy_hieu {{ display: inline-flex; align-items: center; gap: 4px; padding: 1px 7px; border-radius: 999px;
        font-size: 10px; font-weight: 600; background: rgba(16,185,129,.2); color: #6ee7b7;
        border: 1px solid rgba(52,211,153,.25); margin-left: 8px; vertical-align: 2px; }}
    .ai_huy_hieu i {{ width: 6px; height: 6px; border-radius: 50%; background: #34d399; animation: nhay 1.4s infinite; }}
    .st-key-ai_dau [data-testid="stPopover"] button, .st-key-xoa_chat button {{ background: transparent; border: none;
        color: #cbd5e1; min-height: 30px; padding: 4px 6px; }}
    .st-key-ai_dau [data-testid="stPopover"] button:hover, .st-key-xoa_chat button:hover {{ background: rgba(255,255,255,.1);
        color: #fff; }}
    .st-key-pham_vi [data-testid="stButtonGroup"] {{ background: rgba(2,6,23,.6); border: 1px solid rgba(255,255,255,.1);
        border-radius: 12px; padding: 4px; width: 100%; }}
    .st-key-pham_vi [data-testid="stButtonGroup"] > div {{ width: 100%; display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }}
    .st-key-pham_vi button {{ background: transparent !important; border: none !important; color: #cbd5e1 !important;
        border-radius: 8px !important; font-size: 11.5px; font-weight: 600; min-height: 30px; width: 100%;
        padding: 2px 4px !important; white-space: nowrap; }}
    .st-key-pham_vi button[data-testid*="Active"] {{ background: #d9f938 !important; color: #020617 !important; }}
    .st-key-pham_vi button[data-testid*="Active"] [data-testid="stIconMaterial"] {{ color: #020617; }}
    .st-key-ai_ngu_canh {{ background: rgba(248,250,252,.9); border-bottom: 1px solid rgba(226,232,240,.8);
        padding: 10px 14px; gap: .45rem !important; }}
    .st-key-ai_chat [data-testid="stMarkdownContainer"], .st-key-ai_chat [data-testid="stElementContainer"] {{
        margin-bottom: 0 !important; }}
    .st-key-ai_chat [data-testid="stVerticalBlock"] {{ gap: .75rem; }}
    [class*="st-key-tin_"] [data-testid="stVerticalBlock"], [class*="st-key-tin_"] {{ height: auto !important; }}
    .st-key-ai_ngu_canh [data-testid="stMarkdownContainer"], .st-key-ai_dau [data-testid="stMarkdownContainer"],
    .st-key-ai_cuoi [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    .st-key-ai_ngu_canh [data-testid="stElementContainer"] {{ margin: 0 !important; }}
    .ai_dong_ngu_canh {{ min-height: 20px; padding-bottom: 2px; display: flex; align-items: center; justify-content: space-between; gap: 6px 8px; flex-wrap: wrap; }}
    .ai_dong_ngu_canh b {{ font-size: 12px; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .ai_chi_so {{ font-size: 10.5px; font-weight: 500; color: #4338ca; background: #eef2ff; border: 1px solid rgba(199,210,254,.7);
        padding: 1px 8px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; }}
    .ai_loc {{ font-size: 10.5px; color: #64748b; }}
    .ai_loc b {{ color: #334155; }}
    .st-key-chon_nhanh [data-testid="stButtonGroup"] > div {{ flex-wrap: wrap; gap: 4px; }}
    .st-key-chon_nhanh button {{ font-size: 10.5px !important; min-height: 24px !important; padding: 1px 8px !important;
        border-radius: 6px !important; background: #fff; border: 1px solid rgba(226,232,240,.8) !important; color: #475569; }}
    .st-key-chon_nhanh button[data-testid*="Active"] {{ background: #4f46e5 !important; color: #fff !important;
        border-color: #4f46e5 !important; }}
    .st-key-ai_nut {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; }}
    .st-key-ai_nut button {{ background: linear-gradient(90deg, #4f46e5, #6366f1); color: #fff; border: none; border-radius: 12px;
        font-size: 12px; font-weight: 600; min-height: 36px; box-shadow: 0 2px 6px rgba(99,102,241,.15); }}
    .st-key-ai_nut button:hover {{ background: linear-gradient(90deg, #4338ca, #4f46e5); color: #fff; }}
    .st-key-ai_chat {{ background: linear-gradient(180deg, #fff, rgba(248,250,252,.6)); }}
    .st-key-ai_chat > div {{ padding: 12px 14px; }}
    .ai_trong {{ text-align: center; padding: 36px 14px; }}
    .ai_trong .o {{ width: 44px; height: 44px; border-radius: 16px; background: #eef2ff; color: #4f46e5; display: flex;
        align-items: center; justify-content: center; margin: 0 auto 12px; font-size: 20px; }}
    .ai_trong h4 {{ font-size: 12px !important; font-weight: 700; color: #1e293b; margin: 0 0 4px !important; padding: 0 !important; }}
    .ai_trong p {{ font-size: 11.5px; color: #64748b; margin: 0; }}
    [class*="st-key-tin_ban_"] {{ margin-left: auto; max-width: 86%; background: #0f172a; color: #fff;
        border-radius: 16px 16px 4px 16px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(15,23,42,.1); gap: .2rem !important; }}
    [class*="st-key-tin_ban_"] p {{ color: #fff; font-size: 12px; line-height: 1.55; margin: 0; }}
    .tin_dau {{ display: flex; justify-content: space-between; gap: 12px; font-size: 10px; color: #94a3b8; }}
    .tin_dau .ai {{ font-weight: 700; color: #4338ca; font-size: 10.5px; }}
    .tin_dau .ban {{ font-weight: 600; color: #d9f938; }}
    [class*="st-key-tin_ai_"] {{ background: #fff; border: 1px solid rgba(199,210,254,.8); border-radius: 16px 16px 16px 4px;
        padding: 12px; box-shadow: 0 1px 2px rgba(15,23,42,.05); gap: .35rem !important; }}
    [class*="st-key-tin_ai_"] p, [class*="st-key-tin_ai_"] li {{ font-size: 12px; line-height: 1.6; color: #334155; }}
    [class*="st-key-tin_ai_"] strong {{ color: #0f172a; }}
    [class*="st-key-tin_ai_"] h1, [class*="st-key-tin_ai_"] h2, [class*="st-key-tin_ai_"] h3 {{ font-size: 12.5px !important;
        font-weight: 700; color: #312e81; padding: 6px 0 2px !important; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] details {{ border: 1px solid rgba(167,243,208,.8); background: rgba(236,253,245,.6);
        border-radius: 12px; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] summary p {{ font-size: 10.5px; color: #047857; font-weight: 600; }}
    .xac_thuc {{ display: inline-flex; align-items: center; gap: 4px; padding: 1px 7px; border-radius: 999px; font-size: 10px;
        font-weight: 600; white-space: nowrap; }}
    .xac_thuc.dat {{ color: #047857; background: #ecfdf5; }}
    .xac_thuc.can {{ color: #b45309; background: #fffbeb; }}
    .ai_dang_tai {{ border: 1px solid #e2e8f0; background: #fff; border-radius: 12px; padding: 12px; display: flex; gap: 12px;
        align-items: center; font-size: 12px; color: #475569; }}
    .ai_dang_tai .xoay {{ width: 24px; height: 24px; border-radius: 8px; background: #d9f938; display: flex; align-items: center;
        justify-content: center; animation: xoay 1s linear infinite; flex-shrink: 0; }}
    .ai_dang_tai b {{ color: #0f172a; display: block; }}
    .ai_dang_tai small {{ font-size: 11px; color: #94a3b8; }}
    @keyframes xoay {{ to {{ transform: rotate(360deg); }} }}
    .st-key-ai_cuoi {{ background: #f8fafc; border-top: 1px solid rgba(226,232,240,.8); padding: 12px; gap: .5rem !important; }}
    .goi_y_dau {{ display: flex; justify-content: space-between; font-size: 10.5px; font-weight: 600; color: #64748b; }}
    .goi_y_dau span {{ font-size: 10px; color: #4f46e5; }}
    [class*="st-key-goi_y_"] button {{ background: #fff; border: 1px solid rgba(226,232,240,.9); border-radius: 8px;
        font-size: 11px; color: #334155; min-height: 26px; padding: 3px 10px; text-align: left; box-shadow: 0 1px 1px rgba(15,23,42,.03); }}
    [class*="st-key-goi_y_"] button:hover {{ background: #eef2ff; color: #4338ca; border-color: #a5b4fc; }}
    .st-key-ai_cuoi [data-testid="stChatInput"] {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; }}
    .st-key-ai_cuoi [data-testid="stChatInput"] textarea {{ font-size: 12px; }}
    .st-key-ai_cuoi [data-testid="stChatInputSubmitButton"] {{ background: #0f172a; color: #d9f938; border-radius: 8px; }}
    </style>""", unsafe_allow_html=True)


def _doc_link() -> None:
    """Lần đầu mở app: điền sẵn biểu đồ và bộ lọc từ link của robot Hỏi AI trên Power BI."""
    if st.session_state.get("da_doc_link"):
        return
    st.session_state.da_doc_link = True
    tham_so = st.query_params
    ma = tham_so.get("bieu_do", "").upper()
    if ma in q.BIEU_DO:
        st.session_state.trang = q.BIEU_DO[ma].trang
        st.session_state.bieu_do = ma
    for k in ("nam", "thang"):
        if tham_so.get(k, "").isdigit():
            st.session_state[k] = int(tham_so[k])
    for k in ("vung", "bang", "bang_nb"):
        if tham_so.get(k):
            st.session_state[k] = tham_so[k]


def _chon(nhan: str, lua_chon: list, key: str):
    """selectbox có mục "Tất cả"; giá trị lạ (VD từ link) thì về "Tất cả" thay vì báo lỗi."""
    lua_chon = [TAT_CA] + lua_chon
    if st.session_state.get(key) not in lua_chon:
        st.session_state[key] = TAT_CA
    gia_tri = st.sidebar.selectbox(nhan, lua_chon, key=key)
    return None if gia_tri == TAT_CA else gia_tri


def _doi_trang(t: int) -> None:
    st.session_state.trang = t
    st.session_state.bieu_do = next(m for m, b in q.BIEU_DO.items() if b.trang == t)


# ---------------------------------------------------------------------------
# Thanh bên: trang + bộ lọc
# ---------------------------------------------------------------------------
_doc_link()
st.session_state.setdefault("trang", 1)
st.session_state.setdefault("pham_vi", "bieu_do")
st.session_state.setdefault("mo_ai", bool(st.query_params.get("bieu_do")))  # mở sẵn khi đến từ robot trên Power BI
trang = st.session_state.trang
ma_cua_trang = [m for m, b in q.BIEU_DO.items() if b.trang == trang]
if st.session_state.get("bieu_do") not in ma_cua_trang:
    st.session_state.bieu_do = ma_cua_trang[0]
ma = st.session_state.bieu_do
_css(ma, st.session_state.mo_ai and st.session_state.pham_vi == "bieu_do", st.session_state.mo_ai)

st.sidebar.markdown('<div class="sb_logo"><div class="olist_logo"><i style="height:6px"></i><i style="height:10px">'
                    '</i><i style="height:14px"></i></div>Olist BI · Hỏi AI</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sb_muc">TRANG</div>', unsafe_allow_html=True)
for t_, ten_ngan, bieu_tuong in zip(q.TRANG, ("Tổng quan", "Giao hàng", "Người bán"),
                                   (":material/grid_view:", ":material/local_shipping:", ":material/storefront:")):
    st.sidebar.button(ten_ngan, icon=bieu_tuong, key=f"nut_trang_{t_}", width="stretch",
                      type="primary" if t_ == trang else "secondary", on_click=_doi_trang, args=(t_,))


def _dat_lai() -> None:
    for k in ("nam", "thang", "vung", "bang", "bang_nb"):
        st.session_state[k] = TAT_CA


c_loc, c_dat = st.sidebar.columns([3, 2], vertical_alignment="bottom")
c_loc.markdown('<div class="sb_muc">BỘ LỌC</div>', unsafe_allow_html=True)
if any(st.session_state.get(k, TAT_CA) != TAT_CA for k in ("nam", "thang", "vung", "bang", "bang_nb")):
    c_dat.button("Đặt lại", icon=":material/restart_alt:", key="dat_lai", on_click=_dat_lai)
try:
    lc = _lua_chon()
except psycopg.OperationalError:
    st.error("Không kết nối được Postgres. Mở Docker Desktop rồi chạy `docker compose up -d` ở thư mục repo.")
    st.stop()
co_loc = q.TRANG[trang].bo_loc
loc = {"nam": _chon("Năm", [2017, 2018], "nam"), "thang": _chon("Tháng", list(range(1, 13)), "thang")}
if "vung" in co_loc:
    loc["vung"] = _chon("Vùng nhận hàng", lc["vung"], "vung")
if "bang" in co_loc:
    bang_chon = (lc["bang_theo_vung"].get(loc["vung"], []) if loc.get("vung")
                 else sorted(b for ds in lc["bang_theo_vung"].values() for b in ds))
    loc["bang"] = _chon("Bang nhận hàng", bang_chon, "bang")
if "bang_nb" in co_loc:
    loc["bang_nb"] = _chon("Bang người bán", lc["bang_nb"], "bang_nb")
bl = q.bo_loc_cua_trang(trang, **loc)
st.sidebar.caption("Kỳ phân tích cố định 01/2017 – 08/2018 như filter của report Power BI. "
                   "Biểu đồ theo tháng luôn hiện đủ các tháng, tháng đang chọn được đánh dấu.")


# ---------------------------------------------------------------------------
# Biểu đồ: vẽ lại đúng kiểu, màu, nhãn của từng visual trên dashboard Power BI
# ---------------------------------------------------------------------------
TIEU_DE = {  # tiêu đề + tiêu đề phụ như trên Power BI (tiêu đề phụ có thể là hàm của tom_tat)
    "Q1_1": ("Doanh thu theo tháng", None),
    "Q1_2": ("Số đơn và giá trị đơn trung bình theo tháng", None),
    "Q2_1": ("Top 10 theo doanh thu", lambda tt: f"10 danh mục dẫn đầu chiếm "
             f"{q.so_vn(tt['ti_trong_nhom_top10_danh_muc'] * 100, 1)}% doanh thu toàn sàn"),
    "Q2_2": ("Top 5 theo doanh thu", lambda tt: f"5 bang dẫn đầu chiếm "
             f"{q.so_vn(tt['ti_trong_nhom_top5_bang'] * 100, 1)}% doanh thu toàn sàn"),
    "Q3_1": ("Tỉ lệ giao trễ theo tháng", lambda tt: "% đơn đã giao nhận sau ngày dự kiến"),
    "Q3_2": ("10 bang giao trễ nhiều nhất", lambda tt: "Phần đỏ: vượt ngưỡng cảnh báo 10%"),
    "Q4_1": ("Điểm đánh giá theo mức trễ", lambda tt: f"Đường đứt: điểm TB toàn sàn "
             f"{q.so_vn(tt['diem_tb_toan_san'], 2)} ★"),
    "Q4_2": ("Tỉ lệ giao trễ và điểm đánh giá theo tháng",
             lambda tt: "Cột đỏ: trễ > 10%. Đường: điểm TB (trục phải)"),
    "Q5_1": ("Tỉ lệ giao trễ theo khâu bàn giao", None),
    "Q5_2": ("Bàn giao trễ và thời gian vận chuyển theo tháng",
             lambda tt: "Cột đỏ: tháng giao trễ > 10%. Đường: ngày vận chuyển"),
    "Q6_1": ("Người bán có ≥ 30 đơn", lambda tt: "● Trong ngưỡng   ● Vượt ngưỡng   ·   Cỡ chấm = doanh thu"),
    "Q6_2": ("10 người bán cần xử lý trước", lambda tt: "Chuột phải trên Power BI → Chi tiết người bán"),
}
XANH_BANG = {">12%": "#3A49C0", "5–12%": TIM_DAM, "2–5%": TIM, "1–2%": "#D0D8FB", "<1%": "#EEF1FE"}  # chú thích bản đồ


def _x_thang(df) -> list:
    """Trục tháng 2 tầng như Power BI: số tháng, dưới là quý/năm (Q1/17 = quý 1 năm 2017)."""
    return [[f"Q{(int(t) - 1) // 3 + 1}/{int(n) % 100:02d}" for n, t in zip(df.nam, df.thang)],
            [str(int(t)) for t in df.thang]]


def _mo(df) -> list:
    """Độ đậm từng tháng: có lọc tháng thì tháng khác mờ đi (biểu đồ theo tháng không lọc tháng)."""
    return [1 if not bl.thang or int(t) == bl.thang else 0.35 for t in df.thang]


def _nhom_bang(v: float) -> str:
    return ">12%" if v > .12 else "5–12%" if v > .05 else "2–5%" if v > .02 else "1–2%" if v > .01 else "<1%"


def _cot_duong(df, cot, ten_cot, mau_cot, duong, ten_duong, nhan_duong=None, truc_phai="") -> go.Figure:
    """Cột + đường trục phải (Line and clustered column chart của Power BI)."""
    x = _x_thang(df)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=x, y=df[cot], name=ten_cot, marker=dict(color=mau_cot, opacity=_mo(df)))
    fig.add_scatter(x=x, y=df[duong], name=ten_duong, mode="lines+markers" + ("+text" if nhan_duong else ""),
                    line=dict(color=DEN, width=2), marker=dict(size=6, color=DEN), secondary_y=True,
                    text=nhan_duong, textposition="top center", textfont=dict(size=9.5, color=DEN))
    fig.update_yaxes(range=[0, df[cot].max() * 1.7], secondary_y=False)
    fig.update_yaxes(range=[0, df[duong].max() * 1.18], showgrid=False, secondary_y=True, title_text=truc_phai)
    return fig


def _ngang(nhan, gia_tri, mau, chu, tieu_de_y="") -> go.Figure:
    """Thanh ngang có nhãn số ở cuối thanh, không trục X (Clustered bar chart của Power BI)."""
    fig = go.Figure(go.Bar(x=gia_tri, y=nhan, orientation="h", marker_color=mau, text=chu, textposition="outside",
                           cliponaxis=False, textfont=dict(size=10.5, color=DEN)))
    fig.update_yaxes(autorange="reversed", title_text=tieu_de_y)
    fig.update_xaxes(visible=False, range=[0, max(gia_tri) * 1.18])
    return fig


def _ve(ma: str, df, tom_tat: dict):
    if ma == "Q1_1":  # Area chart: đường đen, nền vàng chanh nhạt
        fig = go.Figure(go.Scatter(x=_x_thang(df), y=df.doanh_thu, mode="lines", line=dict(color=DEN, width=2.2),
                                   line_shape="spline", fill="tozeroy", fillcolor="rgba(226,250,44,.38)",
                                   name="Doanh thu"))
        if bl.thang:
            d = df[df.thang == bl.thang]
            fig.add_scatter(x=_x_thang(d), y=d.doanh_thu, mode="markers", marker=dict(size=9, color=DO), name="Đang chọn")
        fig.update_yaxes(tickformat=".2s")
    elif ma == "Q1_2":
        fig = _cot_duong(df, "so_don", "Số đơn", TIM, "gia_tri_don_tb", "Giá trị đơn TB",
                         nhan_duong=[f"{v:.0f}" for v in df.gia_tri_don_tb], truc_phai="BRL/đơn")
    elif ma == "Q2_1":
        fig = _ngang(df.danh_muc_en, df.ti_trong, [CHANH if i < 3 else TIM for i in range(len(df))],
                     [f"{v:.2%}" for v in df.ti_trong], "Danh mục")
    elif ma == "Q2_2":
        d = df.head(5)
        fig = _ngang([f"{t} ({b})" for t, b in zip(d.ten_bang, d.bang)], d.ti_trong,
                     [XANH_BANG[_nhom_bang(v)] for v in d.ti_trong], [f"{v:.2%}" for v in d.ti_trong], "Bang")
    elif ma == "Q3_1":
        fig = go.Figure(go.Scatter(x=_x_thang(df), y=df.ti_le_tre, mode="lines+markers", name="Tỉ lệ giao trễ",
                                   line=dict(color=TIM_DAM, width=2.2),
                                   marker=dict(size=7, color=[DO if v > .10 else TIM_DAM for v in df.ti_le_tre],
                                               opacity=_mo(df))))
        fig.add_hline(y=0.10, line_dash="dash", line_color=XAM, annotation_text="Ngưỡng 10%",
                      annotation_font_size=10, annotation_font_color=XAM)
        fig.update_yaxes(tickformat=".0%")
    elif ma == "Q3_2":  # thanh xếp chồng: phần đến 10% (tím) + phần vượt ngưỡng (đỏ)
        ten = df.ten_bang
        fig = go.Figure()
        fig.add_bar(x=df.ti_le_tre.clip(upper=.10), y=ten, orientation="h", marker_color=TIM, name="Đến 10%")
        fig.add_bar(x=(df.ti_le_tre - .10).clip(lower=0), y=ten, orientation="h", marker_color=DO,
                    name="Phần vượt ngưỡng", text=[f"{v:.1%}" for v in df.ti_le_tre], textposition="outside",
                    cliponaxis=False, textfont=dict(size=10.5, color=DEN))
        fig.update_layout(barmode="stack")
        fig.add_vline(x=0.10, line_dash="dash", line_color=XAM)
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(visible=False, range=[0, df.ti_le_tre.max() * 1.2])
    elif ma == "Q4_1":
        fig = go.Figure(go.Bar(x=df.muc_tre, y=df.diem_tb, marker_color=[CHANH if k == "Đúng hạn" else DO
                                                                         for k in df.ket_qua],
                               text=[q.so_vn(v, 2) for v in df.diem_tb], textposition="outside", cliponaxis=False,
                               textfont=dict(size=11, color=DEN)))
        fig.add_hline(y=tom_tat["diem_tb_toan_san"], line_dash="dash", line_color=XAM)
        fig.update_yaxes(range=[0, 5], title_text="Điểm TB (★)")
    elif ma == "Q4_2":
        fig = _cot_duong(df, "ti_le_tre", "Tỉ lệ giao trễ", [DO if v > .10 else TIM for v in df.ti_le_tre],
                         "diem_tb", "Điểm TB", truc_phai="★")
        fig.update_yaxes(tickformat=".0%", secondary_y=False)
        fig.update_yaxes(range=[1, 5], secondary_y=True)
    elif ma == "Q5_1":
        fig = go.Figure()
        for tuyen, mau in (("Nội bang", TIM), ("Liên bang", TIM_DAM)):
            d = df[df.tuyen == tuyen]
            fig.add_bar(x=d.ban_giao, y=d.ti_le_tre, name=tuyen, marker_color=mau, text=[f"{v:.1%}" for v in d.ti_le_tre],
                        textposition="outside", cliponaxis=False, textfont=dict(size=10.5, color=DEN))
        fig.update_layout(barmode="group")
        fig.update_xaxes(title_text="Người bán bàn giao")
        fig.update_yaxes(tickformat=".0%", range=[0, df.ti_le_tre.max() * 1.25])
    elif ma == "Q5_2":
        fig = _cot_duong(df, "ti_le_ban_giao_tre", "Bàn giao trễ", [DO if v > .10 else TIM for v in df.ti_le_tre],
                         "van_chuyen_tb", "Vận chuyển TB (ngày)", truc_phai="ngày")
        fig.update_yaxes(tickformat=".0%", secondary_y=False)
    elif ma == "Q6_1":
        fig = go.Figure()
        for co, ten, mau in ((False, "Trong ngưỡng", TIM), (True, "Vượt ngưỡng", DO)):
            d = df[df.can_xu_ly == co]
            fig.add_scatter(x=d.ti_le_ban_giao_tre, y=d.diem_tb, mode="markers", name=ten, text=d.nguoi_ban,
                            hovertemplate="%{text}<br>Bàn giao trễ %{x:.1%} · Điểm %{y:.2f}<extra></extra>",
                            marker=dict(color=mau, opacity=.75, line=dict(width=0),
                                        size=(d.doanh_thu / df.doanh_thu.max()) ** .5 * 22 + 4))
        fig.add_vline(x=0.10, line_dash="dash", line_color=XAM, annotation_text="10%", annotation_font_size=10)
        fig.add_hline(y=3.5, line_dash="dash", line_color=XAM, annotation_text="3,5★", annotation_font_size=10)
        fig.update_xaxes(tickformat=".0%", title_text="Bàn giao trễ")
        fig.update_yaxes(title_text="Điểm TB")
    else:
        return None  # Q6_2 là bảng (tableEx) – vẽ bằng st.dataframe
    fig.update_layout(height=255, margin=dict(l=4, r=8, t=8, b=4), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Segoe UI, sans-serif", size=11, color="#4A4E57"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title_text="",
                                  font_size=10.5),
                      showlegend=ma in ("Q1_2", "Q4_2", "Q5_1", "Q5_2"), bargap=0.22, hoverlabel=dict(font_size=11))
    fig.update_xaxes(showgrid=False, linecolor=LUOI, title_font_size=10.5, tickfont_size=10, tickangle=0)
    fig.update_yaxes(gridcolor=LUOI, zeroline=False, title_font_size=10.5, tickfont_size=10.5)
    return fig


def _bang_q6(df) -> None:
    """Bảng '10 người bán cần xử lý trước' như tableEx trên Power BI: cột doanh thu có thanh dữ liệu."""
    st.dataframe(df[["nguoi_ban", "canh_bao", "doanh_thu"]], hide_index=True, width="stretch", height=262,
                 column_config={
                     "nguoi_ban": st.column_config.TextColumn("Người bán", width="medium"),
                     "canh_bao": st.column_config.TextColumn("Vượt ngưỡng"),
                     "doanh_thu": st.column_config.ProgressColumn("Doanh thu (BRL)", format="%.0f", min_value=0,
                                                                  max_value=float(df.doanh_thu.max()), color=TIM)})


def _the_kpi(trang: int, bl: q.BoLoc) -> str:
    """Hàng thẻ KPI: chữ y như thẻ Power BI (queries.the_powerbi), màu theo bản thiết kế."""
    the = _the_pbi(trang, bl)
    kieu_the = {5: ["chanh", "tim", "trang", "trang", "den"], 4: ["chanh", "tim", "trang", "den"]}.get(len(the))
    nen = {"chanh": ("#d4f828", "#c5ea1b", "#020617"), "tim": ("#a4b0fc", "#93a0f8", "#020617"),
           "trang": ("#ffffff", "#e2e8f0", "#020617"), "den": ("#141518", "#141518", "#ffffff")}
    mau_ghi = {  # màu dòng phụ: (thẻ chanh, thẻ tím, thẻ trắng, thẻ đen)
        "tang": ("#064e3b", "#022c22", "#059669", "#d9f938"), "tot": ("#064e3b", "#022c22", "#059669", "#d9f938"),
        "giam": ("#be123c", "#9f1239", "#e11d48", "#fda4af"), "xau": ("#be123c", "#9f1239", "#e11d48", "#fda4af"),
        "canh_bao": ("#92400e", "#78350f", "#b45309", "#fcd34d"),
        "trung_tinh": ("#334155", "#1e293b", "#64748b", "#94a3b8")}
    thu_tu = ["chanh", "tim", "trang", "den"]
    o = []
    for k, c in zip(kieu_the or ["trang"] * len(the), the):
        bg, vien, chu = nen[k]
        o.append(f'<div class="the_kpi" style="background:{bg};border-color:{vien};color:{chu}">'
                 f'<div class="ten">{html.escape(c["ten"])}</div><div class="so">{html.escape(c["so"])}</div>'
                 f'<div class="ghi" style="color:{mau_ghi[c["kieu"]][thu_tu.index(k)]}">{html.escape(c["ghi"])}</div></div>')
    return f'<div class="hang_kpi" style="grid-template-columns:repeat({len(the)},1fr)">' + "".join(o) + "</div>"


# ---------------------------------------------------------------------------
# Phần chính: header + KPI + 4 biểu đồ | khung Trợ lý AI
# ---------------------------------------------------------------------------
st.markdown(f'<div class="olist_header"><div class="olist_logo"><i style="height:5px"></i><i style="height:8px">'
            f'</i><i style="height:11px"></i></div><div class="olist_ten">Olist BI / {q.TRANG[trang].ten}</div>'
            f'<div class="olist_ngay"><b>▦</b> 01/2017 – 08/2018</div></div>', unsafe_allow_html=True)

kpi = _kpi(trang, bl)
st.markdown(_the_kpi(trang, bl), unsafe_allow_html=True)

cot_db, cot_ai = st.container(), st.container()

with cot_db:
    hang = st.columns(2, gap="small") + st.columns(2, gap="small")
    for cot, m in zip(hang, ma_cua_trang):
        bd = q.BIEU_DO[m]
        with cot, st.container(key=f"the_{m}"):
            trai, phai = st.columns([1.9, 1], vertical_alignment="top")
            ten, phu = TIEU_DE[m]
            df, tt = _so_lieu(m, bl)
            phu = phu(tt) if phu and not df.empty else ""
            trai.markdown(f'<p class="tieu_de_the">{html.escape(ten)}</p>'
                          + (f'<p class="phu_the">{html.escape(phu)}</p>' if phu else ""), unsafe_allow_html=True)
            dang = st.session_state.mo_ai and m == ma and st.session_state.pham_vi == "bieu_do"
            if phai.button("Đang hỏi AI" if dang else "Hỏi AI", key=f"hoi_{m}", width="content",
                           icon=":material/radio_button_checked:" if dang else ":material/auto_awesome:"):
                st.session_state.bieu_do, st.session_state.pham_vi, st.session_state.mo_ai = m, "bieu_do", True
                st.rerun()
            if df.empty:
                st.info(tt.get("ghi_chu", "Không có dữ liệu với bộ lọc này"))
            elif m == "Q6_2":
                _bang_q6(df)
            else:
                st.plotly_chart(_ve(m, df, tt), width="stretch", key=f"ve_{m}", config={"displayModeBar": False})

TEN_NGAN = {  # nhãn ngắn của nút chuyển nhanh trong khung AI (không dùng mã Q)
    "Q1_1": "Doanh thu", "Q1_2": "Đơn & AOV", "Q2_1": "Top danh mục", "Q2_2": "Top bang",
    "Q3_1": "Trễ theo tháng", "Q3_2": "Trễ theo bang", "Q4_1": "Điểm theo mức trễ", "Q4_2": "Trễ & điểm",
    "Q5_1": "Khâu bàn giao", "Q5_2": "Bàn giao & vận chuyển", "Q6_1": "Người bán ≥ 30 đơn", "Q6_2": "Cần xử lý",
}
GOI_Y = {  # câu hỏi gợi ý: bấm là hỏi ngay
    "Q1_1": ["Tháng nào doanh thu cao nhất, vì sao?", "01–08/2018 tăng bao nhiêu so với cùng kỳ?"],
    "Q1_2": ["Doanh thu tăng nhờ số đơn hay giá trị đơn?", "Giá trị đơn TB có ổn định không?"],
    "Q2_1": ["Top 3 danh mục chiếm bao nhiêu % doanh thu?", "Danh mục nào nên ưu tiên đẩy mạnh?"],
    "Q2_2": ["São Paulo chiếm bao nhiêu % doanh thu?", "Doanh thu có quá tập trung ở vài bang không?"],
    "Q3_1": ["Những tháng nào giao trễ vượt 10%?", "Tháng 03/2018 giao trễ bao nhiêu?"],
    "Q3_2": ["Bang nào giao trễ nhiều nhất, có đáng tin không?", "Bao nhiêu bang vượt ngưỡng 10%?"],
    "Q4_1": ["Đơn trễ bị chấm thấp hơn bao nhiêu sao?", "Trễ bao nhiêu ngày thì điểm chạm đáy?"],
    "Q4_2": ["Giao trễ tăng thì điểm có giảm theo không?", "Tháng nào điểm đánh giá thấp nhất?"],
    "Q5_1": ["Bàn giao trễ làm giao trễ tăng bao nhiêu lần?", "Nội bang và liên bang khác nhau thế nào?"],
    "Q5_2": ["Tháng 03/2018 trễ do bàn giao hay vận chuyển?", "Các tháng đột biến khác gì tháng thường?"],
    "Q6_1": ["Bao nhiêu người bán vượt ngưỡng?", "Nhóm vượt ngưỡng chiếm bao nhiêu % doanh thu?"],
    "Q6_2": ["Người bán nào cần xử lý trước nhất, vì sao?", "Lỗi phổ biến nhất là bàn giao trễ hay điểm thấp?"],
    "trang": ["Tóm tắt điểm nổi bật của trang này", "KPI nào đang vượt ngưỡng cảnh báo?"],
    "tat_ca": ["Vấn đề nào đáng lo nhất trên cả dashboard?", "Tóm tắt 3 phát hiện chính cho ban giám đốc"],
}
PHAM_VI = {"bieu_do": ":material/bar_chart: Biểu đồ", "trang": ":material/description: Cả trang",
           "tat_ca": ":material/layers: Tất cả"}


def _chi_so(ma: str, tt: dict) -> str:
    """Con số chính hiện trên thanh ngữ cảnh của khung AI (lấy từ số liệu kết luận của biểu đồ)."""
    try:
        if ma in ("Q1_1", "Q1_2"):
            ck = tt["so_cung_ky"]
            cot = "doanh_thu" if ma == "Q1_1" else "gia_tri_don_tb"
            return f"{'' if ma == 'Q1_1' else 'AOV '}{ck[cot]['tang_truong']:+.1%} so cùng kỳ".replace(".", ",")
        if ma == "Q2_1":
            return f"Top 10 chiếm {q.so_vn(tt['ti_trong_nhom_top10_danh_muc'] * 100, 1)}%"
        if ma == "Q2_2":
            return f"Top 5 chiếm {q.so_vn(tt['ti_trong_nhom_top5_bang'] * 100, 1)}%"
        if ma == "Q3_1":
            return f"{len(tt['thang_vuot_nguong'])} tháng vượt 10%"
        if ma == "Q3_2":
            return f"{tt['so_bang_vuot_nguong']}/{tt['tong_so_bang']} bang vượt 10%"
        if ma == "Q4_1":
            return f"Trễ thấp hơn {q.so_vn(tt['chenh_lech_dung_han_tru_tre_han'], 2)}★"
        if ma == "Q4_2":
            return f"Tương quan {q.so_vn(tt['he_so_tuong_quan_tre_va_diem'], 2)}"
        if ma == "Q5_1":
            return f"Bàn giao trễ: gấp {q.so_vn(tt['ban_giao_tre_gap_so_lan'], 1)} lần"
        if ma == "Q5_2":
            return f"{len(tt['thang_dot_bien_K6_tren_10'])} tháng đột biến"
        return f"{tt['so_nguoi_ban_can_xu_ly']}/{tt['so_nguoi_ban_tu_30_don']} vượt ngưỡng"
    except (KeyError, TypeError, ValueError):
        return ""


if st.button("Trợ lý AI", icon=":material/auto_awesome:", key="mo_tro_ly"):
    st.session_state.mo_ai = True
    st.rerun()

with cot_ai, st.container(key="khung_ai"):
    dich_vu = llm.nha_cung_cap()
    pham_vi = st.session_state.pham_vi
    bd = q.BIEU_DO[ma]
    bang, tom_tat = _so_lieu(ma, bl)
    if pham_vi == "bieu_do":
        goi = q.du_lieu_cho_ai(ma, bl, q.KetQua(bang, tom_tat), kpi)
        ma_log, khoa, nhan_pv = ma, f"bieu_do|{ma}|{bl}", TEN_NGAN[ma]
        ten_pv, chi_so = TIEU_DE[ma][0], _chi_so(ma, tom_tat)
    elif pham_vi == "trang":
        goi = _goi_trang(trang, bl)
        ma_log, khoa, nhan_pv = f"trang{trang}", f"trang|{trang}|{bl}", "Cả trang"
        ten_pv, chi_so = f"Cả trang {q.TRANG[trang].ten}", "Thẻ KPI + 4 biểu đồ"
    else:
        goi = _goi_tat_ca(bl.nam, bl.thang)
        ma_log, khoa, nhan_pv = "tat_ca", f"tat_ca|{bl.nam}|{bl.thang}", "Tất cả"
        ten_pv, chi_so = "Cả dashboard", "3 trang · lọc Năm / Tháng"
    hoi_thoai = st.session_state.setdefault("hoi_thoai", {}).setdefault(khoa, [])

    # 1. Header tối: tên trợ lý + huy hiệu model, nút thông tin / xóa, chọn phạm vi
    with st.container(key="ai_dau"):
        c_ten, c_info, c_xoa, c_dong = st.columns([5.4, 1, 1, 1], gap="small", vertical_alignment="center")
        ten_model = dich_vu[0].model.replace("gemini-", "Gemini ").replace("-flash", " Flash") if dich_vu else "Chưa có key"
        c_ten.markdown(f'<div class="ai_ten"><div class="ai_bieu_tuong">✦</div><div><h2>Trợ lý AI Olist'
                       f'<span class="ai_huy_hieu"><i></i>{html.escape(ten_model)}</span></h2>'
                       f'<p>Kiểm chứng tự động với gói số liệu BI</p></div></div>', unsafe_allow_html=True)
        with c_info.popover("", icon=":material/info:", help="Model AI và số liệu AI đang dùng"):
            if dich_vu:
                st.markdown("**Model:** " + " → dự phòng ".join(f"`{d.model}`" for d in dich_vu))
            else:
                st.warning("Chưa có API key. Thêm `GEMINI_API_KEY` vào file `.env` ở gốc repo rồi tải lại trang.")
            st.caption("AI chỉ dùng số trong gói số liệu chuẩn; mọi con số trong câu trả lời được đối chiếu tự động "
                       "(xanh = AI tự tính đúng, cam = không tìm thấy, cần tự kiểm).")
            if pham_vi == "bieu_do" and not bang.empty:
                an = ["seller_id", "danh_muc_en", "can_xu_ly"] + (["nam", "thang"] if "ky" in bang else [])
                hien = bang.drop(columns=[c for c in an if c in bang])
                hien = hien.assign(**{c: hien[c].map(lambda x, k=q.COT[c][1]: q.dinh_dang(x, k))
                                      for c in hien.columns if c in q.COT and q.COT[c][1] != "chu"})
                st.dataframe(hien.rename(columns={c: q.COT[c][0] for c in hien.columns if c in q.COT}),
                             hide_index=True, height=min(36 * (len(hien) + 1), 280))
            st.json(goi, expanded=False)
        if c_xoa.button("", icon=":material/delete:", key="xoa_chat", help="Làm mới cuộc trò chuyện",
                        disabled=not hoi_thoai):
            hoi_thoai.clear()
            st.rerun()
        if c_dong.button("", icon=":material/close:", key="dong_ai", help="Đóng trợ lý"):
            st.session_state.mo_ai = False
            st.rerun()
        st.segmented_control("Phạm vi hỏi", list(PHAM_VI), format_func=PHAM_VI.get, key="pham_vi", required=True,
                             label_visibility="collapsed", width="stretch")

    # 2. Thanh ngữ cảnh: đang hỏi gì + con số chính + chuyển nhanh biểu đồ + bộ lọc
    with st.container(key="ai_ngu_canh"):
        st.markdown(f'<div class="ai_dong_ngu_canh"><b>{html.escape(ten_pv)}</b>'
                    + (f'<span class="ai_chi_so">{html.escape(chi_so)}</span>' if chi_so else "") + "</div>",
                    unsafe_allow_html=True)
        if pham_vi == "bieu_do":
            def _chon_nhanh():
                st.session_state.bieu_do = st.session_state.chon_nhanh
            st.session_state.chon_nhanh = ma
            st.segmented_control("Chuyển biểu đồ", ma_cua_trang, format_func=TEN_NGAN.get, key="chon_nhanh",
                                 required=True, label_visibility="collapsed", on_change=_chon_nhanh)
        st.markdown(f'<div class="ai_loc">Lọc: <b>{html.escape(bl.mo_ta())}</b></div>', unsafe_allow_html=True)

    # 3. Nút hành động chính
    with st.container(key="ai_nut"):
        nhan_nut = {"bieu_do": "Phân tích & giải thích biểu đồ", "trang": "Tóm tắt cả trang",
                    "tat_ca": "Tóm tắt cả dashboard"}[pham_vi]
        bam_nhanh = st.button(nhan_nut, icon=":material/auto_awesome:", disabled=not dich_vu, width="stretch")

    # 4. Cuộc trò chuyện
    khung_chat = st.container(height=470, autoscroll=True, key="ai_chat")

    # 5. Gợi ý câu hỏi + ô nhập
    with st.container(key="ai_cuoi"):
        st.markdown('<div class="goi_y_dau">Gợi ý câu hỏi đào sâu<span>Bấm để hỏi ngay</span></div>',
                    unsafe_allow_html=True)
        goi_y = GOI_Y[ma if pham_vi == "bieu_do" else pham_vi]
        bam_goi_y = None
        with st.container(horizontal=True, gap="small"):
            for i, cau in enumerate(goi_y):
                if st.button(f"{cau} ↗", key=f"goi_y_{i}", disabled=not dich_vu):
                    bam_goi_y = cau
        cau_hoi = st.chat_input("Hỏi thêm AI về " + {"bieu_do": TIEU_DE[ma][0].lower(), "trang": "trang này",
                                                     "tat_ca": "cả dashboard"}[pham_vi] + "…", disabled=not dich_vu)

    def _hoi_ai(nhan: str, goi_ham) -> None:
        hoi_thoai.append({"role": "user", "content": nhan, "gio": datetime.now().strftime("%H:%M")})
        cho = khung_chat.empty()
        cho.markdown(f'<div class="ai_dang_tai"><div class="xoay">↻</div><div><b>Gemini đang đối chiếu gói số liệu '
                     f'{html.escape(nhan_pv.lower())}…</b><small>Đang kiểm tra chéo các chỉ số với bộ lọc hiện tại</small>'
                     f'</div></div>', unsafe_allow_html=True)
        try:
            tl = goi_ham()
            hoi_thoai.append({"role": "assistant", "content": tl.noi_dung, "tl": tl, "gio": datetime.now().strftime("%H:%M")})
        except llm.LoiAI as e:
            hoi_thoai.append({"role": "assistant", "content": "", "loi": str(e), "gio": datetime.now().strftime("%H:%M")})
        cho.empty()

    if bam_nhanh:
        if pham_vi == "bieu_do":
            _hoi_ai(f"Phân tích & giải thích biểu đồ \"{TIEU_DE[ma][0]}\"", lambda: llm.giai_thich(ma, bl, goi))
        else:
            _hoi_ai(f"Tóm tắt {goi['trang'].lower()}", lambda: llm.tom_tat(ma_log, bl, goi))
    cau = cau_hoi or bam_goi_y
    if cau:
        lich_su = [t for t in hoi_thoai if t["content"]]
        _hoi_ai(cau, lambda: llm.hoi_dap(ma_log, bl, goi, lich_su, cau))

    with khung_chat:
        if not hoi_thoai:
            st.markdown(f'<div class="ai_trong"><div class="o">✦</div><h4>Sẵn sàng phân tích "{html.escape(ten_pv)}"</h4>'
                        '<p>Bấm nút phân tích phía trên hoặc chọn một câu hỏi gợi ý bên dưới để AI bóc tách dữ liệu.</p>'
                        '</div>', unsafe_allow_html=True)
        for i, t in enumerate(hoi_thoai):
            if t["role"] == "user":
                with st.container(key=f"tin_ban_{i}"):
                    st.markdown(f'<div class="tin_dau"><span class="ban">👤 Bạn · {html.escape(nhan_pv)}</span>'
                                f'<span>{t.get("gio", "")}</span></div>', unsafe_allow_html=True)
                    st.markdown(t["content"])
                continue
            with st.container(key=f"tin_ai_{i}"):
                if "loi" in t:
                    st.markdown(f'<div class="tin_dau"><span class="ai">🤖 AI phản hồi · {html.escape(nhan_pv)}</span>'
                                f'<span>{t.get("gio", "")}</span></div>', unsafe_allow_html=True)
                    st.error(f"AI chưa trả lời được: {t['loi']}")
                    continue
                tl = t["tl"]
                tk = tl.thong_ke_so
                if tk["tong_so"] == 0:
                    huy_hieu = '<span class="xac_thuc dat">✓ Không có số cần kiểm</span>'
                elif tk["khong_tim_thay"]:
                    huy_hieu = (f'<span class="xac_thuc can">⚠ {tk["tong_so"] - len(tk["khong_tim_thay"])}/{tk["tong_so"]}'
                                ' số khớp</span>')
                else:
                    huy_hieu = f'<span class="xac_thuc dat">✓ {tk["tong_so"]}/{tk["tong_so"]} số khớp</span>'
                st.markdown(f'<div class="tin_dau"><span class="ai">🤖 AI phản hồi · {html.escape(nhan_pv)}</span>'
                            f'{huy_hieu}</div>', unsafe_allow_html=True)
                st.markdown(kiem_so.to_dam(tl.noi_dung, tl.kiem_so))
                with st.expander("Chi tiết kiểm chứng & log"):
                    st.caption(f"{tk['khop_du_lieu']} số khớp dữ liệu · {tk['tu_tinh_dung']} số AI tự tính đúng (xanh) · "
                               f"{len(tk['khong_tim_thay'])} số không tìm thấy (cam)")
                    st.caption(f"{tl.nha_cung_cap} `{tl.model}` · {tl.token_vao:,} + {tl.token_ra:,} token · "
                               f"log `{tl.file_log}`")
                    if tl.model_loi_truoc:
                        st.caption("Đã chuyển model dự phòng vì: " + " · ".join(tl.model_loi_truoc))
                    for c in tl.cong_cu:
                        st.caption(f"AI lấy thêm số liệu: `lay_so_lieu({c['tham_so']})`")
