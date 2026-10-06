# CANSLIM v1 — Execution và accounting hợp đồng

Cập nhật: 28/09/2026. U04 đã có sổ tiền hợp đồng, khớp long/short, đóng một
phần và stop/target/trailing, được kiểm thử riêng và qua vòng lặp engine.
U05/U06 đã ánh xạ lịch phiên và lưu/đọc kết quả hợp đồng. U08 (29/09) đã nối
cây quy tắc, sizing tại Open, giới hạn ngày và giờ thoát; kiểm thử bằng dữ liệu
tổng hợp. Xem [phạm vi thực thi JSON](backtest-api-specification.md).
Chỉ áp dụng profile v1; normalized accounting v0 giữ nguyên.
Các mục trống chưa được dùng làm default. Xem
[rule v1](../strategies/canslim-v1-rules.md) và
[data contract v1](../data/vn30f1m/data-contract-v1.md).

## 1. Execution — R06

- Entry/time-stop/forced exit: quyết định sau Close t → market fill Open
  hợp lệ kế tiếp. Đây là convention mô phỏng đã chốt, không phải fill cùng Close.
- Stop/TP/trailing đã active trước nến: kiểm tra Open rồi High/Low theo rule.
- Long stop: Open ≤ stop → Open; nếu không, Low ≤ stop → stop.
- Short stop: Open ≥ stop → Open; nếu không, High ≥ stop → stop.
- Gap xuyên target: fill target, không dùng Open tốt hơn.
- Stop và target cùng bị chạm trong nến: stop ưu tiên.
- Không partial fill; có partial exit theo quantity nguyên.
- Slippage 0; giá fill/order level phải phù hợp tick mô phỏng 0,1.

### Chi tiết execution chưa chốt

- Làm tròn stop/target theo tick và theo hướng: long stop làm tròn xuống, short stop lên; long target lên, short target xuống theo tick 0,1.
- Stop/TP mới tạo sau fill Open được kiểm tra trong chính nến entry: có; active ngay sau Open fill và được xét High/Low của nến đó; nếu cùng chạm thì stop ưu tiên.
- Thứ tự pending exit, margin exit, forced exit và intrabar orders: Open xử lý pending market exit trước; nếu còn vị thế mới xét stop/trailing/TP; tại Close mới xét margin, time-stop và forced exit để tạo lệnh cho Open kế tiếp.
- TP1/TP2 cùng chạm và quantity còn lại: thực hiện TP1 trước rồi TP2 trong cùng nến; mỗi mức dùng quantity nguyên đã định, TP2 đóng phần còn lại.
- Cancel/replace pending sau partial/full exit: partial hủy TP đã khớp và cập nhật stop/trailing cho quantity còn lại; full exit hủy toàn bộ lệnh/pending của position.
- Thời điểm kiểm tra margin và dữ liệu mark được phép dùng: sau mỗi Close 5 phút bằng Close vừa hoàn tất; sau fill chỉ kiểm tra đủ ký quỹ cho entry, không dùng High/Low tương lai.

## 2. Ledger và P/L — R08

```text
notional = price * 100000 * quantity
required_margin = notional * im_rate

unrealized_long  = (mark - entry_fill) * 100000 * open_quantity
unrealized_short = (entry_fill - mark) * 100000 * open_quantity

equity = cash + unrealized_pnl
available_cash = equity - required_margin - accrued_costs
```

- Mở hợp đồng không trừ toàn bộ notional như BUY normalized v0.
- Partial exit ghi realized P/L cho quantity đã đóng, giải phóng margin
  tương ứng; phần còn lại tiếp tục unrealized.
- Cash, fees, accrued costs và realized phải reconcile, không trừ cùng chi phí hai lần.

### Quy ước ledger còn trống

- Cash được cập nhật tại entry/partial/full exit: entry chỉ trừ thuế/phí mở; không trừ notional hay margin. Partial/full exit cộng P/L đã chốt rồi trừ thuế/phí thoát.
- Phân bổ entry costs khi partial exit: phân bổ theo tỷ lệ quantity đóng/quantity ban đầu, HALF_UP đến 1 VND và không vượt chi phí mở còn chưa phân bổ; lần đóng cuối nhận toàn bộ phần còn lại.
- Realized P/L net/gross và cách trình bày fees: `gross = hướng × (exit-entry) × 100000 × qty`; `net = gross - entry_cost_allocated - exit_cost`; thuế và từng loại phí hiển thị riêng.
- required_margin dùng entry price hay current mark: tại entry dùng fill price; sau mỗi Close dùng Close hiện tại, cuối ngày nếu có vị thế thì dùng DSP.
- accrued_costs gồm khoản nào, thu/trừ khi nào: v1 ghi thuế/phí ngay tại fill nên mặc định 0 sau khi hạch toán; không mô phỏng phí quản lý tài sản ký quỹ theo tháng.
- Precision/rounding tiền VND và residual khi partial: tính bằng Decimal; giá 0,1 điểm, tiền làm tròn HALF_UP đến 1 VND theo từng event; residual dồn lần đóng cuối.
- Settlement và nguồn giá/thời điểm available: v1 phải flat cuối ngày nên không hạch toán settlement qua đêm; nếu mở rộng, chỉ dùng DSP/FSP do VSDC công bố sau khi available.
- Equity reconciliation examples: mỗi fill phải thỏa `equity_after = cash_after + unrealized_after`; full exit phải có `unrealized=0` và chênh cash bằng tổng realized net.

## 3. Margin

Quyết định cập nhật: dùng tỷ lệ ký quỹ cố định 17% cho toàn kỳ backtest v1,
`im_rate = 0.17`. Đây là cấu hình mô phỏng đã chọn, không tuyên bố tỷ lệ
thực tế của mọi ngày lịch sử. Không yêu cầu schedule ký quỹ theo ngày.

- Entry yêu cầu equity ≥ required_margin × 1,10.
- Khi đang giữ mà equity < required_margin: `MARGIN_BREACH`, force close
  Open hợp lệ kế tiếp. Đây là policy simulator, không gọi là maintenance rate
  của cơ quan quản lý.

### Cấu hình áp dụng

- API truyền `accounting.margin_rate: "0.17"`; lưu tỷ lệ đã dùng cùng kết quả.
- Kiểm tra entry sau khi tính phí mở lệnh: trước khi ghi fill, yêu cầu `equity_after_open_cost >= required_margin × 1,10`; không đủ thì reject entry.
- Margin breach khi không có next Open trong phiên: không giữ qua đêm; nếu không còn Open hợp lệ để force close thì `INVALID` thay vì tự tạo giá.
- Margin breach intrabar hay chỉ tại Close: v1 chỉ kiểm tra tại Close mỗi nến 5 phút; không mô phỏng liquidation giữa nến.

## 4. Thuế và phí

Đầu vào API mới gom thông số vào `accounting`: `contract_multiplier`,
`margin_rate`, `pit_rate`, `exchange_fee_per_contract`,
`clearing_fee_per_contract`, `broker_fee_per_contract`. `initial_cash` vẫn
ở ngoài. Chỉ contract_multiplier tùy chọn, mặc định `"100000"`; các khoản
còn lại truyền rõ theo [hướng dẫn payload](strategy-payload-guide.md).
Đây là thay đổi cách truyền cấu hình, không thay công thức thuế/phí bên dưới.

Chốt tách thuế, phí sàn/bù trừ và phí broker; không đổi nghĩa `fee_rate`
của v0 hoặc tính tất cả như một tỷ lệ trên notional.

File quyết định có các đề xuất PIT 0.001, phí sàn 2.700 và bù trừ 2.550
VND/hợp đồng/lượt, công thức tax base theo settlement price và margin.
Những mức/công thức pháp lý này chưa được xác minh cho kỳ 25/03–15/09/2026;
không đưa thành default được áp dụng trong đặc tả này. Tài liệu nguồn nêu
nhiều ngày hiệu lực khác nhau; cần phân kỳ hoặc chốt assumption mô phỏng rõ.

- PIT rate và effective dates: 0,1% mỗi lần chuyển nhượng; 25/03–30/06 theo hướng dẫn cũ, từ 01/07/2026 theo Thông tư 87/2026/TT-BTC; công thức không đổi.
- Tax base/công thức/nguồn giá: `tax_base = fill_price × 100000 × qty × im_rate / 2`; đáo hạn dùng FSP. `PIT = tax_base × 0,001`.
- Taxable events và thời điểm ghi nhận: ghi tại mỗi fill mua/bán; nếu còn vị thế đến đáo hạn thì ghi thêm tại settlement. v1 flat ngày nên không phát sinh thuế đáo hạn.
- Exchange fee/effective dates: HNX 2.700 VND/hợp đồng khớp/lượt; Quyết định 1541/QĐ-BTC hiệu lực 29/04/2025, áp dụng toàn kỳ report.
- Clearing fee/effective dates: VSDC 2.550 VND/hợp đồng thế vị/lượt; áp dụng cơ chế sau KRX trong toàn kỳ report.
- Broker fee: cấu hình riêng theo công ty/gói tài khoản; 0 chỉ khi user chọn rõ `BROKER_FEE_ASSUMPTION=0`.
- Thuế/phí trước và sau mốc thay đổi trong report: 0,1% giữ nguyên; chỉ đổi căn cứ pháp lý từ 01/07/2026. Phí HNX/VSDC giữ nguyên trong 25/03–15/09/2026.
- Nguồn kiểm chứng hoặc assumption được chọn: HNX/VSDC, Quyết định 1541/QĐ-BTC, Công văn 11133/BTC-CST/2017 và Thông tư 87/2026/TT-BTC; broker fee là config.
- Cách tính estimated_roundtrip_cost cho sizing: mỗi hợp đồng = phí+thuế entry tại entry price + phí+thuế exit ước tại stop price; cộng broker fee hai lượt.

## 5. Result và audit v1

Kết quả phải lưu profile/strategy version, resolved config, input/policy hashes,
units và assumptions. Phân biệt signal/order/fill; hiển thị realized/unrealized
riêng. Partial exit giữ liên kết entry và quantity còn lại.

- Schema position/order/fill/trade cho long/short/partial: lưu `position_id`, mã HĐ, side, entry, initial/open qty, stop/TP/trail; order/fill liên kết bằng id; trade giữ từng exit leg và realized P/L.
- Fee/tax breakdown và margin history: mỗi fill lưu `exchange_fee`, `clearing_fee`, `broker_fee`, `pit`; mỗi Close lưu mark, im_rate, required_margin, equity, available_cash và breach flag.
- Thứ tự ưu tiên lý do khi nhiều điều kiện thoát cùng xuất hiện: theo thời điểm sự kiện; nếu cùng thời điểm thì `MARGIN_BREACH > FORCED_EXIT > STOP_LOSS > TRAILING_STOP > TIME_STOP > TP1 > TP2`. Khi cùng nến chạm hai mức chốt lời, xử lý TP1 trước rồi TP2 cho phần còn lại, kể cả khi hai mức bằng giá. Chốt lời trong nến được xử lý trước giới hạn thời gian xét tại Close, theo quy tắc v1.
- Compatibility API/result v0: giữ nguyên schema/ý nghĩa v0; v1 có `accounting_profile=contract_v1` và field mới chỉ xuất khi chạy v1.

## 6. Evidence

- Accounting cases: test long/short, partial, gap stop, TP1+TP2 cùng nến, reject margin, margin breach và full exit reconcile.
- Timing/no-lookahead/determinism: test signal Close→next Open, stop active từ đúng thời điểm, chỉ báo chỉ dùng VNINDEX đã khả dụng và cùng input/hash phải ra cùng kết quả.
- API/storage/reload: serialize toàn bộ config/policy/hash; reload phải khôi phục đúng position, ledger, fee/tax và margin snapshots.

### Kết quả U04

`tests/test_contract_execution.py` kiểm tra tiền, phí, ký quỹ sau phí,
long/short, đóng từng phần, gap, stop trước TP, hai TP cùng nến, trailing,
lệnh đóng tại Open trước stop/TP và kết quả khi cắt chuỗi.
Mốc v0 ở `tests/test_v0_baseline_snapshot.py` giữ nguyên.
U06 đã kiểm thử lưu/đọc kết quả hợp đồng, liên kết từng exit leg bằng ID riêng,
hash input/policy/result, phí/thuế và lịch sử ký quỹ; chưa nghiệm thu dữ liệu thật.

OHLC không cho biết giây chạm mức giá trong nến. Thành phần U04 ghi `fill_date`
bằng Open khi gap, bằng Close của nến khi chạm trong nến; giá vẫn là mức đã
đặt trước. Đây là mốc ghi nhận mô phỏng, không khẳng định thời gian giao dịch thật.
U06 phải giữ rõ ý nghĩa này khi ánh xạ ra API/biểu đồ.
