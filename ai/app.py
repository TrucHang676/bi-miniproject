"""Hỏi AI về biểu đồ của dashboard Olist – app Streamlit đi kèm Power BI.

Chọn biểu đồ + bộ lọc -> hiện đúng số liệu của biểu đồ đó (lấy thẳng từ dds), rồi hỏi AI dựa trên chính số liệu đó:
tóm tắt trang, giải thích biến động, hỏi đáp tự do. Số trong câu trả lời được kiểm lại với dữ liệu (kiem_so.py)
và mỗi lần hỏi lưu log vào ai/outputs/. Cần GEMINI_API_KEY (và GROQ_API_KEY dự phòng) trong .env – xem llm.py.

Chạy từ gốc repo khi Postgres đang chạy:   streamlit run ai/app.py
Nút "Hỏi AI" trong Power BI mở link dạng:  http://localhost:8501/?bieu_do=Q5_2&nam=2018&thang=3
Tham số link: bieu_do (Q1_1 … Q6_2), nam, thang, vung, bang, bang_nb – thiếu tham số nào thì không lọc theo đó.
"""
import plotly.express as px
import plotly.graph_objects as go
import psycopg
import streamlit as st
from plotly.subplots import make_subplots

import kiem_so
import llm
import queries as q

st.set_page_config(page_title="Hỏi AI – Olist BI", page_icon="💬", layout="wide")

# Màu theo dashboard: tím = giá trị chính, đỏ san hô = vượt ngưỡng, xám = đường tham chiếu
TIM, DO, XAM, XANH = "#8C9EF0", "#EF6F61", "#8B9099", "#1D5E12"
TAT_CA = "Tất cả"


@st.cache_data(ttl=600, show_spinner="Đang lấy số liệu từ dds…")
def _so_lieu(ma: str, bl: q.BoLoc):
    kq = q.BIEU_DO[ma].ham(bl)
    return kq.bang, kq.tom_tat


@st.cache_data(ttl=600, show_spinner=False)
def _kpi(trang: int, bl: q.BoLoc):
    return q.the_kpi(trang, bl)


@st.cache_data(ttl=600, show_spinner="Đang gom số liệu cả trang…")
def _goi_trang(trang: int, bl: q.BoLoc):
    return llm.goi_so_lieu_trang(trang, bl)


@st.cache_data(ttl=3600, show_spinner=False)
def _lua_chon():
    return q.danh_sach_lua_chon()


def _doc_link() -> None:
    """Lần đầu mở app: điền sẵn biểu đồ và bộ lọc từ link của nút Power BI."""
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


def _chon(nhan: str, lua_chon: list, key: str, **kw):
    """selectbox có mục "Tất cả"; giá trị lạ (VD từ link) thì về "Tất cả" thay vì báo lỗi."""
    lua_chon = [TAT_CA] + lua_chon
    if st.session_state.get(key) not in lua_chon:
        st.session_state[key] = TAT_CA
    gia_tri = st.sidebar.selectbox(nhan, lua_chon, key=key, **kw)
    return None if gia_tri == TAT_CA else gia_tri


# ---------------------------------------------------------------------------
# Thanh bên: trang, biểu đồ, bộ lọc
# ---------------------------------------------------------------------------
_doc_link()
st.sidebar.title("💬 Hỏi AI về biểu đồ")
trang = st.sidebar.selectbox("Trang dashboard", list(q.TRANG), key="trang",
                             format_func=lambda t: f"Trang {t} – {q.TRANG[t].ten}")
ma_cua_trang = [m for m, b in q.BIEU_DO.items() if b.trang == trang]
if st.session_state.get("bieu_do") not in ma_cua_trang:
    st.session_state.bieu_do = ma_cua_trang[0]
ma = st.sidebar.selectbox("Biểu đồ", ma_cua_trang, key="bieu_do",
                          format_func=lambda m: f"{q.BIEU_DO[m].cau_hoi} · {q.BIEU_DO[m].ten}")

st.sidebar.markdown("**Bộ lọc** (giống slicer của trang)")
try:
    lc = _lua_chon()
except psycopg.OperationalError:
    st.error("Không kết nối được Postgres. Mở Docker Desktop rồi chạy `docker compose up -d` ở thư mục repo.")
    st.stop()
co_loc = q.TRANG[trang].bo_loc
loc = {
    "nam": _chon("Năm", [2017, 2018], "nam"),
    "thang": _chon("Tháng", list(range(1, 13)), "thang"),
}
if "vung" in co_loc:
    loc["vung"] = _chon("Vùng nhận hàng", lc["vung"], "vung")
if "bang" in co_loc:
    bang_chon = (lc["bang_theo_vung"].get(loc["vung"], []) if loc.get("vung")
                 else sorted(b for ds in lc["bang_theo_vung"].values() for b in ds))
    loc["bang"] = _chon("Bang nhận hàng", bang_chon, "bang")
if "bang_nb" in co_loc:
    loc["bang_nb"] = _chon("Bang người bán", lc["bang_nb"], "bang_nb")
bl = q.bo_loc_cua_trang(trang, **loc)
st.sidebar.caption("Kỳ phân tích cố định 01/2017 – 08/2018 như filter của report Power BI.")

# ---------------------------------------------------------------------------
# Nội dung chính
# ---------------------------------------------------------------------------
bd = q.BIEU_DO[ma]
st.caption(f"Trang {bd.trang} – {q.TRANG[bd.trang].ten}")
st.subheader(f"{bd.cau_hoi}. {q.CAU_HOI[bd.cau_hoi]}")
st.markdown(f"**{bd.ten}** · Bộ lọc: {bl.mo_ta()}")

bang, tom_tat = _so_lieu(ma, bl)
kpi = _kpi(bd.trang, bl)

cot_kpi = st.columns(len(kpi))
for c, (k, v) in zip(cot_kpi, kpi.items()):
    c.metric(f"{k} · {v['ten']}", q.dinh_dang(v["gia_tri"], v["kieu"]), help=v.get("ghi_chu") or None)
    if v.get("ghi_chu"):
        c.caption(v["ghi_chu"])

if bang.empty:
    st.warning(tom_tat.get("ghi_chu", "Không có dữ liệu với bộ lọc này"))
    st.stop()

# Biểu đồ theo tháng hiện đủ các tháng để AI có tháng khác mà so (queries._ca_cac_thang)
THEO_THANG = ("Q1_1", "Q1_2", "Q3_1", "Q4_2", "Q5_2")
if bl.thang and ma in THEO_THANG:
    st.caption(f"Biểu đồ theo tháng vẫn hiện đủ các tháng, tháng {bl.thang} được đánh dấu đỏ, để so với các tháng khác. "
               "Thẻ KPI phía trên thì lọc đúng tháng đang chọn như trên Power BI.")


def _hai_truc(x, cot, ten_cot, duong, ten_duong, mau_cot) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=x, y=cot, name=ten_cot, marker_color=mau_cot)
    fig.add_scatter(x=x, y=duong, name=ten_duong, mode="lines+markers", line_color=XANH, secondary_y=True)
    return fig


def _ve(ma: str, df) -> go.Figure:
    """Vẽ lại biểu đồ cùng kiểu với dashboard để người dùng đối chiếu số trước khi hỏi AI."""
    if ma == "Q1_1":
        fig = px.line(df.assign(nam=df.nam.astype(str)), x="thang", y="doanh_thu", color="nam", markers=True,
                      color_discrete_sequence=[XAM, TIM], labels={"thang": "Tháng", "doanh_thu": "Doanh thu (BRL)"})
    elif ma == "Q1_2":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for nam, mau in ((2017, XAM), (2018, TIM)):
            d = df[df.nam == nam]
            fig.add_bar(x=d.thang, y=d.so_don, name=f"Số đơn {nam}", marker_color=mau)
            fig.add_scatter(x=d.thang, y=d.gia_tri_don_tb, name=f"AOV {nam}", mode="lines+markers",
                            line_color=mau, line_dash="dot", secondary_y=True)
    elif ma == "Q2_1":
        fig = px.bar(df, x="ti_trong", y="danh_muc", orientation="h", text_auto=".1%",
                     color_discrete_sequence=[TIM], labels={"ti_trong": "% tổng doanh thu", "danh_muc": ""})
        fig.update_yaxes(autorange="reversed")
    elif ma == "Q2_2":
        d = df.head(10)
        fig = px.bar(d, x="ti_trong", y="ten_bang", orientation="h", text_auto=".1%", color="vung",
                     labels={"ti_trong": "% tổng doanh thu", "ten_bang": "", "vung": "Vùng"})
        fig.update_yaxes(autorange="reversed")
    elif ma == "Q3_1":
        fig = px.line(df, x="ky", y="ti_le_tre", markers=True, color_discrete_sequence=[TIM],
                      labels={"ky": "Tháng", "ti_le_tre": "Tỉ lệ giao trễ"})
        fig.add_hline(y=0.10, line_dash="dash", line_color=XAM, annotation_text="Ngưỡng 10%")
    elif ma == "Q3_2":
        fig = px.bar(df, x="ti_le_tre", y="ten_bang", orientation="h", text_auto=".1%",
                     color=df.ti_le_tre.gt(0.10).map({True: "Vượt 10%", False: "Trong ngưỡng"}),
                     color_discrete_map={"Vượt 10%": DO, "Trong ngưỡng": TIM},
                     labels={"ti_le_tre": "Tỉ lệ giao trễ", "ten_bang": "", "color": ""})
        fig.add_vline(x=0.10, line_dash="dash", line_color=XAM)
        fig.update_yaxes(autorange="reversed")
    elif ma == "Q4_1":
        fig = px.bar(df, x="muc_tre", y="diem_tb", text_auto=".2f", color="ket_qua",
                     color_discrete_map={"Đúng hạn": TIM, "Trễ hạn": DO},
                     labels={"muc_tre": "", "diem_tb": "Điểm TB (★)", "ket_qua": ""})
        fig.add_hline(y=tom_tat["diem_tb_toan_san"], line_dash="dash", line_color=XAM,
                      annotation_text=f"TB toàn sàn {q.so_vn(tom_tat['diem_tb_toan_san'], 2)}")
    elif ma == "Q4_2":
        fig = _hai_truc(df.ky, df.ti_le_tre, "Tỉ lệ giao trễ", df.diem_tb, "Điểm TB (trục phải)",
                        [DO if v > 0.10 else TIM for v in df.ti_le_tre])
    elif ma == "Q5_1":
        fig = px.bar(df, x="ban_giao", y="ti_le_tre", color="tuyen", barmode="group", text_auto=".1%",
                     color_discrete_map={"Nội bang": TIM, "Liên bang": DO},
                     labels={"ban_giao": "Người bán bàn giao", "ti_le_tre": "Tỉ lệ giao trễ", "tuyen": "Tuyến"})
    elif ma == "Q5_2":
        fig = _hai_truc(df.ky, df.ti_le_ban_giao_tre, "Tỉ lệ bàn giao trễ", df.van_chuyen_tb,
                        "Vận chuyển TB, ngày (trục phải)", [DO if v > 0.10 else TIM for v in df.ti_le_tre])
    elif ma == "Q6_1":
        fig = px.scatter(df, x="ti_le_ban_giao_tre", y="diem_tb", size="doanh_thu", hover_name="nguoi_ban",
                         color=df.can_xu_ly.map({True: "Vượt ngưỡng", False: "Trong ngưỡng"}),
                         color_discrete_map={"Vượt ngưỡng": DO, "Trong ngưỡng": TIM},
                         labels={"ti_le_ban_giao_tre": "Tỉ lệ bàn giao trễ", "diem_tb": "Điểm TB (★)", "color": ""})
        fig.add_vline(x=0.10, line_dash="dash", line_color=XAM)
        fig.add_hline(y=3.5, line_dash="dash", line_color=XAM)
    else:  # Q6_2
        fig = px.bar(df, x="doanh_thu", y="nguoi_ban", orientation="h", text="canh_bao", color_discrete_sequence=[DO],
                     labels={"doanh_thu": "Doanh thu (BRL)", "nguoi_ban": ""})
        fig.update_yaxes(autorange="reversed")
    if bl.thang and ma in THEO_THANG:  # đánh dấu tháng đang chọn trên trục tháng
        for x in ([bl.thang] if ma in ("Q1_1", "Q1_2") else df.loc[df.thang == bl.thang, "ky"]):
            fig.add_vline(x=x, line_color=DO, line_width=2, opacity=0.5)
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), legend_title_text="")
    if ma in ("Q3_1", "Q4_2", "Q5_1", "Q5_2"):  # trục tỉ lệ nằm dọc
        fig.update_layout(yaxis_tickformat=".0%")
    if ma in ("Q2_1", "Q2_2", "Q3_2", "Q6_1"):  # trục tỉ lệ nằm ngang
        fig.update_layout(xaxis_tickformat=".0%")
    return fig


trai, phai = st.columns([3, 2])
with trai:
    st.plotly_chart(_ve(ma, bang), width="stretch")
with phai:
    st.markdown("**Số liệu kết luận**")
    st.json(q._sach(tom_tat), expanded=2)

# Bảng hiển thị: số định dạng kiểu Việt; cột kỹ thuật (mã gốc, năm/tháng đã gộp thành cột "ky") ẩn đi
an = ["seller_id", "danh_muc_en", "can_xu_ly"] + (["nam", "thang"] if "ky" in bang else [])
hien = bang.drop(columns=[c for c in an if c in bang])
hien = hien.assign(**{c: hien[c].map(lambda x, k=q.COT[c][1]: q.dinh_dang(x, k))
                      for c in hien.columns if c in q.COT and q.COT[c][1] != "chu"})
hien = hien.rename(columns={c: q.COT[c][0] for c in hien.columns if c in q.COT})
if bl.thang and ma in THEO_THANG:
    dang_xem = (bang.thang == bl.thang).tolist()
    hien = hien.style.apply(lambda r: [f"background-color: {DO}33" if dang_xem[r.name] else ""] * len(r), axis=1)
st.dataframe(hien, hide_index=True, width="stretch", height=min(36 * (len(bang) + 1), 420))

# ---------------------------------------------------------------------------
# Hỏi AI
# ---------------------------------------------------------------------------
st.divider()
st.markdown("#### 💬 Hỏi AI về biểu đồ này")
dich_vu = llm.nha_cung_cap()
if dich_vu:
    st.caption("AI: " + " → dự phòng ".join(f"{d.ten} ({d.model})" for d in dich_vu)
               + ". AI chỉ được dùng số trong gói số liệu bên dưới; số trong câu trả lời được kiểm lại tự động.")
else:
    st.warning("Chưa có API key. Thêm `GEMINI_API_KEY` (và `GROQ_API_KEY` dự phòng) vào file `.env` ở gốc repo "
               "rồi tải lại trang.")

goi = q.du_lieu_cho_ai(ma, bl, q.KetQua(bang, tom_tat), kpi)
with st.expander("Gói số liệu gửi cho AI (JSON)"):
    st.json(goi)

# Mỗi biểu đồ + bộ lọc có 1 cuộc hội thoại riêng, vì số liệu AI dựa vào khác nhau
hoi_thoai = st.session_state.setdefault("hoi_thoai", {}).setdefault(f"{ma}|{bl}", [])

nut1, nut2, nut3, _ = st.columns([1.2, 1.5, 1, 2])
bam_tom_tat = nut1.button("📝 Tóm tắt trang", disabled=not dich_vu, width="stretch")
bam_giai_thich = nut2.button("🔍 Giải thích biểu đồ này", disabled=not dich_vu, width="stretch")
if nut3.button("🗑 Xóa hội thoại", disabled=not hoi_thoai, width="stretch"):
    hoi_thoai.clear()
    st.rerun()
cau_hoi = st.chat_input("VD: Vì sao tháng 03/2018 giao trễ tăng? Bang người bán nào bàn giao trễ nhiều?",
                        disabled=not dich_vu)


def _hoi_ai(nhan: str, goi_ham) -> None:
    hoi_thoai.append({"role": "user", "content": nhan})
    try:
        with st.spinner("AI đang đọc số liệu…"):
            tl = goi_ham()
        hoi_thoai.append({"role": "assistant", "content": tl.noi_dung, "tl": tl})
    except llm.LoiAI as e:
        hoi_thoai.append({"role": "assistant", "content": "", "loi": str(e)})


if bam_tom_tat:
    _hoi_ai(f"📝 Tóm tắt trang {bd.trang} – {q.TRANG[bd.trang].ten}",
            lambda: llm.tom_tat_trang(bd.trang, bl, _goi_trang(bd.trang, bl)))
if bam_giai_thich:
    _hoi_ai(f"🔍 Giải thích biểu đồ \"{bd.ten}\"", lambda: llm.giai_thich(ma, bl, goi))
if cau_hoi:
    lich_su = [t for t in hoi_thoai if t["content"]]
    _hoi_ai(cau_hoi, lambda: llm.hoi_dap(ma, bl, goi, lich_su, cau_hoi))

for t in hoi_thoai:
    with st.chat_message(t["role"]):
        if t["role"] == "user":
            st.markdown(t["content"])
        elif "loi" in t:
            st.error(f"AI chưa trả lời được: {t['loi']}")
        else:
            tl = t["tl"]
            st.markdown(kiem_so.to_dam(tl.noi_dung, tl.kiem_so))
            tk = tl.thong_ke_so
            if tk["tong_so"] == 0:
                kiem = "Không có con số nào cần kiểm"
            else:
                kiem = f"{tk['khop_du_lieu']}/{tk['tong_so']} số khớp dữ liệu"
                if tk["tu_tinh_dung"]:
                    kiem += f", {tk['tu_tinh_dung']} số AI tự tính đúng (tô xanh)"
                kiem = (f"⚠ {kiem}, {len(tk['khong_tim_thay'])} số không tìm thấy trong dữ liệu (tô cam) – cần tự kiểm"
                        if tk["khong_tim_thay"] else f"✅ {kiem}")
            st.caption(f"{kiem} · {tl.nha_cung_cap} {tl.model} · {tl.token_vao:,} + {tl.token_ra:,} token · "
                       f"log: `{tl.file_log}`")
            if tl.model_loi_truoc:
                st.caption("Đã chuyển sang model dự phòng vì: " + " · ".join(tl.model_loi_truoc))
            if tl.cong_cu:
                with st.expander(f"AI đã lấy thêm số liệu {len(tl.cong_cu)} lần"):
                    for c in tl.cong_cu:
                        st.markdown(f"`lay_so_lieu({c['tham_so']})`")
                        st.json(c["ket_qua"], expanded=False)
