"""Hỏi AI về dashboard Olist – app Streamlit đi kèm Power BI; giao diện theo bản thiết kế "Thiết kế lại giao diện AI chatbot".

Thanh bên: chọn trang + bộ lọc (giống slicer). Phần chính: header, hàng thẻ KPI, các biểu đồ của trang (lấy thẳng từ dds
bằng queries.py). Bấm "Hỏi AI" trên thẻ -> chế độ phóng to (bản thiết kế Figma Make mới): bên trái biểu đồ lớn + 3 ô số
nổi bật + nút ‹ › chuyển biểu đồ, bên phải khung Trợ lý AI (hỏi về biểu đồ này / cả trang / toàn báo cáo; nút Giải thích,
câu hỏi có sẵn, Hỏi tiếp, ô chat) và chú mèo đội mũ bông cải ló ra sau mép khung. Số trong câu trả lời được kiểm lại với dữ liệu (kiem_so.py), mỗi lần hỏi lưu log vào ai/outputs/.
Cần GEMINI_API_KEY (và GROQ_API_KEY dự phòng) trong .env – xem llm.py.

Chạy từ gốc repo khi Postgres đang chạy:   streamlit run ai/app.py
Robot "Hỏi AI" trong Power BI mở link dạng:  http://localhost:8501/?bieu_do=Q5_2&nam=2018&thang=3
Tham số link: bieu_do (Q1_1 … Q6_2), nam, thang, vung, bang, vung_nb, bang_nb – thiếu tham số nào thì không lọc theo đó.
Biểu đồ dựng lại theo cấu hình visual trong bản PBIP (kiểu, màu, nhãn, trục Năm → Quý → Tháng, đường ngưỡng).
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import psycopg
import streamlit as st
import streamlit.components.v1 as components
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
    """Giao diện theo bản thiết kế 'Thiết kế lại giao diện AI chatbot' (Figma Make, bản mới): font Lexend, thẻ biểu đồ
    viền mảnh nổi lên khi rê chuột, nút 'Hỏi AI' viên thuốc tím nhạt; chế độ phóng to phủ nền tối; khung Trợ lý AI sáng
    (xanh chanh nhạt -> trắng -> tím nhạt), bong bóng chat, câu trả lời Giải thích chia thẻ; mèo con ló sau khung AI."""
    the_chon = f".st-key-the_{ma_chon}" if dang_hoi_bieu_do else ".khong_co"
    nut_chon = f".st-key-hoi_{ma_chon}" if dang_hoi_bieu_do else ".khong_co"
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700&display=swap');
    .stApp, .stApp p, .stApp div, .stApp label, .stApp button, .stApp input, .stApp textarea, .stApp li,
    .stApp span:not([data-testid="stIconMaterial"]) {{ font-family: 'Lexend', -apple-system, sans-serif; }}
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
    .the_kpi .ten {{ font-size: 13px; opacity: .85; font-weight: 500; }}
    .the_kpi .so {{ font-size: 27px; font-weight: 700; letter-spacing: -.02em; line-height: 1.2; margin: 4px 0; }}
    .the_kpi .ghi {{ font-size: 12px; font-weight: 500; line-height: 1.35; }}

    /* ---------- thẻ biểu đồ (ChartCard của bản thiết kế) ---------- */
    [class*="st-key-the_"] {{ background: #fff; border-radius: 16px; border: 2px solid transparent; padding: 16px 16px 8px;
        box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 0 0 1px rgba(226,232,240,.8); transition: all .2s; }}
    [data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> div > [class*="st-key-the_"]) {{ height: 100%; }}
    [data-testid="stVerticalBlock"] > div:has(> [class*="st-key-the_"]) {{ flex: 1 1 auto; }}
    [class*="st-key-the_"] {{ height: 100%; }}
    [class*="st-key-the_"]:hover {{ transform: translateY(-2px); box-shadow: 0 12px 28px -12px rgba(15,23,42,.18),
        0 0 0 1px #cbd5e1; }}
    {the_chon} {{ border-color: #d9f938; box-shadow: 0 0 0 4px rgba(217,249,56,.25); }}
    .tieu_de_the {{ font-weight: 600; font-size: 14.5px; color: #0f172a; margin: 0; line-height: 1.35; }}
    .stApp p.phu_the {{ font-size: 12.5px !important; line-height: 1.4; color: #64748b; margin: 2px 0 0; }}
    .st-key-the_ban_do {{ padding: 6px 4px; }}
    .bang_pbi {{ overflow-y: auto; margin-top: 4px; }}
    .bang_pbi table {{ width: 100%; border-collapse: collapse; font-size: 11px; line-height: 1.25; color: {DEN}; }}
    .bang_pbi th {{ text-align: left; font-weight: 700; padding: 4px 6px; border-bottom: 1px solid #E2E5EA;
        position: sticky; top: 0; background: #fff; white-space: nowrap; }}
    .bang_pbi th small {{ margin-left: 4px; font-size: 8px; color: {DEN}; }}
    .bang_pbi td {{ padding: 2px 6px; white-space: nowrap; border: none; }}
    .bang_pbi tbody tr:nth-child(even) {{ background: #F3F4F6; }}
    .bang_pbi td.do {{ color: #B8382B; }}
    .bang_pbi td.thanh {{ position: relative; width: 36%; text-align: right; }}
    .bang_pbi td.thanh i {{ position: absolute; left: 0; top: 2px; bottom: 2px; background: {TIM}; }}
    .bang_pbi td.thanh span {{ position: relative; }}
    [class*="st-key-hoi_"] {{ display: flex; justify-content: flex-end; }}
    [class*="st-key-hoi_"] .stButton {{ width: auto; max-width: 100%; }}
    [class*="st-key-hoi_"] button {{ border-radius: 999px; min-height: 28px; padding: 3px 12px; font-size: 11.5px;
        font-weight: 600; background: #eef2ff; color: #4338ca; border: 1px solid #e0e7ff; white-space: nowrap;
        transition: all .2s; max-width: 100%; }}
    [class*="st-key-hoi_"] [data-testid="stIconMaterial"] {{ color: inherit; }}
    [class*="st-key-the_"]:hover [class*="st-key-hoi_"] button, [class*="st-key-hoi_"] button:hover {{
        background: #0f172a; color: #d9f938; border-color: #0f172a; }}
    [class*="st-key-to_"] button {{ background: transparent; border: none; color: #94a3b8; min-height: 28px; height: 28px;
        width: 28px; padding: 0; opacity: 0; transition: opacity .2s; }}
    [class*="st-key-the_"]:hover [class*="st-key-to_"] button {{ opacity: 1; }}
    [class*="st-key-to_"] button:hover {{ color: #0f172a; background: transparent; }}
    .pt_phim {{ text-align: right; font-size: 11px; color: #94a3b8; }}
    /* tooltip Plotly bo góc + có lề như bản thiết kế: viền tròn dày cùng màu nền, đổ bóng */
    .stApp .hoverlayer .hovertext path {{ stroke: #0f172a !important; stroke-width: 16px !important;
        stroke-linejoin: round; }}
    .stApp .hoverlayer .hovertext {{ filter: drop-shadow(0 10px 18px rgba(15,23,42,.28)); }}
    .stApp .hoverlayer .hovertext text {{ font-family: 'Lexend', sans-serif !important; }}
    .pt_phim kbd {{ font-family: inherit; font-size: 10.5px; border: 1px solid #e2e8f0; border-radius: 4px; padding: 0 4px;
        color: #64748b; background: #fff; }}
    {nut_chon} button {{ background: #0f172a; color: #d9f938; border-color: #0f172a;
        box-shadow: 0 0 0 3px rgba(217,249,56,.35); }}
    {nut_chon} [data-testid="stIconMaterial"] {{ color: #d9f938; animation: nhay 1.4s ease-in-out infinite; }}
    @keyframes nhay {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}

    /* ---------- chế độ phóng to + khung Trợ lý AI (bản thiết kế Figma Make mới) ---------- */
    .st-key-lop_phu {{ --rong_ai: clamp(420px, 34vw, 640px);  /* độ rộng khung AI co giãn theo màn hình */
        position: fixed; inset: 0; z-index: 999995; padding: 24px; gap: 64px !important;
        flex-wrap: nowrap !important; align-items: stretch !important; background: rgba(2,6,23,.55);
        backdrop-filter: blur(3px); animation: hien .25s ease-out both; }}
    @keyframes hien {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .st-key-lop_phu > div:has(.meo) {{ position: absolute; width: 0; height: 0; overflow: visible; }}
    /* Streamlit bọc mỗi container trong 1 stLayoutWrapper: đặt kích thước trên thẻ bọc */
    .st-key-lop_phu > div:has(> .st-key-o_phong_to) {{ flex: 1 1 0 !important; min-width: 0; }}
    .st-key-lop_phu > div:has(> .st-key-khung_ai) {{ flex: 0 0 var(--rong_ai) !important; max-width: var(--rong_ai); }}
    .st-key-lop_phu > div:has(> .st-key-khung_ai) > .st-key-khung_ai,
    .st-key-lop_phu > div:has(> .st-key-o_phong_to) > .st-key-o_phong_to {{ width: 100% !important; height: 100%;
        flex: 1 1 auto !important; }}
    .st-key-khung_ai > div:has(> .st-key-ai_chat) {{ flex: 1 1 0 !important; min-height: 0; }}
    .st-key-khung_ai > div:has(> .st-key-ai_dau), .st-key-khung_ai > div:has(> .st-key-ai_cuoi) {{ flex: 0 0 auto !important; }}
    .st-key-ai_mo_dau, .st-key-ai_tiep, [class*="st-key-tin_ai_"] {{ margin-left: 38px !important;
        width: calc(100% - 38px) !important; box-sizing: border-box; }}
    .st-key-ai_dau [data-testid="stPopoverButton"] > div > div:last-child {{ display: none; }}
    .st-key-o_phong_to {{ min-width: 0; background: #fff; border-radius: 16px;
        padding: 22px 24px 14px !important; overflow-y: auto; gap: .8rem !important;
        box-shadow: 0 24px 60px -12px rgba(15,23,42,.45), 0 0 0 2px #d9f938;
        animation: phong_to .32s cubic-bezier(.16,1,.3,1) both; }}
    @keyframes phong_to {{ from {{ opacity: 0; transform: scale(.94) translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
    .pt_dau {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
    .pt_dang_hoi {{ display: inline-flex; align-items: center; gap: 6px; background: #0f172a; color: #d9f938;
        border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 600; }}
    .pt_dang_hoi i, .the_dang_hoi i {{ width: 8px; height: 8px; border-radius: 50%; background: #d9f938;
        box-shadow: 0 0 0 0 rgba(217,249,56,.7); animation: nhip 1.4s ease-out infinite; }}
    @keyframes nhip {{ 0% {{ box-shadow: 0 0 0 0 rgba(217,249,56,.7); }} 100% {{ box-shadow: 0 0 0 8px rgba(217,249,56,0); }} }}
    .pt_so_thu_tu {{ font-size: 11px; font-weight: 500; color: #94a3b8; }}
    .stApp h2.pt_ten {{ font-size: 23px !important; font-weight: 700 !important; letter-spacing: -.02em; color: #0f172a;
        padding: 0 !important; margin: 0 !important; line-height: 1.3; }}
    .stApp p.pt_phu {{ font-size: 13px !important; color: #64748b; margin: 2px 0 0; }}
    .st-key-pt_nut button {{ min-height: 36px; border-radius: 12px; border: 1px solid #e2e8f0; background: #fff;
        color: #475569; padding: 0 10px; font-size: 12px; font-weight: 600; }}
    .st-key-pt_nut button:hover {{ background: #f1f5f9; color: #0f172a; border-color: #e2e8f0; }}
    .st-key-thu_nho button {{ background: #f1f5f9; border-color: #f1f5f9; color: #334155; }}
    .pt_o_so {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
    .pt_o_so div {{ border-radius: 12px; padding: 10px 14px; border: 1px solid #e2e8f0; background: #f8fafc; }}
    .pt_o_so div.chanh {{ background: #d9f938; border-color: #d9f938; }}
    .pt_o_so span {{ display: block; font-size: 11px; color: #64748b; }}
    .pt_o_so div.chanh span {{ color: #1e293b; }}
    .pt_o_so b {{ display: block; font-size: 16px; font-weight: 700; letter-spacing: -.01em; color: #0f172a; }}

    .st-key-khung_ai {{ background: #fff;
        border-radius: 28px; overflow: hidden; position: relative; z-index: 2; gap: 0 !important;
        display: flex; flex-direction: column; box-shadow: 0 30px 70px -20px rgba(15,23,42,.5), 0 0 0 1px rgba(15,23,42,.05);
        animation: truot_vao .38s cubic-bezier(.16,1,.3,1) .06s both; }}
    @keyframes truot_vao {{ from {{ transform: translateX(32px); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
    .st-key-mo_tro_ly {{ position: fixed; right: 22px; bottom: 22px; z-index: 999980; }}
    .st-key-mo_tro_ly button {{ background: #0f172a; color: #d9f938; border: none; border-radius: 999px; padding: 10px 18px;
        font-size: 13px; font-weight: 600; box-shadow: 0 10px 30px -6px rgba(15,23,42,.45), 0 0 0 3px rgba(217,249,56,.35); }}
    .st-key-mo_tro_ly button:hover {{ background: #1e1b4b; color: #d9f938; }}

    /* header sáng: xanh chanh nhạt -> trắng -> tím nhạt */
    .st-key-ai_dau {{ background: linear-gradient(135deg, #f4fdcc 0%, #ffffff 50%, #eef2ff 100%); padding: 16px 20px !important;
        position: relative; overflow: hidden; gap: .55rem !important; flex: 0 0 auto; }}
    .st-key-ai_dau::before {{ content: ""; position: absolute; right: -48px; top: -64px; width: 160px; height: 160px;
        border-radius: 50%; background: rgba(199,210,254,.4); filter: blur(40px); pointer-events: none; }}
    .ai_ten {{ display: flex; align-items: center; gap: 12px; }}
    .ai_bieu_tuong {{ position: relative; width: 44px; height: 44px; border-radius: 16px; background: #0f172a; color: #d9f938;
        display: flex; align-items: center; justify-content: center; font-size: 19px; flex-shrink: 0;
        box-shadow: 0 10px 15px -3px rgba(15,23,42,.2); }}
    .ai_bieu_tuong i {{ position: absolute; right: -2px; bottom: -2px; width: 14px; height: 14px; border-radius: 50%;
        background: #34d399; border: 2.5px solid #fff; box-sizing: border-box; }}
    .ai_ten h2 {{ font-size: 15px !important; font-weight: 600 !important; color: #0f172a !important; margin: 0 !important;
        padding: 0 !important; line-height: 1.25; }}
    .ai_ten p {{ font-size: 11.5px !important; color: #64748b; margin: 2px 0 0 !important; white-space: nowrap; }}
    .st-key-ai_dau [data-testid="stPopover"] button, .st-key-lam_moi button, .st-key-dong_ai button {{
        background: transparent; border: none; color: #64748b; min-height: 32px; height: 32px; width: 32px;
        padding: 0; border-radius: 12px; }}
    .st-key-ai_dau [data-testid="stPopover"] button:hover, .st-key-lam_moi button:hover, .st-key-dong_ai button:hover {{
        background: #fff; color: #0f172a; }}
    .ai_hoi_ve {{ font-size: 11px; font-weight: 500; color: #64748b; margin: 2px 0 -2px; }}
    .st-key-ai_dau [data-testid="stMarkdownContainer"], .st-key-ai_cuoi [data-testid="stMarkdownContainer"],
    .st-key-o_phong_to [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    .st-key-pham_vi [data-testid="stButtonGroup"] {{ background: rgba(255,255,255,.8); border-radius: 16px; padding: 4px;
        width: 100%; box-shadow: 0 1px 2px rgba(15,23,42,.05), 0 0 0 1px rgba(226,232,240,.7); }}
    .st-key-pham_vi [data-testid="stButtonGroup"] > div {{ width: 100%; display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }}
    .st-key-pham_vi button {{ background: transparent !important; border: none !important; color: #475569 !important;
        border-radius: 12px !important; font-size: 12px; font-weight: 500; min-height: 30px; width: 100%;
        padding: 2px 4px !important; white-space: nowrap; }}
    .st-key-pham_vi button:hover {{ background: #f1f5f9 !important; color: #0f172a !important; }}
    .st-key-pham_vi button[data-testid*="Active"] {{ background: #0f172a !important; color: #fff !important;
        box-shadow: 0 1px 2px rgba(15,23,42,.1); }}
    .ai_chip_hang {{ display: flex; flex-wrap: wrap; gap: 6px; font-size: 11px; }}
    .ai_chip {{ display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 4px 10px; background: #fff;
        box-shadow: 0 0 0 1px #e2e8f0; color: #334155; font-weight: 500; max-width: 100%; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap; }}
    .ai_chip .bt {{ color: #6366f1; font-weight: 700; }}
    .ai_chip.chanh {{ background: #ecfaa8; color: #365314; font-weight: 600; box-shadow: none; }}
    .ai_chip.loc {{ color: #64748b; font-weight: 400; }}

    /* cuộc trò chuyện */
    .st-key-ai_chat {{ background: rgba(248,250,252,.7); height: 100% !important; min-height: 0;
        border: none !important; border-radius: 0 !important; }}
    .st-key-ai_chat > div {{ padding: 16px !important; }}
    .st-key-ai_chat [data-testid="stVerticalBlock"] {{ gap: 1rem; }}
    .st-key-ai_chat [data-testid="stMarkdownContainer"], .st-key-ai_chat [data-testid="stElementContainer"] {{ margin-bottom: 0 !important; }}
    .ai_hang {{ display: flex; align-items: flex-start; gap: 10px; animation: hien .25s ease-out both; }}
    .ai_anh {{ width: 28px; height: 28px; border-radius: 12px; background: #0f172a; color: #d9f938; display: flex;
        align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; margin-top: 2px; }}
    .ai_bong, [class*="st-key-tin_ai_"] {{ background: #fff; border-radius: 20px; border-top-left-radius: 6px;
        padding: 12px 14px !important; box-shadow: 0 1px 2px rgba(15,23,42,.05), 0 0 0 1px rgba(226,232,240,.7);
        font-size: 13px; line-height: 1.6; color: #334155; flex: 1; min-width: 0; }}
    [class*="st-key-tin_ai_"] {{ position: relative; overflow: visible !important; gap: .4rem !important;
        width: auto !important; animation: hien .25s ease-out both; }}
    [class*="st-key-tin_ai_"]::before {{ content: "✦"; position: absolute; left: -38px; top: 2px; width: 28px; height: 28px;
        border-radius: 12px; background: #0f172a; color: #d9f938; display: flex; align-items: center; justify-content: center;
        font-size: 13px; }}
    [class*="st-key-tin_ai_"] p, [class*="st-key-tin_ai_"] li {{ font-size: 12.5px; line-height: 1.6; color: #475569; }}
    [class*="st-key-tin_ai_"] p:first-child strong {{ color: #0f172a; }}
    [class*="st-key-tin_ai_"] h1, [class*="st-key-tin_ai_"] h2, [class*="st-key-tin_ai_"] h3 {{ font-size: 12.5px !important;
        font-weight: 600; color: #0f172a; padding: 6px 0 2px !important; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] {{ border-top: 1px solid #f1f5f9; padding-top: 8px; margin-top: 2px; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] details {{ border: none; background: transparent; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] summary {{ display: inline-flex; width: auto; padding: 4px 10px;
        border-radius: 999px; background: #ecfdf5; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] summary p {{ font-size: 11px; font-weight: 500; color: #047857; }}
    [class*="st-key-tin_ai_"]:has(.co_so_cam) [data-testid="stExpander"] summary {{ background: #fffbeb; }}
    [class*="st-key-tin_ai_"]:has(.co_so_cam) [data-testid="stExpander"] summary p {{ color: #b45309; }}
    [class*="st-key-tin_ai_"] [data-testid="stExpander"] [data-testid="stCaptionContainer"] p {{ font-size: 10.5px; color: #94a3b8; }}
    [class*="st-key-xem_"] button {{ background: #f8fafc; border: none; border-radius: 16px; text-align: left;
        justify-content: flex-start; font-size: 12px; font-weight: 600; color: #0f172a; min-height: 36px; }}
    [class*="st-key-xem_"] button:hover {{ background: #eef2ff; color: #4338ca; }}
    [class*="st-key-xem_"] button > div, [class*="st-key-xem_"] button [data-testid="stMarkdownContainer"] {{
        justify-content: flex-start; width: 100%; text-align: left; }}
    .ban_hang {{ display: flex; justify-content: flex-end; animation: hien .25s ease-out both; margin-bottom: 1rem; }}
    .ban_bong {{ max-width: 82%; background: #0f172a; color: #fff; border-radius: 20px; border-bottom-right-radius: 6px;
        padding: 10px 14px; font-size: 13px; line-height: 1.55; box-shadow: 0 1px 2px rgba(15,23,42,.1); }}
    .ai_loi {{ color: #b91c1c; font-size: 12.5px; }}
    .ai_doc {{ display: flex; align-items: center; gap: 8px; font-size: 12px !important; color: #64748b !important; }}
    .ai_doc span {{ display: inline-flex; gap: 4px; }}
    .ai_doc i {{ width: 8px; height: 8px; border-radius: 50%; background: #818cf8; animation: nay .9s infinite; }}
    .ai_doc i:nth-child(2) {{ animation-delay: .14s; }}
    .ai_doc i:nth-child(3) {{ animation-delay: .28s; }}
    @keyframes nay {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-5px); }} }}

    /* bong bóng 'Giải thích biểu đồ' (InsightBubble) */
    .ib_nhan {{ display: inline-flex; align-items: center; gap: 4px; background: #0f172a; color: #d9f938; border-radius: 999px;
        padding: 2px 9px; font-size: 10.5px; font-weight: 500; margin-bottom: 8px; }}
    .ib_chinh {{ font-size: 13.5px; font-weight: 600; line-height: 1.6; color: #0f172a; }}
    .ib_muc {{ margin-top: 12px; font-size: 11px; font-weight: 600; color: #64748b; }}
    .ib_the {{ background: #f8fafc; border-radius: 16px; padding: 10px; margin-top: 6px; }}
    .ib_the_dau {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
    .ib_the_dau b {{ font-size: 12.5px; color: #0f172a; font-weight: 600; }}
    .ib_the p, .ib_lam p {{ margin: 2px 0 0 !important; font-size: 12px !important; line-height: 1.6; color: #475569 !important; }}
    .ib_tag {{ border-radius: 999px; padding: 2px 8px; font-size: 10.5px; font-weight: 600; flex-shrink: 0; white-space: nowrap; }}
    .tag_chanh {{ background: #ecfaa8; color: #365314; }}
    .tag_tim {{ background: #eef2ff; color: #4338ca; }}
    .tag_xanh {{ background: #ecfdf5; color: #047857; }}
    .tag_vang {{ background: #fffbeb; color: #b45309; }}
    .ib_lam {{ list-style: none; padding: 0; margin: 6px 0 0; }}
    .ib_lam li {{ display: flex; gap: 10px; margin-bottom: 8px; }}
    .ib_lam li i {{ font-style: normal; width: 20px; height: 20px; border-radius: 50%; background: #d9f938; color: #0f172a;
        font-size: 10.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }}
    .ib_lam b {{ color: #0f172a; }}
    .so_xanh {{ background: rgba(28,131,225,.14); border-radius: 4px; padding: 0 2px; }}
    .so_cam {{ background: rgba(255,164,33,.22); border-radius: 4px; padding: 0 2px; }}

    /* lời mở đầu: nút Giải thích lớn + câu hỏi có sẵn */
    .st-key-ai_mo_dau, .st-key-ai_tiep {{ gap: .55rem !important; animation: hien .25s ease-out both; }}
    .st-key-nut_giai_thich button {{ background: linear-gradient(135deg, #4f46e5, #8b5cf6); color: #fff; border: none;
        border-radius: 16px; padding: 12px 14px; min-height: 66px; justify-content: flex-start; text-align: left;
        box-shadow: 0 10px 15px -3px rgba(99,102,241,.25); transition: transform .2s; }}
    .st-key-nut_giai_thich button:hover {{ color: #fff; transform: translateY(-2px); border: none; }}
    .st-key-nut_giai_thich button [data-testid="stIconMaterial"] {{ width: 40px; height: 40px; border-radius: 12px;
        background: rgba(255,255,255,.15); color: #d9f938; display: flex; align-items: center; justify-content: center;
        font-size: 20px; margin-right: 4px; }}
    .st-key-nut_giai_thich button p {{ font-size: 13.5px !important; font-weight: 600 !important; text-align: left; }}
    .st-key-nut_giai_thich button p::after {{ content: "Xu hướng chính, điểm nổi bật và việc nên làm"; display: block;
        font-size: 11.5px; font-weight: 400; color: #e0e7ff; }}
    .st-key-nut_giai_thich button::after, [class*="st-key-goi_y_"] button::after {{ content: "→"; margin-left: auto;
        padding-left: 8px; font-size: 14px; }}
    .ai_nho {{ font-size: 11px; font-weight: 500; color: #64748b; margin-bottom: -4px; }}
    .st-key-nut_giai_thich button > div, [class*="st-key-goi_y_"] button > div {{ flex: 1 1 auto;
        justify-content: flex-start; text-align: left; }}
    [class*="st-key-goi_y_"] button {{ background: #fff; border: none; border-radius: 16px; padding: 8px 12px 8px 8px;
        min-height: 48px; justify-content: flex-start; text-align: left; font-size: 12.5px; color: #334155;
        box-shadow: 0 1px 2px rgba(15,23,42,.05), 0 0 0 1px rgba(226,232,240,.8); }}
    [class*="st-key-goi_y_"] button:hover {{ color: #0f172a; box-shadow: 0 0 0 1px #a5b4fc; border: none; }}
    [class*="st-key-goi_y_"] button::after {{ color: #cbd5e1; }}
    [class*="st-key-goi_y_"] button:hover::after {{ color: #6366f1; }}
    [class*="st-key-goi_y_"] button p {{ font-size: 12.5px !important; text-align: left; }}
    [class*="st-key-goi_y_"] [data-testid="stIconMaterial"] {{ width: 32px; height: 32px; border-radius: 12px; display: flex;
        align-items: center; justify-content: center; font-size: 17px; flex-shrink: 0; margin-right: 4px; }}
    .st-key-goi_y_0 [data-testid="stIconMaterial"] {{ background: #f1fcc2; color: #3f6212; }}
    .st-key-goi_y_1 [data-testid="stIconMaterial"] {{ background: #eef2ff; color: #4f46e5; }}
    .st-key-goi_y_2 [data-testid="stIconMaterial"] {{ background: #fdf2f8; color: #db2777; }}
    .ai_dam_bao {{ display: flex; gap: 6px; font-size: 11px; line-height: 1.6; color: #94a3b8; }}
    .ai_dam_bao b {{ color: #10b981; }}
    .st-key-ai_tiep button {{ background: #fff; border: none; border-radius: 999px; padding: 5px 12px; min-height: 0;
        font-size: 11.5px; color: #475569; box-shadow: 0 0 0 1px #e2e8f0; }}
    .st-key-ai_tiep button p {{ font-size: 11.5px !important; }}
    .st-key-ai_tiep button:hover {{ color: #4338ca; box-shadow: 0 0 0 1px #a5b4fc; border: none; }}
    .st-key-chip_giai_thich button {{ background: #4f46e5; color: #fff; box-shadow: none; font-weight: 500; }}
    .st-key-chip_giai_thich button:hover {{ background: #4338ca; color: #fff; box-shadow: none; }}

    /* ô nhập */
    .st-key-ai_cuoi {{ background: #fff; border-top: 1px solid #f1f5f9; padding: 12px 16px 10px !important; gap: 6px !important;
        flex: 0 0 auto; }}
    .st-key-ai_cuoi [data-testid="stChatInput"] {{ background: rgba(241,245,249,.8); border: 1px solid transparent; border-radius: 16px; }}
    .st-key-ai_cuoi [data-testid="stChatInput"]:focus-within {{ background: #fff; border-color: #a5b4fc; }}
    .st-key-ai_cuoi [data-testid="stChatInput"] textarea {{ font-size: 13px; }}
    .st-key-ai_cuoi [data-testid="stChatInputSubmitButton"] {{ background: #d9f938; color: #0f172a; border-radius: 12px;
        box-shadow: 0 1px 2px rgba(15,23,42,.1); }}
    .st-key-ai_cuoi [data-testid="stChatInputSubmitButton"]:disabled {{ background: #e2e8f0; color: #94a3b8; box-shadow: none; }}
    .st-key-ai_cuoi [data-testid="stChatInput"] {{ position: relative; padding-left: 26px; }}
    .st-key-ai_cuoi [data-testid="stChatInput"]::before {{ content: ""; position: absolute; left: 14px; top: 50%; width: 16px;
        z-index: 2; pointer-events: none;
        height: 16px; transform: translateY(-50%); background: no-repeat center / 16px url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7.9 20A9 9 0 1 0 4 16.1L2 22Z'/%3E%3C/svg%3E"); }}
    .ai_chan {{ text-align: center; font-size: 10.5px; color: #94a3b8; }}
    .hd_tieu_de {{ font-size: 13px; font-weight: 600; color: #0f172a; margin-bottom: 8px; }}
    .hd_buoc {{ list-style: none; padding: 0; margin: 0; }}
    .hd_buoc li {{ display: flex; gap: 10px; margin-bottom: 10px; }}
    .hd_buoc i {{ font-style: normal; width: 24px; height: 24px; border-radius: 50%; background: #d9f938; color: #0f172a;
        font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
    .hd_buoc b {{ display: block; font-size: 12.5px; color: #0f172a; }}
    .hd_buoc span {{ font-size: 11.5px; color: #64748b; line-height: 1.5; }}
    .hd_model {{ background: #f8fafc; border-radius: 12px; padding: 8px 12px; font-size: 10.5px; color: #64748b; }}

    /* mèo con đội mũ bông cải: lớp đầu nằm dưới khung AI, lớp chân + bong bóng nằm trên */
    .meo_lop {{ position: fixed; top: 44px; right: calc(var(--rong_ai) - 6px); width: 110px; height: 130px; pointer-events: none; }}
    .meo_sau {{ z-index: 1; }}
    .meo_truoc {{ z-index: 3; }}
    .meo svg {{ width: 100%; height: 100%; overflow: visible; position: absolute; inset: 0; }}
    .meo_sau svg {{ filter: drop-shadow(0 6px 10px rgba(15,23,42,.28)); }}
    .meo_vao {{ width: 100%; height: 100%; animation: meo_lo_ra .7s cubic-bezier(.34,1.56,.64,1) .45s both; }}
    @keyframes meo_lo_ra {{ from {{ transform: translateX(56px); }} to {{ transform: none; }} }}
    .meo_lac {{ transform-box: view-box; transform-origin: 80px 110px; animation: meo_lac 3.4s ease-in-out 1.2s infinite; }}
    @keyframes meo_lac {{ 0%, 100% {{ transform: rotate(0); }} 50% {{ transform: rotate(-4deg); }} }}
    .meo_chop {{ transform-box: fill-box; transform-origin: center; animation: meo_chop 4.5s ease-in-out infinite; }}
    @keyframes meo_chop {{ 0%, 92%, 100% {{ transform: scaleY(1); }} 95% {{ transform: scaleY(.1); }} }}
    .meo_tay_vao {{ animation: meo_tay .35s ease-out .95s both; }}
    @keyframes meo_tay {{ from {{ opacity: 0; transform: translateX(-6px); }} to {{ opacity: 1; transform: none; }} }}
    .meo_vo {{ transform-box: view-box; transform-origin: 80px 62px; animation: meo_vo 2.6s ease-in-out 1.4s infinite; }}
    @keyframes meo_vo {{ 0%, 60%, 100% {{ transform: rotate(0); }} 68% {{ transform: rotate(-8deg); }} 76% {{ transform: rotate(3deg); }}
        84% {{ transform: rotate(-6deg); }} }}
    .meo_gian {{ display: none; }}
    .meo_no {{ transform-box: fill-box; transform-origin: center; animation: meo_no .6s ease-in-out infinite; }}
    @keyframes meo_no {{ 0%, 100% {{ transform: scale(1); }} 50% {{ transform: scale(1.15); }} }}
    .meo_cham {{ position: absolute; left: 34px; top: 14px; width: 46px; height: 78px; border-radius: 999px; border: none;
        background: transparent; cursor: pointer; pointer-events: auto; padding: 0; }}
    .meo_cham:focus {{ outline: none; }}
    .meo_bong {{ position: absolute; right: 36px; top: 118px; width: max-content; max-width: 180px; border-radius: 16px;
        border-top-right-radius: 6px; padding: 8px 12px; font-size: 11.5px; font-weight: 600; line-height: 1.35; color: #fff;
        background: #0f172a; box-shadow: 0 10px 15px -3px rgba(15,23,42,.25); transform-origin: top right;
        animation: meo_gioi_thieu 4.5s ease forwards; transition: opacity .3s, transform .3s; }}
    .meo_bong::after {{ content: "Meo~ hỏi trợ lý ở đây nè!"; animation: meo_loi 16s steps(1) 4.5s infinite; }}
    @keyframes meo_gioi_thieu {{ 0%, 90% {{ opacity: 1; transform: scale(1); }} 100% {{ opacity: 0; transform: scale(.9); }} }}
    @keyframes meo_loi {{ 0% {{ content: "Bấm \\"Giải thích biểu đồ này\\" thử xem!"; }} 25% {{ content: "Dùng nút ‹ › để đổi biểu đồ nha"; }}
        50% {{ content: "Dấu tích xanh là số liệu đã khớp đó"; }} 75% {{ content: "Meo~ hỏi trợ lý ở đây nè!"; }} }}
    .meo_cham:hover ~ .meo_bong {{ opacity: 1; transform: scale(1); animation: none; }}
    .meo_cham:focus ~ .meo_gian {{ display: block; }}
    .meo_cham:focus ~ .meo_bong {{ opacity: 1; transform: scale(1); animation: meo_rung .18s linear 6; background: #f43f5e; }}
    .meo_cham:focus ~ .meo_bong::after {{ content: "Grừ grừ!! Đừng chọc mình!"; animation: none; }}
    @keyframes meo_rung {{ 0%, 100% {{ transform: translateX(0) rotate(0); }} 25% {{ transform: translateX(-2px) rotate(-2deg); }}
        75% {{ transform: translateX(2px) rotate(2deg); }} }}
    @media (max-width: 1100px) {{ .meo {{ display: none; }} }}
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
    for k in ("vung", "bang", "vung_nb", "bang_nb"):
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
    for k in ("nam", "thang", "vung", "bang", "vung_nb", "bang_nb"):
        st.session_state[k] = TAT_CA


c_loc, c_dat = st.sidebar.columns([3, 2], vertical_alignment="bottom")
c_loc.markdown('<div class="sb_muc">BỘ LỌC</div>', unsafe_allow_html=True)
if any(st.session_state.get(k, TAT_CA) != TAT_CA for k in ("nam", "thang", "vung", "bang", "vung_nb", "bang_nb")):
    c_dat.button("Đặt lại", icon=":material/restart_alt:", key="dat_lai", on_click=_dat_lai)
try:
    lc = _lua_chon()
except psycopg.OperationalError:
    st.error("Không kết nối được Postgres. Mở Docker Desktop rồi chạy `docker compose up -d` ở thư mục repo.")
    st.stop()
co_loc = q.TRANG[trang].bo_loc
loc = {"nam": _chon("Năm", [2017, 2018], "nam"), "thang": _chon("Tháng", list(range(1, 13)), "thang")}
if "vung" in co_loc:
    loc["vung"] = _chon("Vùng", lc["vung"], "vung")
if "bang" in co_loc:
    bang_chon = (lc["bang_theo_vung"].get(loc["vung"], []) if loc.get("vung")
                 else sorted(b for ds in lc["bang_theo_vung"].values() for b in ds))
    loc["bang"] = _chon("Bang", bang_chon, "bang")
if "vung_nb" in co_loc:
    loc["vung_nb"] = _chon("Vùng người bán", lc["vung_nb"], "vung_nb")
if "bang_nb" in co_loc:
    loc["bang_nb"] = _chon("Bang người bán", lc["bang_nb_theo_vung"].get(loc.get("vung_nb"), lc["bang_nb"])
                           if loc.get("vung_nb") else lc["bang_nb"], "bang_nb")
bl = q.bo_loc_cua_trang(trang, **loc)


# ---------------------------------------------------------------------------
# Biểu đồ: dựng lại theo đúng cấu hình visual trong bản PBIP (bi-pbip/…Report/definition/pages)
# Màu: theme "Olist Lime Soft" (powerbi/theme_olist.json) + các measure màu của report.
# ---------------------------------------------------------------------------
CHANH_PBI, TIM_NHAT, TIM_DAM_PBI, TIM_DEN = "#C8E62A", "#D3DBFC", "#6F80EC", "#3A47C4"
CHU_TRUC, LUOI_PBI, CHU_NHAN = "#8B9099", "#EEF0F3", "#4A4E57"
# Hộp tooltip kiểu bản thiết kế: nền tối, chữ sáng, font Lexend
TOOLTIP = dict(bgcolor="#0f172a", bordercolor="#0f172a", align="left",
               font=dict(family="Lexend, sans-serif", size=12, color="#f8fafc"))
MAU_NHOM_BANG = {5: TIM_DEN, 4: TIM_DAM_PBI, 3: TIM, 2: TIM_NHAT, 1: TIM_NHAT}  # measure 'Màu tỉ trọng địa lý'

# Bố cục từng trang như Power BI (trang 1280 × 720): (mã, độ rộng visual) theo hàng; chiều cao visual của mỗi hàng
BO_CUC = {1: ([("Q1_1", 487), ("Q1_2", 574)], [("Q2_1", 373), ("ban_do_Q2_2", 602)]),
          2: ([("Q3_1", 531), ("Q3_2", 530)], [("Q4_1", 531), ("Q4_2", 530)]),
          3: ([("Q5_1", 531), ("Q5_2", 530)], [("Q6_1", 531), ("Q6_2", 530)])}
CAO_BIEU_DO = 270  # chiều cao vùng vẽ chung cho mọi thẻ biểu đồ (px)


def _nhom_ti_trong(p: float) -> int:
    """Measure 'Nhóm tỉ trọng bang': 5 nhóm theo % tổng doanh thu."""
    return 5 if p > .12 else 4 if p > .05 else 3 if p > .02 else 2 if p > .01 else 1


def _phu_q4_1(tt, df) -> str:
    """Measure 'Phụ đề điểm theo mức trễ' (bỏ câu "Bấm ↑ để gộp nhóm" – chỉ dùng được trên Power BI)."""
    dung = df[df.ket_qua == "Đúng hạn"]
    tre = df[df.ket_qua == "Trễ hạn"]
    if dung.empty or tre.empty:
        return ""
    diem_tre = (tre.diem_tb * tre.so_don_co_danh_gia).sum() / tre.so_don_co_danh_gia.sum()
    return (f"Đơn trễ {q.so_vn(diem_tre, 2)}★, thấp hơn đơn đúng hạn "
            f"{q.so_vn(dung.diem_tb.iloc[0] - diem_tre, 2)}★")


TIEU_DE = {  # tiêu đề + tiêu đề phụ y như trên Power BI; tiêu đề phụ là hàm (tom_tat, bảng số liệu) hoặc None
    "Q1_1": ("Doanh thu theo tháng", None),
    "Q1_2": ("Số đơn và giá trị đơn trung bình theo tháng", None),
    "Q2_1": ("Top 10 theo doanh thu", lambda tt, df: f"{min(10, len(df))} danh mục dẫn đầu chiếm "
             f"{q.so_vn(tt['ti_trong_nhom_top10_danh_muc'] * 100, 1)}% doanh thu toàn sàn"),
    "Q2_2": ("Top 5 theo doanh thu", lambda tt, df: f"{min(5, len(df))} bang dẫn đầu chiếm "
             f"{q.so_vn(tt['ti_trong_nhom_top5_bang'] * 100, 1)}% doanh thu toàn sàn"),
    "Q3_1": ("Tỉ lệ giao trễ theo tháng", lambda tt, df: "% đơn đã giao nhận sau ngày dự kiến"),
    "Q3_2": ("10 bang giao trễ nhiều nhất", None),
    "Q4_1": ("Điểm đánh giá theo mức trễ", _phu_q4_1),
    "Q4_2": ("Tỉ lệ giao trễ và điểm đánh giá theo tháng",
             lambda tt, df: "Cột: tỉ lệ trễ, đỏ khi trên 10%. Đường: điểm TB (trục phải)"),
    "Q5_1": ("Tỉ lệ giao trễ theo khâu bàn giao", None),
    "Q5_2": ("Bàn giao trễ, thời gian xử lý và vận chuyển theo tháng", None),
    "Q6_1": ("Người bán có ≥ 30 đơn", None),
    "Q6_2": ("10 người bán cần xử lý trước", None),
}


def _pct(v: float, le: int = 1) -> str:
    """Nhãn % như nhãn dữ liệu của Power BI (report dùng định dạng en-US: 6.8%)."""
    return f"{v * 100:.{le}f}%"


def _mo(df) -> list:
    """Độ đậm từng tháng: có lọc tháng thì tháng khác mờ đi (biểu đồ theo tháng không lọc tháng)."""
    return [1 if not bl.thang or int(t) == bl.thang else 0.35 for t in df.thang]


def _ky(df) -> list:
    return [f"Tháng {int(t)}/{int(n)}" for n, t in zip(df.nam, df.thang)]


def _tip(tieu_de: str, dong: list) -> str:
    """Nội dung tooltip kiểu bản thiết kế: tiêu đề xanh chanh in đậm, mỗi dòng '● nhãn   giá trị đậm'.
    dong = [(nhãn, giá trị) hoặc (nhãn, giá trị, màu chấm)]."""
    o = [f"<span style='color:#d9f938'><b>{html.escape(str(tieu_de))}</b></span>"]
    for d in dong:
        mau = "#e2e8f0" if len(d) > 2 and d[2] in (DEN, "#0f172a") else (d[2] if len(d) > 2 else "")  # đen -> sáng trên nền tối
        cham = f"<span style='color:{mau}'>●</span> " if mau else ""
        o.append(f"{cham}<span style='color:#cbd5e1'>{html.escape(d[0])}</span>   <b>{html.escape(str(d[1]))}</b>")
    return "<br>".join(o)


def _truc_ky(fig, df) -> list:
    """Trục 3 tầng Tháng / Quý / Năm có vạch chấm phân cách (Năm → Quý → Tháng, concatenateLabels = false).
    Trả về toạ độ x (0 … n-1) cho các trace."""
    n = len(df)
    x = list(range(n))
    fig.update_xaxes(tickmode="array", tickvals=x, ticktext=[str(int(t)) for t in df.thang], range=[-0.6, n - 0.4],
                     ticks="", showline=False)
    quy = [(int(nm), (int(t) - 1) // 3 + 1) for nm, t in zip(df.nam, df.thang)]

    def nhom(khoa):
        ra, dau = [], 0
        for i in range(1, n + 1):
            if i == n or khoa[i] != khoa[dau]:
                ra.append((dau, i - 1, khoa[dau]))
                dau = i
        return ra

    vach = dict(color="#C9CDD4", width=1, dash="dot")
    for y in (-25, -45, -65):  # vạch ngang dưới hàng tháng, quý, năm
        fig.add_shape(type="line", xref="paper", x0=0, x1=1, yref="paper", ysizemode="pixel", yanchor=0, y0=y, y1=y,
                      line=vach)
    for a, b, (_, qq) in nhom(quy):
        fig.add_annotation(x=(a + b) / 2, y=0, xref="x", yref="paper", yanchor="top", yshift=-27, showarrow=False,
                           text=f"Quý {qq}", font=dict(size=11, color=CHU_TRUC))
        if b < n - 1:
            fig.add_shape(type="line", x0=b + .5, x1=b + .5, xref="x", yref="paper", ysizemode="pixel", yanchor=0,
                          y0=0, y1=-45, line=vach)
    for a, b, nm in nhom([k[0] for k in quy]):
        fig.add_annotation(x=(a + b) / 2, y=0, xref="x", yref="paper", yanchor="top", yshift=-47, showarrow=False,
                           text=str(nm), font=dict(size=11, color=CHU_TRUC))
        if b < n - 1:
            fig.add_shape(type="line", x0=b + .5, x1=b + .5, xref="x", yref="paper", ysizemode="pixel", yanchor=0,
                          y0=0, y1=-65, line=vach)
    fig.update_layout(margin_b=70)
    return x


def _chu_thich(fig, muc: list[tuple[str, str]]) -> None:
    """Chú thích góc trên phải, chấm tròn + chữ như legend Power BI (TopRight, cỡ 8)."""
    fig.add_annotation(x=1, y=1, xref="paper", yref="paper", xanchor="right", yanchor="bottom", yshift=6,
                       showarrow=False, align="right", font=dict(size=11.5, color=CHU_NHAN),
                       text="  ".join(f'<span style="color:{m}">●</span> {html.escape(t)}' for t, m in muc))
    fig.update_layout(margin_t=30)


def _truc_trieu(vmax: float) -> dict:
    """Trục giá trị đơn vị triệu, 1 chữ số thập phân (labelDisplayUnits = 1.000.000, labelPrecision = 1)."""
    buoc = next(b for b in (0.1e6, 0.2e6, 0.5e6, 1e6, 2e6, 5e6) if vmax / b <= 4)
    gia = [i * buoc for i in range(int(vmax // buoc) + 2)]
    return dict(tickmode="array", tickvals=gia, ticktext=[f"{q.so_vn(v / 1e6, 1)} triệu" for v in gia])


def _ve(ma: str, df, tom_tat: dict, cao: int):
    fig = make_subplots(specs=[[{"secondary_y": True}]]) if ma in ("Q1_2", "Q4_2", "Q5_2") else go.Figure()
    if ma == "Q1_1":  # lineChart: đường mượt #121316, vùng #E2FA2C, không marker, trục triệu
        x = _truc_ky(fig, df)
        fig.add_scatter(x=x, y=df.doanh_thu, mode="lines", line=dict(color=DEN, width=2, shape="spline"),
                        fill="tozeroy", fillcolor="rgba(226,250,44,.45)", name="Doanh thu",
                        customdata=[_tip(k, [("Doanh thu", f"{q.so_vn(dt)} BRL", DEN), ("Số đơn", q.so_vn(sd))])
                                    for k, dt, sd in zip(_ky(df), df.doanh_thu, df.so_don)], hovertemplate="%{customdata}<extra></extra>")
        if bl.thang:
            d = [i for i, t in enumerate(df.thang) if int(t) == bl.thang]
            fig.add_scatter(x=d, y=df.doanh_thu.iloc[d], mode="markers", marker=dict(size=8, color=DO),
                            hoverinfo="skip", showlegend=False)
        fig.update_yaxes(rangemode="tozero", **_truc_trieu(df.doanh_thu.max()))
        if cao >= 500:  # chế độ phóng to: đánh dấu đỉnh như bản thiết kế
            i = int(df.doanh_thu.values.argmax())
            fig.add_scatter(x=[i], y=[df.doanh_thu.iloc[i]], mode="markers+text", hoverinfo="skip",
                            marker=dict(size=11, color=DEN, line=dict(color="#d9f938", width=3)),
                            text=[f"<b>Đỉnh {df.doanh_thu.iloc[i] / 1e6:.2f} tr</b>"], textposition="top center",
                            textfont=dict(size=12.5, color=DEN), cliponaxis=False)
    elif ma == "Q1_2":  # combo: cột #A9B8F8 số đơn, đường #121316 giá trị đơn TB có nhãn, trục phải 0–160 "BRL/đơn"
        x = _truc_ky(fig, df)
        fig.add_bar(x=x, y=df.so_don, name="Số đơn", marker=dict(color=TIM, opacity=_mo(df)),
                    customdata=[_tip(k, [("Số đơn", q.so_vn(sd), TIM), ("Giá trị đơn TB", f"{q.so_vn(a, 2)} BRL", DEN),
                                         ("Doanh thu", f"{q.so_vn(dt)} BRL")])
                                for k, sd, a, dt in zip(_ky(df), df.so_don, df.gia_tri_don_tb, df.doanh_thu)],
                    hovertemplate="%{customdata}<extra></extra>")
        fig.add_scatter(x=x, y=df.gia_tri_don_tb, name="Giá trị đơn TB", mode="lines+markers+text",
                        line=dict(color=DEN, width=2), marker=dict(size=5, color=DEN), secondary_y=True,
                        text=[f"{v:.0f}" for v in df.gia_tri_don_tb], textposition="top center",
                        textfont=dict(size=10.5, color=DEN), cliponaxis=False,
                        hoverinfo="skip")
        buoc = 5000 if df.so_don.max() > 5000 else 1000  # trục số đơn bước 5.000 như Power BI
        moc = list(range(0, int(df.so_don.max() // buoc + 1) * buoc + 1, buoc))
        fig.update_yaxes(rangemode="tozero", tickmode="array", tickvals=moc, ticktext=[q.so_vn(v) for v in moc],
                         secondary_y=False)
        fig.update_yaxes(range=[0, 160], tickvals=[0, 100], showgrid=False, title_text="BRL/đơn", secondary_y=True)
        _chu_thich(fig, [("Số đơn", TIM), ("Giá trị đơn TB", DEN)])
    elif ma in ("Q2_1", "Q2_2"):  # clusteredBarChart: nhãn % ở cuối thanh, ẩn trục giá trị, có tiêu đề trục danh mục
        d = df.head(10 if ma == "Q2_1" else 5)
        if ma == "Q2_1":  # measure 'Màu danh mục': 3 danh mục dẫn đầu xanh chanh, còn lại tím
            nhan, mau, truc = list(d.danh_muc_en), [CHANH_PBI if i < 3 else TIM for i in range(len(d))], "Danh mục"
            chi_tiet = [_tip(dm, [("Doanh thu", f"{q.so_vn(dt)} BRL", m), ("Số đơn", q.so_vn(sd)),
                                  ("Tỉ trọng", f"{q.so_vn(p * 100, 2)}%")])
                        for dm, dt, sd, p, m in zip(d.danh_muc, d.doanh_thu, d.so_don, d.ti_trong, mau)]
        else:  # cột state_label "São Paulo (SP)", màu theo 5 nhóm tỉ trọng
            nhan = [f"{t} ({b})" for t, b in zip(d.ten_bang, d.bang)]
            mau, truc = [MAU_NHOM_BANG[_nhom_ti_trong(p)] for p in d.ti_trong], "Bang"
            chi_tiet = [_tip(n, [("Doanh thu", f"{q.so_vn(dt)} BRL", m), ("Số đơn", q.so_vn(sd)),
                                 ("Tỉ trọng", f"{q.so_vn(p * 100, 2)}%")])
                        for n, dt, sd, p, m in zip(nhan, d.doanh_thu, d.so_don, d.ti_trong, mau)]
        fig.add_bar(x=d.ti_trong, y=nhan, orientation="h", marker_color=mau,
                    text=[f"{q.so_vn(v * 100, 2)}%" for v in d.ti_trong],
                    textposition="outside", cliponaxis=False, textfont=dict(size=10.5, color=DEN),
                    customdata=chi_tiet, hovertemplate="%{customdata}<extra></extra>")
        fig.update_yaxes(autorange="reversed", title_text=truc, showgrid=False,
                         title_font=dict(color=DEN, size=12.5, weight="bold"))
        fig.update_xaxes(visible=False, range=[0, d.ti_trong.max() * 1.22])
        fig.update_layout(bargap=0.18 if ma == "Q2_1" else 0.32)
    elif ma == "Q3_1":  # lineChart mượt #121316 + vùng #A9B8F8, đường ngưỡng 10% đỏ nét đứt có nhãn
        x = _truc_ky(fig, df)
        fig.add_scatter(x=x, y=df.ti_le_tre, mode="lines+markers", line=dict(color=DEN, width=2, shape="spline"),
                        marker=dict(size=5, color=DEN, opacity=_mo(df)), fill="tozeroy", fillcolor="rgba(169,184,248,.45)",
                        customdata=[_tip(k, [("Tỉ lệ giao trễ", f"{q.so_vn(v * 100, 2)}%", DO if v > .10 else DEN),
                                             ("Đơn giao trễ", q.so_vn(t)), ("Đơn đã giao", q.so_vn(g))])
                                    for k, v, t, g in zip(_ky(df), df.ti_le_tre, df.don_tre, df.don_da_giao)],
                        hovertemplate="%{customdata}<extra></extra>", name="Tỉ lệ trễ")
        fig.add_hline(y=0.10, line=dict(color=DO, dash="dash", width=1.5), annotation_text="Ngưỡng 10%",
                      annotation_position="top right", annotation_font=dict(size=11, color=DO))
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        if cao >= 500:
            i = int(df.ti_le_tre.values.argmax())
            fig.add_scatter(x=[i], y=[df.ti_le_tre.iloc[i]], mode="markers+text", hoverinfo="skip",
                            marker=dict(size=11, color=DEN, line=dict(color="#d9f938", width=3)),
                            text=[f"<b>Cao nhất {df.ti_le_tre.iloc[i] * 100:.1f}%</b>"], textposition="top center",
                            textfont=dict(size=12.5, color=DEN), cliponaxis=False)
    elif ma == "Q3_2":  # barChart xếp chồng: đến 10% tím + phần vượt đỏ, tổng in đậm, vạch 10% xám đậm
        fig.add_bar(x=df.ti_le_tre.clip(upper=.10), y=df.ten_bang, orientation="h", marker_color=TIM, name="Đến 10%",
                    customdata=[_tip(f"{t} ({b})", [("Tỉ lệ giao trễ", f"{q.so_vn(v * 100, 2)}%", DO if v > .10 else TIM),
                                                     ("Đơn giao trễ", q.so_vn(n)), ("Đơn đã giao", q.so_vn(g))])
                                for t, b, v, n, g in zip(df.ten_bang, df.bang, df.ti_le_tre, df.don_tre, df.don_da_giao)],
                    hovertemplate="%{customdata}<extra></extra>")
        fig.add_bar(x=(df.ti_le_tre - .10).clip(lower=0), y=df.ten_bang, orientation="h", marker_color=DO,
                    name="Phần vượt ngưỡng", hoverinfo="skip")
        fig.add_scatter(x=df.ti_le_tre, y=df.ten_bang, mode="text", text=[f"<b>{_pct(v)}</b>" for v in df.ti_le_tre],
                        textposition="middle right", textfont=dict(size=10.5, color=DEN), hoverinfo="skip",
                        cliponaxis=False)
        fig.update_layout(barmode="stack", bargap=0.3)
        fig.add_vline(x=0.10, line=dict(color=CHU_NHAN, dash="dash", width=1.5))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(visible=False, range=[0, df.ti_le_tre.max() * 1.2])
    elif ma == "Q4_1":  # cột theo nhóm số ngày trễ: đúng hạn xanh chanh, trễ đỏ; nhãn giữa cột; vạch TB sàn
        fig.add_bar(x=df.muc_tre, y=df.diem_tb, marker_color=[CHANH_PBI if k == "Đúng hạn" else DO for k in df.ket_qua],
                    text=[f"{v:.2f}" for v in df.diem_tb], textposition="inside", insidetextanchor="middle",
                    textfont=dict(size=10.5, color=DEN),
                    customdata=[_tip(m, [("Điểm TB", f"{q.so_vn(v, 2)}★", CHANH_PBI if k == "Đúng hạn" else DO),
                                         ("Lượt đánh giá", q.so_vn(n)),
                                         ("TB toàn sàn", f"{q.so_vn(tom_tat['diem_tb_toan_san'], 2)}★")])
                                for m, k, v, n in zip(df.muc_tre, df.ket_qua, df.diem_tb, df.so_don_co_danh_gia)],
                    hovertemplate="%{customdata}<extra></extra>")
        fig.add_hline(y=tom_tat["diem_tb_toan_san"], line=dict(color=CHU_TRUC, dash="dash", width=1.5),
                      annotation_text=f"TB sàn {tom_tat['diem_tb_toan_san']:.2f}", annotation_position="top right",
                      annotation_font=dict(size=11, color=CHU_TRUC))
        fig.update_yaxes(range=[0, 5], dtick=1)
        fig.update_layout(bargap=0.25)
    elif ma == "Q4_2":  # combo: cột tỉ lệ trễ (đỏ > 10%), đường điểm TB đen, trục phải 3,6–4,4
        x = _truc_ky(fig, df)
        fig.add_bar(x=x, y=df.ti_le_tre, name="Tỉ lệ trễ", marker=dict(color=[DO if v > .10 else TIM for v in df.ti_le_tre],
                                                                         opacity=_mo(df)),
                    customdata=[_tip(k, [("Tỉ lệ trễ", f"{q.so_vn(v * 100, 2)}%", DO if v > .10 else TIM),
                                         ("Điểm TB", f"{q.so_vn(d, 2)}★", DEN), ("Đơn đã giao", q.so_vn(g))])
                                for k, v, d, g in zip(_ky(df), df.ti_le_tre, df.diem_tb, df.don_da_giao)],
                    hovertemplate="%{customdata}<extra></extra>")
        fig.add_scatter(x=x, y=df.diem_tb, name="Điểm TB", mode="lines+markers", line=dict(color=DEN, width=2),
                        marker=dict(size=5, color=DEN), secondary_y=True, hoverinfo="skip")
        fig.update_yaxes(tickformat=".0%", rangemode="tozero", secondary_y=False)
        fig.update_yaxes(range=[3.6, 4.4], showgrid=False, tickformat=".1f", secondary_y=True)
        _chu_thich(fig, [("Tỉ lệ trễ", TIM), ("Điểm TB", DEN)])
    elif ma == "Q5_1":  # cột nhóm: Liên bang đen, Nội bang tím; nhãn % 1 chữ số ở đầu cột
        # 1 tooltip cho cả 2 tuyến của cùng khâu bàn giao (2 hộp riêng sẽ đè lên nhau)
        tip = {b: _tip(f"Bàn giao {b.lower()}", [
            (f"{r.tuyen}", f"{q.so_vn(r.ti_le_tre * 100, 2)}% trễ · {q.so_vn(r.don_da_giao)} đơn",
             DEN if r.tuyen == "Liên bang" else TIM) for r in df[df.ban_giao == b].sort_values("tuyen").itertuples()])
            for b in df.ban_giao.unique()}
        for tuyen, mau in (("Liên bang", DEN), ("Nội bang", TIM)):
            d = df[df.tuyen == tuyen]
            fig.add_bar(x=d.ban_giao, y=d.ti_le_tre, name=tuyen, marker_color=mau, text=[_pct(v) for v in d.ti_le_tre],
                        textposition="outside", cliponaxis=False, textfont=dict(size=10.5, color=DEN),
                        customdata=[tip[b] for b in d.ban_giao],
                        hovertemplate="%{customdata}<extra></extra>" if tuyen == "Liên bang" else None,
                        hoverinfo=None if tuyen == "Liên bang" else "skip")
        fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0)
        fig.update_yaxes(tickformat=".0%", range=[0, df.ti_le_tre.max() * 1.25])
        _chu_thich(fig, [("Liên bang", DEN), ("Nội bang", TIM)])
    elif ma == "Q5_2":  # combo: cột bàn giao trễ (đỏ ở kỳ giao trễ > 10%), đường vận chuyển đen, xử lý xám nét đứt
        x = _truc_ky(fig, df)
        fig.add_bar(x=x, y=df.ti_le_ban_giao_tre, name="Bàn giao trễ",
                    marker=dict(color=[DO if v > .10 else TIM for v in df.ti_le_tre], opacity=_mo(df)),
                    customdata=[_tip(k, [("Bàn giao trễ", f"{q.so_vn(b * 100, 2)}% · {q.so_vn(l)} lượt",
                                          DO if t > .10 else TIM),
                                         ("Xử lý TB", f"{q.so_vn(x_, 1)} ngày", XAM), ("Vận chuyển TB", f"{q.so_vn(v, 1)} ngày", DEN),
                                         ("Giao trễ", f"{q.so_vn(t * 100, 2)}%")])
                                for k, b, l, x_, v, t in zip(_ky(df), df.ti_le_ban_giao_tre, df.luot_ban_giao_tre,
                                                             df.xu_ly_tb, df.van_chuyen_tb, df.ti_le_tre)],
                    hovertemplate="%{customdata}<extra></extra>")
        fig.add_scatter(x=x, y=df.van_chuyen_tb, name="Vận chuyển TB", mode="lines+markers",
                        line=dict(color=DEN, width=2), marker=dict(size=5, color=DEN), secondary_y=True, hoverinfo="skip")
        fig.add_scatter(x=x, y=df.xu_ly_tb, name="Xử lý TB", mode="lines+markers",
                        line=dict(color=XAM, width=2, dash="dash"), marker=dict(size=5, color=XAM), secondary_y=True,
                        hoverinfo="skip")
        fig.update_yaxes(tickformat=".0%", rangemode="tozero", secondary_y=False)
        fig.update_yaxes(rangemode="tozero", showgrid=False, tickformat="d", secondary_y=True)
        _chu_thich(fig, [("Bàn giao trễ", TIM), ("Vận chuyển TB", DEN), ("Xử lý TB", XAM)])
    elif ma == "Q6_1":  # scatter: màu theo cờ M5, cỡ theo doanh thu, 2 vạch ngưỡng đỏ, trục điểm 2–5
        for co, mau in ((False, TIM), (True, DO)):
            d = df[df.can_xu_ly == co]
            fig.add_scatter(x=d.ti_le_ban_giao_tre, y=d.diem_tb, mode="markers", showlegend=False,
                            marker=dict(color=mau, opacity=.8, line=dict(width=0),
                                        size=(d.doanh_thu / df.doanh_thu.max()) ** .5 * 20 + 4),
                            customdata=[_tip(n, [("Bàn giao trễ", f"{q.so_vn(b * 100, 2)}%", mau), ("Điểm TB", f"{q.so_vn(dd, 2)}★"),
                                                 ("Số đơn", q.so_vn(sd)), ("Doanh thu", f"{q.so_vn(dt)} BRL")])
                                        for n, b, dd, sd, dt in zip(d.nguoi_ban, d.ti_le_ban_giao_tre, d.diem_tb,
                                                                    d.so_don, d.doanh_thu)],
                            hovertemplate="%{customdata}<extra></extra>")
        fig.add_vline(x=0.10, line=dict(color=DO, dash="dash", width=1.5))
        fig.add_hline(y=3.5, line=dict(color=DO, dash="dash", width=1.5))
        fig.update_xaxes(tickformat=".0%", title_text="Bàn giao trễ", rangemode="tozero", showgrid=True)
        fig.update_yaxes(title_text="Điểm TB", range=[2, 5])
        _chu_thich(fig, [("Trong ngưỡng", TIM), ("Vượt ngưỡng", DO), ("Cỡ chấm = doanh thu", CHU_NHAN)])
    else:
        return None  # Q6_2 là bảng (tableEx) – _bang_q6
    theo_thang = ma in ("Q1_1", "Q1_2", "Q3_1", "Q4_2", "Q5_2")
    che_do = "closest" if ma == "Q6_1" else "y" if ma in ("Q2_1", "Q2_2", "Q3_2") else "x"
    if theo_thang:  # vạch dọc chấm chấm theo con trỏ như bản thiết kế
        fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="hovered data", spikedash="dot",
                         spikecolor="#94a3b8", spikethickness=1)
    fig.update_layout(height=cao, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(family="Segoe UI, sans-serif", size=11, color=CHU_NHAN), hoverlabel=TOOLTIP,
                      hovermode=che_do, hoverdistance=-1 if che_do != "closest" else 20, spikedistance=-1,
                      margin=dict(l=4, r=8, t=30,
                                  b=fig.layout.margin.b if fig.layout.margin.b is not None else 4))
    fig.update_xaxes(showgrid=fig.layout.xaxis.showgrid or False, gridcolor=LUOI_PBI, zeroline=False,
                     tickfont=dict(size=11.5, color=CHU_TRUC), title_font=dict(size=11.5, color=CHU_NHAN), tickangle=0)
    fig.update_yaxes(gridcolor=LUOI_PBI, zeroline=False, tickfont=dict(size=11.5, color=CHU_TRUC))
    if ma in ("Q2_1", "Q2_2"):  # nhãn danh mục / bang đậm hơn như Power BI
        fig.update_yaxes(tickfont=dict(size=12, color=CHU_NHAN))
    return fig


@st.cache_resource(show_spinner=False)
def _ban_do_bang() -> dict:
    """powerbi/maps/brazil_states.json (TopoJSON, bản đồ của shapeMap) -> GeoJSON cho Plotly; id = mã bang."""
    tp = json.loads((Path(__file__).resolve().parent.parent / "powerbi" / "maps" / "brazil_states.json")
                    .read_text(encoding="utf-8"))
    cung = tp["arcs"]

    def vong(ds):
        diem = []
        for i in ds:
            c = cung[i] if i >= 0 else cung[~i][::-1]
            diem += c if not diem else c[1:]
        return diem

    ra = []
    for g in tp["objects"]["states"]["geometries"]:
        if g["type"] == "Polygon":
            hinh = {"type": "Polygon", "coordinates": [vong(r) for r in g["arcs"]]}
        else:
            hinh = {"type": "MultiPolygon", "coordinates": [[vong(r) for r in p] for p in g["arcs"]]}
        ra.append({"type": "Feature", "id": g["properties"]["state_code"], "geometry": hinh, "properties": {}})
    return {"type": "FeatureCollection", "features": ra}


def _ve_ban_do(df, cao: int) -> go.Figure:
    """shapeMap: tô 27 bang theo 'Nhóm tỉ trọng bang' (1–5), thang màu #EEF1FE → #A9B8F8 → #3A47C4, viền trắng."""
    nhom = [_nhom_ti_trong(p) for p in df.ti_trong]
    fig = go.Figure(go.Choropleth(
        geojson=_ban_do_bang(), locations=df.bang, z=nhom, zmin=1, zmax=5, showscale=False,
        colorscale=[[0, "#EEF1FE"], [.5, TIM], [1, TIM_DEN]], marker_line_color="#FFFFFF", marker_line_width=0.8,
        customdata=[_tip(f"{t} ({b})", [("Doanh thu", f"{q.so_vn(dt)} BRL", MAU_NHOM_BANG[_nhom_ti_trong(p)]),
                                         ("Số đơn", q.so_vn(sd)), ("Tỉ trọng", f"{q.so_vn(p * 100, 2)}%")])
                    for t, b, dt, sd, p in zip(df.ten_bang, df.bang, df.doanh_thu, df.so_don, df.ti_trong)],
        hovertemplate="%{customdata}<extra></extra>"))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator",
                    domain=dict(x=[0.18, 1], y=[0, 1]))  # chừa góc trái cho chú thích như Power BI
    chu_thich = [("> 12%", TIM_DEN), ("5–12%", TIM_DAM_PBI), ("2–5%", TIM), ("1–2%", TIM_NHAT), ("< 1%", "#EEF1FE")]
    fig.add_annotation(x=0, y=0.02, xref="paper", yref="paper", xanchor="left", yanchor="bottom", showarrow=False,
                       align="left", font=dict(size=12.5, color=CHU_NHAN),
                       text="Theo bang<br>" + "<br>".join(f"<span style='color:{m};font-size:16px'>●</span>  {t}"
                                                          for t, m in chu_thich))
    fig.update_layout(height=cao, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      hoverlabel=TOOLTIP)
    return fig


def _bang_q6(df, cao: int) -> None:
    """tableEx '10 người bán cần xử lý trước': chữ 7pt, cột Vượt ngưỡng chữ đỏ #B8382B, doanh thu có thanh dữ liệu
    #A9B8F8 (số nằm bên phải thanh), dòng xen kẽ nền xám nhạt."""
    lon = float(df.doanh_thu.max()) or 1
    dong = "".join(
        f'<tr><td>{html.escape(n)}</td><td class="do">{html.escape(c)}</td>'
        f'<td class="thanh"><i style="width:{v / lon * 100:.1f}%"></i><span>{v:,.0f}</span></td></tr>'
        for n, c, v in zip(df.nguoi_ban, df.canh_bao, df.doanh_thu))
    st.markdown(f'<div class="bang_pbi" style="max-height:{cao}px"><table><thead><tr><th>Người bán</th>'
                f'<th>Vượt ngưỡng</th><th>Doanh thu (BRL)<small>▼</small></th></tr></thead><tbody>{dong}</tbody>'
                f'</table></div>', unsafe_allow_html=True)


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

cot_db = st.container()

def _o_bieu_do(m: str, cao: int) -> None:
    """1 ô biểu đồ: tiêu đề (+ phụ đề) | nút phóng to + Hỏi AI ở góc phải | biểu đồ / bảng."""
    trai, phai = st.columns([1.9, 1], vertical_alignment="top")
    ten, phu = TIEU_DE[m]
    df, tt = _so_lieu(m, bl)
    phu = phu(tt, df) if phu and not df.empty else ""
    trai.markdown(f'<p class="tieu_de_the">{html.escape(ten)}</p>'
                  f'<p class="phu_the">{html.escape(phu) if phu else "&nbsp;"}</p>', unsafe_allow_html=True)
    dang = st.session_state.mo_ai and m == ma and st.session_state.pham_vi == "bieu_do"
    o_nut = phai.container(horizontal=True, horizontal_alignment="right", gap="small",
                           vertical_alignment="center")  # nút sát góc phải thẻ
    if o_nut.button("", icon=":material/open_in_full:", key=f"to_{m}", help="Phóng to biểu đồ"):
        st.session_state.bieu_do, st.session_state.pham_vi, st.session_state.mo_ai = m, "bieu_do", True
        st.rerun()
    if o_nut.button("Đang hỏi AI" if dang else "Hỏi AI", key=f"hoi_{m}", width="content",
                    icon=":material/radio_button_checked:" if dang else ":material/auto_awesome:"):
        st.session_state.bieu_do, st.session_state.pham_vi, st.session_state.mo_ai = m, "bieu_do", True
        st.rerun()
    if df.empty:
        st.info(tt.get("ghi_chu", "Không có dữ liệu với bộ lọc này"))
    elif m == "Q6_2":
        _bang_q6(df, cao)
    else:
        st.plotly_chart(_ve(m, df, tt, cao), width="stretch", key=f"ve_{m}", config={"displayModeBar": False})


with cot_db:
    for i_hang, hang_bd in enumerate(BO_CUC[trang]):
        cao = CAO_BIEU_DO  # mọi biểu đồ ở cả 3 trang cao bằng nhau
        for cot, (m, _) in zip(st.columns([w for _, w in hang_bd], gap="small"), hang_bd):
            if m == "ban_do_Q2_2":  # như Power BI: 1 thẻ chung, trái bản đồ "Doanh thu theo bang", phải Top 5
                with cot, st.container(key="the_Q2_2"):
                    c_ban_do, c_top5 = st.columns([0.47, 0.53], gap="medium")
                    with c_ban_do:
                        st.markdown('<p class="tieu_de_the">Doanh thu theo bang</p><p class="phu_the">&nbsp;</p>',
                                    unsafe_allow_html=True)
                        df, _tt = _so_lieu("Q2_2", bl)
                        if not df.empty:
                            st.plotly_chart(_ve_ban_do(df, cao), width="stretch", key="ve_ban_do",
                                            config={"displayModeBar": False})
                    with c_top5:
                        _o_bieu_do("Q2_2", cao)
                continue
            with cot, st.container(key=f"the_{m}"):
                _o_bieu_do(m, cao)

GOI_Y = {  # câu hỏi có sẵn (3 câu / biểu đồ, như bản thiết kế), viết bằng lời thường cho người đọc báo cáo
    "Q1_1": ["Tháng nào bán được nhiều tiền nhất, vì sao?", "8 tháng đầu 2018 bán được nhiều hơn cùng kỳ 2017 bao nhiêu?",
             "Doanh thu năm 2018 có đang chững lại không?"],
    "Q1_2": ["Doanh thu tăng là nhờ bán được nhiều đơn hơn hay mỗi đơn đắt hơn?",
             "Trung bình mỗi đơn khách trả bao nhiêu tiền, có thay đổi không?", "Tháng nào số đơn tăng vọt?"],
    "Q2_1": ["3 nhóm hàng bán chạy nhất chiếm bao nhiêu phần doanh thu?", "Nên tập trung đẩy mạnh nhóm hàng nào?",
             "Doanh thu có dựa quá nhiều vào vài nhóm hàng không?"],
    "Q2_2": ["Bang São Paulo chiếm bao nhiêu phần doanh thu?", "Doanh thu có dồn vào quá ít bang không?",
             "Vùng nào mang lại nhiều doanh thu nhất?"],
    "Q3_1": ["Những tháng nào có hơn 10% đơn giao trễ?", "Tháng 03/2018 có bao nhiêu đơn bị giao trễ?",
             "Năm 2018 giao hàng có đúng hẹn hơn năm 2017 không?"],
    "Q3_2": ["Bang nào bị giao trễ nhiều nhất? Số liệu có đủ tin cậy không?", "Bao nhiêu bang có hơn 10% đơn giao trễ?",
             "Các bang hay bị giao trễ nằm ở vùng nào?"],
    "Q4_1": ["Đơn giao trễ bị khách chấm thấp hơn bao nhiêu sao?", "Giao trễ bao lâu thì khách chấm điểm thấp nhất?",
             "Đơn giao đúng hẹn được khách chấm bao nhiêu sao?"],
    "Q4_2": ["Tháng nào giao trễ nhiều thì khách có chấm điểm thấp hơn không?", "Tháng nào khách chấm điểm thấp nhất?",
             "Giao trễ ảnh hưởng tới điểm đánh giá nhiều không?"],
    "Q5_1": ["Người bán gửi hàng trễ thì khách nhận trễ nhiều hơn bao nhiêu?",
             "Giao trong cùng bang và khác bang trễ khác nhau thế nào?",
             "Người bán gửi hàng đúng hạn mà khách vẫn nhận trễ thì bao nhiêu?"],
    "Q5_2": ["Tháng 03/2018 giao trễ là do người bán hay do khâu vận chuyển?",
             "Những tháng giao trễ tăng vọt khác gì tháng bình thường?",
             "Người bán chuẩn bị hàng có chậm hơn trước không?"],
    "Q6_1": ["Bao nhiêu người bán đang có vấn đề (gửi hàng trễ hoặc bị chấm thấp)?",
             "Nhóm người bán có vấn đề chiếm bao nhiêu phần doanh thu?",
             "Người bán gửi hàng trễ có bị khách chấm điểm thấp hơn không?"],
    "Q6_2": ["Nên làm việc với người bán nào trước, vì sao?",
             "Người bán hay mắc lỗi gì nhất: gửi hàng trễ hay bị chấm điểm thấp?",
             "10 người bán này chiếm bao nhiêu doanh thu của nhóm có vấn đề?"],
    "trang": ["Trang này cho thấy điều gì quan trọng nhất?", "Chỉ số nào đang xấu hơn mức cho phép?",
              "Nên ưu tiên cải thiện việc gì trước?"],
    "tat_ca": ["Tóm tắt tình hình kinh doanh từ 01/2017 đến 08/2018", "Vấn đề lớn nhất trong báo cáo là gì?",
               "3 việc nên làm ngay là gì?"],
}
PHAM_VI = {"bieu_do": "Biểu đồ này", "trang": "Cả trang", "tat_ca": "Toàn báo cáo"}
NUT_CHINH = {"bieu_do": "Giải thích biểu đồ này", "trang": "Tóm tắt cả trang", "tat_ca": "Tóm tắt toàn báo cáo"}
BIEU_TUONG_GOI_Y = [":material/trending_up:", ":material/calendar_month:", ":material/help:"]


def _chi_so(ma: str, tt: dict) -> str:
    """Con số chính hiện trên chip ngữ cảnh của khung AI (lấy từ số liệu kết luận của biểu đồ)."""
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


def _tr(v: float) -> str:
    """Số tiền gọn kiểu thẻ KPI: 13,45 tr / 835 (BRL)."""
    return f"{q.so_vn(v / 1e6, 2)} tr" if abs(v) >= 1e6 else q.so_vn(v)


def _so_noi_bat(ma: str, df, tt: dict) -> list[tuple[str, str]]:
    """3 ô số nổi bật ở chế độ phóng to (ô đầu tô xanh chanh) – tính từ đúng bảng số liệu đang vẽ."""
    try:
        if ma == "Q1_1":
            d = df.loc[df.doanh_thu.idxmax()]
            return [("Tổng doanh thu", f"{_tr(df.doanh_thu.sum())} BRL"), ("Đỉnh cao nhất", f"{_tr(d.doanh_thu)} · {d.ky}"),
                    ("01–08/2018 so cùng kỳ", f"{tt['so_cung_ky']['doanh_thu']['tang_truong']:+.0%}")]
        if ma == "Q1_2":
            d = df.loc[df.so_don.idxmax()]
            return [("Tổng số đơn", q.so_vn(df.so_don.sum())),
                    ("Giá trị đơn TB toàn kỳ", f"{q.so_vn(df.doanh_thu.sum() / df.so_don.sum(), 2)} BRL"),
                    ("Tháng nhiều đơn nhất", f"{q.so_vn(d.so_don)} · {d.ky}")]
        if ma == "Q2_1":
            return [("Top 10 chiếm", f"{q.so_vn(tt['ti_trong_nhom_top10_danh_muc'] * 100, 1)}% doanh thu"),
                    ("Dẫn đầu", f"{df.danh_muc.iloc[0]} · {q.so_vn(df.ti_trong.iloc[0] * 100, 1)}%"),
                    ("Top 3 chiếm", f"{q.so_vn(df.ti_trong.head(3).sum() * 100, 1)}%")]
        if ma == "Q2_2":
            v = tt["theo_vung"][0]
            return [("Top 5 bang chiếm", f"{q.so_vn(tt['ti_trong_nhom_top5_bang'] * 100, 1)}% doanh thu"),
                    ("Dẫn đầu", f"{df.ten_bang.iloc[0]} · {q.so_vn(df.ti_trong.iloc[0] * 100, 1)}%"),
                    ("Vùng lớn nhất", f"{v['vung']} · {q.so_vn(v['ti_trong'] * 100, 1)}%")]
        if ma == "Q3_1":
            d = df.loc[df.ti_le_tre.idxmax()]
            return [("Tỉ lệ giao trễ toàn kỳ", f"{q.so_vn(df.don_tre.sum() / df.don_da_giao.sum() * 100, 2)}%"),
                    ("Tháng trễ nhất", f"{q.so_vn(d.ti_le_tre * 100, 1)}% · {d.ky}"),
                    ("Số tháng vượt 10%", f"{len(tt['thang_vuot_nguong'])} / {len(df)} tháng")]
        if ma == "Q3_2":
            return [("Bang trễ nhất", f"{df.ten_bang.iloc[0]} · {q.so_vn(df.ti_le_tre.iloc[0] * 100, 1)}%"),
                    ("Bang vượt 10%", f"{tt['so_bang_vuot_nguong']} / {tt['tong_so_bang']} bang"),
                    ("Đơn đã giao của bang trễ nhất", q.so_vn(df.don_da_giao.iloc[0]))]
        if ma == "Q4_1":
            return [("Đơn đúng hạn", f"{q.so_vn(df.diem_tb.iloc[0], 2)}★"),
                    ("Đơn trễ (chung)", f"{q.so_vn(tt['diem_tb_theo_ket_qua_giao']['Trễ hạn'], 2)}★"),
                    ("TB toàn sàn", f"{q.so_vn(tt['diem_tb_toan_san'], 2)}★")]
        if ma == "Q4_2":
            d = df.loc[df.diem_tb.idxmin()]
            return [("Tương quan trễ – điểm", q.so_vn(tt["he_so_tuong_quan_tre_va_diem"], 2)),
                    ("Tháng điểm thấp nhất", f"{q.so_vn(d.diem_tb, 2)}★ · {d.ky}"),
                    ("Tháng trễ nhất", tt["thang_tre_cao_nhat"])]
        if ma == "Q5_1":
            t = tt["ti_le_tre_moi_tuyen"]
            return [("Bàn giao trễ làm giao trễ", f"gấp {q.so_vn(tt['ban_giao_tre_gap_so_lan'], 1)} lần"),
                    ("Giao trễ khi bàn giao đúng hạn", f"{q.so_vn(t['Đúng hạn'] * 100, 1)}%"),
                    ("Giao trễ khi bàn giao trễ", f"{q.so_vn(t['Trễ hạn'] * 100, 1)}%")]
        if ma == "Q5_2":
            x, v = df.loc[df.xu_ly_tb.idxmax()], df.loc[df.van_chuyen_tb.idxmax()]
            return [("Tháng đột biến (trễ > 10%)", str(len(tt["thang_dot_bien_K6_tren_10"]))),
                    ("Xử lý lâu nhất", f"{q.so_vn(x.xu_ly_tb, 2)} ngày · {x.ky}"),
                    ("Vận chuyển lâu nhất", f"{q.so_vn(v.van_chuyen_tb, 1)} ngày · {v.ky}")]
        return [("Người bán vượt ngưỡng", f"{tt['so_nguoi_ban_can_xu_ly']} / {tt['so_nguoi_ban_tu_30_don']}"),
                ("Chiếm doanh thu toàn sàn", f"{q.so_vn(tt['ti_trong_doanh_thu_nguoi_ban_can_xu_ly'] * 100, 1)}%"),
                ("Vi phạm cả hai ngưỡng", str(tt["trong_do_vi_pham_ca_hai"]))]
    except (KeyError, TypeError, ValueError, IndexError):
        return []


def _html_ai(s: str) -> str:
    """Chữ AI (đã tô số bằng kiem_so.to_dam) -> HTML: **đậm**, :blue-background[...] / :orange-background[...]."""
    s = html.escape(s)
    s = re.sub(r":blue-background\[([^\]]*)\]", r'<span class="so_xanh">\1</span>', s)
    s = re.sub(r":orange-background\[([^\]]*)\]", r'<span class="so_cam">\1</span>', s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def _tach_giai_thich(s: str) -> dict | None:
    """Câu trả lời 'Giải thích' theo khuôn TOM_TAT / NOI_BAT / GIA_THUYET / DE_XUAT (prompts/explain_trend.md)."""
    kq = {"tom_tat": "", "noi_bat": [], "gia_thuyet": [], "de_xuat": []}
    for dong in s.splitlines():
        m = re.match(r"[\s\-*•]*\**(TOM_TAT|NOI_BAT|GIA_THUYET|DE_XUAT)\**\s*:\s*(.+)", dong)
        if not m:
            continue
        loai, nd = m.group(1), [p.strip() for p in m.group(2).split("|")]
        if loai == "TOM_TAT":
            kq["tom_tat"] = " ".join(nd)
        elif loai == "NOI_BAT":
            kq["noi_bat"].append((nd[0], nd[1] if len(nd) > 2 else "", nd[-1] if len(nd) > 1 else ""))
        else:  # AI đôi khi thêm 1 nhãn ngắn ở giữa như dòng NOI_BAT: bỏ nhãn đó, giữ nội dung
            noi_dung = nd[-1] if len(nd) >= 3 and len(nd[1]) <= 24 else ". ".join(nd[1:])
            kq["gia_thuyet" if loai == "GIA_THUYET" else "de_xuat"].append((nd[0], noi_dung))
    return kq if kq["tom_tat"] and (kq["noi_bat"] or kq["de_xuat"]) else None


def _bong_giai_thich(ten: str, p: dict) -> str:
    """Bong bóng 'Giải thích biểu đồ' như InsightBubble của bản thiết kế."""
    mau_tag = ["tag_chanh", "tag_tim", "tag_xanh"]
    o = [f'<div class="ib_nhan">✦ {html.escape(ten)}</div><div class="ib_chinh">{_html_ai(p["tom_tat"])}</div>']
    if p["noi_bat"] or p["gia_thuyet"]:
        o.append('<div class="ib_muc">Điểm nổi bật</div>')
        for i, (td, tag, ct) in enumerate(p["noi_bat"]):
            o.append(f'<div class="ib_the"><div class="ib_the_dau"><b>{_html_ai(td)}</b>'
                     + (f'<span class="ib_tag {mau_tag[i % 3]}">{_html_ai(tag)}</span>' if tag else "")
                     + f'</div><p>{_html_ai(ct)}</p></div>')
        for td, ct in p["gia_thuyet"]:
            o.append(f'<div class="ib_the"><div class="ib_the_dau"><b>{_html_ai(td)}</b>'
                     f'<span class="ib_tag tag_vang">Giả thuyết</span></div><p>{_html_ai(ct)}</p></div>')
    if p["de_xuat"]:
        o.append('<div class="ib_muc"><span class="ib_den">💡</span> Nên làm gì tiếp</div><ol class="ib_lam">')
        o += [f'<li><i>{i}</i><p><b>{_html_ai(td)}.</b> {_html_ai(ct)}</p></li>'
              for i, (td, ct) in enumerate(p["de_xuat"], 1)]
        o.append("</ol>")
    return "".join(o)


# ---- Mèo con đội mũ bông cải ló ra sau mép trái khung AI (bản thiết kế: CatMascot) ----
MEO_DAU = """<svg viewBox="0 0 110 130" class="meo_lac"><defs>
<radialGradient id="meo-mu" cx="38%" cy="28%" r="80%"><stop offset="0" stop-color="#d6f0a6"/><stop offset=".55" stop-color="#b0d977"/><stop offset="1" stop-color="#93c25a"/></radialGradient>
<radialGradient id="meo-long" cx="45%" cy="38%" r="70%"><stop offset="0" stop-color="#fff8ee"/><stop offset=".7" stop-color="#f6e4cc"/><stop offset="1" stop-color="#ead3b2"/></radialGradient>
<linearGradient id="meo-tai" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fdf6ea"/><stop offset="1" stop-color="#ecdcc2"/></linearGradient>
<radialGradient id="meo-mat" cx="45%" cy="40%" r="60%"><stop offset="0" stop-color="#a9bfb6"/><stop offset=".65" stop-color="#647d86"/><stop offset="1" stop-color="#3e505b"/></radialGradient>
<radialGradient id="meo-ma" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#ff9fac" stop-opacity=".7"/><stop offset="1" stop-color="#ff9fac" stop-opacity="0"/></radialGradient>
</defs><g transform="translate(6 0) rotate(-12 80 90)">
<path d="M37 48 Q35 27 40 15.5 Q43.5 11.5 47 15 Q55 23.5 61 32 Z" fill="url(#meo-tai)" stroke="#e2c7a2" stroke-width="1.5" stroke-linejoin="round"/>
<path d="M75 32 Q84.5 22 93.5 15.5 Q97.5 13.5 98.5 18 Q101 32 99 48 Z" fill="url(#meo-tai)" stroke="#e2c7a2" stroke-width="1.5" stroke-linejoin="round"/>
<ellipse cx="68" cy="59" rx="34" ry="32" fill="url(#meo-mu)" stroke="#7fae4a" stroke-width="1.6"/>
<ellipse cx="39.5" cy="66" rx="4" ry="5.6" fill="#f3a7a7" opacity=".9"/>
<path d="M63.6 40 Q66 44 64.2 47.5 L68.8 47.5 Q67 44 69.4 40 Z" fill="#dcf1b6" stroke="#6f9c3c" stroke-width="1.1" stroke-linejoin="round"/>
<g fill="#3f8a4a" stroke="#2f6e3a" stroke-width=".9"><circle cx="61.4" cy="37.6" r="4.1"/><circle cx="71.4" cy="37.6" r="4.1"/><circle cx="66.4" cy="34.4" r="4.7"/><circle cx="66.4" cy="39.4" r="3.6"/></g>
<g fill="#63ad5f"><circle cx="65" cy="32.8" r="1.4"/><circle cx="60.2" cy="36.4" r="1.1"/><circle cx="70.4" cy="36.2" r="1.1"/></g>
<ellipse cx="66" cy="67.5" rx="25.5" ry="21" fill="#93c25a"/><ellipse cx="66" cy="67.5" rx="24" ry="19.5" fill="url(#meo-long)"/>
<ellipse cx="66" cy="55.5" rx="13" ry="5.5" fill="#d8c1a1" opacity=".45"/>
<path d="M62 51.5 L62.6 55 M66 50.5 L66 54.5 M70 51.5 L69.4 55" stroke="#c9ad88" stroke-width="1.4" stroke-linecap="round" opacity=".7"/>
<ellipse cx="51.5" cy="73.5" rx="6" ry="3.6" fill="url(#meo-ma)"/><ellipse cx="80.5" cy="72.5" rx="6" ry="3.6" fill="url(#meo-ma)"/>
<ellipse cx="62.4" cy="76" rx="5.6" ry="4.3" fill="#fffdf8"/><ellipse cx="69.6" cy="76" rx="5.6" ry="4.3" fill="#fffdf8"/><ellipse cx="66" cy="80.5" rx="6" ry="3.6" fill="#fffdf8"/>
<g class="meo_chop"><circle cx="56.5" cy="65" r="6.2" fill="url(#meo-mat)" stroke="#2f3b44" stroke-width="1.1"/><circle cx="75" cy="64" r="6" fill="url(#meo-mat)" stroke="#2f3b44" stroke-width="1.1"/>
<ellipse cx="57.3" cy="64.2" rx="3.8" ry="4.4" fill="#1b232b"/><ellipse cx="75.8" cy="63.2" rx="3.7" ry="4.3" fill="#1b232b"/>
<circle cx="59.1" cy="62.2" r="2" fill="#fff"/><circle cx="77.5" cy="61.2" r="1.9" fill="#fff"/><circle cx="54.4" cy="67.4" r=".9" fill="#fff"/><circle cx="72.9" cy="66.4" r=".9" fill="#fff"/></g>
<path d="M63.4 71 Q66 69.6 68.6 71 Q67.2 73.8 66 73.8 Q64.8 73.8 63.4 71 Z" fill="#f08e9a" stroke="#c96b78" stroke-width=".8"/>
<path d="M66 73.8 L66 75.4 M63.4 75.9 Q64.7 77.5 66 75.6 Q67.3 77.5 68.6 75.9" stroke="#7a5a48" stroke-width="1.2" stroke-linecap="round" fill="none"/>
<path d="M50 74 Q40 71 30 70.5 M50 77 Q40.5 77.5 31 80.5 M51 79.5 Q43 82 36 86 M82 73 Q92 70 101 69.5 M82 76 Q91.5 77 100 79.5" stroke="#fff" stroke-width="1" stroke-linecap="round" fill="none" opacity=".95"/>
</g></svg>"""
MEO_TAY = """<svg viewBox="0 0 110 130" class="meo_tay_vao"><g class="meo_vo">
<g transform="translate(80 62) rotate(-40)" fill="#f8e9d4" stroke="#e2c7a2" stroke-width="1.5" stroke-linejoin="round">
<path d="M0 -5.5 C4 -6 8 -6 11 -5.8 L11 5.8 C8 6 4 6 0 5.5"/>
<path d="M10 -6 C14 -7.5 20 -7 23 -5.5 C26 -5 26.5 -2.5 25 -1.5 C27 -0.5 27 1.5 25 2 C26.5 3 26 5.5 23 6 C20 7.2 14 7.5 10 6 Z"/>
<path d="M20.5 -2.8 L24 -2.2 M20.5 2.8 L24 2.2" fill="none" stroke="#cfae86" stroke-width="1.2" stroke-linecap="round"/></g></g>
<path d="M79 92 C83 87 92 87.5 93.5 92.5 C95 97.5 89.5 101.5 82 101.5 C78 101.5 76 96.5 79 92 Z" fill="#f8e9d4" stroke="#e2c7a2" stroke-width="1.5" stroke-linejoin="round"/>
<path d="M87.5 90.5 L87 100 M91 91.5 L90.6 98.5" stroke="#cfae86" stroke-width="1.2" stroke-linecap="round"/></svg>"""
MEO_GIAN = """<svg viewBox="0 0 110 130" class="meo_gian meo_lac">
<g transform="translate(-8 5)"><path class="meo_no" d="M30 21 Q34 25 30 29 M39 21 Q35 25 39 29 M30.5 20 Q34.5 24 38.5 20 M30.5 30 Q34.5 26 38.5 30" stroke="#ef4444" stroke-width="2.4" stroke-linecap="round" fill="none"/></g>
<g transform="translate(6 0) rotate(-12 80 90)">
<path d="M48 54 L65 54 L65 65 L48 60.6 Z" fill="#f6e4cc"/><path d="M67 53 L84 53 L84 59.6 L67 64 Z" fill="#f6e4cc"/>
<path d="M49.2 60.9 L64.2 64.8 M67.8 63.8 L82.8 59.9" stroke="#3b2f25" stroke-width="1.8" stroke-linecap="round"/>
<path d="M49.5 56.5 Q56 57 62.5 60.4 M82.5 55.5 Q76 56 69.5 59.4" stroke="#8a6b4f" stroke-width="2.4" stroke-linecap="round" fill="none"/>
<path d="M61.6 76 Q66 73.6 70.4 76 Q68.8 82 66 82 Q63.2 82 61.6 76 Z" fill="#8b2f3c"/><ellipse cx="66" cy="80.3" rx="2.6" ry="1.4" fill="#f08e9a"/>
<path d="M63 75.5 L64.1 78.4 L65.1 75 Z M66.9 75 L67.9 78.4 L69 75.5 Z" fill="#fff"/></g></svg>"""
MEO_HTML = (f'<div class="meo"><div class="meo_lop meo_sau"><div class="meo_vao">{MEO_DAU}</div></div>'
            f'<div class="meo_lop meo_truoc">{MEO_TAY}<button type="button" class="meo_cham" '
            f'aria-label="Mèo con đội mũ bông cải, bấm thử xem"></button>{MEO_GIAN}<div class="meo_bong"></div></div></div>')


# ---------------------------------------------------------------------------
# Chế độ phóng to + khung Trợ lý AI (bản thiết kế Figma Make "Thiết kế lại giao diện AI chatbot")
# ---------------------------------------------------------------------------
def _chuyen_bieu_do(buoc: int) -> None:
    i = ma_cua_trang.index(st.session_state.bieu_do)
    st.session_state.bieu_do = ma_cua_trang[(i + buoc) % len(ma_cua_trang)]


def _dong_ai() -> None:
    st.session_state.mo_ai = False


def _xem_bieu_do(m: str) -> None:
    st.session_state.bieu_do, st.session_state.pham_vi = m, "bieu_do"


if not st.session_state.mo_ai:
    if st.button("Trợ lý AI", icon=":material/auto_awesome:", key="mo_tro_ly"):
        st.session_state.mo_ai = True
        st.rerun()
    st.stop()

with st.sidebar:
    components.html("""<script>
const w = window.parent, d = w.document;
if (!w.__olist_phim) {
  w.__olist_phim = true;
  d.addEventListener('keydown', (e) => {
    if (!d.querySelector('.st-key-lop_phu')) return;
    const t = e.target, dang_go = t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT');
    const bam = (k) => { const b = d.querySelector('.st-key-' + k + ' button'); if (b) { e.preventDefault(); b.click(); } };
    if (e.key === 'Escape') bam('thu_nho');
    else if (!dang_go && e.key === 'ArrowLeft') bam('truoc');
    else if (!dang_go && e.key === 'ArrowRight') bam('sau');
  });
  let am = null;
  const gru = () => {  // 2 tiếng gầm trầm ngắn: "grừ grừ"
    try {
      am = am || new (w.AudioContext || w.webkitAudioContext)();
      am.resume();
      const t0 = am.currentTime;
      [0, 0.38].forEach((lech) => {
        const bd = t0 + lech, o = am.createOscillator(), loc = am.createBiquadFilter(), run = am.createGain(),
              lfo = am.createOscillator(), sau = am.createGain(), bao = am.createGain();
        o.type = 'sawtooth'; o.frequency.setValueAtTime(120, bd); o.frequency.exponentialRampToValueAtTime(78, bd + 0.32);
        loc.type = 'lowpass'; loc.frequency.value = 480; loc.Q.value = 5;
        run.gain.value = 0.55; lfo.frequency.value = 26; sau.gain.value = 0.45; lfo.connect(sau).connect(run.gain);
        bao.gain.setValueAtTime(0.0001, bd); bao.gain.exponentialRampToValueAtTime(0.22, bd + 0.04);
        bao.gain.exponentialRampToValueAtTime(0.0001, bd + 0.33);
        o.connect(loc).connect(run).connect(bao).connect(am.destination);
        o.start(bd); lfo.start(bd); o.stop(bd + 0.36); lfo.stop(bd + 0.36);
      });
    } catch (loi) {}
  };
  d.addEventListener('click', (e) => {
    const nut = e.target.closest && e.target.closest('.meo_cham');
    if (!nut) return;
    nut.focus(); gru();
    clearTimeout(w.__olist_meo); w.__olist_meo = setTimeout(() => nut.blur(), 1900);
  });
}
</script>""", height=0)

dich_vu = llm.nha_cung_cap()
pham_vi = st.session_state.pham_vi
bang, tom_tat = _so_lieu(ma, bl)
ten_bd = TIEU_DE[ma][0]
if pham_vi == "bieu_do":
    goi = q.du_lieu_cho_ai(ma, bl, q.KetQua(bang, tom_tat), kpi)
    ma_log, khoa, chu_de, chip_1 = ma, f"bieu_do|{ma}|{bl}", ten_bd, ten_bd
elif pham_vi == "trang":
    goi = _goi_trang(trang, bl)
    ma_log, khoa, chu_de = f"trang{trang}", f"trang|{trang}|{bl}", f"trang {q.TRANG[trang].ten}"
    chip_1 = f"{len(ma_cua_trang)} biểu đồ · {q.TRANG[trang].ten}"
else:
    goi = _goi_tat_ca(bl.nam, bl.thang)
    ma_log, khoa, chu_de, chip_1 = "tat_ca", f"tat_ca|{bl.nam}|{bl.thang}", "toàn bộ báo cáo", "3 trang báo cáo"
hoi_thoai = st.session_state.setdefault("hoi_thoai", {}).setdefault(khoa, [])
da_bat_dau = bool(hoi_thoai)
nhan_loc = "Toàn kỳ, không lọc" if bl.mo_ta().startswith("không lọc") else bl.mo_ta()

with st.container(horizontal=True, key="lop_phu"):
    # ---- Bên trái: biểu đồ phóng to ----
    with st.container(key="o_phong_to"):
        trai, phai = st.columns([3, 1.25], vertical_alignment="top")
        phu = TIEU_DE[ma][1]
        phu = phu(tom_tat, bang) if phu and not bang.empty else ""
        trai.markdown(f'<div class="pt_dau"><span class="pt_dang_hoi"><i></i>Đang hỏi AI</span>'
                      f'<span class="pt_so_thu_tu">{ma_cua_trang.index(ma) + 1} / {len(ma_cua_trang)}</span></div>'
                      f'<h2 class="pt_ten">{html.escape(ten_bd)}</h2>'
                      + (f'<p class="pt_phu">{html.escape(phu)}</p>' if phu else ""), unsafe_allow_html=True)
        with phai.container(horizontal=True, horizontal_alignment="right", gap="small", key="pt_nut"):
            st.button("", icon=":material/chevron_left:", key="truoc", help="Biểu đồ trước",
                      on_click=_chuyen_bieu_do, args=(-1,))
            st.button("", icon=":material/chevron_right:", key="sau", help="Biểu đồ tiếp theo",
                      on_click=_chuyen_bieu_do, args=(1,))
            st.button("Thu nhỏ", icon=":material/close_fullscreen:", key="thu_nho", on_click=_dong_ai)
        so = _so_noi_bat(ma, bang, tom_tat)
        if so:
            st.markdown('<div class="pt_o_so">' + "".join(
                f'<div class="{"chanh" if i == 0 else ""}"><span>{html.escape(n)}</span><b>{html.escape(v)}</b></div>'
                for i, (n, v) in enumerate(so)) + "</div>", unsafe_allow_html=True)
        if bang.empty:
            st.info(tom_tat.get("ghi_chu", "Không có dữ liệu với bộ lọc này"))
        elif ma == "Q6_2":
            _bang_q6(bang, 560)
        else:
            st.plotly_chart(_ve(ma, bang, tom_tat, 560), width="stretch", key=f"phong_to_{ma}",
                            config={"displayModeBar": False})
        st.markdown('<div class="pt_phim"><kbd>Esc</kbd> để đóng · <kbd>←</kbd> <kbd>→</kbd> để chuyển biểu đồ</div>',
                    unsafe_allow_html=True)

    st.markdown(MEO_HTML, unsafe_allow_html=True)

    # ---- Bên phải: khung Trợ lý AI ----
    with st.container(key="khung_ai"):
        with st.container(key="ai_dau"):
            c_ten, c_info, c_moi, c_dong = st.columns([6, 1, 1, 1], gap="small", vertical_alignment="center")
            ten_model = (dich_vu[0].model.replace("gemini-", "Gemini ").replace("-flash", " Flash").replace("-lite", " Lite")
                         if dich_vu else "")
            c_ten.markdown('<div class="ai_ten"><div class="ai_bieu_tuong">✦<i></i></div><div><h2>Trợ lý AI Olist</h2>'
                           f'<p>{"Sẵn sàng trả lời · " + html.escape(ten_model) if dich_vu else "Chưa có API key"}</p>'
                           '</div></div>', unsafe_allow_html=True)
            with c_info.popover("", icon=":material/info:", help="Cách sử dụng"):
                st.markdown('<div class="hd_tieu_de">Dùng trợ lý trong 3 bước</div><ol class="hd_buoc">'
                            '<li><i>1</i><div><b>Chọn phạm vi</b><span>Hỏi về biểu đồ đang mở, cả trang, hoặc toàn '
                            'báo cáo.</span></div></li><li><i>2</i><div><b>Bấm Giải thích hoặc đặt câu hỏi</b><span>Chọn '
                            'câu có sẵn hay tự gõ câu hỏi bằng tiếng Việt.</span></div></li><li><i>3</i><div><b>Kiểm tra '
                            'dấu tích xanh</b><span>Cho biết các con số trong câu trả lời đã khớp với báo cáo.</span>'
                            '</div></li></ol>', unsafe_allow_html=True)
                if dich_vu:
                    st.markdown(f'<div class="hd_model">Mô hình chính <code>{html.escape(dich_vu[0].model)}</code>'
                                + "".join(f', dự phòng <code>{html.escape(d.model)}</code>' for d in dich_vu[1:])
                                + "</div>", unsafe_allow_html=True)
                else:
                    st.warning("Chưa có API key. Thêm `GEMINI_API_KEY` vào file `.env` ở gốc repo rồi tải lại trang.")
                with st.expander("Số liệu AI đang dùng"):
                    if pham_vi == "bieu_do" and not bang.empty:
                        an = ["seller_id", "danh_muc_en", "can_xu_ly"] + (["nam", "thang"] if "ky" in bang else [])
                        hien = bang.drop(columns=[c for c in an if c in bang])
                        hien = hien.assign(**{c: hien[c].map(lambda x, k=q.COT[c][1]: q.dinh_dang(x, k))
                                              for c in hien.columns if c in q.COT and q.COT[c][1] != "chu"})
                        st.dataframe(hien.rename(columns={c: q.COT[c][0] for c in hien.columns if c in q.COT}),
                                     hide_index=True, height=min(36 * (len(hien) + 1), 260))
                    st.json(goi, expanded=False)
            if da_bat_dau and c_moi.button("", icon=":material/restart_alt:", key="lam_moi",
                                           help="Cuộc trò chuyện mới"):
                hoi_thoai.clear()
                st.rerun()
            c_dong.button("", icon=":material/close:", key="dong_ai", help="Đóng", on_click=_dong_ai)
            st.markdown('<div class="ai_hoi_ve">Bạn muốn hỏi về</div>', unsafe_allow_html=True)
            st.segmented_control("Phạm vi hỏi", list(PHAM_VI), format_func=PHAM_VI.get, key="pham_vi", required=True,
                                 label_visibility="collapsed", width="stretch")
            chi_so = _chi_so(ma, tom_tat) if pham_vi == "bieu_do" else ""
            st.markdown('<div class="ai_chip_hang">'
                        f'<span class="ai_chip"><b class="bt">▥</b>{html.escape(chip_1)}</span>'
                        + (f'<span class="ai_chip chanh">↗ {html.escape(chi_so)}</span>' if chi_so else "")
                        + f'<span class="ai_chip loc">⏷ {html.escape(nhan_loc)}</span></div>', unsafe_allow_html=True)

        yeu_cau = None  # (câu hiện ở bong bóng người dùng, "giai_thich" | "hoi")
        with st.container(height=420, autoscroll=True, key="ai_chat"):
            st.markdown(f'<div class="ai_hang"><div class="ai_anh">✦</div><div class="ai_bong">Chào bạn! Mình đang xem '
                        f'cùng bạn <b>{html.escape(chu_de)}</b>. Bạn có thể nhờ mình giải thích, hoặc hỏi bất kỳ điều gì '
                        'về số liệu nhé.</div></div>', unsafe_allow_html=True)
            goi_y = GOI_Y[ma if pham_vi == "bieu_do" else pham_vi]
            if not da_bat_dau:
                with st.container(key="ai_mo_dau"):
                    if st.button(NUT_CHINH[pham_vi], icon=":material/auto_awesome:", key="nut_giai_thich",
                                 width="stretch", disabled=not dich_vu):
                        yeu_cau = (f"{NUT_CHINH[pham_vi]} giúp mình nhé", "giai_thich")
                    st.markdown('<div class="ai_nho">Hoặc chọn một câu hỏi có sẵn</div>', unsafe_allow_html=True)
                    for i, cau in enumerate(goi_y):
                        if st.button(cau, icon=BIEU_TUONG_GOI_Y[i % 3], key=f"goi_y_{i}", width="stretch",
                                     disabled=not dich_vu):
                            yeu_cau = (cau, "hoi")
                    st.markdown('<div class="ai_dam_bao"><b>✓</b>Mọi con số AI đưa ra đều được đối chiếu với báo cáo. '
                                'Dấu tích xanh nghĩa là đã khớp.</div>', unsafe_allow_html=True)
            for i, t in enumerate(hoi_thoai):
                if t["role"] == "user":
                    st.markdown(f'<div class="ban_hang"><div class="ban_bong">{html.escape(t["content"])}</div></div>',
                                unsafe_allow_html=True)
                    continue
                with st.container(key=f"tin_ai_{i}"):
                    if "loi" in t:
                        st.markdown(f'<div class="ai_loi">AI chưa trả lời được: {html.escape(t["loi"])}</div>',
                                    unsafe_allow_html=True)
                        continue
                    tl = t["tl"]
                    tk = tl.thong_ke_so
                    chu = kiem_so.to_dam(tl.noi_dung, tl.kiem_so)
                    phan = _tach_giai_thich(chu) if t.get("loai") == "giai_thich" else None
                    if phan:
                        st.markdown(_bong_giai_thich(t.get("ten", ten_bd), phan), unsafe_allow_html=True)
                    else:
                        st.markdown(chu)
                    if t.get("loai") == "tom_tat" and t.get("pham_vi") == "trang":
                        st.markdown('<div class="ib_muc">Từng biểu đồ · bấm để xem kỹ</div>', unsafe_allow_html=True)
                        for m in ma_cua_trang:
                            st.button(f"{TIEU_DE[m][0]}  →", key=f"xem_{i}_{m}", width="stretch",
                                      on_click=_xem_bieu_do, args=(m,))
                    if tk["tong_so"] == 0:
                        nhan_kc = "✓ Không có số cần kiểm"
                    elif tk["khong_tim_thay"]:
                        nhan_kc = f"⚠ {tk['tong_so'] - len(tk['khong_tim_thay'])}/{tk['tong_so']} số khớp – số tô cam cần tự kiểm"
                        st.markdown('<span class="co_so_cam"></span>', unsafe_allow_html=True)
                    else:
                        nhan_kc = f"✓ {tk['tong_so']}/{tk['tong_so']} số khớp"
                    with st.expander(nhan_kc):
                        st.caption(f"{tk['khop_du_lieu']} số khớp dữ liệu · {tk['tu_tinh_dung']} số AI tự tính đúng "
                                   f"(xanh) · {len(tk['khong_tim_thay'])} số không tìm thấy (cam)")
                        st.caption(f"{tl.nha_cung_cap} `{tl.model}` · {tl.token_vao:,} + {tl.token_ra:,} token · "
                                   f"log `{tl.file_log}`")
                        if tl.model_loi_truoc:
                            st.caption("Đã chuyển model dự phòng vì: " + " · ".join(tl.model_loi_truoc))
                        for c in tl.cong_cu:
                            st.caption(f"AI lấy thêm số liệu: `lay_so_lieu({c['tham_so']})`")
            cho = st.empty()
            if da_bat_dau:
                with st.container(key="ai_tiep"):
                    st.markdown('<div class="ai_nho">Hỏi tiếp</div>', unsafe_allow_html=True)
                    da_hoi = {t["content"] for t in hoi_thoai if t["role"] == "user"}
                    with st.container(horizontal=True, gap="small"):
                        if not any(t.get("loai") in ("giai_thich", "tom_tat") for t in hoi_thoai) and st.button(
                                NUT_CHINH[pham_vi], icon=":material/auto_awesome:", key="chip_giai_thich",
                                disabled=not dich_vu):
                            yeu_cau = (f"{NUT_CHINH[pham_vi]} giúp mình nhé", "giai_thich")
                        for i, cau in enumerate(c for c in goi_y if c not in da_hoi):
                            if st.button(cau, key=f"tiep_{i}", disabled=not dich_vu):
                                yeu_cau = (cau, "hoi")

        with st.container(key="ai_cuoi"):
            go_vao = st.chat_input("Nhập câu hỏi của bạn…", disabled=not dich_vu)
            st.markdown('<div class="ai_chan">Nhấn Enter để gửi · AI chỉ dùng số liệu trong báo cáo</div>',
                        unsafe_allow_html=True)
        if go_vao:
            yeu_cau = (go_vao, "hoi")

    if yeu_cau:
        cau, kieu = yeu_cau
        cho.markdown(f'<div class="ban_hang"><div class="ban_bong">{html.escape(cau)}</div></div>'
                     '<div class="ai_hang"><div class="ai_anh">✦</div><div class="ai_bong ai_doc"><span><i></i><i></i>'
                     '<i></i></span>Đang đọc số liệu…</div></div>', unsafe_allow_html=True)
        lich_su = [t for t in hoi_thoai if t["content"]]
        hoi_thoai.append({"role": "user", "content": cau})
        loai = "hoi_dap"
        try:
            if kieu == "giai_thich" and pham_vi == "bieu_do":
                tl, loai = llm.giai_thich(ma, bl, goi), "giai_thich"
            elif kieu == "giai_thich":
                tl, loai = llm.tom_tat(ma_log, bl, goi), "tom_tat"
            else:
                tl = llm.hoi_dap(ma_log, bl, goi, lich_su, cau)
            hoi_thoai.append({"role": "assistant", "content": tl.noi_dung, "tl": tl, "loai": loai, "ten": ten_bd,
                              "pham_vi": pham_vi, "gio": datetime.now().strftime("%H:%M")})
        except llm.LoiAI as e:
            hoi_thoai.append({"role": "assistant", "content": "", "loi": str(e)})
        st.rerun()
