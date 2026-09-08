# Kế hoạch backtest HPG

Cập nhật: **08/09/2026**. Bản chính về phase, mã công việc, thời gian và output: **[Backtesting_work_breakdown_plan.xlsx](Backtesting_work_breakdown_plan.xlsx)**, hai sheet `Tổng quan 4 phase` và `Kế hoạch chi tiết`.

## 1. Mục tiêu thực sự

- Hoàn thành một bài test thực tập: xây được luồng **HPG → chiến lược → giao dịch mô phỏng → P/L → lịch sử hiệu suất → web chart**, sau đó thêm **ngôn ngữ tự nhiên → StrategySpec → backtest**.
- Năng lực cần thể hiện qua sản phẩm:
  - Hiểu yêu cầu.
  - Chia việc vừa sức
  - Giải thích được quy tắc và con số
  - Kiểm tra trước khi báo hoàn thành
  - Kết nối agent vào một hệ thống có đầu vào/đầu ra rõ.
- **Đích cuối: Một demo đúng và giải thích được trong phạm vi đã chốt.**

## 2. Bốn phase theo Excel

| Phase                                | Thời gian        | Quỹ ngày làm việc | Đầu ra chính                                                                         |
| ------------------------------------ | ----------------- | --------------------: | --------------------------------------------------------------------------------------- |
| 1 — Nghiệp vụ & MVP backtest      | 08–15/09/2026    |                     6 | HPG + CANSLIM-lite v0 chạy từ dữ liệu tới giao dịch, P/L, equity; API tối thiểu |
| 2 — Tổng quát hóa backtest       | 16–21/09/2026    |                     4 | StrategySpec và backtest service dùng chung; ít nhất**2 chiến lược**       |
| 3 — Web chart & trực quan hóa     | 22–25/09/2026    |                     4 | Nến, volume, indicator, marker mua/bán, bảng giao dịch và hiệu suất từ API      |
| 4 — Agent & hoàn thiện end-to-end | 28/09–02/10/2026 |                     5 | Ngôn ngữ tự nhiên → spec hợp lệ → API → chart; test, tài liệu và final demo |

## 3. Đã biết, chưa biết và giả định

| Loại                            | Nội dung                                                                                                                                                                               |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Đã biết                       | HPG 2020–2023; CANSLIM-lite v0; API trước, chart sau, agent cuối; mốc MVP 15/09; lịch 4 phase trong Excel                                                                         |
| Dữ liệu                        | P1.2 chỉ kiểm tra định dạng, đơn vị, missing/duplicate và raw/adjusted khi nhận; không có đầu việc tìm nhà cung cấp hoặc crawl dữ liệu                             |
| Cần chốt ở P1.1/P1.3          | Điều kiện mua/bán CANSLIM-lite v0; vốn; sizing; phí/slippage; giá khớp; trạng thái cuối kỳ; khung nến                                                                      |
| Cần chốt trước P4            | Indicator/toán tử mà agent hỗ trợ; model/tài khoản được phép dùng; cách hỏi lại khi yêu cầu chưa rõ                                                                  |
| Giả định phạm vi đề xuất  | Nến ngày; một mã; mua rồi bán số đang giữ; không margin/bán khống; một vị thế tại một thời điểm                                                                     |
| Giả định khớp đề xuất     | Tính signal khi phiên đóng; mô phỏng khớp Open phiên đủ điều kiện tiếp theo; không lấy Close vừa tạo signal làm giá khớp                                           |
| Giả định báo cáo đề xuất | Không nạp/rút vốn giữa kỳ; giữ vị thế mở cuối kỳ và báo riêng lãi/lỗ tạm tính; không tự ép bán                                                                   |
| Giả định lịch                | Một thực tập sinh triển khai; mentor phản hồi các quyết định cần thiết kịp thời. Thời lượng trong Excel là ước lượng, không phải cam kết đã đủ nguồn lực |

CANSLIM-lite chưa được định nghĩa chỉ bằng tên. Cần ghi rõ phần nào của CAN SLIM gốc được giữ, phần nào chưa hỗ trợ. CAN SLIM có cả yếu tố lợi nhuận doanh nghiệp, cung–cầu, doanh nghiệp dẫn đầu, tổ chức và xu hướng thị trường; OHLCV một mã không đủ tái hiện toàn bộ phương pháp. [Nguồn William O’Neil/MarketSmith](https://www.williamoneilchina.com/can-slim-overview/?lang=en).

## 4. Các khái niệm cần học, đúng lúc cần dùng

| Khái niệm               | Hiểu đơn giản                                                                                                                           | Học để làm việc nào |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| OHLCV, nến               | Open, High, Low, Close và khối lượng trong một khoảng thời gian; thân nến nối Open–Close, bóng nến tới High–Low              | P1.2, P3.1                |
| Indicator                 | Con số tính từ dữ liệu; MA là trung bình, BB là vùng biến động, MACD dựa trên chênh lệch EMA, MFI kết hợp giá và volume | P1.3/P1.5, P2.2, P3.2     |
| Signal                    | Điều kiện chiến lược đã đúng, ví dụ điều kiện mua được thỏa                                                              | P1.1, P1.4/P1.5           |
| Order / executed trade    | Yêu cầu mua/bán / lần khớp mô phỏng; có signal chưa chắc đã khớp                                                               | P1.4/P1.6                 |
| Cash / position           | Tiền còn lại / số cổ phiếu đang giữ                                                                                                 | P1.6                      |
| Position sizing           | Mỗi lần mua bao nhiêu cổ phiếu hoặc dùng bao nhiêu vốn                                                                             | P1.1, P1.6, P2.3          |
| Fee / slippage            | Phí giao dịch / độ lệch giả định của giá khớp so với giá tham chiếu                                                           | P1.1, P1.6, P2.3          |
| Realized / unrealized P/L | Lãi/lỗ của phần đã bán / lãi/lỗ tạm tính của phần còn giữ                                                                    | P1.6, P3.3/P3.4           |
| Equity                    | Tổng giá trị tài khoản theo thời gian; mô hình đơn giản là tiền + giá trị cổ phiếu đang giữ                              | P1.6, P3.4                |
| Warm-up                   | Số nến lịch sử cần có trước khi indicator dùng được                                                                             | P1.5                      |
| Look-ahead                | Dùng thông tin tương lai để quyết định trong quá khứ, làm backtest sai                                                          | P1.4/P1.7                 |
| StrategySpec              | Bản mô tả chiến lược có cấu trúc: indicator, tham số, điều kiện mua/bán                                                       | P2.1, P4.2                |
| Validation                | Kiểm tra dữ liệu/quy tắc có hợp lệ và được hỗ trợ trước khi chạy                                                            | P2.1/P2.3, P4.3           |

Nguồn học tham khảo: [Fidelity Technical Indicator Guide](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/overview).

## 5. Hướng dẫn thực hiện

### Phase 1 — Nghiệp vụ & MVP backtest

Câu hỏi cần trả lời: **“Với rule đã chốt, tôi tính được giao dịch và tài khoản đúng chưa?”**

| Mã / lịch / effort theo Excel | Việc cần làm vừa đủ                                                                                       | Bằng chứng hoàn thành                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| P1.1 — 08/09 — 0,5 ngày      | Viết một bảng giả định: signal, lệnh, giá khớp, long-only, vốn, sizing, phí/slippage, cuối kỳ      | Giải thích được một ví dụ mua rồi bán; các default rõ ràng                         |
| P1.2 — 08/09 — 0,5 ngày      | Kiểm tra dữ liệu được cấp: cột, kiểu, thứ tự ngày, thiếu/trùng, đơn vị, raw/adjusted           | Data contract ngắn; biết dữ liệu nào dùng để tính signal và giá khớp                |
| P1.3 — 09/09 — 1 ngày        | Chốt CANSLIM-lite v0 thành bảng điều kiện mua/bán; xác định indicator/params cần dùng và phần bỏ | Rule table đủ rõ để người khác đọc cùng một dữ liệu sẽ quyết định giống bạn |
| P1.4 — 10/09 — 0,5 ngày      | Vẽ luồng signal → fill → cash/position → P/L/equity; định nghĩa field trả ra                           | Một ví dụ từ signal tới kết quả; tránh dùng thông tin tương lai                     |
| P1.5 — 10–11/09 — 1,5 ngày  | Tính indicator và tín hiệu của rule v0; xử lý giai đoạn chưa đủ nến                                | Chuỗi BUY/SELL có lý do; đối chiếu thủ công vài mốc                                   |
| P1.6 — 11–14/09 — 2 ngày    | Áp dụng sizing/phí/giá khớp; cập nhật tiền, vị thế, P/L, equity; không tự khớp mọi signal         | Danh sách lần khớp, bảng trade và lịch sử tài khoản kiểm tra được                  |
| P1.7 — 14–15/09 — 1 ngày    | API tối thiểu, request/response mẫu; chạy các test số học/thời gian trọng yếu                         | Có thể gọi API, xem các bảng và chạy lại ví dụ                                        |

Các field cốt lõi, không phải schema lớn bắt buộc:

- **Signal:** ngày, BUY/SELL, lý do.
- **Lần khớp:** ngày signal, ngày khớp, chiều mua/bán, giá, số lượng, phí; nếu không khớp thì có lý do.
- **Trade history:** ngày/giá vào và ra, số lượng, net P/L; phần chưa bán không coi là trade đóng.
- **Performance history:** ngày, cash, lượng đang giữ, equity; summary có P/L/return cơ bản.

Ví dụ kiểm tra **giả lập**, không phải biểu phí thật: vốn 10.000.000 đồng; mua 100 cổ phiếu giá 20.000, bán giá 22.000; phí mỗi bên 0,1%; không thuế và không slippage trong fixture này. Tiền mua gồm phí = 2.002.000; tiền bán sau phí = 2.197.800; **net P/L = 195.800; equity cuối = 10.195.800; return = 1,958%**. Nếu mô hình được chốt có thuế thì bổ sung test riêng, không bỏ thuế âm thầm trong kết quả thật.

Nếu chưa bán và Close cuối là 21.000: cash = 7.998.000; equity = 10.098.000; lãi tạm tính = 98.000 theo cách tính đã gồm phí mua, chưa giả định phí bán. Đây là lý do cần theo dõi vị thế mở, không chỉ cộng lãi/lỗ giao dịch đã đóng.

**Qua Phase 1 khi:** đúng rule v0 đã thống nhất; API trả đủ các bảng từ dữ liệu thật được cấp; fixture mua/bán và vị thế mở khớp số tính tay; mô hình và giới hạn được ghi rõ. Chưa cần web chart hoàn chỉnh.

### Phase 2 — Tổng quát hóa backtest

Câu hỏi cần trả lời: **“Thay chiến lược có phải sửa lại engine không?”**

| Mã / ngày / effort theo Excel | Việc cần làm vừa đủ                                                                             | Bằng chứng hoàn thành                                                    |
| ------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| P2.1 — 16/09 — 1 ngày        | Định nghĩa StrategySpec: indicator, params, entry, exit và validation                             | CANSLIM-lite v0 có thể biểu diễn bằng spec; không cần DSL phức tạp  |
| P2.2 — 17/09 — 1 ngày        | Tách indicator và phép điều kiện thành module dùng lại                                       | Danh mục hỗ trợ ngắn; nhiều strategy gọi cùng interface               |
| P2.3 — 18/09 — 1 ngày        | API nhận date range, strategy params, fee/slippage, sizing; chuẩn hóa response                     | Default/đơn vị/range rõ; input sai trả lỗi rõ                         |
| P2.4 — 21/09 — 1 ngày        | Chạy CANSLIM-lite và một strategy đơn giản khác; chạy lại v0 để kiểm tra không bị hỏng | Ít nhất 2 strategy mà không sửa core; sample result và regression test |

Chiến lược thứ hai đề xuất: MA crossover để dễ kiểm tra.

**Qua Phase 2 khi:** đổi strategy/params được qua cùng API; kết quả v0 không đổi khi chỉ tách cấu trúc; unsupported indicator/operator trả lỗi.

### Phase 3 — Web chart & trực quan hóa

Câu hỏi cần trả lời: **“Người xem có hiểu kết quả và đối chiếu giao dịch trên chart được không?”**

| Mã / ngày / effort theo Excel | Việc cần làm vừa đủ                                                            | Bằng chứng hoàn thành                                                           |
| ------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| P3.1 — 22/09 — 1 ngày        | Vẽ nến OHLCV và volume, zoom/scroll cơ bản                                      | Ngày và giá trên chart khớp dữ liệu API                                      |
| P3.2 — 23/09 — 1 ngày        | MA/BB trên chart; MACD/MFI ở panel phù hợp                                       | Giá trị khớp backend; không tự tính lại bằng công thức khác ở frontend  |
| P3.3 — 24/09 — 1 ngày        | Marker mua/bán từ lần **đã khớp**, bảng entry/exit/quantity/P&L/return | Marker đúng ngày và giá; bảng và chart cùng kết quả                       |
| P3.4 — 25/09 — 1 ngày        | Equity/performance và summary; kết nối API đầu-cuối                            | Một lần chạy trả các phần đồng bộ; có trạng thái lỗi/không giao dịch |

**Qua Phase 3 khi:** gọi API rồi xem được toàn bộ kết quả trên web. Giữ UI đơn giản; chưa cần tài khoản người dùng, realtime, dashboard phức tạp hoặc nhiều mã.

### Phase 4 — Agent & hoàn thiện end-to-end

Câu hỏi cần trả lời: **“Agent có chuyển đúng ý người dùng thành một yêu cầu mà engine chạy được không?”**

| Mã / lịch / effort theo Excel | Việc cần làm vừa đủ                                         | Bằng chứng hoàn thành                                                               |
| ------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| P4.1 — 28/09 — 0,5 ngày      | Ghi rõ indicator/toán tử/pattern entry-exit mà agent hỗ trợ | Danh mục hữu hạn; có ví dụ được và chưa được hỗ trợ                     |
| P4.2 — 28–29/09 — 1,5 ngày  | Chuyển câu tiếng Việt thành StrategySpec đã có ở P2      | Một số cách diễn đạt tương đương ra cùng ý nghĩa; không sinh code tự do |
| P4.3 — 30/09 — 1 ngày        | Kiểm tra field/operator/indicator/params và dữ liệu cần      | Input sai báo rõ; câu mơ hồ như “giá tốt” phải hỏi làm rõ                 |
| P4.4 — 01/10 — 1 ngày        | Nối agent → backtest API → kết quả → web chart              | Cùng spec qua agent và gọi API trực tiếp cho cùng kết quả                       |
| P4.5 — 02/10 — 1 ngày        | Chạy test chính, chuẩn bị demo và hướng dẫn               | Final demo lặp lại được; có cách chạy/dùng và giới hạn hỗ trợ             |

**Qua Phase 4 khi:** người dùng nhập mô tả thuộc phạm vi hỗ trợ, xem spec hợp lệ và nhận đúng bảng/chart; yêu cầu không rõ hoặc ngoài phạm vi được xử lý rõ ràng; có test và tài liệu. “Bất kỳ chiến lược nào” là hướng mở rộng, không tự nhận demo đã hỗ trợ mọi chiến lược.

## 6. Research vừa đủ, gắn với đầu việc

| WBS        | Cần tìm hiểu / keyword                                                                      | Loại nguồn nên tìm                                          | Dừng khi                                                                             |
| ---------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| P1.1/P1.4  | `signal order fill backtest`, `position sizing fee slippage`, `next bar open look ahead` | Tài liệu engine chính thức; giáo dục CTCK                 | Giải thích được thời điểm signal, khớp và tiền thay đổi                  |
| P1.2       | `OHLCV raw adjusted price data dictionary`                                                   | Người cấp dữ liệu và metadata đi kèm                    | Biết đơn vị, cột và cách hiểu giá; không nghiên cứu nguồn dữ liệu mới |
| P1.3/P1.5  | `William O'Neil CAN SLIM`, tên indicator thực sự dùng, `indicator warm up`             | Nguồn William O’Neil/MarketSmith; rule mentor; docs indicator | Rule table có công thức/ngưỡng và ví dụ                                       |
| P1.6/P1.7  | `realized unrealized pnl equity`, `backtest accounting commission`                         | Docs engine và ví dụ tính tay độc lập                    | Tự đối chiếu được cash, quantity, P/L, equity                                  |
| P2.1–P2.4 | `strategy configuration schema`, `indicator registry`, `API request validation`          | Docs thư viện/framework đã chọn                            | Hai strategy chạy cùng core, tham số sai được bắt                              |
| P3.1–P3.4 | `Lightweight Charts candlestick markers panes`                                               | TradingView docs/repo chính thức                              | Nến/indicator/marker lấy cùng output backend                                       |
| P4.1–P4.3 | `structured output JSON Schema`, `semantic validation`, `ambiguous user request`         | Docs model/framework được đơn vị chọn                    | Spec đúng; biết khi nào hỏi lại hoặc báo chưa hỗ trợ                       |

Nguồn khởi đầu: [Backtrader — order execution](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/), [MarketSmith — CAN SLIM](https://www.williamoneilchina.com/can-slim-overview/?lang=en), [Fidelity — indicators](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/overview), [Lightweight Charts — repo chính thức](https://github.com/tradingview/lightweight-charts).

## 7. Acceptance và test cases tối thiểu

Đây là bộ test đề xuất cho từng phần, không phải test đã chạy. Mỗi case chỉ cần đầu vào ngắn, expected result rõ và bằng chứng thực tế.

| Case | WBS        | Tình huống                                                       | Kết quả cần thấy                                                                       |
| ---- | ---------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| T1   | P1.2       | Trùng ngày, OHLC sai, thiếu cột                                | Báo dữ liệu không hợp lệ; không chạy im lặng                                      |
| T2   | P1.5       | Chưa đủ nến cho indicator                                      | Chưa sinh signal từ indicator chưa hợp lệ; không lấy dữ liệu tương lai bù vào |
| T3   | P1.4/P1.7  | Signal sau Close; phiên kế tiếp nghỉ                           | Không khớp cùng Close hoặc ngày nghỉ; dùng phiên hợp lệ kế tiếp theo profile   |
| T4   | P1.6/P1.7  | Mua rồi bán với ví dụ phí ở mục 5                          | P/L 195.800 và equity 10.195.800 trong đúng fixture không thuế/slippage đó          |
| T5   | P1.6/P1.7  | Vị thế còn mở cuối kỳ                                        | Có quantity/equity/unrealized; không tự ép bán hoặc bỏ phần đang giữ             |
| T6   | P1.6/P1.7  | Không có signal, thiếu tiền, signal ở nến cuối              | Không tạo fill giả; tiền/vị thế hợp lý; lý do không khớp rõ                    |
| T7   | P1.7/P2.4  | Cùng input chạy lại; chỉ sửa dữ liệu sau ngày t            | Kết quả lặp lại; phần trước/đến t không thay vì dữ liệu tương lai           |
| T8   | P2.4       | Đổi giữa 2 strategy và đổi params                            | Không sửa core; v0 không thay kết quả do refactor; input sai báo rõ                 |
| T9   | P3.2–P3.4 | So một nến, indicator, fill và dòng history                    | Cùng ngày/giá/số liệu với backend; marker dùng lần đã khớp                      |
| T10  | P4.2/P4.4  | Câu rõ tạo cùng spec với API trực tiếp                      | Kết quả backtest giống nhau; số agent trình bày lấy từ engine                      |
| T11  | P4.3       | “Mua khi giá tốt”; indicator ngoài phạm vi; thiếu dữ liệu | Hỏi rõ hoặc báo chưa hỗ trợ; không âm thầm chạy rule khác                      |
| T12  | P4.5       | Người khác làm theo hướng dẫn demo                          | Chạy được luồng cuối, hiểu ví dụ và giới hạn                                   |

Khi rule cần dữ liệu BCTC, thêm case chỉ dùng sau thời điểm công bố. Khi mô hình có xử lý quyền, thêm case không tạo lãi/lỗ giả hoặc cộng quyền hai lần. Đây là test phụ thuộc mô hình được chọn, không yêu cầu bạn xây toàn bộ cơ chế thị trường ngay lập tức.

## 8. Các yêu cầu khác được xác định

**Yêu cầu xuyên suốt: cập nhật GitHub, Zalo tóm tắt tiến độ và document mỗi 2 ngày**
