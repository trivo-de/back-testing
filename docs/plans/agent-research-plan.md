# Research agent và mở rộng backtest

Đây là thiết kế dự kiến; chưa triển khai agent hoặc cài SDK mới.
Tài liệu này phân biệt source hiện có, đề xuất research và điều kiện nghiệm thu;
không phê duyệt thêm strategy hoặc thay scope dữ liệu hiện hành.

## 1. Mục tiêu và hiện trạng đã kiểm tra

Bảng dưới là snapshot kiểm kê ngày 17/09, không phải trạng thái hiện tại.
Đến 21/09, source intraday đã có API, engine timestamp và repository Parquet/JSON;
CANSLIM, VN-Index R1 và normalized accounting đã được chốt. Nghiệm thu đủ kỳ

Đầu ra mong muốn: người dùng nhập “backtest mã xxx nếu giá vượt ...” hoặc
“dùng thuật toán xxx để backtest”, hệ thống làm rõ yêu cầu, chạy engine và trả
summary, nến, executed fills, trades, equity và metadata như output hiện có.

| Thành phần           | State                            | Bằng chứng tại thời điểm kiểm tra                                                                                                                            |
| ---------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Kế hoạch agent       | Done (tài liệu)                | P4.1–P4.5 trong backtest-plan-v0.md: danh mục hỗ trợ, tiếng Việt → spec, validation, nối API/chart, demo                                                    |
| Tổng quát hóa       | Not started ở mức StrategySpec | P2.1–P2.4 có kế hoạch; application/contracts.py mới có RunConfig                                                                                              |
| Chọn strategy         | Có nền tảng                   | domain/strategies/__init__.py có registry, mới đăng ký canslim_breakout_v0                                                                               |
| Application/API/result | Có source                       | BacktestService.run/get/list; POST/list/detail /api/backtests; result_mapper.py                                                                                     |
| Phạm vi source        | Legacy HPG daily                 | config.py giới hạn HPG; domain/market.py dùng date; request chưa nhận entry/exit tùy chọn                                                                    |
| Persistence            | Source PostgreSQL                | infrastructure/database.py;[Parquet + JSON](technical-plan.md#6-persistence-parquet-json) là target 18/09; metadata/session SQLite hoặc PostgreSQL còn chờ chốt |
| Chart snapshot VN30F1M | Done trong lượt 17/09          | market-chart.html/mjs, /api/market-chart, vendor 5.2.0; dữ liệu thật và browser đã kiểm tra; chart theo run/marker/equity chưa có                          |
| Agent chạy thật      | Not started                      | Chưa có strategy_agent/, provider, schema/spec interpreter hoặc bộ eval prompt                                                                                  |
| VN30F1M                | Blocked phần nghiệp vụ        | Contract 5 phút đã có; strategy và futures accounting chưa được duyệt                                                                                     |

“Cổ phiếu xxx” là hướng mở rộng ngoài target VN30F1M hiện hành. Agent không tự
mở rộng dữ liệu được hỗ trợ. Chọn một mã cho mỗi run trước; portfolio nhiều mã là
scope riêng, không đồng nghĩa với thay symbol trong prompt.

## 3. Thiết kế agent tối thiểu đề xuất

### 3.1. Kiến trúc hệ thống dự kiến

MVP đề xuất: một agent phục vụ baseline VN30F1M 5 phút, chọn
`canslim_breakout_v0` và config được phép. Web chat và agent là phần cần xây;
API, engine, repository và chart được tái sử dụng. Bedrock là hướng tích hợp
theo checklist local; model ID, region, budget và khả năng tool calling trên
model được cấp phải xác minh khi triển khai, chưa có runtime evidence trong plan.

```mermaid
flowchart TB
    U["Người dùng: prompt tiếng Việt"] --> W["Web chat dự kiến: HTML / CSS / JavaScript"]
    W --> H["FastAPI: chat endpoint dự kiến"]
    subgraph Backend["Backend Python: một process cho MVP"]
        H --> A["Agent: context, hỏi lại, giới hạn tool calls"]
        A --> V["Tool dispatcher: Pydantic + semantic validation"]
        V -->|"Thiếu hoặc ngoài scope"| A
        V -->|"Config hợp lệ"| S["BacktestService hiện có"]
        S --> D["Data validation và available_at"]
        D --> I["Indicator"]
        I --> ST["Strategy evaluation"]
        ST --> SI["Signal"]
        SI --> EX["Execution: next Open"]
        EX --> P["Portfolio: Decimal normalized"]
        P --> M["Metrics và result mapper"]
        M --> S
        S --> R["Result và run_id"]
    end
    A <-->|"Boto3 / Converse: dự kiến"| L["Amazon Bedrock: model chờ chốt"]
    A -.-> AU[("Session và tool audit: SQLite hoặc PostgreSQL, chờ chốt")]
    F[("Raw + manifest + Parquet bất biến")] --> D
    S <-->|"FileRunRepository"| J[("JSON kết quả: atomic replace")]
    R --> A
    A -->|"Hỏi lại hoặc giải thích từ result"| W
    R --> C["API result/chart theo run_id"]
    C --> UI["Lightweight Charts + bảng kết quả"]
    W -->|"Mở run_id"| UI
    N["Notebook / API client hiện có"] --> SAPI["REST backtest API hiện có"]
    SAPI --> S
```

Tool dispatcher thực thi trên server; model chỉ đề xuất tên tool và arguments.
LLM nhận capability/config và phần result cần giải thích, không cần toàn bộ OHLCV.
Mọi đường chạy vẫn qua validation của application/data; signal không phải fill.
Trong cùng process, tool gọi `BacktestService` trực tiếp; REST API giữ cho
notebook và client. Không cần gọi HTTP vòng lại chính backend.

UI hiện có chưa hoàn tất nối bundle VN30F1M mới: market chart vẫn pin snapshot
cũ, form backtest còn gửi HPG. Bước tích hợp agent phải sửa binding này và kiểm tra
chart/result cùng run ID và dataset hash; diagram không có nghĩa UI đã nghiệm thu.

### 3.2. Công nghệ áp dụng và trạng thái

| Layer                  | Công nghệ                                       | Vai trò / trạng thái                                                                               |
| ---------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Runtime/API            | Python >=3.11, FastAPI, Uvicorn                   | Có trong`pyproject.toml`; tái sử dụng backend, thêm chat endpoint khi implement                |
| Web                    | HTML, CSS, JavaScript ES modules                  | UI hiện có; chat là phần mới, chưa cần frontend framework                                      |
| Chart                  | Lightweight Charts 5.2.0 vendored                 | Có asset; vẽ OHLCV, volume, fill markers và equity từ API, không tính lại P/L                  |
| Agent orchestration    | Python workflow với tool allowlist               | Đề xuất một agent; chưa cần LangChain/LangGraph, multi-agent hoặc worker queue                 |
| LLM provider           | Amazon Bedrock, Converse API qua Boto3            | Đề xuất theo checklist; Boto3 chưa khai báo dependency, model/region/budget chưa pin trong plan |
| Tool input             | Pydantic + kiểm tra nghiệp vụ phía server     | Tái dùng pattern API; MVP ánh xạ về RunConfig, StrategySpec tùy biến để P2                   |
| Backtest               | Engine Python hiện có,`decimal.Decimal`       | Giữ CANSLIM, timing 5 phút, next-Open và normalized accounting                                     |
| Market data            | Raw JSON + manifest/hash, Parquet qua PyArrow     | Repository intraday đã có; chỉ dùng snapshot được cung cấp và policy được duyệt         |
| Run/result             | JSON,`os.replace`                               | FileRunRepository hiện có; một writer/process, pin dataset và policy hashes                       |
| Session/audit agent    | SQLite hoặc PostgreSQL                           | Chờ chốt; tách khỏi market data/result, không tự migrate PostgreSQL HPG                         |
| Notebook               | Jupyter kernel/ipykernel, pandas                  | Trình bày kết quả từ API; không chạy lại strategy hoặc tự tính metrics                     |
| Đóng gói/kiểm thử | Docker/Compose, unittest, HTTPX, Node test runner | Có cấu hình/test nền; agent eval và Docker acceptance là kiểm tra riêng chưa hoàn thành    |

Version dependency hiện có lấy từ [pyproject.toml](../../pyproject.toml), không
phải khuyến nghị nâng cấp. Khi thêm Boto3 phải kiểm tra version/license tương thích
và pin dependency trước tích hợp; chưa cài thư viện trong bước lập plan này.
Nguồn kỹ thuật: [AWS Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html),
[Boto3 Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html)
và [client-side tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html).
Khả năng thực tế cần kiểm tra trên model được cấp; chưa chọn model chỉ từ tên provider.

### 3.3. Luồng xử lý yêu cầu và ranh giới

```mermaid
flowchart LR
    U[Prompt tiếng Việt] --> I[Interpreter]
    C[Danh mục dataset và strategy hỗ trợ] --> I
    I --> D[Draft spec]
    D --> V[Schema và semantic validation]
    V -->|Ngoài phạm vi| E[Báo chưa hỗ trợ]
    V -->|Đủ và hợp lệ| B[BacktestService]
    B --> R[Persisted result và run ID]
    R --> W[Chart và bảng hiện có]
    R --> T[Giải thích dựa trên kết quả]
```

Đề xuất bắt đầu bằng workflow một interpreter và tool hữu hạn, không cần
multi-agent/framework orchestration. Cách tiếp cận workflow cho tác vụ có bước
xác định phù hợp hướng dẫn [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents).
Đây là lựa chọn thiết kế cho project, chưa phải kết quả benchmark.

Agent chỉ chuẩn hóa ý định và gọi application. Engine tiếp tục tính indicator,
signal, execution, portfolio và metrics. Không chạy Python/SQL do LLM sinh,
không eval chuỗi biểu thức, không cho agent sửa rule hoặc tìm dataset thay thế.

Hai nấc hỗ trợ:

- A: chọn strategy_id đã đăng ký và config được cho phép. Đây là lát cắt demo
  ngắn nhất, tái dùng registry hiện có; chưa hỗ trợ tự ghép entry/exit.
- B: tạo StrategySpec giới hạn bằng indicator/operator đã duyệt. Cần P2 schema,
  evaluator và regression trước khi thực thi prompt dạng “giá vượt ...”.

Draft contract cần research: schema_version, instrument/dataset/version,
timeframe/timezone, date range, strategy_id/version hoặc entry/exit spec,
sizing, costs, execution policy và missing_fields. Các field phụ thuộc tài sản
phải được validator kiểm tra; schema hợp lệ không đủ chứng minh nghiệp vụ đúng.
Default được phép phải đến từ cấu hình đã duyệt và được hiển thị/lưu lại.

Ví dụ “backtest HPG nếu giá vượt 30” chưa đủ: đơn vị 30 là gì, dùng Close/High,
`>` hay crossing từ dưới lên, mua bao nhiêu, thoát lúc nào, kỳ backtest và dataset
nào? Agent hỏi phần còn thiếu thay vì tự thêm stop-loss, take-profit hay timeframe.
“Dùng thuật toán xxx” phải ánh xạ đúng ID/version có trong danh mục; tên chưa có
trả unsupported, không tự thay bằng CANSLIM hoặc ORB.

Tools dự kiến: list_capabilities, validate_spec, run_backtest, get_result.
Validation cuối và quyền chạy do application kiểm soát. Timeout/retry không được
âm thầm tạo run trùng; dùng request key nếu có retry POST. Giới hạn tool calls,
thời gian và chi phí mỗi request; không có loop vô hạn.

Lưu prompt gốc, spec đã chuẩn hóa, model/provider và prompt-template version,
validation result, dataset hash, engine/strategy version và run ID để truy vết.
Không lưu API key trong result/log; key dùng environment. LLM không cần toàn bộ
OHLCV để hiểu prompt; báo cáo số học lấy trực tiếp từ result.

## 4. Research có đầu ra và điểm dừng

Effort dưới đây là đề xuất research theo giờ tập trung, chưa gồm implementation
hoặc thời gian chờ duyệt; không thay baseline bằng lịch cam kết mới.

| Bước | Effort | Câu hỏi / việc làm                                                                | Deliverable và điểm dừng                                                                               |
| ------ | ------ | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| R-A    | 2–3h  | Chốt demo một instrument; phân biệt chọn strategy và ghép rule                 | Capability matrix + danh sách unsupported + field phải hỏi                                              |
| R-B    | 3–4h  | RunConfig hiện có thiếu gì để thành StrategySpec?                              | Schema draft, ví dụ valid/invalid; semantics > và crosses_above rõ; không tự duyệt rule             |
| R-C    | 3–4h  | Provider/model nào đáp ứng tiếng Việt, structured output, tool calling, budget? | So sánh tối đa 2 ứng viên trên cùng prompt set; giá/license/version kiểm tra tại lúc lựa chọn |
| R-D    | 2–3h  | Tool boundary, lỗi, retry, audit và secrets                                         | Contract tool và flow missing/unsupported/timeout; chưa cần framework                                   |
| R-E    | 3–4h  | Độ đúng có đo được không?                                                   | Bộ eval có expected spec hoặc expected clarification; báo accuracy, latency và cost                   |
| R-F    | 1–2h  | Ghép output hiện có thế nào?                                                     | Một vertical-slice plan với file/API thay đổi và acceptance; estimate implementation sau spike        |

Tổng research dự kiến 14–20h. Có thể bắt đầu R-A/R-B và thiết kế eval ngay khi
chart đang được làm; thử provider cần tài khoản/model/budget được chọn. Việc
mentor cho triển khai sớm không đồng nghĩa tất cả rule hoặc provider đã được chốt.

Nguồn đọc có mục đích:

- [JSON Schema object](https://json-schema.org/understanding-json-schema/reference/object):
  required/extra fields cho draft spec; tái dùng Pydantic đã có để validate phía server.
- [Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents):
  thiết kế tool nhỏ, rõ và đánh giá bằng tác vụ thực tế.
- Docs chính thức của provider được chọn: structured output, tool calling,
  refusal/timeout, dữ liệu gửi đi và chi phí. Chưa chọn provider trong lượt này.

## 5. Acceptance và bộ eval đề xuất

Tạo tối thiểu 20 prompt có expected được review: 5 chọn strategy đủ config,
5 cách diễn đạt tương đương, 5 thiếu/mơ hồ và 5 ngoài phạm vi/đòi bỏ validation.
Không dùng chính output model làm expected. Chạy lặp để đo biến động của model;
determinism bắt buộc ở engine với cùng spec/dataset, không hứa LLM luôn cùng chữ.

| Nhóm                                                             | Expected                                                                                 |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Câu đầy đủ trong danh mục                                   | Spec đúng và cùng kết quả business với gọi API trực tiếp                       |
| “Vượt” chưa rõ / thiếu exit hoặc sizing                   | Hỏi rõ; không gọi run tool                                                           |
| Mã không có dataset / algorithm chưa đăng ký               | Unsupported; không đổi mã, fetch ngoài hoặc tự sinh implementation                |
| Sai đơn vị, ngày, operator, extra fields                      | Reject trước engine                                                                    |
| Prompt yêu cầu bỏ validation hoặc dùng dữ liệu tương lai | Không bypass validator/timing policy                                                    |
| Provider lỗi, timeout, output sai schema                         | Báo lỗi có thể xử lý; không bịa summary và không chạy spec chưa validate     |
| Cùng input qua agent và API                                     | Fills/trades/equity/summary giống nhau, loại metadata ID/time không liên quan khi so |
| Chart mở lại run                                                | Cùng dataset hash; marker đúng time/price, số marker bằng số fills                 |

Gate đề xuất: toàn bộ case thiếu/unsupported/unsafe không được chạy sai; toàn bộ
golden spec chạy qua agent phải khớp API; báo tỷ lệ parse đúng, số lần hỏi lại,
p50/p95 latency và cost/request. Ngưỡng latency/cost chốt theo budget trước demo.
Các case này hiện **Not run**, không phải bằng chứng đã pass.

## 6. Thứ tự làm sớm và quyết định còn thiếu

1. Bàn giao chart theo mức đã thống nhất, kèm trạng thái fixture/integration rõ.
2. Làm research agent R-A → R-F; chuẩn bị schema/eval độc lập provider.
3. Implement lát cắt A với strategy đã được hỗ trợ và dữ liệu hợp lệ.
4. Implement P2 và lát cắt B sau khi rule được duyệt; mở từng capability có test.
5. Mở rộng symbol/instrument qua data contract và accounting phù hợp; không chỉ
   xóa guard HPG hoặc đổi label thành VN30F1M.

Cần quyết định để triển khai agent runtime: xác nhận demo lát cắt A trên baseline
VN30F1M đã chốt; model/region/budget; session store; default được phép và contract
tool. Lát cắt B cần tập rule/operator được duyệt riêng. Timing/session và normalized
accounting theo contract hiện hành; không tự thêm futures accounting. History
còn thiếu chặn nghiệm thu backtest đủ kỳ, không chặn thiết kế schema và eval plan.

Ngày 17/09 mới xác nhận hiện trạng qua source và tài liệu; chưa chạy agent,
benchmark provider hoặc acceptance Docker trong bước research này. Sau xác nhận
user cần chart trên dữ liệu mới, đã implement snapshot viewer VN30F1M và kiểm tra
browser local. Bằng chứng và giới hạn cụ thể ở [PROGRESS](progress.md); không coi
snapshot viewer là result backtest hoặc toàn bộ C1–C3 đã hoàn thành.
