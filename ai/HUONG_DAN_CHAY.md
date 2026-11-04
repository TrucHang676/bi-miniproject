# Hướng dẫn chạy Trợ lý AI (cho thành viên nhóm)

> App hỏi AI về các biểu đồ của dashboard Olist. App chạy **trên máy của bạn** (`http://localhost:8501`) và đọc
> kho `dds` trong Postgres Docker của chính máy đó, không deploy lên mạng. Robot "Trợ lý AI" trong Power BI chỉ
> mở link tới app này, nên **phải bật app trước khi bấm robot**.
>
> Lệnh gõ trong PowerShell **tại thư mục gốc repo** `bi-miniproject/`. Chi tiết kỹ thuật (cấu trúc code, prompt,
> cách kiểm chứng) xem [README.md](README.md).

## 1. Chuẩn bị (làm 1 lần trên mỗi máy)

| Bước | Làm gì | Kết quả đúng |
|---|---|---|
| 1. Lấy code mới | `git pull` | `Already up to date` hoặc danh sách file mới |
| 2. Có dữ liệu | Docker Desktop đang mở, `docker compose up -d`; `dds` đã nạp đủ 10 batch (máy nào mở được dashboard Power BI có số là đủ) | `docker compose ps` thấy `olist-postgres` **running** |
| 3. Kiểm tra Python | `python --version` | **3.11 trở lên** (pandas 3 không chạy trên 3.10) |
| 4. Cài thư viện | `python -m pip install -r ai/requirements.txt` | Dòng cuối `Successfully installed …` hoặc `Requirement already satisfied` |
| 5. Lấy key Gemini (miễn phí) | Vào `aistudio.google.com/apikey`, đăng nhập Google → **Create API key** → copy key. **Không** bấm *Set up billing* (gói free không cần thẻ) | Có 1 chuỗi bắt đầu bằng `AIza…` |
| 6. Điền key | Mở file `.env` ở gốc repo, thêm dòng `GEMINI_API_KEY=<key vừa copy>` (mẫu ở `.env.example`) | – |
| 7. Kiểm tra số liệu | `python ai/kiem_tra_so_lieu.py` | Dòng cuối `50/50 số khớp` |
| 8. Kiểm tra AI | `python ai/llm.py --thu` | Dòng đầu dạng `[Gemini · gemini-3.5-flash · … · x khớp dữ liệu …]`, sau đó là câu trả lời |

> **Mỗi người dùng key của mình.** Không gửi key qua Zalo / Messenger / chat, không commit `.env` (file này đã
> nằm trong `.gitignore`). Key lỡ lộ thì vào lại trang trên xóa key cũ, tạo key mới.

## 2. Mỗi lần dùng

1. Mở **Docker Desktop**, đợi *Engine running* (Postgres tự bật theo nếu đã `docker compose up -d` trước đó).
2. Bấm đúp file **`ai/chay_app.bat`**. Một cửa sổ đen hiện `Local URL: http://localhost:8501` và trình duyệt tự
   mở app. **Để cửa sổ đen mở suốt lúc dùng**, đóng nó là tắt app.
3. Mở file `.pbix` mới nhất của nhóm, bấm **robot Trợ lý AI** ở góc trên trang. Trong Power BI Desktop phải
   **giữ Ctrl + bấm** vào robot (bấm thường chỉ chọn hình). App mở đúng trang và bộ lọc đang xem trên dashboard.

Không cần Power BI cũng được: mở thẳng `http://localhost:8501` trong trình duyệt rồi chọn trang, bộ lọc ở thanh bên.

Dùng xong: đóng cửa sổ đen (hoặc bấm Ctrl + C trong đó).

## 3. Cách dùng app

| Muốn… | Làm |
|---|---|
| Chuyển trang dashboard | Thanh bên trái: **Tổng quan / Giao hàng / Người bán** |
| Lọc năm, tháng, vùng, bang | Thanh bên → mục **BỘ LỌC**; **Đặt lại** để bỏ lọc |
| Hỏi về 1 biểu đồ | Bấm **Hỏi AI** trên góc biểu đồ đó → khung Trợ lý AI mở bên phải |
| Đổi phạm vi hỏi | Đầu khung Trợ lý AI: **Biểu đồ** (1 biểu đồ) / **Cả trang** / **Tất cả** (cả dashboard) |
| AI tự phân tích | Nút **Phân tích & giải thích biểu đồ** (phạm vi Biểu đồ) hoặc **Tóm tắt cả trang** / **Tóm tắt cả dashboard** |
| Hỏi tự do | Bấm 1 câu gợi ý, hoặc gõ vào ô **Hỏi thêm AI về …** ở cuối khung rồi Enter |
| Xóa đoạn chat | Biểu tượng thùng rác trên đầu khung Trợ lý AI |
| Đóng / mở lại khung AI | Nút ✕ trên khung / nút **Trợ lý AI** nổi ở góc phải |

### Đọc kết quả kiểm chứng

App tự đối chiếu **mọi con số** trong câu trả lời với dữ liệu mà AI được xem:

| Thấy gì | Nghĩa là |
|---|---|
| Huy hiệu **✓ x/x số khớp** | Mọi số đều có trong dữ liệu dashboard |
| Số tô **xanh** | AI tự tính (VD chênh lệch, gấp mấy lần) và phép tính đúng |
| Số tô **cam** | Không tìm thấy trong dữ liệu – **kiểm tra lại trên dashboard trước khi dùng** |
| **Chi tiết kiểm chứng & log** | Model đã dùng, số token, tên file log trong `ai/outputs/` |

Câu trả lời chỉ dựa trên số liệu của dashboard. Những gì dữ liệu không có (lợi nhuận, hãng vận chuyển, tuổi khách…)
AI sẽ nói "không đủ dữ liệu"; lý do chưa chứng minh được thì AI ghi là "giả thuyết". Không gõ thông tin cá nhân vào
ô chat (gói free của Gemini có thể được Google dùng để cải thiện sản phẩm).

## 4. Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách khắc phục |
|---|---|---|
| Bấm `chay_app.bat` hiện `'python' is not recognized` | Chưa cài Python hoặc chưa thêm vào PATH | Cài Python 3.11+ từ python.org, **tick "Add python.exe to PATH"**, mở lại cửa sổ |
| `No module named streamlit` (hoặc pandas, plotly, psycopg, openai) | Chưa cài thư viện, hoặc cài vào bản Python khác | `python -m pip install -r ai/requirements.txt` (dùng đúng `python -m pip`) |
| `Port 8501 is already in use` | Đang có 1 cửa sổ app khác chạy | Dùng luôn tab app đang mở, hoặc đóng cửa sổ đen cũ rồi bấm lại `chay_app.bat`. File `.bat` cố định cổng 8501 vì robot Power BI trỏ tới đúng cổng này |
| Bấm robot trong Power BI ra trang **"This site can't be reached"** | Chưa bật app | Bấm `chay_app.bat` trước, rồi bấm lại robot |
| Bấm robot không có gì xảy ra | Power BI Desktop đang ở chế độ sửa | **Ctrl + bấm** vào robot |
| App báo **"Không kết nối được Postgres"** | Docker Desktop chưa mở / container Postgres chưa chạy | Mở Docker Desktop → `docker compose up -d` → tải lại trang (F5) |
| App báo **"Chưa có API key"**, nút hỏi bị khóa | `.env` chưa có `GEMINI_API_KEY` hoặc viết sai tên | Sửa `.env`, rồi đóng cửa sổ đen và bấm lại `chay_app.bat` |
| Biểu đồ trống / "Không có dữ liệu với bộ lọc này" | Bộ lọc không có đơn nào, hoặc `dds` chưa nạp | Bấm **Đặt lại**; vẫn trống thì chạy `python ai/kiem_tra_so_lieu.py` – không ra 50/50 nghĩa là DB máy bạn chưa nạp đủ dữ liệu |
| AI báo **"API key sai hoặc đã bị thu hồi"** | Key copy thiếu ký tự hoặc đã xóa | Tạo key mới ở `aistudio.google.com/apikey`, điền lại `.env` |
| AI báo **"hết lượt miễn phí (429)"** | Gói free giới hạn số câu hỏi mỗi phút / mỗi ngày | Đợi khoảng 1 phút rồi hỏi lại; hết lượt trong ngày thì mai dùng tiếp hoặc thêm `GROQ_API_KEY` (dự phòng, xem [README.md](README.md)) |
| AI báo **"đang quá tải (503)"** hoặc **"quá 60 giây"** | Máy chủ Google đang đông | App đã tự thử model nhẹ hơn; vẫn lỗi thì thử lại sau ít phút |
| AI báo **"không kết nối được (kiểm tra mạng)"** | Mất mạng | AI cần Internet (biểu đồ thì không) – kiểm tra Wi-Fi |

Vẫn lỗi: chụp màn hình cửa sổ đen + thông báo trên app gửi Thanh (đừng chụp dính key trong `.env`).
