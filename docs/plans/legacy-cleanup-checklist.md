# Checklist dọn luồng cũ và đổi tên thư mục API

## Task lớn và cách chia việc

Phạm vi chung: gỡ luồng thực thi v0 và PostgreSQL, giữ luồng JSON cùng các
thành phần tính toán còn dùng, sau đó chuyển package sang `backtesting_api`.
Các mục 1–9 bên dưới là chi tiết để nghiệm thu các task lớn sau, không phải
chín task độc lập. Mỗi task cần có một agent chịu trách nhiệm và báo cáo riêng.

| Mã | Task lớn và kết quả cần đạt | Mục chi tiết | Phụ thuộc |
| --- | --- | --- | --- |
| T0 | Chuẩn bị: ghi nhận thay đổi sẵn, kết quả kiểm thử ban đầu, bằng chứng JSON và quyết định lịch sử kho file; phân công người sở hữu file | 1–3, phần chuẩn bị của 9 | Trước các task sửa source |
| T1 | Gỡ PostgreSQL: ứng dụng không nối PostgreSQL; không còn adapter, script, migration, dịch vụ Docker hay dependency PostgreSQL | Phần PostgreSQL của 4, 6, 7, 9 | T0; phối hợp T5 ở file chung |
| T2 | Gỡ bộ chạy CANSLIM v0 và API registry: không còn cách chọn/chạy v0 trong hệ thống hiện tại | 5; phần registry/config/test v0 của 4, 6, 7, 9 | T0; hoàn tất gỡ phụ thuộc sau T1/T3 |
| T3 | Dọn kho dữ liệu v0 và giao diện kho: kho phục vụ đúng JSON hiện tại; phần đọc lịch sử file được giữ hay gỡ theo quyết định rõ ràng | Phần kho file/ports/bundle của 3, 4, 6, 7, 9 | T0 và quyết định lịch sử file; phối hợp T2/T5 |
| T4 | Đổi package: di chuyển vào `backtesting_api`, sửa import, tài nguyên đóng gói, điểm khởi chạy và nơi gọi | 2, 8; phần đổi tên của 4, 9 | T1–T3 đã tích hợp và kiểm tra |
| T5 | Điều phối tích hợp, tài liệu và nghiệm thu: sửa file chung, thống nhất giao diện, cập nhật tài liệu trước từng thay đổi và xác minh toàn hệ thống | 4, 9 và các phần dùng chung của 6–8 | Bắt đầu cùng T0; nghiệm thu cuối sau T4 |

Trạng thái task lớn:

- [X] T0 — Chuẩn bị và phân công.
- [ ] T1 — Gỡ PostgreSQL.
- [ ] T2 — Gỡ CANSLIM v0 và API registry.
- [ ] T3 — Dọn kho dữ liệu v0 và giao diện kho.
- [ ] T4 — Đổi package sang `backtesting_api`.
- [ ] T5 — Tích hợp, tài liệu và nghiệm thu toàn hệ thống.

### Phạm vi sở hữu khi nhiều agent cùng làm

| Task | File/phần việc agent trực tiếp sở hữu |
| --- | --- |
| T0/T5 | Ghi nhận trạng thái; checklist; tài liệu hiện hành; `config.py`, `pyproject.toml`, `requirements.txt`, notebook; test dùng chung như `test_config.py`, `test_engine_contract.py`, `test_application_api.py`, `test_inline_pipeline.py` |
| T1 | `infrastructure/database.py`, hai script PostgreSQL, migration v0, `main.py`, `compose.yaml`, `Dockerfile`, `.env.example`, test PostgreSQL/migration |
| T2 | `domain/strategies/`, `application/legacy_run_backtest.py`, `application/contracts.py`, `application/result_mapper.py`, `api/backtest_routes.py`, `api/app.py`, test riêng strategy/registry/mapper v0 |
| T3 | `infrastructure/file_repository.py`, `infrastructure/snapshot_bundle.py`, `application/ports.py`, `application/run_backtest.py`, test riêng bundle; đề xuất xử lý lịch sử file |
| T4 | Toàn bộ đường dẫn/package và các tham chiếu đổi tên, sau khi T1–T3 ngừng sửa source và bàn giao cho T4 |

Quy tắc phối hợp:

- T5 là vai trò điều phối, có thể do agent chính đảm nhiệm, không bắt buộc
  tạo một agent riêng. Ghi người nhận từng task trước khi triển khai.
- T1–T3 có thể khảo sát và sửa các file sở hữu riêng song song sau T0. Các
  thay đổi liên quan nhau phải tích hợp theo thứ tự phụ thuộc; không coi mỗi
  nhánh riêng là hệ thống đã chạy được khi những nơi import chưa được sửa.
- Mỗi file chỉ có một người sửa tại một thời điểm. Với `config.py`, metadata
  dependency, notebook, tài liệu và test chung, agent T1–T3 gửi yêu cầu thay đổi
  cụ thể cho T5; T5 thực hiện và kiểm tra. Không tự sửa chồng lên file chung.
- T2 chỉ xóa `contracts.py`/`result_mapper.py` sau khi T1, T3 và T5 xác nhận
  đã gỡ các import tương ứng. T3 báo rõ hàm còn cần cho lịch sử file; việc gỡ
  PostgreSQL không tự quyết định gỡ lịch sử phiên bản 1 trong kho file.
- T5 cập nhật tài liệu sở hữu cho từng task trước khi agent sửa source; cuối
  đợt rà lại toàn bộ tên file, lệnh, liên kết và mô tả còn sót.
- T4 thực hiện sau khi T1–T3 đã tích hợp; không di chuyển package trong lúc
  agent khác còn sửa đường dẫn cũ. Khi bàn giao T4, quyền sửa file chuyển sang
  T4 cho phạm vi đổi tên; sau đó bàn giao lại T5 để nghiệm thu.
- Agent báo file đã sửa, checkbox liên quan, kết quả kiểm tra và phụ thuộc
  còn chờ. T5 tổng hợp đánh dấu để tránh nhiều agent ghi chồng vào checklist.
  Chỉ đánh dấu task lớn khi các checkbox thuộc phạm vi của nó đã hoàn tất,
  thay đổi đã tích hợp và kiểm tra liên quan đạt; không đánh dấu theo báo cáo
  khảo sát hoặc phần sửa riêng chưa tích hợp.

## Cách thực hiện và đánh dấu

- Đọc `AGENTS.md`, `.agents/docs/README.md` và các tài liệu liên quan được dẫn
  trong checklist trước khi sửa. Checklist là kế hoạch công việc, không thay
  thế quy tắc chiến lược, dữ liệu hoặc tính tiền trong tài liệu sở hữu.
- Thực hiện theo từng task/nhóm công việc; một task có thể xử lý checkbox ở
  nhiều mục. Không bắt buộc hoàn thành toàn bộ một mục rồi mới sang mục tiếp theo.
- Giữ thứ tự phụ thuộc: chốt phạm vi → cập nhật tài liệu sở hữu → sửa source
  và cấu hình → kiểm thử → đánh dấu phần đã xác minh.
- Checkbox đã đánh dấu về quyết định của người dùng là thông tin đã chốt;
  không hỏi lại, trừ khi có yêu cầu mới thay đổi quyết định đó.
- Chỉ đánh dấu checkbox công việc khi mọi việc trong ô đã hoàn thành và các
  kiểm tra cần thiết đã đạt. Làm một phần hoặc còn lỗi thì để trống; tách ô
  thành các việc nhỏ nếu cần theo dõi riêng. Không đánh dấu theo việc dự kiến.
- Chỉ xử lý phạm vi task được giao; không đánh dấu cả mục hoặc toàn bộ
  checklist chỉ vì một task đã xong. Mục mô tả phạm vi không có checkbox.
- Sau mỗi task, báo các checkbox đã hoàn thành, file thay đổi, kiểm tra đã
  chạy và phần còn lại. Kiểm tra chưa chạy phải được báo rõ, không coi là đạt.

Ví dụ task gỡ PostgreSQL: dùng quyết định đã chốt ở mục 3, sửa tài liệu ở
mục 4, gỡ nơi nối và cấu hình ở mục 6–7, rồi kiểm thử ở mục 9. Đánh dấu từng
ô liên quan đã hoàn thành; các ô đổi tên package ở mục 2 và 8 vẫn để trống
nếu task chưa thực hiện việc đó.

## 1. Mục tiêu và phạm vi

Giữ một luồng thực thi: JSON → kiểm tra dữ liệu → chỉ báo → điều kiện chiến
lược → tín hiệu → khớp lệnh → tài khoản → kết quả → kho file. Gỡ bộ chạy
CANSLIM v0, registry v0 và các phụ thuộc chỉ phục vụ luồng đó khỏi source hiện hành.
Tên package đích là `backtesting_api`, thay tên gắn với HPG.

PostgreSQL nằm ngoài hệ thống đích. Người dùng xác nhận đã lưu bản sao dữ liệu
và script khởi tạo/migration trong thư mục khác ngoài repo. Không chuyển dữ liệu
PostgreSQL vào kho file, không giữ chức năng đọc lịch sử từ PostgreSQL và không
giữ bộ chạy, script, migration hoặc cấu hình PostgreSQL trong hệ thống này.

Không thay quy tắc trong JSON, ngưỡng chỉ báo, cách tính tiền, thời điểm dữ liệu
khả dụng hoặc quy tắc khớp lệnh. Không xóa dữ liệu thị trường, kết quả đã lưu,
database hay volume `postgres_data` trong đợt dọn source.

Tài liệu đối chiếu: [thiết kế hệ thống](../design/system-design.md),
[cấu trúc project](../design/project-structure.md),
[đặc tả API](../design/backtest-api-specification.md),
[hướng dẫn JSON](../design/strategy-payload-guide.md),
[kế hoạch kỹ thuật](technical-plan.md).

## 2. Chốt cách đổi tên

Người dùng chốt tên thư mục/package là `backtesting_api` và tự chuẩn bị thư mục
đích. Source sẽ được di chuyển vào thư mục đó trong đợt triển khai sau; bước
chuẩn bị checklist không tạo thư mục hoặc di chuyển source.

| Thành phần                             | Hiện tại                | Đích                       |
| ---------------------------------------- | ------------------------- | ---------------------------- |
| Tên phân phối trong`pyproject.toml` | `backtest-hpg`          | `backtesting_api`          |
| Thư mục package Python                 | `src/backtest_hpg/`     | `src/backtesting_api/`     |
| Đường dẫn import                     | `backtest_hpg.*`        | `backtesting_api.*`        |
| Điểm khởi chạy                       | `backtest_hpg.main:app` | `backtesting_api.main:app` |

- [X] Chốt tên thư mục/package là `backtesting_api`.
- [ ] Trước khi triển khai, đối chiếu vị trí thư mục người dùng đã chuẩn bị với
  đích `src/backtesting_api/`.
- [ ] Chốt khởi chạy `main:app`; gỡ alias `intraday_main.py` và sửa nơi gọi.
- [ ] Không tạo package chuyển tiếp `backtest_hpg` sau khi đổi tên.

## 3. Ghi nhận trạng thái trước khi dọn

- [X] Ghi nhận `git status`, phần sửa sẵn và file chưa được theo dõi; giữ nguyên
  thay đổi của người dùng ngoài phạm vi đợt dọn.
- [X] Chạy bộ test hiện tại bằng `.venv` và test JavaScript; ghi rõ lỗi tồn tại
  trước đợt dọn. Lần rà trước ghi nhận test `test_api_validate_and_run_with_raw_payload`
  kiểm tra `run_id` ở cấp ngoài cùng, trong khi kết quả trả `metadata.run_id`;
  kiểm tra lại phiên bản đã lưu trước khi kết luận lỗi còn tồn tại.
- [X] Lưu bằng chứng từ bộ dữ liệu tổng hợp cố định và cùng JSON: summary,
  signals, orders, fills, trades, equity, evaluations, input/policy hash.
  Khi so kết quả, tách UUID của lượt chạy khỏi nội dung nghiệp vụ.
- [X] Người dùng xác nhận dữ liệu PostgreSQL và script khởi tạo/migration đã
  được lưu ngoài repo; hệ thống không cần truy cập hoặc giữ dữ liệu PostgreSQL.
- [X] Liệt kê lịch sử có sẵn trong kho file và chức năng đọc lại cần giữ;
  không nhập lịch sử PostgreSQL vào kho file trong đợt dọn này.

## 4. Cập nhật tài liệu sở hữu trước source

- [X] T1: sửa phần lưu trữ trong thiết kế hệ thống, cấu trúc project và kế hoạch
  kỹ thuật theo kho file; gỡ mô tả kết nối, cấu hình và schema PostgreSQL.
- [ ] Sửa đặc tả API: chỉ mô tả endpoint còn phục vụ hệ thống; gỡ danh mục
  `/api/strategies` và `/api/strategies/{strategy_id}` của registry v0.
- [X] T1: gỡ hướng dẫn/liên kết PostgreSQL trong README và đặc tả giao diện;
  hướng dẫn chạy ứng dụng, Docker và notebook dùng kho file.
- [ ] Gỡ tên file, lệnh và liên kết không còn dùng trực tiếp; không thêm đoạn
  dạng “cập nhật: đã xóa…” hoặc giữ cây thư mục cũ như cấu trúc đang hoạt động.
- [ ] Kiểm tra liên kết tài liệu. Có liên kết tới các kế hoạch `engine-upgrade-*`
  nhưng file tương ứng không có trong `docs/plans` tại lần rà này; xử lý bằng
  tài liệu thực sự tồn tại, không tạo nội dung giả thay thế.

T2 tiếp tục cập nhật mô tả luồng JSON và gỡ hướng dẫn CANSLIM v0 khi gỡ bộ chạy.
T4 cập nhật tên package và thống nhất điểm khởi chạy trong tài liệu, Docker và
notebook theo mục 8.

## 5. Gỡ bộ chạy và API v0

- [ ] Gỡ `api/backtest_routes.py:create_strategy_router()`, `list_strategies()`,
  `get_strategy_schema()` và import registry; gỡ đăng ký router trong `api/app.py`.
- [ ] Gỡ `application/legacy_run_backtest.py` và `run_legacy_manifest()`.
- [ ] Gỡ `domain/strategies/canslim_breakout_v0.py`: `Parameters`,
  `data_requirements()`, `IndicatorSnapshot`, `calculate_snapshot()`, `size_buy()`,
  `Decision`, `evaluate_entry()`, `evaluate_exit()`, `CanslimStrategy`, `run()`.
- [ ] Gỡ `domain/strategies/__init__.py`: `StrategyDefinition`, `strategies`,
  `ENGINE_CAPABILITIES`, `get_strategy_definition()`, `get_strategy_parameters()`,
  `describe_strategy()`; bỏ thư mục nếu không còn source.
- [ ] Gỡ `application/contracts.py:RunConfig` sau khi tháo hết nơi phụ thuộc.
- [ ] Gỡ `application/result_mapper.py` sau khi tháo PostgreSQL và bộ chạy v0;
  luồng JSON tiếp tục dùng `inline_results.py`, không đổi độ chính xác kết quả.

## 6. Làm sạch phần dùng chung

- [ ] `application/ports.py`: mô tả đúng kho JSON với `start_inline()`,
  `get_input()` và các hàm đọc/lưu kết quả; gỡ `start_run()`, `RunConfig`,
  `DatasetSnapshot` khỏi giao diện kho hiện tại. Không xóa file chỉ vì tên không có `inline`.
- [ ] `application/run_backtest.py`: bỏ nhánh ghép hai kho trong `get()`,
  `list()`, `get_chart()` và tham số chọn kho cũ; dùng một kho file xuyên suốt.
- [X] `main.py`: bỏ lựa chọn `BACKTEST_LEGACY_BACKEND`, import/tạo
  `PostgresRunRepository` và `get_database_url()`; tiếp tục nối bộ chạy JSON.
- [ ] `file_repository.py`: gỡ `prepare_dataset()`, `validate_policy()`,
  `start_run()` và lệnh chuẩn bị dataset cũ ở cuối file.
- [ ] Tách việc đọc lịch sử phiên bản 1 khỏi việc chạy v0. Chỉ gỡ `_read_dataset()`,
  `_read_parquet()`, `_raw_rows()`, `PARQUET_SCHEMA`, `PRICE_FIELDS`, `DATASET_ID`
  và các nhánh phiên bản 1 khi quyết định lịch sử tại mục 3 đã được xử lý.
- [ ] Gỡ `infrastructure/snapshot_bundle.py` khi không còn nơi đọc bundle
  lịch sử hoặc lệnh chuẩn bị dữ liệu cần giữ; không thay đầu vào JSON bằng nguồn tự tìm.
- [ ] Rà `DatasetSnapshot` và phần model chỉ phục vụ v0 sau khi gỡ nơi gọi.
  Giữ `Bar`, `StrategyBar` và các model vẫn được luồng hiện tại sử dụng.
- [ ] Giữ các thành phần dùng chung: `engine.py`, `execution.py`, `portfolio.py`,
  `contract_accounting.py`, `indicators.py`, `expressions.py`, `trading.py`,
  `results.py` và phần còn dùng trong `market.py`, `market_snapshot.py`.
- [ ] Giữ chế độ tính tiền `normalized` nếu JSON hiện tại vẫn hỗ trợ;
  không đồng nhất chế độ này với bộ chạy CANSLIM v0.

## 7. Cấu hình, PostgreSQL và script

- [ ] Gỡ `CanslimBreakoutV0Settings`, `CANSLIM_BREAKOUT_V0`, `parameters()`.
- [ ] Gỡ `BACKTEST.supported_symbol`, `BACKTEST.result_label`, `ResultSettings`,
  `RESULT` khi không còn nơi dùng; giữ `BACKTEST.engine_version` cho kết quả JSON.
- [ ] Gỡ các hằng không còn nơi dùng: `VN30F1M_DATASET_ID`, `VN30F1M_CONTENT_HASH`,
  `VN30F1M_SNAPSHOT_DEFAULT`.
- [ ] Gỡ `INTRADAY.policy_path`, `VN30F1M_POLICY_PATH`, `INTRADAY_SNAPSHOT_URLS`
  khi đã tháo bộ dữ liệu cũ; giữ đường dẫn kho file và chính sách còn dùng bởi JSON.
- [X] Gỡ `infrastructure/database.py`, `scripts/run_postgres_acceptance.py`,
  `scripts/apply_migrations.py`, `migrations/001_initial.sql` và thư mục
  `migrations/` nếu không còn nội dung. Không tạo thành phần thay thế để đọc
  PostgreSQL; không chạy SQL xóa bảng hoặc xóa database bên ngoài source.
- [X] Gỡ `DatabaseSettings`, `DATABASE`, `get_database_url()`, `DATABASE_URL`
  và các mẫu `POSTGRES_*` khỏi cấu hình ứng dụng không còn dùng PostgreSQL.
- [X] Sửa Compose: gỡ dịch vụ `db`, `depends_on`/healthcheck PostgreSQL,
  `DATABASE_URL`, `POSTGRES_*`, `BACKTEST_LEGACY_BACKEND` và khai báo volume
  `postgres_data`; giữ mount kho kết quả JSON. Việc gỡ khai báo không bao gồm
  chạy `docker compose down -v` hoặc xóa volume vật lý đã có.
- [X] Sửa Dockerfile: bỏ chạy/copy script migration v0; dùng điểm khởi chạy mới.
- [X] Gỡ dependency `psycopg` cùng import và hướng dẫn cài đặt PostgreSQL.
- [ ] Rà dependency `pyarrow`; chỉ gỡ khi phần đọc dữ liệu file còn giữ không
  dùng nó. Không thêm dependency cho việc đổi tên.

## 8. Di chuyển package và sửa tham chiếu

- [ ] Di chuyển package theo tên đã chốt ở mục 2, giữ nguyên các lớp thư mục
  `api/`, `application/`, `domain/`, `infrastructure/`, `web/` còn cần.
- [ ] Sửa import, chuỗi đích `patch()`, điểm khởi chạy Uvicorn và đường dẫn
  tài nguyên trong source, test, script, notebook và Docker.
- [ ] Sửa tên phân phối, mô tả và `package-data` trong `pyproject.toml`;
  rà `requirements.txt` và metadata sinh ra khi cài theo chế độ chỉnh sửa.
- [ ] Rà tên HPG trong tiêu đề API, tài liệu và cấu hình sản phẩm;
  giữ nguyên symbol HPG trong dữ liệu/fixture lịch sử nếu còn giữ chúng.
- [ ] Rà các đường dẫn tính bằng `Path(__file__)` để `.env`, tài nguyên web
  và kho dữ liệu vẫn trỏ đúng sau di chuyển.
- [ ] Cài lại package trong `.venv` hiện có và xác nhận import package mới;
  ứng dụng không còn dựa vào package cũ đã cài trước đó.
- [ ] Quét tên cũ trên file Git quản lý và notebook. Phân biệt chuỗi lịch sử
  được giữ có chủ đích với tham chiếu đang thực thi; không thay UUID/hash
  trong fixture lịch sử để làm kết quả kiểm thử khớp.

## 9. Test và nghiệm thu

- [ ] Gỡ test chỉ dành cho bộ chạy/registry/API v0: rà `test_indicators_strategy.py`,
  `test_intraday_backtest.py`, `test_strategy_backtest.py`, `test_strategy_api.py`.
- [ ] Gỡ test PostgreSQL/migration: `test_database_parameters.py`,
  `test_migration_contract.py`; gỡ `test_precision.py` khi mapper v0 đã được gỡ.
  Giữ kiểm tra độ chính xác kết quả JSON hiện tại trong các test luồng JSON.
- [ ] Với `test_engine_contract.py`, `test_application_api.py`, `test_config.py`,
  `test_inline_pipeline.py`, `test_snapshot_bundle.py`, `test_v0_baseline_snapshot.py`:
  bỏ phụ thuộc bộ chạy cũ nhưng giữ kiểm tra dùng chung và lịch sử còn hỗ trợ;
  chỉ bỏ cả file nếu mọi trường hợp đều thuộc chức năng đã gỡ.
- [ ] Chạy test Python và JavaScript; không bỏ một kiểm tra còn cần chỉ vì nó thất bại.
- [ ] Kiểm tra ứng dụng mới: trang chủ, tài nguyên `.mjs` đúng MIME, kiểm tra JSON,
  chạy backtest, danh sách, đọc kết quả, đọc input và chart sau khởi động lại.
- [ ] API danh mục v0 không còn được đăng ký; `/docs` phản ánh đúng API hiện tại.
- [ ] Ứng dụng và Docker khởi chạy không cần PostgreSQL, `DATABASE_URL`,
  `POSTGRES_*` hoặc `psycopg`; không còn đường đọc/ghi PostgreSQL trong source,
  test, notebook, script và hướng dẫn chạy hiện hành.
- [ ] So bằng chứng trước/sau: cùng dữ liệu/JSON cho cùng kết quả nghiệp vụ,
  thời điểm signal/fill/equity và hash đầu vào/chính sách.
- [ ] Kiểm tra không đọc dữ liệu tương lai; thay dữ liệu tương lai không làm
  đổi kết quả trước đó, đối chiếu dữ liệu đầy đủ và dữ liệu cắt ở cùng thời điểm.
- [ ] Build/chạy Docker với package mới khi môi trường hỗ trợ; báo rõ phần chưa chạy.
- [ ] Kiểm tra liên kết tài liệu, package-data, tham chiếu tên cũ và `git diff --check`.

Hoàn tất khi source chỉ còn bộ chạy JSON, tên package/điểm khởi chạy thống nhất,
lịch sử được xử lý theo quyết định rõ ràng, các kiểm tra cần thiết đạt và tài liệu
mô tả đúng hệ thống hiện tại. Không commit hoặc push trong phạm vi checklist này.
