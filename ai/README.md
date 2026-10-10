# Generative AI – AI-Assisted Analytics

## Mô hình & cách tích hợp
- **LLM / Dịch vụ:**
- **Cách tích hợp:** [API + Python / Streamlit / công cụ AI trong Power BI]

## Luồng xử lý (đảm bảo kết quả có căn cứ)

```
Data Warehouse ──SQL──▶ KPI (JSON) ──▶ Prompt + KPI ──▶ LLM ──▶ Summary / Giải thích
                         │                                        │
                         └────────── lưu lại để đối chiếu ────────┘ → outputs/
```

## Chức năng

| Chức năng | Đầu vào | Đầu ra | Prompt |
|-----------|---------|--------|--------|
| AI-generated Summary | KPI tổng quan | Đoạn tóm tắt | `prompts/summary.md` |
| Giải thích biến động | KPI theo thời gian / theo chiều | Giải thích nguyên nhân | `prompts/explain_trend.md` |
| Hỏi đáp ngôn ngữ tự nhiên (khuyến khích) | Câu hỏi người dùng | Câu trả lời + số liệu | `prompts/qa.md` |

## Kiểm chứng & hạn chế suy diễn
- [ ] Prompt chỉ cho phép dùng số liệu được cung cấp
- [ ] Câu trả lời trích dẫn lại số liệu
- [ ] Lưu cặp (KPI đầu vào, kết quả AI) trong `outputs/`
- [ ] So sánh với số liệu trên dashboard

## Ví dụ kết quả
[Dán 1–2 ví dụ đầu vào/đầu ra.]
