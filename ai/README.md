# Generative AI – AI-Assisted Analytics

## Mô hình & cách tích hợp
- **LLM / Dịch vụ:** Google Gemini (gói free của Google AI Studio, mặc định `gemini-3.5-flash`, quá tải thì
  `gemini-3.5-flash-lite`); dự phòng Groq
  (gói free, `llama-3.3-70b-versatile`) khi Gemini hết lượt hoặc lỗi. Nhóm chọn dịch vụ miễn phí; Ollama chạy
  trên máy cũng gắn được (biến `OLLAMA_MODEL`) nhưng máy không có card đồ họa rời nên chậm, trả lời yếu hơn.
- **Cách tích hợp:** app Streamlit đi kèm Power BI. Mỗi trang dashboard có nút "Hỏi AI" mở app với đúng biểu đồ
  và bộ lọc đang xem; app lấy số liệu của biểu đồ đó từ `dds` rồi mới gửi cho LLM. Copilot trong Power BI cần
  Fabric capacity trả phí nên không dùng. Gemini, Groq, Ollama đều có cổng tương thích OpenAI nên `llm.py` dùng
  chung thư viện `openai`; đổi dịch vụ / model chỉ sửa `.env`.

`.env` ở gốc repo (không lên Git):

```
GEMINI_API_KEY=...          # aistudio.google.com -> Get API key
GROQ_API_KEY=...            # console.groq.com -> API Keys (dự phòng, không bắt buộc)
# AI_MODEL_GEMINI=gemini-3.5-flash,gemini-3.5-flash-lite   AI_MODEL_GROQ=llama-3.3-70b-versatile
#   (đổi model nếu cần; nhiều model cách nhau dấu phẩy = thử lần lượt)
```

Gói free của Gemini có thể được Google dùng để cải thiện sản phẩm – Olist là dữ liệu công khai trên Kaggle nên
chấp nhận được, nhưng không gõ thông tin cá nhân vào ô chat.

## Cấu trúc

| File | Việc |
|---|---|
| `db.py` | Kết nối Postgres, đọc `.env` ở gốc repo (mặc định `localhost:5432` như Power BI) |
| `queries.py` | 12 hàm số liệu cho 12 biểu đồ Q1–Q6 + thẻ KPI 3 trang, tính lại đúng công thức trong `powerbi/measures.dax`; gói dữ liệu gửi AI (`du_lieu_cho_ai`) |
| `kiem_tra_so_lieu.py` | Đối chiếu số của `queries.py` với bảng nghiệm thu B6 (`powerbi/README.md`) |
| `llm.py` | Gọi LLM (Gemini -> Groq -> Ollama), công cụ `lay_so_lieu` cho AI lấy số của biểu đồ khác, 3 chức năng `tom_tat_trang` / `giai_thich` / `hoi_dap`, ghi log |
| `kiem_so.py` | Tách mọi con số trong câu trả lời AI, đối chiếu với dữ liệu AI được xem; số không khớp được tô cam |
| `app.py` | App Streamlit bố cục giống dashboard: thanh bên chọn trang + bộ lọc (như slicer), header, thẻ KPI tô màu, các biểu đồ của trang dựng lại theo cấu hình visual trong bản PBIP (kiểu, màu, nhãn, trục Năm → Quý → Tháng, đường ngưỡng, bản đồ bang trang 1, bảng top 10 có thanh dữ liệu); bấm **Hỏi AI** trên thẻ mở chế độ phóng to: biểu đồ lớn + 3 ô số nổi bật + nút ‹ › chuyển biểu đồ, bên phải khung Trợ lý AI hỏi theo phạm vi **Biểu đồ này** / **Cả trang** / **Toàn báo cáo** (nút Giải thích / Tóm tắt, câu hỏi có sẵn, Hỏi tiếp, ô chat), giao diện theo bản thiết kế Figma Make. Theme màu ở `.streamlit/config.toml` (gốc repo) |
| `prompts/` | Prompt cho tóm tắt (`summary.md`), giải thích biến động (`explain_trend.md`), hỏi đáp (`qa.md`) – mỗi file có phần `## System` và `## User` |
| `outputs/` | Log mỗi lần hỏi: số liệu đầu vào, công cụ AI đã gọi, câu trả lời, kết quả kiểm số, số token |

## Chạy trên máy từng thành viên
> Hướng dẫn từng bước + cách dùng app + lỗi thường gặp: **[HUONG_DAN_CHAY.md](HUONG_DAN_CHAY.md)**.

App chạy **trên máy mỗi người** (`localhost:8501`), đọc kho `dds` trong Postgres Docker của chính máy đó – không
deploy lên mạng. Robot "Trợ lý AI" trong Power BI mở link `http://localhost:8501/...`, nên phải mở app trước khi bấm robot.

1. `git pull`, Postgres đang chạy (`docker compose up -d`) và `dds` đã nạp đủ 10 batch (như khi mở Power BI).
2. Lần đầu: `pip install -r ai/requirements.txt`; lấy key Gemini miễn phí ở `aistudio.google.com/apikey`
   (Create API key, **không** bấm Set up billing), điền vào dòng `GEMINI_API_KEY=` trong `.env` (mẫu ở `.env.example`).
   Mỗi người dùng key của mình, không gửi key qua chat / Git.
3. Bấm đúp `ai/chay_app.bat` (hoặc `streamlit run ai/app.py` từ gốc repo). Trình duyệt mở `http://localhost:8501`.
4. Mở Power BI, bấm robot ở góc trên → app mở đúng trang + bộ lọc đang xem.

Cổng 8501 đang bị app khác chiếm thì Streamlit báo lỗi (file `.bat` cố định cổng 8501 để khớp link trong Power BI) –
tắt cửa sổ Streamlit cũ rồi chạy lại.

## Chạy thử
Cần Postgres đang chạy (`docker compose up -d`) và đã nạp `dds`. Từ gốc repo:

```bash
pip install -r ai/requirements.txt
python ai/kiem_tra_so_lieu.py
python ai/llm.py --thu
streamlit run ai/app.py
```

`llm.py --thu` hỏi thử 1 câu về Q5 tháng 03/2018 để biết key và model chạy được; `llm.py --models` liệt kê model
mà key hiện có dùng được.

`kiem_tra_so_lieu.py` phải ra toàn ✓ (04/11/2026: 50/50) thì số gửi cho AI mới khớp dashboard.

Link mở thẳng 1 biểu đồ (nút "Hỏi AI" trong Power BI sẽ ghép link này theo bộ lọc đang chọn):
`http://localhost:8501/?bieu_do=Q5_2&nam=2018&thang=3`

| Tham số | Giá trị |
|---|---|
| `bieu_do` | `Q1_1`, `Q1_2` … `Q6_2` (câu hỏi + số thứ tự biểu đồ trên trang) |
| `nam`, `thang` | Năm, tháng (bỏ trống = không lọc) |
| `vung`, `bang` | Vùng, bang nhận hàng (trang 1; trang 2 chỉ có vùng) |
| `vung_nb`, `bang_nb` | Vùng, bang người bán (trang 3) |

Biểu đồ theo tháng (Q1, Q3 (1), Q4 (2), Q5 (2)) luôn hiện đủ các tháng và đánh dấu tháng đang chọn, để AI có
tháng khác mà so sánh; thẻ KPI thì lọc đúng tháng như trên Power BI.

## Luồng xử lý (đảm bảo kết quả có căn cứ)

```
Power BI ──nút Hỏi AI (biểu đồ + bộ lọc)──▶ app.py
dds ──SQL (queries.py, khớp B6)──▶ gói số liệu JSON ──▶ prompt + gói ──▶ LLM ──▶ câu trả lời
                                        ▲                                │
              công cụ lay_so_lieu ──────┘ (AI cần số biểu đồ khác)       ▼
                                                     kiem_so.py: số trong câu trả lời có trong dữ liệu không
                                                                         │
                                                     outputs/: đầu vào + câu trả lời + kết quả kiểm số
```

AI không tự viết SQL: muốn thêm số chỉ được chọn 1 trong 12 biểu đồ có sẵn qua `lay_so_lieu`, nên mọi số AI
thấy đều tính bằng cùng công thức với dashboard.

## Chức năng

| Chức năng | Nút / ô trong app | Đầu vào | Đầu ra | Prompt |
|-----------|---|---------|--------|--------|
| AI-generated Summary | Tóm tắt cả trang / Tóm tắt toàn báo cáo | Thẻ KPI + kết luận của cả 4 biểu đồ trên trang | Tình hình chung, điểm nổi bật, cần chú ý | `prompts/summary.md` |
| Giải thích biến động | Giải thích biểu đồ này | Gói số liệu biểu đồ đang xem (+ biểu đồ khác qua công cụ) | Biến động (câu chính), yếu tố đóng góp (thẻ Điểm nổi bật), giả thuyết, đề xuất (Nên làm gì tiếp) – AI trả theo khuôn TOM_TAT / NOI_BAT / GIA_THUYET / DE_XUAT để app chia thẻ | `prompts/explain_trend.md` |
| Hỏi đáp ngôn ngữ tự nhiên (khuyến khích) | Ô chat | Câu hỏi + lịch sử chat + gói số liệu | Câu trả lời kèm số | `prompts/qa.md` |

## Kiểm chứng & hạn chế suy diễn
- [x] Prompt chỉ cho phép dùng số liệu được cung cấp; dữ liệu không có (lợi nhuận, hãng vận chuyển…) thì không suy diễn
- [x] Câu trả lời trích dẫn lại số liệu; tách sự thật với giả thuyết (giải thích biến động)
- [x] Kiểm số tự động: mỗi số trong câu trả lời đối chiếu với dữ liệu AI được xem (`kiem_so.py`), app ghi "x/y số khớp"
- [x] Lưu log mỗi lần hỏi trong `outputs/`
- [x] So sánh với số liệu trên dashboard – số đầu vào của AI khớp nghiệm thu B6 (`kiem_tra_so_lieu.py`)

## Ví dụ kết quả (04/11/2026, gemini-3.5-flash, gói free)

**Hỏi đáp** – đang xem Q5 (2), lọc 03/2018, hỏi "Tháng 3/2018 bang nhận hàng nào giao trễ nhiều nhất? Có đáng tin
không?". AI tự gọi `lay_so_lieu(bieu_do=Q3_2, nam=2018, thang=3)` rồi trả lời: theo tỉ lệ là Sergipe 64,71%
(11 / 17 đơn) nhưng không đáng tin vì chỉ 17 đơn; Rio de Janeiro 34,49% (298 / 864 đơn) đáng tin hơn.
Kiểm số 10/10 khớp. Log: `outputs/20261104-180809_hoi_dap_Q5_2.json`.

**Giải thích biến động** – Q5 (2) tháng 03/2018: giao trễ 18,96% do vận chuyển kéo dài (12,97 ngày so với
trung bình 7,65 ngày các tháng khác), không do bàn giao (8,41%, gần mức bình thường 7,88%); khớp phân tích
ở `docs/business_questions.md` Q5.

**Kiểm số bắt được lỗi thật** – trong 1 lần giải thích, AI tự cộng số đơn của 2 tuyến ra 87.692 / 4.718; app
tô cam vì không có trong dữ liệu. Số đúng (đếm lại từ `dds`) là 87.456 / 4.717 – cộng 2 tuyến đếm trùng đơn có
nhiều người bán. Sau đó `queries.py` đưa sẵn số đơn đã đếm lại vào gói số liệu Q5 (1).
