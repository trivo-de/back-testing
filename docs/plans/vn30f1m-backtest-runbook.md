# VN30F1M — chạy API và notebook với JSON

Ứng dụng dùng package `backtesting_api`, nhận dữ liệu và chiến lược trong một
JSON, lưu đầu vào và kết quả tại kho file. Chạy các lệnh bên dưới từ thư mục
gốc repository.

## 1. Cài đặt

```powershell
.venv\Scripts\python.exe -m pip install -e ".[test,intraday,notebook]"
```

`pyarrow` thuộc nhóm `intraday`, phục vụ đọc nến Parquet của các lượt chạy
lịch sử phiên bản 1 trong `data/backtest-store/runs`.

## 2. Chuẩn bị JSON và chính sách

Chuẩn bị JSON theo [hướng dẫn payload](../design/strategy-payload-guide.md)
và [đặc tả API](../design/backtest-api-specification.md). Đặt file dùng cho
notebook tại `data/payload.json`, hoặc chỉ định `BACKTEST_PAYLOAD`.
JSON chứa dữ liệu, kỳ báo cáo, chỉ báo, điều kiện chiến lược, quy tắc khớp lệnh
và cấu hình tính tiền. Mẫu `src/backtesting_api/web/canslim-v1-example.json`
minh họa cấu trúc; thay dữ liệu minh họa bằng dữ liệu cần chạy.

Các đường dẫn mặc định:

| Biến môi trường | Mặc định | Vai trò |
| --- | --- | --- |
| `BACKTEST_STORE_PATH` | `data/backtest-store` | Kho đầu vào và kết quả |
| `INLINE_POLICY_PATH` | `docs/data/vn30f1m/runtime-policy-v1.json` | Chính sách khi dữ liệu JSON có map hợp đồng |

Ứng dụng đọc biến môi trường của tiến trình. Với Docker, cấu hình Compose
nhận giá trị từ `.env` theo [mẫu](../../.env.example).
Kỳ báo cáo và dữ liệu phải tuân theo [hợp đồng dữ liệu](../data/vn30f1m/data-contract.md);
không điền nến thiếu hoặc dùng dữ liệu chưa khả dụng để chạy qua kiểm tra.

## 3. Khởi động API

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m uvicorn backtesting_api.main:app --host 127.0.0.1 --port 8000
```

Trang `/` nhận JSON, kiểm tra, chạy và hiển thị kết quả; `/docs` mô tả API:

| Phương thức và đường dẫn | Chức năng |
| --- | --- |
| `POST /api/backtests/validate` | Kiểm tra JSON và dữ liệu trước khi chạy |
| `POST /api/backtests` | Chạy và lưu kết quả |
| `GET /api/backtests` | Đọc danh sách các lượt chạy thành công |
| `GET /api/backtests/{run_id}` | Đọc kết quả |
| `GET /api/backtests/{run_id}/input` | Đọc đầu vào JSON |
| `GET /api/backtests/{run_id}/chart` | Đọc dữ liệu biểu đồ |

Chạy một tiến trình ghi kho file. Kết quả hoàn tất được công bố bằng thao tác
thay file nguyên tử; lượt chạy lỗi hoặc đang chạy không xuất hiện như kết quả
thành công. Khởi động lại ứng dụng vẫn đọc được các kết quả đã lưu.
Signal được đánh giá sau Close; khớp lệnh theo quy tắc trong JSON, không dùng
giá tương lai. Các run lịch sử được đọc từ kho đã có.

## 4. Notebook

Mở `notebooks/backtest-results.ipynb` bằng kernel `.venv`, khởi động API rồi
chạy các ô mã. Notebook gửi JSON, nhận `metadata.run_id`, sau đó đọc lại kết
quả của cùng lượt chạy; không tính lại chiến lược hoặc lãi/lỗ.

| Biến môi trường | Mặc định | Vai trò |
| --- | --- | --- |
| `BACKTEST_API_URL` | `http://127.0.0.1:8000` | Địa chỉ API |
| `BACKTEST_PAYLOAD` | `data/payload.json` tại gốc repository | File đầu vào |
| `BACKTEST_REPORT_START` | Theo JSON | Ghi đè `report.start_date` |
| `BACKTEST_REPORT_END` | Theo JSON | Ghi đè `report.end_date` |

Thay kỳ báo cáo phải giữ dữ liệu khởi tạo chỉ báo cần thiết; thay kỳ báo cáo
có thể tạo kết quả khác. Không dùng kết quả kiểm thử tổng hợp làm bằng chứng
nghiệm thu dữ liệu thật.

## 5. Kiểm thử và Docker

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/web/*.test.mjs
docker compose up --build
```

Compose khởi động `backtesting_api.main:app` tại cổng 8000 và gắn
`data/backtest-store` để giữ kết quả qua các lần khởi động container.
