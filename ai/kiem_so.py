"""Kiểm số trong câu trả lời của AI: mỗi con số AI viết có nằm trong dữ liệu đã đưa cho nó không.

Mỗi số được xếp 1 trong 3 loại:
- "khop": bằng 1 giá trị trong gói số liệu / kết quả công cụ sau khi làm tròn theo số chữ số AI viết
  (tỉ lệ thập phân 0,0679 khớp với "6,8%");
- "tu_tinh": không có sẵn nhưng ra đúng bằng 1 phép tính (+ − ÷, % tăng) giữa 2 số đã khớp trong câu trả lời,
  VD "12,97 − 7,65 = 5,32" – AI tự tính và tính đúng (sai số làm tròn ≤ 1%);
- còn lại: không tìm thấy -> app tô cam để người xem tự kiểm (chưa chắc sai), không tự sửa.
Bỏ qua số nguyên ≤ 12 (tháng, số thứ tự) và năm 2016–2019.
"""
import math
import re

_DON_VI = {"triệu": 1e6, "tr": 1e6, "nghìn": 1e3, "ngàn": 1e3, "tỷ": 1e9, "tỉ": 1e9}
_SO = re.compile(
    r"(?<![\w/.,])"
    r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"   # 13.449.529,68 | 6,79 | 4.29 | 97905
    r"(?![\w/]|[.,]\d)"
    r"(\s*%)?"
    r"(\s*(?:triệu|tr|nghìn|ngàn|tỷ|tỉ)\b)?"
)


def _cach_doc(chuoi: str) -> list[tuple[float, int]]:
    """Các cách hiểu 1 chuỗi số -> [(giá trị, số chữ số thập phân)]. Ưu tiên kiểu Việt, thử thêm kiểu Anh."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", chuoi):
        nguyen, _, le = chuoi.partition(",")
        kq = [(float(nguyen.replace(".", "") + ("." + le if le else "")), len(le))]
        if chuoi.count(".") == 1 and not le:  # "1.003" cũng có thể là 1,003 kiểu Anh
            kq.append((float(chuoi), 3))
        return kq
    if "," in chuoi:
        nguyen, le = chuoi.split(",")
        kq = [(float(f"{nguyen}.{le}"), len(le))]
        if len(le) == 3:  # "1,234" kiểu Anh = 1234
            kq.append((float(nguyen + le), 0))
        return kq
    if "." in chuoi:
        return [(float(chuoi), len(chuoi.split(".")[1]))]
    return [(float(chuoi), 0)]


def tach_so(van_ban: str) -> list[dict]:
    """Mọi con số cần kiểm trong 1 đoạn văn: vị trí, chữ gốc, các cách hiểu (đã nhân đơn vị triệu / nghìn)."""
    ds = []
    for m in _SO.finditer(van_ban):
        chuoi, phan_tram, don_vi = m.group(1), bool(m.group(2)), m.group(3)
        he_so = _DON_VI[don_vi.strip()] if don_vi else 1.0
        cach = [(v * he_so, d, he_so) for v, d in _cach_doc(chuoi)]
        v0, d0, _ = cach[0]
        if not phan_tram and not don_vi and d0 == 0 and (v0 <= 12 or 2016 <= v0 <= 2019):
            continue
        ds.append({"bat_dau": m.start(), "ket_thuc": m.end(), "chu": m.group(0).strip(), "phan_tram": phan_tram,
                   "cach_hieu": cach})
    return ds


def _gia_tri(du_lieu) -> list[float]:
    """Mọi số trong dữ liệu (kể cả số nằm trong chuỗi, VD ghi chú "+138,3% so cùng kỳ")."""
    kq = []
    if isinstance(du_lieu, bool) or du_lieu is None:
        return kq
    if isinstance(du_lieu, (int, float)):
        if not (isinstance(du_lieu, float) and math.isnan(du_lieu)):
            kq.append(float(du_lieu))
    elif isinstance(du_lieu, str):
        for s in tach_so(du_lieu):
            for v, _, _ in s["cach_hieu"]:
                kq += [v, v / 100] if s["phan_tram"] else [v]
    elif isinstance(du_lieu, dict):
        for v in du_lieu.values():
            kq += _gia_tri(v)
    elif isinstance(du_lieu, (list, tuple)):
        for v in du_lieu:
            kq += _gia_tri(v)
    return kq


def kiem(tra_loi: str, *nguon) -> list[dict]:
    """Đối chiếu số trong câu trả lời với mọi số của các nguồn (gói số liệu, kết quả công cụ, câu hỏi)."""
    gia_tri = []
    for n in nguon:
        gia_tri += _gia_tri(n)
    ung_vien = gia_tri + [v * 100 for v in gia_tri]  # tỉ lệ thập phân 0,0679 <-> 6,79%
    kq = []
    for s in tach_so(tra_loi):
        khop = any(
            abs(c - v) <= 0.5 * 10 ** (-d) * he_so + 1e-9 * max(1.0, abs(v))
            for v, d, he_so in s["cach_hieu"] for c in ung_vien
        )
        kq.append({**s, "khop": khop, "tu_tinh": ""})
    # Số chưa khớp: thử các phép tính giữa 2 số đã khớp (giá trị như AI viết)
    toan_hang = [(s["cach_hieu"][0][0], s["chu"]) for s in kq if s["khop"]]
    for s in kq:
        if not s["khop"]:
            s["tu_tinh"] = _tim_phep_tinh(s["cach_hieu"], toan_hang)
    return kq


def _tim_phep_tinh(cach_hieu: list, toan_hang: list[tuple[float, str]]) -> str:
    """Lượt 1 chỉ cho sai số làm tròn (tránh gán nhầm phép tính trùng hợp), lượt 2 nới tới 1%."""
    for luot in (1, 2):
        for x, d, _ in cach_hieu:
            sai_so = 0.5 * 10 ** (-d) + 1e-9 if luot == 1 else max(0.5 * 10 ** (-d), 0.01 * abs(x))
            for i, (a, ca) in enumerate(toan_hang):
                for j, (b, cb) in enumerate(toan_hang):
                    if i == j:
                        continue
                    phep = [(a + b, f"{ca} + {cb}"), (a - b, f"{ca} − {cb}")]
                    if b:
                        phep += [(a / b, f"{ca} ÷ {cb}"), ((a / b - 1) * 100, f"({ca} ÷ {cb} − 1) × 100")]
                    for gia_tri, mo_ta in phep:
                        if abs(gia_tri - x) <= sai_so:
                            return mo_ta
    return ""


def dem(ket_qua: list[dict]) -> dict:
    return {
        "tong_so": len(ket_qua),
        "khop_du_lieu": sum(s["khop"] for s in ket_qua),
        "tu_tinh_dung": sum(bool(s["tu_tinh"]) for s in ket_qua),
        "khong_tim_thay": [s["chu"] for s in ket_qua if not s["khop"] and not s["tu_tinh"]],
    }


def to_dam(tra_loi: str, ket_qua: list[dict]) -> str:
    """Markdown của câu trả lời (cú pháp màu của Streamlit): số AI tự tính đúng tô xanh, số không tìm thấy tô cam."""
    ra, tu = [], 0
    for s in ket_qua:
        if s["khop"]:
            continue
        mau = "blue" if s["tu_tinh"] else "orange"
        ra += [tra_loi[tu:s["bat_dau"]], f":{mau}-background[{tra_loi[s['bat_dau']:s['ket_thuc']]}]"]
        tu = s["ket_thuc"]
    return "".join(ra) + tra_loi[tu:]
