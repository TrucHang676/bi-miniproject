# Tích hợp Generative AI – nội dung cho báo cáo

> Bản nháp cho phần AI của báo cáo (đề mục 3.5). Code và cách chạy: [ai/README.md](../ai/README.md).
> Số liệu trong file lấy từ các lần chạy thật ngày 04/11/2026 (log ở `ai/outputs/`). Đánh số mục theo báo cáo chung khi dán.

## 1. Yêu cầu và cách đáp ứng

| Yêu cầu của đề (mục 3.5) | Cách nhóm đáp ứng |
|---|---|
| Sử dụng một LLM hoặc dịch vụ Generative AI | Google Gemini (`gemini-3.5-flash`, gói miễn phí của Google AI Studio) gọi qua API |
| Tự động tạo bản tóm tắt (AI-generated Summary) từ KPI và kết quả phân tích | Nút **Tóm tắt trang**: AI nhận thẻ KPI + số liệu kết luận của cả 4 biểu đồ trên trang |
| Giải thích xu hướng, biến động, vấn đề phát hiện trên dashboard | Nút **Giải thích biểu đồ này**: biến động → yếu tố đóng góp → giả thuyết → đề xuất |
| Kết quả dựa trên số liệu đã tính, kiểm chứng được, hạn chế suy diễn | Số đầu vào tính cùng công thức với dashboard (khớp 50/50 số nghiệm thu); AI không tự viết SQL; kiểm số tự động từng con số trong câu trả lời; lưu log mọi lần hỏi |
| *Khuyến khích:* hỏi đáp bằng ngôn ngữ tự nhiên | Ô chat; AI tự gọi công cụ lấy số của biểu đồ khác khi cần |

## 2. Lựa chọn cách tích hợp

| Cách | Đánh giá | Chọn |
|---|---|---|
| Copilot trong Power BI | Cần Fabric capacity trả phí, tài khoản sinh viên không có | Không |
| Q&A visual / Smart narrative có sẵn | Không phải LLM (ghép câu theo mẫu), Q&A chỉ hiểu tiếng Anh | Không |
| Python visual trong Power BI gọi API | Chỉ chạy trong Desktop, API key nằm trong file `.pbix` chia sẻ, chữ hiện dạng ảnh | Không |
| **App Streamlit đi kèm + nút "Hỏi AI" trên Power BI** | Đề cho phép "API, ứng dụng Python"; key nằm trong `.env` trên máy; giao diện chat thật | **Có** |

Mỗi trang dashboard có một **robot trợ lý** nhỏ (trắng, kính xanh) ở header: ảnh SVG động, robot nhấp nhô và cứ 5 giây lại bật
một đám mây chat ("Chào bạn 👋 Cần mình giải thích biểu đồ không?", "Tháng nào giao trễ bất thường? Hỏi mình nè!",
"Bấm vào mình để hỏi AI nhé ✨") để gợi ý người dùng hỏi. Bấm vào robot (nút trong suốt phủ lên ảnh) sẽ mở app với
đúng trang và bộ lọc đang chọn: một measure DAX ghép link theo slicer, VD
`http://localhost:8501/?bieu_do=Q5_1&nam=2018&thang=3`. Người dùng xem biểu đồ trên Power BI rồi hỏi tiếp ngay trên
app mà không phải chọn lại bộ lọc.

## 3. Lựa chọn LLM

Nhóm chọn dịch vụ **miễn phí**.

| Lựa chọn | Chi phí | Ưu điểm | Nhược điểm |
|---|---|---|---|
| **Gemini – Google AI Studio (chọn)** | Miễn phí, không gắn thẻ | Nhanh (khoảng 4–15 giây / câu), tiếng Việt tốt, gọi công cụ ổn định | Giới hạn số lượt / phút; cần mạng; gói free có thể được Google dùng để cải thiện sản phẩm |
| Groq (dự phòng) | Miễn phí | Nhanh; dùng làm phương án khi Gemini hết lượt | Model mã nguồn mở, tiếng Việt kém hơn |
| Ollama (chạy trên máy) | Miễn phí, không giới hạn | Offline, dữ liệu không rời máy | Máy nhóm không có GPU rời → chạy CPU chậm; model nhỏ dễ suy luận sai, gọi công cụ kém |
| API trả phí (Claude, GPT…) | Trả theo token | Chất lượng cao nhất | Nhóm không dùng chi phí |

Olist là dữ liệu công khai trên Kaggle nên việc gói free có thể dùng dữ liệu là chấp nhận được.

Gemini, Groq và Ollama đều có cổng tương thích OpenAI nên code dùng chung thư viện `openai`; đổi dịch vụ chỉ sửa `.env`.
Ngày 04/11/2026: `gemini-2.5-flash` đã bị gỡ (lỗi 404), `gemini-3.8-flash` thường báo quá tải (503). Vì vậy app
dùng `gemini-3.5-flash` và tự chuyển sang `gemini-3.5-flash-lite` khi model chính lỗi.

## 4. Kiến trúc và luồng xử lý

```
Power BI ──nút Hỏi AI (biểu đồ + bộ lọc qua link)──▶ app Streamlit (ai/app.py)
dds ──SQL, cùng công thức DAX (ai/queries.py)──▶ gói số liệu JSON ──▶ prompt + gói ──▶ Gemini ──▶ câu trả lời
                                    ▲                                     │
          công cụ lay_so_lieu ──────┘ (AI cần số của biểu đồ khác)        ▼
                                          kiểm số (ai/kiem_so.py) ──▶ hiển thị + lưu log (ai/outputs/)
```

| Thành phần | Vai trò |
|---|---|
| `queries.py` | 12 hàm số liệu cho 12 biểu đồ Q1–Q6 và thẻ KPI 3 trang, viết lại bằng SQL đúng công thức trong `powerbi/measures.dax` (đếm đơn riêng biệt, đánh giá mới nhất, ngưỡng M5…); mỗi biểu đồ có thêm "số liệu kết luận" (VD Q5: gấp 3,91 lần) |
| `kiem_tra_so_lieu.py` | Đối chiếu số của `queries.py` với bảng nghiệm thu B6 của Power BI: **50/50 khớp** |
| `llm.py` | Ghép prompt + gói số liệu, gọi LLM, chạy công cụ, chuyển model dự phòng, ghi log |
| `kiem_so.py` | Tách mọi con số trong câu trả lời, đối chiếu với dữ liệu AI đã được xem |
| `prompts/` | 3 prompt: tóm tắt, giải thích biến động, hỏi đáp |
| `app.py` | Giao diện: chọn biểu đồ và bộ lọc, xem thẻ KPI, biểu đồ, bảng số, gói số liệu gửi AI, nút và ô chat |

Biểu đồ theo tháng không bị lọc theo tháng (tháng đang chọn được đánh dấu). Lý do: nếu chỉ còn 1 tháng thì AI không
có tháng bình thường để so, nên không trả lời được câu "đột biến do đâu". Thẻ KPI vẫn lọc đúng tháng như trên Power BI.

## 5. Cơ chế đảm bảo kết quả có căn cứ

1. **Số đầu vào đúng.** AI chỉ nhận số do `queries.py` tính từ `dds`, cùng nguồn và cùng công thức với dashboard;
   đã kiểm 50/50 số nghiệm thu B6.
2. **AI không tự viết SQL.** Cần thêm số thì AI chỉ được gọi công cụ `lay_so_lieu` để chọn 1 trong 12 biểu đồ có sẵn
   (kèm bộ lọc), nên mọi số AI thấy đều tính bằng công thức đã kiểm.
3. **Quy tắc trong prompt.** Chỉ dùng số được đưa vào; mỗi nhận định kèm số; số tự tính phải ghi phép tính; tách
   **sự thật từ dữ liệu** với **giả thuyết**; khi nói "cao / bình thường" phải so với mức của các tháng / nhóm khác;
   không suy diễn về thứ dữ liệu không có (lợi nhuận, hãng vận chuyển, nhân khẩu học khách hàng).
4. **Kiểm số tự động.** Mỗi con số trong câu trả lời được xếp 1 trong 3 loại: *khớp dữ liệu*; *AI tự tính đúng* (ra
   đúng bằng 1 phép cộng / trừ / chia / % tăng giữa 2 số đã khớp, tô xanh); *không tìm thấy* (tô cam để người xem tự kiểm).
   App ghi "x/y số khớp dữ liệu" dưới mỗi câu trả lời.
5. **Lưu log.** Mỗi lần hỏi lưu 1 file JSON: gói số liệu đầu vào, công cụ AI đã gọi, câu trả lời, kết quả kiểm số,
   model, số token. Người chấm mở log là đối chiếu được.

## 6. Kết quả thử nghiệm (04/11/2026)

| # | Chức năng | Biểu đồ / bộ lọc | Model | Kết quả | Kiểm số |
|---|---|---|---|---|---|
| 1 | Hỏi đáp: "Vì sao 03/2018 giao trễ tăng mạnh? Do bàn giao hay vận chuyển?" | Q5 (2), 03/2018 | gemini-3.5-flash | Giao trễ 18,96% do vận chuyển 12,97 ngày (TB các tháng khác 7,65); bàn giao 8,41% gần mức thường 7,88% | 12 khớp + 4 AI tự tính đúng |
| 2 | Giải thích biến động | Q5 (2), 03/2018 | gemini-3.5-flash-lite (model chính lỗi, tự chuyển) | Đủ 4 phần biến động / yếu tố / giả thuyết / đề xuất | 16/16 khớp |
| 3 | Hỏi đáp cần biểu đồ khác: "Tháng 3/2018 bang nào giao trễ nhiều nhất? Có đáng tin không?" | Q5 (2) → AI gọi `lay_so_lieu(Q3_2, 2018, 3)` | gemini-3.5-flash | SE 64,71% nhưng chỉ 17 đơn → không đáng tin; RJ 34,49% trên 864 đơn đáng tin hơn | 10/10 khớp |
| 4 | Tóm tắt trang 3 | 03/2018 | gemini-3.5-flash | Tình hình chung, 4 điểm nổi bật, cần chú ý (K12 8,41% chưa đạt mục tiêu 5%, chưa vượt cảnh báo 10%) | 36/36 khớp |
| 5 | Giải thích biến động (sau khi thêm quy tắc so với mức bình thường) | Q5 (2), 03/2018 | gemini-3.5-flash | Kết luận "khâu bàn giao không phải nguyên nhân chính của đỉnh tháng 3"; tự gọi Q5 (1) để tính "gấp 3,91 lần" | 23 khớp + 5 tự tính đúng + **2 không tìm thấy** |

Kết luận của AI ở lần 1, 2, 5 trùng với phân tích Q5 trong `docs/business_questions.md`: 03/2018 bàn giao bình thường,
đột biến do khâu vận chuyển.

**Kiểm số bắt được lỗi thật (lần 5).** AI tự cộng số đơn của 2 tuyến nội bang + liên bang, ra 87.692 đơn đã giao /
4.718 đơn trễ. App tô cam vì không có trong dữ liệu. Đếm lại từ `dds` ra **87.456 / 4.717**: cộng 2 tuyến bị đếm
trùng những đơn có nhiều người bán thuộc 2 tuyến khác nhau. Sau đó nhóm đưa sẵn số đơn đã đếm đúng vào gói số liệu
Q5 (1) để AI trích thẳng. Ví dụ này cho thấy kiểm số giúp phát hiện số AI tự suy ra sai, không chỉ số bịa.

Mỗi câu hỏi tốn khoảng 3.000–6.000 token đầu vào và 200–700 token đầu ra, nằm trong gói miễn phí.

## 7. Hạn chế và hướng phát triển

| Hạn chế | Hướng xử lý |
|---|---|
| Gói free giới hạn số lượt / phút, model có lúc quá tải | Tự chuyển model dự phòng (đã làm); có thể thêm Groq |
| App chạy `localhost`: nút "Hỏi AI" chỉ mở được trên máy đang chạy app | Triển khai app lên máy chủ (VD Streamlit Community Cloud) kèm kết nối DW |
| Hỏi đáp chỉ trong phạm vi 12 biểu đồ có sẵn | Thêm hàm truy vấn mới vào `queries.py` (vẫn không cho AI viết SQL) |
| Kiểm số chỉ kiểm con số, không kiểm nhận định bằng chữ (VD "tăng mạnh") | Đánh giá thêm bằng bộ câu hỏi mẫu có đáp án |
| Slicer chọn nhiều giá trị (VD 2 tháng) thì link chỉ mang được "không lọc" | Ghép danh sách giá trị vào link |
