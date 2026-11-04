"""Gọi LLM cho app hỏi AI: Gemini (gói free) làm chính, Groq (gói free) dự phòng khi Gemini hết lượt hoặc lỗi.

Cả hai có cổng tương thích OpenAI nên dùng chung thư viện openai. Cấu hình trong .env ở gốc repo:
    GEMINI_API_KEY=...    AI_MODEL_GEMINI=gemini-3.5-flash,gemini-3.5-flash-lite   (model có mặc định, chỉ cần key)
    GROQ_API_KEY=...      AI_MODEL_GROQ=llama-3.3-70b-versatile
    OLLAMA_MODEL=...      (tùy chọn: chạy offline bằng Ollama, OLLAMA_URL mặc định http://localhost:11434/v1)
Mỗi biến AI_MODEL_* nhận nhiều model cách nhau dấu phẩy, thử lần lượt (model đầu quá tải thì dùng model sau).
04/11/2026 với key gói free: gemini-3.5-flash ~4 giây/câu, 3.5-flash-lite và 3.1-flash-lite chạy được,
gemini-3.8-flash / gemini-flash-latest báo 503 (quá tải), gemini-2.5-flash đã bị gỡ (404).
Mỗi lần hỏi lưu 1 file JSON vào ai/outputs/: số liệu đầu vào, công cụ AI đã gọi, câu trả lời, kết quả kiểm số.

Từ gốc repo:  python ai/llm.py --models   (model dùng được với key hiện có)
              python ai/llm.py --thu      (hỏi thử 1 câu về Q5 tháng 03/2018)
"""
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import openai
from openai import OpenAI

import kiem_so
import queries as q  # import db -> đã nạp .env

THU_MUC = Path(__file__).resolve().parent
SO_VONG_CONG_CU = 3  # tối đa 3 lượt gọi công cụ cho 1 câu hỏi, sau đó bắt AI trả lời
SO_LUOT_LICH_SU = 6  # số tin nhắn chat gần nhất gửi kèm


@dataclass(frozen=True)
class NhaCungCap:
    ten: str
    base_url: str
    model: str
    api_key: str


def nha_cung_cap() -> list[NhaCungCap]:
    """Thứ tự thử: các model Gemini -> Groq -> Ollama; chỉ lấy dịch vụ đã có key / cấu hình trong .env."""
    cau_hinh = [
        ("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY",
         "AI_MODEL_GEMINI", "gemini-3.5-flash,gemini-3.5-flash-lite"),
        ("Groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "AI_MODEL_GROQ", "llama-3.3-70b-versatile"),
    ]
    ds = []
    for ten, url, bien_key, bien_model, mac_dinh in cau_hinh:
        if os.getenv(bien_key):
            for model in os.getenv(bien_model, mac_dinh).split(","):
                if model.strip():
                    ds.append(NhaCungCap(ten, url, model.strip(), os.environ[bien_key]))
    if os.getenv("OLLAMA_MODEL"):
        ds.append(NhaCungCap("Ollama", os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
                             os.environ["OLLAMA_MODEL"], "ollama"))
    return ds


class LoiAI(Exception):
    """Không dịch vụ nào trả lời được; thông điệp ghi lý do của từng dịch vụ."""


@dataclass
class TraLoi:
    noi_dung: str
    nha_cung_cap: str
    model: str
    cong_cu: list = field(default_factory=list)   # [{cong_cu, tham_so, ket_qua}]
    kiem_so: list = field(default_factory=list)   # kết quả kiem_so.kiem
    token_vao: int = 0
    token_ra: int = 0
    file_log: str = ""
    model_loi_truoc: list = field(default_factory=list)  # model đã thử trước mà lỗi (quá tải, hết lượt…)

    @property
    def thong_ke_so(self) -> dict:
        """{tong_so, khop_du_lieu, tu_tinh_dung, khong_tim_thay} – xem kiem_so.py."""
        return kiem_so.dem(self.kiem_so)


# ---------------------------------------------------------------------------
# Prompt và công cụ
# ---------------------------------------------------------------------------
def _doc_prompt(ten_file: str) -> tuple[str, str]:
    """Tách phần "## System" và "## User" của 1 file trong ai/prompts/."""
    van_ban = (THU_MUC / "prompts" / ten_file).read_text(encoding="utf-8")
    phan = {}
    for khoi in re.split(r"^## ", van_ban, flags=re.M)[1:]:
        tieu_de, _, noi_dung = khoi.partition("\n")
        phan[tieu_de.strip()] = noi_dung.strip()
    return phan["System"], phan["User"]


def _dien(mau: str, **gia_tri) -> str:
    for k, v in gia_tri.items():
        mau = mau.replace("{{" + k + "}}", v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1))
    return mau


CONG_CU = [{
    "type": "function",
    "function": {
        "name": "lay_so_lieu",
        "description": (
            "Lấy số liệu của 1 biểu đồ trên dashboard Olist, tính thẳng từ kho dữ liệu bằng cùng công thức với Power BI. "
            "Chỉ gọi khi câu hỏi cần số mà gói số liệu hiện có không có. Các biểu đồ: "
            + "; ".join(f"{m} = {b.ten} (trang {b.trang})" for m, b in q.BIEU_DO.items())
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "bieu_do": {"type": "string", "enum": list(q.BIEU_DO), "description": "Mã biểu đồ"},
                "nam": {"type": "integer", "description": "2017 hoặc 2018; bỏ trống = cả kỳ 01/2017 – 08/2018"},
                "thang": {"type": "integer", "description": "1–12; bỏ trống = mọi tháng"},
                "vung": {"type": "string",
                         "description": "Vùng nhận hàng: Norte, Nordeste, Centro-Oeste, Sudeste, Sul (trang 1, 2)"},
                "bang": {"type": "string", "description": "Mã bang nhận hàng 2 chữ, VD SP (chỉ trang 1)"},
                "bang_nb": {"type": "string", "description": "Mã bang người bán 2 chữ, VD SP (chỉ trang 3)"},
            },
            "required": ["bieu_do"],
        },
    },
}]


def _chay_cong_cu(ten: str, tham_so_json: str) -> tuple[dict, dict]:
    """Chạy lay_so_lieu; mọi lỗi trả lại cho AI dưới dạng {"loi": ...} để nó tự sửa tham số."""
    try:
        ts = json.loads(tham_so_json or "{}")
    except json.JSONDecodeError:
        return {}, {"loi": "Tham số không phải JSON hợp lệ"}
    ma = str(ts.get("bieu_do", "")).upper()
    if ten != "lay_so_lieu" or ma not in q.BIEU_DO:
        return ts, {"loi": f"Không có biểu đồ '{ts.get('bieu_do')}'. Chọn 1 trong: {', '.join(q.BIEU_DO)}"}
    bd = q.BIEU_DO[ma]
    try:
        loc = {k: ts.get(k) for k in ("vung", "bang", "bang_nb")}
        for k in ("nam", "thang"):
            loc[k] = int(ts[k]) if str(ts.get(k, "")).strip().isdigit() else None
        bl = q.bo_loc_cua_trang(bd.trang, **loc)
        return ts, q.du_lieu_cho_ai(ma, bl, bd.ham(bl), q.the_kpi(bd.trang, bl), toi_da_dong=25)
    except Exception as e:  # noqa: BLE001 – lỗi truy vấn cũng trả cho AI thay vì làm hỏng câu trả lời
        return ts, {"loi": f"Không lấy được số liệu: {e}"}


# ---------------------------------------------------------------------------
# Gọi LLM
# ---------------------------------------------------------------------------
def _goi(ncc: NhaCungCap, tin_nhan: list[dict], dung_cong_cu: bool) -> TraLoi:
    # model quá tải có lúc treo không trả lời -> chờ 60 giây rồi chuyển model sau, không để người dùng chờ lâu
    client = OpenAI(api_key=ncc.api_key, base_url=ncc.base_url, timeout=60, max_retries=1)
    tin_nhan = list(tin_nhan)
    da_goi, vao, ra = [], 0, 0
    for vong in range(SO_VONG_CONG_CU + 1):
        kw = {}
        if dung_cong_cu:
            # vòng cuối vẫn khai báo công cụ (lịch sử có tin nhắn công cụ) nhưng không cho gọi nữa
            kw = {"tools": CONG_CU, "tool_choice": "none" if vong == SO_VONG_CONG_CU else "auto"}
        r = client.chat.completions.create(model=ncc.model, messages=tin_nhan, temperature=0.2, **kw)
        if r.usage:
            vao += r.usage.prompt_tokens or 0
            ra += r.usage.completion_tokens or 0
        msg = r.choices[0].message
        if not msg.tool_calls:
            return TraLoi((msg.content or "").strip(), ncc.ten, ncc.model, da_goi, token_vao=vao, token_ra=ra)
        # Gửi lại nguyên văn tin nhắn của model: Gemini 3.x gắn thought_signature (extra_content) vào lời gọi
        # công cụ và báo lỗi 400 nếu lượt sau thiếu nó
        tin_nhan.append(msg.model_dump(exclude_none=True))
        for t in msg.tool_calls:
            ts, kq = _chay_cong_cu(t.function.name, t.function.arguments)
            da_goi.append({"cong_cu": t.function.name, "tham_so": ts, "ket_qua": kq})
            tin_nhan.append({"role": "tool", "tool_call_id": t.id, "content": json.dumps(kq, ensure_ascii=False)})
    raise LoiAI(f"{ncc.ten}: AI gọi công cụ quá {SO_VONG_CONG_CU} lượt mà chưa trả lời")


def _hoi(tin_nhan: list[dict], dung_cong_cu: bool) -> TraLoi:
    """Thử lần lượt từng dịch vụ; dịch vụ đầu lỗi (hết lượt, sai key, mất mạng…) thì chuyển dịch vụ sau."""
    ds = nha_cung_cap()
    if not ds:
        raise LoiAI("Chưa có API key. Thêm GEMINI_API_KEY (và GROQ_API_KEY dự phòng) vào file .env ở gốc repo "
                    "rồi chạy lại app.")
    loi = []
    for ncc in ds:
        ten = f"{ncc.ten} {ncc.model}"
        try:
            tl = _goi(ncc, tin_nhan, dung_cong_cu)
            tl.model_loi_truoc = loi
            return tl
        except openai.AuthenticationError:
            loi.append(f"{ten}: API key sai hoặc đã bị thu hồi")
        except openai.RateLimitError:
            loi.append(f"{ten}: hết lượt miễn phí (429) – đợi khoảng 1 phút rồi hỏi lại")
        except openai.NotFoundError:
            loi.append(f"{ten}: không có model này – đổi AI_MODEL_{ncc.ten.upper()} trong .env "
                       "(xem danh sách: python ai/llm.py --models)")
        except openai.APITimeoutError:
            loi.append(f"{ten}: quá 60 giây chưa trả lời (model đang quá tải)")
        except openai.APIConnectionError:
            loi.append(f"{ten}: không kết nối được (kiểm tra mạng)")
        except openai.InternalServerError as e:
            loi.append(f"{ten}: Google / dịch vụ đang quá tải ({e.status_code}) – thử lại sau ít phút")
        except openai.APIStatusError as e:
            loi.append(f"{ten}: lỗi {e.status_code} – {str(e.message)[:200]}")
        except LoiAI as e:
            loi.append(str(e))
    raise LoiAI(" · ".join(loi))


def _ghi_log(che_do: str, ma: str, bl: q.BoLoc, cau_hoi: str, goi: dict, tl: TraLoi) -> str:
    thu_muc = THU_MUC / "outputs"
    thu_muc.mkdir(exist_ok=True)
    ten = f"{datetime.now():%Y%m%d-%H%M%S}_{che_do}_{ma}"
    duong_dan = thu_muc / f"{ten}.json"
    i = 2
    while duong_dan.exists():
        duong_dan, i = thu_muc / f"{ten}_{i}.json", i + 1
    duong_dan.write_text(json.dumps({
        "thoi_gian": datetime.now().isoformat(timespec="seconds"),
        "che_do": che_do,
        "bieu_do": ma,
        "bo_loc": bl.mo_ta(),
        "dich_vu": tl.nha_cung_cap,
        "model": tl.model,
        "model_loi_truoc": tl.model_loi_truoc,
        "cau_hoi": cau_hoi,
        "goi_so_lieu_dau_vao": goi,
        "cong_cu_da_goi": tl.cong_cu,
        "tra_loi": tl.noi_dung,
        "kiem_so": {**tl.thong_ke_so,
                    "phep_tinh_ai_tu_lam": [f"{s['chu']} = {s['tu_tinh']}" for s in tl.kiem_so if s["tu_tinh"]]},
        "token": {"vao": tl.token_vao, "ra": tl.token_ra},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return duong_dan.relative_to(THU_MUC.parent).as_posix()


def _hoan_tat(che_do: str, ma: str, bl: q.BoLoc, cau_hoi: str, goi: dict, tl: TraLoi) -> TraLoi:
    """Kiểm số trong câu trả lời với mọi dữ liệu AI được thấy, rồi ghi log."""
    tl.kiem_so = kiem_so.kiem(tl.noi_dung, goi, [c["ket_qua"] for c in tl.cong_cu], cau_hoi)
    tl.file_log = _ghi_log(che_do, ma, bl, cau_hoi, goi, tl)
    return tl


# ---------------------------------------------------------------------------
# 3 chức năng của app
# ---------------------------------------------------------------------------
def goi_so_lieu_trang(trang: int, bl: q.BoLoc, so_dong: int = 8) -> dict:
    """Gói cho tóm tắt trang: thẻ KPI + số liệu kết luận và vài dòng đầu của cả 4 biểu đồ trên trang."""
    kpi = q.the_kpi(trang, bl)
    bieu_do = {}
    for ma, bd in q.BIEU_DO.items():
        if bd.trang == trang:
            goi = q.du_lieu_cho_ai(ma, bl, bd.ham(bl), kpi, toi_da_dong=so_dong)
            bieu_do[ma] = {k: goi[k] for k in ("bieu_do", "cau_hoi_nghiep_vu", "so_lieu_ket_luan", "don_vi_cot",
                                               "bang_so_lieu", "so_dong_bang")}
    return q._sach({
        "trang": f"Trang {trang} – {q.TRANG[trang].ten}",
        "bo_loc": bl.mo_ta(),
        "the_kpi": {k: {"ten": v["ten"], "gia_tri": v["gia_tri"], "ghi_chu": v.get("ghi_chu", "")}
                    for k, v in kpi.items()},
        "bieu_do": bieu_do,
        "ghi_chu": f"Tỉ lệ ghi dạng số thập phân (0,0679 = 6,79%); mỗi bảng chỉ gửi tối đa {so_dong} dòng đầu.",
    })


def goi_so_lieu_tat_ca(nam: int | None, thang: int | None, so_dong: int = 3) -> dict:
    """Gói cho câu hỏi về cả dashboard: gói của cả 3 trang, cùng lọc năm / tháng (slicer Năm, Tháng đồng bộ 3 trang)."""
    return {
        "trang": "Cả dashboard (3 trang)",
        "bo_loc": q.BoLoc(nam=nam, thang=thang).mo_ta(),
        "cac_trang": [goi_so_lieu_trang(t, q.bo_loc_cua_trang(t, nam=nam, thang=thang), so_dong) for t in q.TRANG],
    }


def tom_tat(ma_log: str, bl: q.BoLoc, goi: dict) -> TraLoi:
    """Tóm tắt 1 trang (goi_so_lieu_trang) hoặc cả dashboard (goi_so_lieu_tat_ca)."""
    he_thong, nguoi_dung = _doc_prompt("summary.md")
    tin_nhan = [
        {"role": "system", "content": _dien(he_thong, goi_so_lieu=goi)},
        {"role": "user", "content": _dien(nguoi_dung, trang=goi["trang"], bo_loc=goi["bo_loc"])},
    ]
    return _hoan_tat("tom_tat", ma_log, bl, "", goi, _hoi(tin_nhan, dung_cong_cu=False))


def tom_tat_trang(trang: int, bl: q.BoLoc, goi: dict) -> TraLoi:
    return tom_tat(f"trang{trang}", bl, goi)


def giai_thich(ma: str, bl: q.BoLoc, goi: dict) -> TraLoi:
    he_thong, nguoi_dung = _doc_prompt("explain_trend.md")
    tin_nhan = [
        {"role": "system", "content": _dien(he_thong, goi_so_lieu=goi)},
        {"role": "user", "content": _dien(nguoi_dung, bieu_do=q.BIEU_DO[ma].ten)},
    ]
    return _hoan_tat("giai_thich", ma, bl, "", goi, _hoi(tin_nhan, dung_cong_cu=True))


def hoi_dap(ma: str, bl: q.BoLoc, goi: dict, lich_su: list[dict], cau_hoi: str) -> TraLoi:
    """lich_su: [{"role": "user" | "assistant", "content": ...}] của các lượt trước trên cùng biểu đồ."""
    he_thong, nguoi_dung = _doc_prompt("qa.md")
    tin_nhan = ([{"role": "system", "content": _dien(he_thong, goi_so_lieu=goi)}]
                + [{"role": t["role"], "content": t["content"]} for t in lich_su[-SO_LUOT_LICH_SU:]]
                + [{"role": "user", "content": _dien(nguoi_dung, cau_hoi=cau_hoi)}])
    return _hoan_tat("hoi_dap", ma, bl, cau_hoi, goi, _hoi(tin_nhan, dung_cong_cu=True))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--models" in sys.argv:
        for ncc in nha_cung_cap():
            try:
                ids = sorted(m.id for m in OpenAI(api_key=ncc.api_key, base_url=ncc.base_url).models.list())
                print(f"{ncc.ten} (đang dùng {ncc.model}):\n  " + "\n  ".join(ids))
            except openai.APIError as e:
                print(f"{ncc.ten}: lỗi {e}")
        if not nha_cung_cap():
            print("Chưa có API key nào trong .env")
    elif "--thu" in sys.argv:
        bl = q.BoLoc(nam=2018, thang=3)
        kq = q.ban_giao_va_van_chuyen_theo_thang(bl)
        goi = q.du_lieu_cho_ai("Q5_2", bl, kq, q.the_kpi(3, bl))
        tl = hoi_dap("Q5_2", bl, goi, [], "Vì sao tháng 03/2018 giao trễ tăng mạnh? Do bàn giao hay do vận chuyển?")
        tk = tl.thong_ke_so
        print(f"[{tl.nha_cung_cap} · {tl.model} · {tl.token_vao}+{tl.token_ra} token · {tk['tong_so']} số: "
              f"{tk['khop_du_lieu']} khớp dữ liệu, {tk['tu_tinh_dung']} AI tự tính đúng, "
              f"không tìm thấy {tk['khong_tim_thay']}]\n")
        print(kiem_so.to_dam(tl.noi_dung, tl.kiem_so))
        print(f"\nCông cụ đã gọi: {[c['tham_so'] for c in tl.cong_cu]}\nLog: {tl.file_log}")
    else:
        print(__doc__)
