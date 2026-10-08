# Thiết kế hệ thống — Backtesting API

## 1. Mục tiêu và luồng xử lý

Ứng dụng đồng bộ nhận JSON và đi qua các lớp:
`data → indicator → strategy evaluation → signal → execution → portfolio → metrics`.
Giao diện và notebook gọi cùng API; domain không chọn rule dựa trên tên symbol.
Quy tắc thuộc [hướng dẫn JSON](strategy-payload-guide.md),
[CANSLIM v1](../strategies/canslim-v1-rules.md) và
[accounting](canslim-v1-execution-accounting.md).

```mermaid
flowchart LR
    UI[UI] --> API[HTTP API]
    API --> APP[BacktestService]
    APP --> DATA[Kiểm tra và ánh xạ JSON]
    DATA --> STRAT[Chỉ báo và cây điều kiện]
    STRAT --> ENGINE[Engine: tín hiệu, khớp lệnh, tài khoản]
    ENGINE --> RESULT[Kết quả JSON]
    APP --> STORE[(FileRunRepository)]
    RESULT --> STORE
    STORE --> API
```

### 1.1. Một yêu cầu POST /api/backtests đi qua hàm nào?

Sơ đồ dưới đây đối chiếu với source hiện tại. Đây là lời gọi đồng bộ: API
chờ chạy và lưu xong mới trả HTTP 201. Khi khởi động, `main.build_service()`
nối `BacktestService` với `FileRunRepository` và đặt
`inline_runner=run_inline_strategy`; không dựng lại service cho mỗi yêu cầu.

```mermaid
sequenceDiagram
    autonumber
    actor Client as UI
    participant HTTP as FastAPI / backtest_routes
    participant Schema as inline_schemas
    participant Service as BacktestService
    participant Data as inline_data
    participant Strategy as inline_strategy
    participant Repo as FileRunRepository
    participant Mapper as inline_results

    Client->>HTTP: POST /api/backtests (JSON)
    HTTP->>Schema: Kiểm tra bằng InlineRunRequest trước khi vào route
    Note over Schema: Các bộ kiểm tra lồng nhau gồm prices(), timestamps(),<br/>directions(), expressions(), requirements()
    Schema-->>HTTP: request hợp lệ
    HTTP->>HTTP: run_backtest(request)<br/>request.model_dump(mode='json', by_alias=True, exclude_none=True)
    HTTP->>Service: run_inline(payload)
    Service->>Service: validate_inline(payload)
    Service->>Service: prepare_inline(payload)
    opt trade_data có contract_map
        Service->>Service: Đọc inline_policy_path bằng json.loads(path.read_bytes())
    end
    Service->>Data: resolve_inline(payload, policy)
    Data->>Data: normalize_raw_source() cho từng nguồn<br/>_bars() đổi timestamp và giá
    opt Có contract_map
        Data->>Data: Ánh xạ contract_code<br/>_session_gaps() kiểm tra phiên và ghi khoảng thiếu
    end
    Data-->>Service: InlineData (bars, market_bars, khoảng báo cáo, metadata)
    Service->>Service: Kiểm tra available_at == closed_at của nến giao dịch
    Service->>Strategy: check_runtime(payload)
    Strategy-->>Service: Cấu hình thuộc phạm vi bộ chạy hỗ trợ
    Service->>Repo: start_inline(payload, policy, data)
    Repo->>Repo: Ghim inputs/input_hash.json<br/>ghi runs/run_id.json với status=running
    Repo-->>Service: run_id, input_hash, policy_hash
    alt Chạy và lưu thành công
        Service->>Strategy: inline_runner(data, payload) = run_inline_strategy(data, payload)
        Note over Strategy: Khởi tạo chỉ báo, bộ thực thi và gọi run_engine()<br/>Chi tiết vòng lặp ở mục 1.2
        Strategy-->>Service: BacktestResult
        Service->>Service: Kiểm tra ngày khớp nằm trong khoảng báo cáo
        Service->>Mapper: inline_result_to_dict(run_id, data, result, hashes, accounting)
        alt accounting.model == contract
            Mapper->>Mapper: contract_result_to_dict() → exact_json()
        else accounting.model == normalized
            Mapper->>Mapper: normalized_result_to_dict() → exact_json()
        end
        Mapper-->>Service: response dạng JSON
        Service->>Repo: complete_run(run_id, result, response)
        Repo->>Repo: Kiểm tra run/input/hash<br/>_publish_json() → _publish_bytes() → os.replace()
        Repo-->>Service: Đã công bố status=succeeded và result_hash
        Service-->>HTTP: response
        HTTP-->>Client: HTTP 201 + kết quả
    else Có ngoại lệ sau start_inline() trong khối try của run_inline()
        Service->>Repo: fail_run(run_id, error)
        Repo->>Repo: Ghi status=failed và error_type
        Service-->>HTTP: Ném lại ngoại lệ
        HTTP-->>Client: HTTP lỗi theo loại ngoại lệ
    end
```

Kiểm tra schema không đạt thì FastAPI trả 422 trước khi gọi `run_backtest()`.
Lỗi ở `validate_inline()` hoặc `start_inline()` xảy ra trước khối `try` chạy
chiến lược, nên không đi qua `fail_run()`. Route đổi `ValueError` thành 422;
`OSError`, `KeyError`, `TypeError` thành 503; ngoại lệ khác không được route
này ánh xạ riêng. Nếu chính `fail_run()` lỗi thì việc ghi trạng thái failed
cũng không được bảo đảm.

`POST /api/backtests/validate` đi qua route `validate_inline(request)` →
`request.model_dump()` → `service.validate_inline(payload)` rồi trả kết quả
kiểm tra. Nó không gọi `start_inline()`, `run_inline_strategy()` hoặc lưu run.
Đầu vào HTTP hiện bắt buộc cung cấp `trade_data`; nhánh `auto_fetch_data`
trong `prepare_inline()` không thuộc cấu trúc `InlineRunRequest` hiện tại.

### 1.2. Trong mỗi nến, engine gọi gì và theo thứ tự nào?

`run_inline_strategy()` gọi lại `check_runtime(payload)`, dựng
`IndicatorData(data, payload)` và chọn bộ thực thi:

- `contract`: `InlineExecution` kế thừa `ContractExecution`, dùng `ContractPortfolio`.
- `normalized`: `InlineNormalizedExecution` kế thừa `NormalizedExecution`, dùng `Portfolio`.

Sau đó hàm gọi `run_engine(..., signal_provider=evaluate, execution=lambda cash: executor, on_open=executor.before_open)`.
`evaluate(context)` là hàm nằm bên trong `run_inline_strategy()`, không phải
endpoint hay phương thức của engine. `run_engine()` kiểm tra thứ tự/thời gian
nến và gọi hàm `execution` để nhận lại bộ thực thi đã dựng.

```mermaid
sequenceDiagram
    autonumber
    participant Runner as run_inline_strategy
    participant Engine as run_engine
    participant Exec as executor (theo model)
    participant Ledger as portfolio (theo model)
    participant Eval as evaluate(context)
    participant Series as IndicatorData
    participant Expr as expressions

    Runner->>Engine: run_engine(data.bars, evaluate, ...)
    loop Từng nến theo thứ tự thời gian (kể cả lịch sử khởi tạo)
        Engine->>Exec: before_open(bar.trading_date)
        Note over Exec: Cập nhật ngày và giờ Open<br/>contract còn kiểm tra khoảng thiếu khi giữ vị thế,<br/>qua đêm và hạn hết vị thế
        opt Có tín hiệu chờ từ Close trước
            Engine->>Exec: execute(signal, signal_date, bar.trading_date, bar.open)
            Note over Exec,Ledger: Tính lượng tại giá khớp và cập nhật sổ tiền<br/>chuỗi gọi cụ thể ở mục 1.3
            Exec-->>Engine: fill, trade hoặc lỗi
            Note over Engine: ValueError thông thường → order REJECTED<br/>InvalidExecution → dừng lần chạy<br/>khớp thành công → ghi order, fill và trade nếu có
        end
        Engine->>Exec: intrabar(bar)
        alt contract có vị thế và bracket
            Exec->>Exec: ContractExecution.intrabar(): xét stop trước target
            opt Chạm stop hoặc target
                Exec->>Exec: self.execute() → InlineExecution.execute()<br/>→ ContractExecution.execute()
                Exec->>Ledger: ContractPortfolio.exit(quantity, price)
                Ledger-->>Exec: Sổ tiền mới, costs, allocated, net
            end
            Exec->>Exec: Cập nhật trailing sau xử lý nến nếu đã kích hoạt
            Exec-->>Engine: Các sự kiện thoát đã khớp
        else normalized hoặc không có bracket/vị thế
            Exec-->>Engine: Không có sự kiện trong nến
        end
        opt Nến thuộc khoảng báo cáo
            Engine->>Ledger: mark(bar.close)
            Ledger-->>Engine: Snapshot để ghi equity_history
        end
        Engine->>Engine: Thêm nến vào completed<br/>chỉ thêm market_bars có available_at <= bar.closed_at
        Engine->>Eval: signal_provider(DecisionContext(...))
        Eval->>Series: at(bar.closed_at)
        Series-->>Eval: Chuỗi dữ liệu/chỉ báo đã khả dụng và số mẫu
        Eval->>Ledger: mark(bar.close)
        Ledger-->>Eval: Snapshot để dựng account/day/position refs
        alt Đang giữ vị thế và có exit.bar_close
            loop Nhãn điều kiện thoát theo priority, dừng khi gặp điều kiện đúng
                Eval->>Expr: evaluate_expression(condition, values, conditions)
                Expr-->>Eval: Đúng / sai hoặc MissingValue
            end
            opt Có điều kiện thoát đúng
                Eval->>Exec: close_signal(nhãn điều kiện)
                Exec-->>Eval: FixedSignal SELL hoặc CLOSE
            end
        else Không giữ vị thế
            Eval->>Eval: Kiểm tra khoảng báo cáo, giờ mở,<br/>chờ vào lại, khoảng thiếu và warmup
            opt Đủ điều kiện xét mở
                Eval->>Expr: evaluate_expression(daily_limits.stop_new_entry) nếu có
                opt Chưa chạm giới hạn ngày
                    Eval->>Expr: evaluate_expression() cho từng nhánh entry.any
                    Eval->>Eval: Một nhánh đúng → FixedSignal<br/>nhiều nhánh đúng → SIGNAL_CONFLICT<br/>không có nhánh đúng → không có tín hiệu
                    opt Có tín hiệu mở
                        Eval->>Expr: evaluate_expression() cho entry.details nếu có
                    end
                end
            end
        end
        Eval->>Eval: Ghi evaluations nếu thuộc khoảng báo cáo
        Eval-->>Engine: FixedSignal hoặc None
        opt Có tín hiệu trong khoảng được giao dịch
            Engine->>Exec: validate(signal)
            Engine->>Engine: Ghi SignalRecord và pending cho Open kế tiếp
        end
    end
    Engine->>Engine: Ghi order PENDING nếu hết dữ liệu<br/>tạo Summary và BacktestResult
    Engine-->>Runner: BacktestResult
    Runner->>Runner: Kiểm tra vị thế cuối kỳ khi cấm qua đêm<br/>đổi lệnh mở còn chờ thành REJECTED / END_OF_REPORT<br/>gắn evaluations và position_details bằng replace()
```

`IndicatorData.__init__()` tính trước các chuỗi chỉ báo theo từng đoạn dữ
liệu; `at(stamp)` chỉ trả phần có `available_at <= stamp`, giới hạn từ điểm
khởi tạo lại sau đổi hợp đồng hoặc khoảng thiếu. Tính trước chuỗi không cho
phép `evaluate()` đọc mẫu tương lai. `evaluate_expression()` gọi
`validate_expression()` trước khi tính; `all`/`any` đánh giá mọi toán hạng.

Nếu thiếu dữ liệu khi xét mở, `evaluate()` ghi `UNEVALUABLE` và không tạo
tín hiệu. Khi xét thoát theo Close, `MissingValue` ở một nhãn khiến bộ chạy
bỏ qua nhãn đó và xét nhãn tiếp theo. Margin/time-stop/giờ thoát theo Close
được xét qua biểu thức đã khai báo; không có một hàm tự thêm các quy tắc này.

### 1.3. Lời gọi khớp lệnh và vị trí source

| Bước                   | Chuỗi hàm thực tế                                                                                                                                                                                 | File                                                                                                                                                                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nhận HTTP               | `create_backtest_router()` đăng ký route `run_backtest(request)`                                                                                                                               | [backtest_routes.py](../../src/backtesting_api/api/backtest_routes.py)                                                                                                                                                         |
| Kiểm tra cấu trúc     | `InlineRunRequest` và các bộ kiểm tra của `DataInput`, `EntryInput`, `StrategyInput`                                                                                                     | [inline_schemas.py](../../src/backtesting_api/api/inline_schemas.py)                                                                                                                                                           |
| Điều phối             | `run_inline()` → `validate_inline()` → `prepare_inline()`                                                                                                                                     | [run_backtest.py](../../src/backtesting_api/application/run_backtest.py)                                                                                                                                                       |
| Dữ liệu                | `resolve_inline()` → `normalize_raw_source()`, `_bars()` và `_session_gaps()` khi có map                                                                                                   | [inline_data.py](../../src/backtesting_api/application/inline_data.py)                                                                                                                                                         |
| Chuẩn bị chiến lược | `run_inline_strategy()` → `check_runtime()`, `IndicatorData.__init__()`, khởi tạo executor → `run_engine()`                                                                               | [inline_strategy.py](../../src/backtesting_api/application/inline_strategy.py)                                                                                                                                                 |
| Vòng lặp               | `run_engine()` → `before_open()`, `execute()` nếu có pending, `intrabar()`, `mark()`, `evaluate()`, `validate()` nếu có tín hiệu                                                 | [engine.py](../../src/backtesting_api/domain/engine.py)                                                                                                                                                                        |
| Tính điều kiện       | `evaluate()` → `IndicatorData.at()` → `evaluate_expression()` → `validate_expression()`                                                                                                    | [inline_strategy.py](../../src/backtesting_api/application/inline_strategy.py), [expressions.py](../../src/backtesting_api/domain/expressions.py)                                                                               |
| Mua normalized           | `InlineNormalizedExecution.execute()` → `NormalizedExecution.execute()` → hàm `size(context)` → `Portfolio.buy()`                                                                         | [inline_strategy.py](../../src/backtesting_api/application/inline_strategy.py), [execution.py](../../src/backtesting_api/domain/execution.py), [portfolio.py](../../src/backtesting_api/domain/portfolio.py)                     |
| Bán normalized          | `InlineNormalizedExecution.execute()` → `NormalizedExecution.execute()` → `Portfolio.sell()`                                                                                                  | [execution.py](../../src/backtesting_api/domain/execution.py), [portfolio.py](../../src/backtesting_api/domain/portfolio.py)                                                                                                    |
| Mở contract             | `InlineExecution.execute()` kiểm tra thời gian, tính lượng và bracket → `ContractExecution.execute()` → `validate()` → `ContractPortfolio.enter()` → `ContractAccounting.costs()` | [inline_strategy.py](../../src/backtesting_api/application/inline_strategy.py), [execution.py](../../src/backtesting_api/domain/execution.py), [contract_accounting.py](../../src/backtesting_api/domain/contract_accounting.py) |
| Đóng contract          | `InlineExecution.execute()` → `ContractExecution.execute()` → `validate()` → `ContractPortfolio.exit()` → `ContractAccounting.costs()`                                                  | [execution.py](../../src/backtesting_api/domain/execution.py), [contract_accounting.py](../../src/backtesting_api/domain/contract_accounting.py)                                                                                |
| Chuyển kết quả        | `inline_result_to_dict()` → hàm theo model → `exact_json()`                                                                                                                                    | [inline_results.py](../../src/backtesting_api/application/inline_results.py)                                                                                                                                                   |
| Ghi đầu vào/kết quả | `start_inline()`, `complete_run()` hoặc `fail_run()` → `_publish_json()` / `_publish_bytes()`                                                                                             | [file_repository.py](../../src/backtesting_api/infrastructure/file_repository.py)                                                                                                                                              |

`portfolio` là sổ tiền bất biến: `buy()`/`sell()` hoặc `enter()`/`exit()` trả
sổ tiền mới; executor thay `self.portfolio`, engine lấy lại sổ tiền đó sau
khớp. `mark()` chỉ trả snapshot, không tự tạo giao dịch. Khối lượng được tính
lúc `execute()`, không cố định từ lúc phát tín hiệu.

## 2. Ranh giới module

| Thành phần        | Source                                                                                  | Trách nhiệm                                                       |
| ------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Điểm khởi chạy  | `backtesting_api/main.py`                                                             | Nối repository, bộ chạy JSON, chính sách và FastAPI           |
| HTTP                | `api/app.py`, `api/backtest_routes.py`, `api/inline_schemas.py`                   | Kiểm tra yêu cầu và ánh xạ lỗi HTTP                          |
| Điều phối        | `application/run_backtest.py`, `application/ports.py`                               | Kiểm tra, chạy, lưu và đọc qua một repository                |
| Dữ liệu           | `application/inline_data.py`, `infrastructure/market_snapshot.py`                   | Ánh xạ và kiểm tra OHLCV, thời gian, map hợp đồng           |
| Chiến lược JSON  | `application/inline_strategy.py`, `domain/expressions.py`, `domain/indicators.py` | Chỉ báo, biểu thức, điều kiện và trạng thái chiến lược |
| Thực thi và tiền | `domain/engine.py`, `execution.py`, `portfolio.py`, `contract_accounting.py`    | Điều phối thời gian, khớp lệnh và sổ tài khoản            |
| Kết quả           | `application/inline_results.py`, `domain/results.py`                                | Chuyển kết quả engine thành JSON                                |
| Kho file            | `infrastructure/file_repository.py`                                                   | Ghim đầu vào, lưu/đọc kết quả và dựng dữ liệu chart     |
| Giao diện          | `web/`                                                                                | Trình bày cùng một kết quả từ API                            |

Domain không import API, application, infrastructure hoặc web. Chiến lược được
khai báo bằng chỉ báo/biểu thức trong JSON; không thực thi mã Python do HTTP gửi.
Cấu trúc đầy đủ tại [cấu trúc repository](project-structure.md).

## 3. Thời gian, tín hiệu và trạng thái

Engine xử lý các bước tại nến: thực thi lệnh chờ ở Open → áp dụng fill/rejection
→ xử lý thoát trong nến theo rule → ghi tài khoản tại Close → đánh giá điều kiện
bằng dữ liệu đã khả dụng → tạo tín hiệu/lệnh chờ cho Open kế tiếp.
Dữ liệu thị trường được ghép theo available_at, không theo chỉ số dòng.

```mermaid
stateDiagram-v2
    [*] --> Flat
    Flat --> EntryPending: tín hiệu sau Close
    EntryPending --> Holding: khớp tại Open hợp lệ
    EntryPending --> Flat: lệnh bị từ chối hoặc hết hiệu lực
    Holding --> ExitPending: tín hiệu thoát sau Close
    Holding --> Holding: đóng một phần trong nến
    Holding --> Flat: đóng toàn bộ trong nến
    ExitPending --> Holding: đóng một phần hoặc bị từ chối
    ExitPending --> Flat: đóng toàn bộ
```

Signal, order và fill là record khác nhau. Không có fill thì không được tạo
trade hoặc thay đổi vị thế như đã giao dịch. Sizing sử dụng giá/thông tin tại
lúc thực thi, theo nhóm sizing/accounting trong JSON. Normalized và contract
là hai mô hình tiền hiện hỗ trợ; các giới hạn cụ thể thuộc đặc tả API.

IndicatorData chuẩn bị chuỗi nhưng mỗi lần đánh giá chỉ đọc phần đã khả dụng.
Thiếu lịch sử hoặc dữ liệu bắt buộc tại t phải ghi UNEVALUABLE. Không lặp nến
tham chiếu, không tự điền gap, không ghép giá hợp đồng tương lai để tính quá khứ.

## Các trường hợp lỗi và phục hồi theo luồng

Bảng này đặt lỗi tại đúng layer để không lẫn trách nhiệm giữa data, strategy,
execution, portfolio và repository. Mã `SDD-EX-*` là điểm nối cho state-machine
test và integration test.

| Case ID       | Điểm phát sinh                                                                | Ảnh hưởng trạng thái/dữ liệu                                                                                  | Hành động hệ thống                                                                                                         |
| ------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `SDD-EX-01` | Data loader/validator gặp schema, OHLC, thứ tự hoặc metadata sai             | Chưa được phép vào indicator/strategy; chưa có signal hoặc fill hợp lệ                                    | Dừng run và trả structured validation error; không tự sửa hoặc điền dữ liệu                                          |
| `SDD-EX-02` | Indicator/strategy thiếu warm-up hoặc required value tại`t`                 | Chỉ lần đánh giá hiện tại không có signal; state vị thế giữ nguyên                                      | Ghi reason unevaluable và tiếp tục các bar hợp lệ sau đó                                                                |
| `SDD-EX-03` | Execution nhận pending nhưng không có Open kế tiếp hợp lệ                | Order ghi trạng thái chưa khớp hoặc cuối kỳ theo cấu hình; không phát sinh fill hoặc thay đổi position | Ghi trạng thái cuối kỳ/missing next bar theo result contract; không tạo giá giả                                         |
| `SDD-EX-04` | Execution hoặc ledger từ chối order do quantity/cash/side/fee                 | Signal vẫn tồn tại; order rejected; position và ledger không đổi bởi fill                                    | Ghi order outcome/reason, chuyển sang bước mark/evaluate kế tiếp                                                           |
| `SDD-EX-05` | Core phát hiện invariant sai như cash âm ngoài tolerance hoặc position âm | Run không còn đủ điều kiện thành công; child records không được xem là result hoàn chỉnh             | Đánh dấu failed với structured error; không trả partial result thành công                                               |
| `SDD-EX-06` | Repository không ghi atomically hoặc artifact/result sai hash/schema khi đọc | Không được công bố aggregate succeeded; dữ liệu lỗi không được dùng làm result                        | Công bố từng tệp bằng thay thế nguyên tử; không công bố kết quả thiếu, từ chối tệp sai khi đọc               |
| `SDD-EX-07` | Evaluator có nguy cơ nhìn thấy dữ liệu sau decision hoặc full array       | Có nguy cơ làm sai signal, fill và tính tái lập                                                               | Chỉ truyền prefix/record có`available_at <= decision`; causality test phải chặn vi phạm                                 |
| `SDD-EX-08` | Service restart sau khi run đã thành công hoặc failed                       | Run thành công phải giữ được business result; run failed không xuất hiện trong history thành công        | Repository reload theo hash/schema; API chỉ đọc succeeded; trạng thái failed được lưu trong tệp run để đối chiếu |

## 4. Kho file và trạng thái lượt chạy

`BACKTEST_STORE_PATH` mặc định `data/backtest-store`:

```text
backtest-store/
├── inputs/<input_hash>.json       # JSON đầy đủ, chính sách và metadata dữ liệu
├── runs/<run_id>.json             # running / failed / succeeded và kết quả
├── datasets/                     # Dataset/Parquet đã ghim cho lịch sử phiên bản 1
└── policies/                     # Chính sách của lịch sử đã có
```

`start_inline()` ghi đầu vào, tính input_hash/policy_hash và tạo run running.
Core chạy trong bộ nhớ; `complete_run()` kiểm tra run/input và công bố toàn bộ
kết quả succeeded bằng thay tệp nguyên tử, kèm result_hash. Lỗi sau khi tạo run
được lưu bằng `fail_run()`. Đây là công bố từng tệp, không phải giao dịch nhiều
file; run chỉ thành công khi tệp kết quả đầy đủ đã được công bố.

`get_run()` kiểm tra phiên bản, trạng thái, run_id, hash kết quả và đầu vào/chính
sách của phiên bản 2. `list_runs()` chỉ trả succeeded, theo tên tệp giảm dần;
không coi thứ tự UUID là thứ tự thời gian tạo. API không cung cấp danh sách failed.
`GET /api/backtests/history` dùng `iter_run_summaries()` để đọc và kiểm tra
từng kết quả, lọc theo tỷ suất sinh lời/vốn cuối kỳ rồi trả tóm tắt có phân
trang. Không giữ toàn bộ kết quả các lần chạy trong bộ nhớ. Web không gọi
danh sách đầy đủ và không tự mở lịch sử khi khởi động. Hiện tìm kiếm vẫn
cần đọc tệp JSON của các lần chạy được xét; khi số tệp làm việc quét chậm,
có thể bổ sung chỉ mục tóm tắt, không thay định dạng kết quả chỉ để giảm RAM web.
`get_input()` phục vụ kết quả phiên bản 2; lịch sử phiên bản 1 không có input JSON
này và trả lỗi tương thích khi gọi endpoint input.

Chart phiên bản 2 dựng từ đầu vào đã ghim; không chạy lại chiến lược hoặc gọi
nguồn ngoài. Trường open_time của một đầu vào lịch sử được ánh xạ khi đọc trên
bản sao; JSON mới vẫn bắt buộc time. Chart phiên bản 1 đọc manifest và nến
Parquet của lịch sử còn giữ; pyarrow phục vụ nhánh đọc này.

Kho có một tiến trình ghi. Đường dẫn chính sách/kho file tương đối được xác
định từ thư mục làm việc; chạy ứng dụng từ gốc repository theo
[runbook](../plans/vn30f1m-backtest-runbook.md).

## 5. Giao diện và đọc kết quả

API trả một result cho mỗi run. Summary, chart, fill marker, bảng giao dịch,
vị thế mở, audit và equity đều dùng cùng run_id/hash. Frontend chỉ định dạng
và lọc record, không tính lại chỉ báo hoặc tiền. Lỗi chart không tạo lượt chạy
mới; nút thử lại đọc kết quả/chart theo run_id đã có.
Chi tiết tại [đặc tả giao diện](web-ui-specification.md).

## 6. Kiểm thử và mở rộng

Kiểm thử các lớp dữ liệu/biểu thức, trạng thái lệnh, tính tiền, lỗi ghi nguyên
tử, hash/schema, đọc lịch sử, API, notebook và ánh xạ chart. Đối chiếu đầy đủ
với dữ liệu cắt tại t và dữ liệu tương lai bị thay đổi; chạy cùng JSON nhiều
lần phải giữ kết quả nghiệp vụ sau khi tách UUID.

Agent/MCP là thiết kế dự kiến tại [kế hoạch agent](../plans/agent-research-plan.md),
chưa tham gia luồng thực thi. Chưa có queue, nhiều tiến trình ghi hoặc kho phiên
agent được chọn. Mở rộng phải dùng cùng kiểm tra JSON và application boundary.
