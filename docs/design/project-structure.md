# Cấu trúc repository

Ứng dụng dùng package `backtesting_api`, nhận JSON và lưu đầu vào/kết quả
qua `FileRunRepository`. Hướng dẫn chạy tại [API và notebook](../guides/run-backtest.md).

## 1. Các thành phần hiện tại

| Đường dẫn | Vai trò |
| --- | --- |
| `src/backtesting_api/main.py` | Nối service, kho file, bộ tải dữ liệu và FastAPI |
| `src/backtesting_api/config.py` | Cấu hình API, phiên bản engine, đường dẫn kho |
| `src/backtesting_api/api/app.py` | Phục vụ trang, tài nguyên và hai snapshot cục bộ |
| `src/backtesting_api/api/backtest_routes.py` | Endpoint kiểm tra, chạy, lịch sử, result/input/chart |
| `src/backtesting_api/api/inline_schemas.py` | Kiểm tra cấu trúc JSON bằng Pydantic |
| `src/backtesting_api/application/inline_data.py` | Ánh xạ nến, thời gian, kỳ báo cáo, lịch và mã hợp đồng |
| `src/backtesting_api/application/inline_strategy.py` | Chỉ báo, cây điều kiện, sizing và trạng thái chiến lược |
| `src/backtesting_api/application/inline_results.py` | Chuyển kết quả thành JSON |
| `src/backtesting_api/application/run_backtest.py` | Điều phối kiểm tra/chạy/lưu/đọc |
| `src/backtesting_api/application/ports.py` | Giao diện kho kết quả |
| `src/backtesting_api/domain/` | Nến, tín hiệu, lệnh, chỉ báo, biểu thức, engine và sổ tiền |
| `src/backtesting_api/infrastructure/auto_fetch_data.py` | Lấy hai nguồn VNDIRECT, giữ nến đã đóng |
| `src/backtesting_api/infrastructure/market_snapshot.py` | Kiểm tra và chuẩn hóa dữ liệu nguồn |
| `src/backtesting_api/infrastructure/file_repository.py` | Ghim JSON bằng hash, lưu/đọc run và dữ liệu chart |
| `src/backtesting_api/web/` | HTML, CSS, các module giao diện và mẫu JSON |
| `src/backtesting_api/web/vendor/` | Lightweight Charts, giấy phép và ghi nhận nguồn |
| `notebooks/backtest-results.ipynb` | Gửi JSON và trình bày kết quả từ API |
| `tests/` | Kiểm thử Python, JavaScript và fixture nhỏ |
| `docs/data/vn30f1m/runtime-policy*.json` | Cấu hình lịch phiên và bảng đáo hạn |
| `compose.yaml`, `Dockerfile` | Đóng gói và chạy cùng kho file được gắn ngoài container |

## 2. Đường đi của yêu cầu

```text
backtesting_api.main:app
  → api/backtest_routes.py
  → application/run_backtest.py
  → application/inline_data.py
  → application/inline_strategy.py
  → domain/engine.py
  → application/inline_results.py
  → infrastructure/file_repository.py
```

- `main.build_service()` nối `run_inline_strategy` vào `BacktestService`.
- Khi tự lấy dữ liệu, service gọi `AutoDataFetcher` trước khi ánh xạ nến.
- Không chọn chiến lược theo tên symbol; mọi điều kiện phải có trong JSON.
- [Sơ đồ tuần tự](system-design.md) mô tả thứ tự lời gọi và xử lý lỗi.

## 3. Ranh giới module

| Khu vực | Trách nhiệm | Ranh giới |
| --- | --- | --- |
| `api/` | HTTP và schema | Không tính chiến lược hoặc tiền |
| `application/` | Điều phối, dữ liệu JSON, chiến lược JSON và kết quả | Không phụ thuộc kho lưu cụ thể |
| `domain/` | Nghiệp vụ, thực thi và sổ tiền | Không import HTTP, application hoặc infrastructure |
| `infrastructure/` | Dữ liệu bên ngoài và kho file | Không tự thêm quy tắc giao dịch |
| `web/`, `notebooks/` | Nhập yêu cầu, trình bày kết quả API | Không tính lại chỉ báo, tín hiệu hoặc P/L |

`domain/market.py`, `trading.py` và `results.py` chứa các kiểu dữ liệu theo
nghiệp vụ. `engine.py` xử lý thời gian; `execution.py` xử lý khớp;
`portfolio.py` và `contract_accounting.py` giữ hai mô hình tiền hiện có.

## 4. Cấu hình và kho file

| Cấu hình | Nội dung |
| --- | --- |
| `API` | Tiêu đề, phiên bản và đường dẫn API |
| `BACKTEST` | Phiên bản engine |
| `INTRADAY` | Kho kết quả từ `BACKTEST_STORE_PATH`, mặc định `data/backtest-store` |
| `INLINE_POLICY_PATH` | Mặc định `docs/data/vn30f1m/runtime-policy-v1.json` |
| `AUTO_FETCH_POLICY_PATH` | Mặc định `docs/data/vn30f1m/runtime-policy.json` |

- Đầu vào/chính sách/metadata nằm trong `inputs/<input_hash>.json`; trạng thái và kết quả nằm trong `runs/<run_id>.json`.
- Một tiến trình ghi, công bố từng tệp bằng thay thế nguyên tử.
- Nhánh đọc kết quả phiên bản 1 vẫn dùng dataset/Parquet đã ghim; yêu cầu JSON mới không đăng ký dataset.

## 5. Tài nguyên giao diện

- `index.html` nạp `backtest-input.mjs`, `backtest-app.mjs`, `backtest-data.mjs`, `backtest-chart.mjs` và `language.mjs`.
- CSS nhập liệu/điều hướng nằm trong `backtest-input.css` và `backtest-navigation.css`; `theme.css`/`theme.mjs` cung cấp giao diện nền.
- Ứng dụng chính dùng `preview=True` để nạp `preview.css` và thay module theme bằng `preview-theme.mjs`.
- Tài nguyên được đóng gói qua `pyproject.toml`.

## 6. Dữ liệu và tài liệu cục bộ

`.env`, `.venv/`, `.agents/`, `local_only_docs/`, `outputs/`, `logs/`
và phần lớn `data/` được Git bỏ qua. Hai ngoại lệ ignore
`data/preprocessing.ipynb` và `data/dataset_manifest.json` không có nghĩa là
chúng thuộc luồng chạy JSON hiện tại. API không đọc manifest này.

Dữ liệu gốc và kết quả lớn ở cục bộ; fixture nhỏ thuộc `tests/fixtures/`.
`.agents/` chứa công cụ/tài liệu của trợ lý, không phải thành phần sản phẩm.
