"""Đối chiếu số do ai/queries.py tính với số Power BI ra trong bảng nghiệm thu B6 (powerbi/README.md).

Chạy từ gốc repo khi Postgres đang chạy:   python ai/kiem_tra_so_lieu.py
Có dòng ✗ = truy vấn tính khác Power BI -> AI sẽ nhận số sai, phải sửa trước khi dùng.
"""
import sys

import queries as q

sys.stdout.reconfigure(encoding="utf-8")
ket_qua = []


def so(ten: str, thuc: float, mong_doi: float, sai_so: float) -> None:
    dat = abs(thuc - mong_doi) <= sai_so
    ket_qua.append(dat)
    print(f"{'✓' if dat else '✗'} {ten:<46} ra {thuc:>16,.4f}   phải ra {mong_doi:>16,.4f}")


bl = q.BoLoc()

# Trang 1
k = q.the_kpi(1, bl)
so("K1 Doanh thu", k["K1"]["gia_tri"], 13_449_529.68, 0.01)
so("K2 Số đơn", k["K2"]["gia_tri"], 97_905, 0)
so("K3 Giá trị đơn TB", k["K3"]["gia_tri"], 137.37, 0.005)
so("K4 Số khách hàng", k["K4"]["gia_tri"], 94_703, 0)
so("K5 Tỉ lệ khách mua lại", k["K5"]["gia_tri"], 0.02265, 0.00005)
ck = q.doanh_thu_theo_thang(bl).tom_tat["so_cung_ky"]
so("Q1 doanh thu 01–08/2017", ck["doanh_thu"]["2017"], 3_080_850.81, 0.01)
so("Q1 doanh thu 01–08/2018", ck["doanh_thu"]["2018"], 7_341_037.41, 0.01)
so("Q1 M2 % so cùng kỳ", ck["doanh_thu"]["tang_truong"], 1.383, 0.0005)
so("Q1 số đơn 01–08/2017", ck["so_don"]["2017"], 22_562, 0)
so("Q1 số đơn 01–08/2018", ck["so_don"]["2018"], 53_530, 0)
so("Q1 AOV 01–08/2017", ck["gia_tri_don_tb"]["2017"], 136.55, 0.005)
so("Q1 AOV 01–08/2018", ck["gia_tri_don_tb"]["2018"], 137.14, 0.005)
thang = q.doanh_thu_theo_thang(bl).bang.set_index("ky")
so("Q1 doanh thu đỉnh 11/2017", thang.at["11/2017", "doanh_thu"], 1_003_862, 1)
dm = q.top10_danh_muc(bl).bang.set_index("danh_muc_en")
so("Q2 health_beauty", dm.at["health_beauty", "ti_trong"], 0.0930, 0.00005)
bang = q.doanh_thu_theo_bang(bl).bang.set_index("bang")
for b, v in {"SP": 0.3830, "RJ": 0.1340, "MG": 0.1166, "RS": 0.0550, "PR": 0.0502}.items():
    so(f"Q2 bang {b}", bang.at[b, "ti_trong"], v, 0.00005)

# Trang 2
k = q.the_kpi(2, bl)
so("K6 Tỉ lệ giao trễ", k["K6"]["gia_tri"], 6_531 / 96_203, 0.000001)
so("K7 Thời gian giao TB", k["K7"]["gia_tri"], 12.54, 0.005)
so("K8 Điểm đánh giá TB", k["K8"]["gia_tri"], 4.089, 0.0005)
so("K9 Tỉ lệ đánh giá tiêu cực", k["K9"]["gia_tri"], 0.1463, 0.00005)
tre = q.tre_theo_thang(bl)
thang = tre.bang.set_index("ky")
for t, v in {"11/2017": 0.1240, "02/2018": 0.1413, "03/2018": 0.1896}.items():
    so(f"Q3 tỉ lệ trễ {t}", thang.at[t, "ti_le_tre"], v, 0.00005)
so("Q3 số tháng vượt 10%", len(tre.tom_tat["thang_vuot_nguong"]), 3, 0)
top_bang = q.tre_theo_bang(bl).bang.iloc[0]
so(f"Q3 bang trễ nhất ({top_bang.bang}, phải là AL)", top_bang.ti_le_tre if top_bang.bang == "AL" else -1, 0.2146, 0.00005)
muc = q.diem_theo_muc_tre(bl)
cap1 = muc.tom_tat["diem_tb_theo_ket_qua_giao"]
so("Q4 điểm Đúng hạn", cap1["Đúng hạn"], 4.29, 0.005)
so("Q4 điểm Trễ hạn", cap1["Trễ hạn"], 2.27, 0.005)
cap2 = muc.bang.set_index("muc_tre").diem_tb
for m, v in {"Trễ 1–3 ngày": 3.29, "Trễ 4–7 ngày": 2.10, "Trễ 8–14 ngày": 1.67, "Trễ > 14 ngày": 1.72}.items():
    so(f"Q4 điểm {m}", cap2[m], v, 0.005)

# Trang 3
k = q.the_kpi(3, bl)
so("K10 Số người bán hoạt động", k["K10"]["gia_tri"], 3_029, 0)
so("K11 Doanh thu TB mỗi người bán", k["K11"]["gia_tri"], 4_440.25, 0.005)
so("K12 Tỉ lệ bàn giao trễ (trong kỳ)", k["K12"]["gia_tri"], 0.0890, 0.00005)
so("K13 Tỷ trọng top 10% người bán", k["K13"]["gia_tri"], 0.6738, 0.00005)
q5 = q.tre_theo_ban_giao(bl)
tl = q5.tom_tat["ti_le_tre_moi_tuyen"]
so("Q5 giao trễ khi bàn giao trễ", tl["Trễ hạn"], 0.2108, 0.00005)
so("Q5 giao trễ khi bàn giao đúng hạn", tl["Đúng hạn"], 0.0539, 0.00005)
tuyen = q5.bang.set_index(["ban_giao", "tuyen"]).ti_le_tre
for (bg, ty), v in {("Đúng hạn", "Nội bang"): 0.029, ("Đúng hạn", "Liên bang"): 0.068,
                    ("Trễ hạn", "Nội bang"): 0.207, ("Trễ hạn", "Liên bang"): 0.212}.items():
    so(f"Q5 {bg} · {ty}", tuyen[(bg, ty)], v, 0.0005)
q6 = q.top10_nguoi_ban_can_xu_ly(bl).tom_tat
so("Q6 số người bán ≥ 30 đơn", q6["so_nguoi_ban_tu_30_don"], 633, 0)
so("Q6 số người bán cần xử lý (M5 = 1)", q6["so_nguoi_ban_can_xu_ly"], 191, 0)
so("Q6 tỉ trọng doanh thu người bán cần xử lý", q6["ti_trong_doanh_thu_nguoi_ban_can_xu_ly"], 0.219, 0.0005)

# Lọc 1 bang thì số trên thẻ phải bằng dòng của bang đó ở biểu đồ theo bang (bộ lọc đi đúng vào cả 3 fact).
# Không so với kịch bản B7 #4 được: số B7 #4 (SP 5.163.867, AL 21,41%) đo khi bỏ lọc kỳ phân tích.
tre_bang = q.tre_theo_bang(q.BoLoc()).bang.set_index("bang")
for b in ("SP", "AL"):
    loc = q.BoLoc(bang=b)
    so(f"Lọc bang {b}: K1 = dòng {b} của Q2 (2)", q.the_kpi(1, loc)["K1"]["gia_tri"], bang.at[b, "doanh_thu"], 0.01)
    if b in tre_bang.index:
        so(f"Lọc bang {b}: K6 = dòng {b} của Q3 (2)", q.the_kpi(2, loc)["K6"]["gia_tri"], tre_bang.at[b, "ti_le_tre"],
           0.000001)

# Mọi biểu đồ chạy được với các tổ hợp bộ lọc (không so số, chỉ bắt lỗi)
for loc in [dict(nam=2018, thang=3), dict(nam=2017, vung="Nordeste"), dict(thang=12, bang="RJ", bang_nb="SP"),
            dict(nam=2018, thang=11)]:
    for ma, bd in q.BIEU_DO.items():
        bl = q.bo_loc_cua_trang(bd.trang, **loc)
        bd.ham(bl), q.the_kpi(bd.trang, bl)
print("✓ 12 biểu đồ chạy được với 4 tổ hợp bộ lọc")

print(f"\n{sum(ket_qua)}/{len(ket_qua)} số khớp")
sys.exit(0 if all(ket_qua) else 1)
