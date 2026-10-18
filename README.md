# Backtesting API

Backtest chiến lược JSON trên dữ liệu thị trường phái sinh Việt Nam. Luồng xử lý:
JSON → kiểm tra dữ liệu → chỉ báo → điều kiện chiến lược → tín hiệu → khớp lệnh
→ tài khoản → kết quả trong kho file → giao diện web.

Package Python: `backtesting_api`. API lưu đầu vào và kết quả qua
`FileRunRepository` tại `data/backtest-store`; giao diện và notebook đọc cùng
kết quả từ API. Parquet phục vụ việc đọc các lượt chạy lịch sử phiên bản 1.

## Cài đặt trên Windows

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Chạy API và giao diện

```powershell
.venv\Scripts\python.exe -m uvicorn backtesting_api.main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000`; `/docs` hiển thị đặc tả API. Chạy lệnh từ thư mục
gốc repository để đường dẫn chính sách và kho file được xác định đúng.

Trang `/` nhận JSON hoặc file JSON, cho phép kiểm tra, chạy và xem lại kết quả.
Mẫu v1 trên form có hai nến minh họa; thay bằng dữ liệu và chiến lược cần chạy.

- `POST /api/backtests/validate`: kiểm tra JSON và dữ liệu.
- `POST /api/backtests`: chạy và lưu kết quả.
- `GET /api/backtests`: danh sách kết quả đã lưu.
- `GET /api/backtests/history`: tóm tắt có bộ lọc và phân trang.
- `GET /api/backtests/{run_id}`: đọc kết quả.
- `GET /api/backtests/{run_id}/input`: đọc đầu vào.
- `GET /api/backtests/{run_id}/chart`: đọc dữ liệu biểu đồ.

Hai endpoint POST nhận dữ liệu nhập tay hoặc `"auto_fetch_data": true`.
Khi bật tự lấy, API ưu tiên tải VN30F1M và VNINDEX 5 phút từ VNDIRECT. Nếu có
`report`, khoảng tải bắt đầu từ sáu tháng trước `start_date` và kết thúc tại
`end_date`; nếu không có thì lấy sáu tháng gần nhất đến hiện tại. Chỉ dùng nến
đã đóng. Tải lỗi thì dừng, không dùng dữ liệu nhập tay.
Chi tiết lựa chọn nguồn và giới hạn lịch hợp đồng tại
[đặc tả API](docs/design/backtest-api-specification.md#3-cấu-trúc-request).

## Kiểm thử

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node --test tests/web/*.test.mjs
```

## Xem kết quả bằng notebook

```powershell
.venv\Scripts\python.exe -m pip install -e ".[notebook]"
```

Khởi động API, mở `notebooks/backtest-results.ipynb` bằng kernel `.venv`, rồi
chạy các ô mã. `BACKTEST_API_URL` mặc định là `http://127.0.0.1:8000`;
`BACKTEST_PAYLOAD` trỏ tới file JSON, mặc định `data/payload.json`.
Xem [hướng dẫn API và notebook](docs/guides/run-backtest.md).

## Chạy bằng Docker

```powershell
docker compose up --build
```

Mở `http://127.0.0.1:8000`. Compose gắn kho kết quả tại
`data/backtest-store`; các lần khởi động lại đọc cùng kho file.

## Tài liệu

- [Cấu trúc repository](docs/design/project-structure.md)
- [Đặc tả API](docs/design/backtest-api-specification.md)
- [Hướng dẫn JSON chiến lược](docs/design/strategy-payload-guide.md)
- [Đặc tả yêu cầu](docs/requirements/software-requirements-specification.md)
- [Thiết kế hệ thống](docs/design/system-design.md)
- [Tài liệu project](docs/README.md)
- [Hợp đồng dữ liệu VN30F1M](docs/data/vn30f1m/data-contract.md)
- [Đặc tả giao diện](docs/design/web-ui-specification.md)

Dữ liệu gốc, `.env`, kết quả sinh ra và công cụ hỗ trợ cục bộ nằm trong các
vùng được Git bỏ qua, theo [cấu trúc repository](docs/design/project-structure.md).
