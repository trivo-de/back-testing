# Chạy API, giao diện và notebook

## 1. Cài đặt

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Để mở notebook:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[notebook]"
```

## 2. Chuẩn bị yêu cầu và cấu hình

Chuẩn bị JSON theo [hướng dẫn payload](../design/strategy-payload-guide.md) và [đặc tả API](../design/backtest-api-specification.md). [Mẫu JSON](../../src/backtesting_api/web/canslim-v1-example.json) có hai nến mỗi nguồn để minh họa cấu trúc.

- Gửi dữ liệu nhập tay hoặc bật `auto_fetch_data=true` để lấy hai nguồn.
- Có `report`: API lấy lịch sử khởi tạo theo `warmup_bars` và chỉ báo trước `start_date`, tải đến hết `end_date`.
- Lỗi tải kết thúc yêu cầu. Để chạy đúng dữ liệu đã kiểm tra, gửi payload cụ thể từ `/validate`.

| Biến môi trường        | Mặc định                                  | Vai trò                                            |
| -------------------------- | -------------------------------------------- | --------------------------------------------------- |
| `BACKTEST_STORE_PATH`    | `data/backtest-store`                      | Kho đầu vào/kết quả                            |
| `INLINE_POLICY_PATH`     | `docs/data/vn30f1m/runtime-policy-v1.json` | Lịch phiên khi có contract_map                   |
| `AUTO_FETCH_POLICY_PATH` | `docs/data/vn30f1m/runtime-policy.json`    | Bảng đáo hạn khi tự lấy dữ liệu hợp đồng |

Thiết lập biến môi trường cho tiến trình trước khi chạy. Xem quy tắc kỳ báo cáo và dữ liệu thiếu tại [hợp đồng dữ liệu](../data/vn30f1m/data-contract.md).

## 3. Khởi động API và giao diện

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m uvicorn backtesting_api.main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000` cho giao diện; `/docs` cho OpenAPI.
Form cho nhập tham số, dữ liệu, điền mẫu hoặc tải JSON; kiểm tra/chạy và xem
lịch sử qua cùng API.

| Endpoint                              | Chức năng                                            |
| ------------------------------------- | ------------------------------------------------------ |
| `POST /api/backtests/validate`      | Kiểm tra cấu trúc, dữ liệu và tổ hợp thực thi |
| `POST /api/backtests`               | Chạy đồng bộ, lưu xong mới trả 201              |
| `GET /api/backtests`                | Danh sách đầy đủ các kết quả thành công      |
| `GET /api/backtests/history`        | Tóm tắt có lọc và phân trang                     |
| `GET /api/backtests/{run_id}`       | Kết quả                                              |
| `GET /api/backtests/{run_id}/input` | Đầu vào đã ghim của kết quả phiên bản 2      |
| `GET /api/backtests/{run_id}/chart` | Nến đã ghim của cùng run                          |

- Chạy một tiến trình ghi kho. Danh sách kết quả chỉ chứa lượt thành công.
- GET result/input/chart đọc dữ liệu đã lưu.
- Hai nút dữ liệu có sẵn đọc file cục bộ cố định; thiếu file thì tải JSON lên.

## 4. Notebook

Mở [notebooks/backtest-results.ipynb](../../notebooks/backtest-results.ipynb)
bằng kernel `.venv`, khởi động API rồi chạy các ô mã. Notebook gửi JSON,
nhận run_id và đọc lại kết quả của chính lượt chạy đó; không tính lại tiền.

| Biến                     | Mặc định                                | Vai trò                   |
| ------------------------- | ------------------------------------------ | -------------------------- |
| `BACKTEST_API_URL`      | `http://127.0.0.1:8000`                  | API                        |
| `BACKTEST_PAYLOAD`      | `data/payload.json` tại gốc repository | File yêu cầu             |
| `BACKTEST_REPORT_START` | Theo JSON                                  | Ghi đè report.start_date |
| `BACKTEST_REPORT_END`   | Theo JSON                                  | Ghi đè report.end_date   |

Thay kỳ báo cáo vẫn phải giữ đủ lịch sử khởi tạo và nến thực thi.
Không dùng kết quả tổng hợp làm bằng chứng nghiệm thu dữ liệu thật.

## 5. Docker và kiểm thử

```powershell
docker compose up --build
```

- [compose.yaml](../../compose.yaml) dùng `APP_PORT`, mặc định 8000.
- Kho kết quả: `./data/backtest-store` → `/app/backtest-store`; được giữ khi khởi động lại.
- Snapshot: gắn `./data` chỉ đọc tại `/app/data`.
- Compose đọc `APP_PORT` từ môi trường/`.env`; chính sách dùng mặc định trong image hoặc cấu hình thêm tại Compose.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node --test tests/web/*.test.mjs
```

[Danh mục kiểm thử](../testing/vn30f1m/canslim-v1-test-cases.md) nêu phạm vi
và giới hạn của các test.
