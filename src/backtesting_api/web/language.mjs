// Presentation labels only; form values and persisted JSON stay untouched.
const labels = [
    ['Ngôn ngữ', 'Ngôn ngữ', 'Language'],
    ['☰ Mục lục', '☰ Mục lục', '☰ Contents'],
    ['Mục lục trang', 'Mục lục trang', 'Page contents'],
    ['Nhập liệu', 'Nhập liệu', 'Inputs'],
    ['Tải JSON / điền mẫu', 'Tải JSON / điền mẫu', 'Upload JSON / load example'],
    ['Tham số lần chạy', 'Tham số lần chạy', 'Run settings'],
    ['Dữ liệu giao dịch', 'Dữ liệu giao dịch', 'Trading data'],
    ['Dữ liệu thị trường', 'Dữ liệu thị trường', 'Market data'],
    ['Tiền và khối lượng', 'Tiền và khối lượng', 'Accounting and sizing'],
    ['Tính tiền và khối lượng', 'Tính tiền và khối lượng', 'Accounting and sizing'],
    ['Chỉ báo', 'Chỉ báo', 'Indicators'],
    ['Điều kiện chiến lược', 'Điều kiện chiến lược', 'Strategy rules'],
    ['Kiểm tra / chạy', 'Kiểm tra / chạy', 'Validate / run'],
    ['Tìm lịch sử', 'Tìm lịch sử', 'Search history'],
    ['Kết quả', 'Kết quả', 'Results'],
    ['Summary', 'Tổng quan', 'Summary'], ['Charts', 'Biểu đồ', 'Charts'],
    ['Fills', 'Lệnh đã khớp', 'Fills'], ['Closed Trades', 'Giao dịch đã đóng', 'Closed trades'],
    ['Open Position', 'Vị thế đang mở', 'Open position'],
    ['Signal / Orders', 'Tín hiệu / Lệnh', 'Signals / orders'],
    ['Signals / Orders', 'Tín hiệu / Lệnh', 'Signals / orders'],
    ['Equity History', 'Lịch sử vốn', 'Equity history'], ['Equity', 'Vốn tài khoản', 'Equity'],
    ['Tải payload JSON để tự điền form', 'Tải JSON để tự điền biểu mẫu', 'Upload request JSON to fill the form'],
    ['Điền mẫu', 'Điền mẫu', 'Load example'],
    ['Chọn mẫu hoặc tải payload JSON, sau đó chỉnh tham số và chọn tự lấy hoặc nạp dữ liệu.', 'Chọn mẫu hoặc tải JSON, sau đó chỉnh tham số và chọn tự lấy hoặc nạp dữ liệu.', 'Load an example or upload request JSON, then edit settings and choose automatic or manual data.'],
    ['Lấy dữ liệu tự động (VN30F1M và VNINDEX, 5 phút)', 'Lấy dữ liệu tự động (VN30F1M và VNINDEX, 5 phút)', 'Fetch data automatically (VN30F1M and VNINDEX, 5 minutes)'],
    ['Nếu nhập kỳ báo cáo, máy chủ chỉ lấy thêm số nến cần để khởi tạo chỉ báo trước ngày bắt đầu và tải đến hết ngày kết thúc. Nếu bỏ kỳ báo cáo, máy chủ lấy sáu tháng gần nhất đến hiện tại. Không cần nạp dữ liệu thủ công.', 'Nếu nhập kỳ báo cáo, máy chủ chỉ lấy thêm số nến cần để khởi tạo chỉ báo trước ngày bắt đầu và tải đến hết ngày kết thúc. Nếu bỏ kỳ báo cáo, máy chủ lấy sáu tháng gần nhất đến hiện tại. Không cần nạp dữ liệu thủ công.', 'With a report period, the server fetches only the required indicator warm-up bars before its start, through its end date. Without one, it fetches the latest six months through now. No manual data upload is required.'],
    ['Tải JSON dữ liệu giao dịch', 'Tải JSON dữ liệu giao dịch', 'Upload trading data JSON'],
    ['Tải JSON dữ liệu thị trường', 'Tải JSON dữ liệu thị trường', 'Upload market data JSON'],
    ['Nạp VN30F1M có sẵn', 'Nạp VN30F1M có sẵn', 'Load available VN30F1M'],
    ['Nạp VNINDEX có sẵn', 'Nạp VNINDEX có sẵn', 'Load available VNINDEX'],
    ['Bỏ dữ liệu giao dịch', 'Bỏ dữ liệu giao dịch', 'Clear trading data'],
    ['Bỏ dữ liệu thị trường', 'Bỏ dữ liệu thị trường', 'Clear market data'],
    ['Thông tin nguồn giao dịch', 'Thông tin nguồn giao dịch', 'Trading source settings'],
    ['Thông tin nguồn thị trường', 'Thông tin nguồn thị trường', 'Market source settings'],
    ['Thêm chỉ báo', 'Thêm chỉ báo', 'Add indicator'], ['Xóa chỉ báo', 'Xóa chỉ báo', 'Remove indicator'],
    ['Điều kiện chiến lược — JSON', 'Điều kiện chiến lược — JSON', 'Strategy rules — JSON'],
    ['Chỉ chứa điều kiện vào/ra lệnh và giới hạn trong ngày. Dữ liệu nến được nạp riêng ở trên.', 'Chỉ chứa điều kiện vào/ra lệnh và giới hạn trong ngày. Dữ liệu nến được nạp riêng ở trên.', 'Entry/exit rules and daily limits only. Load candle data separately above.'],
    ['Kiểm tra payload', 'Kiểm tra đầu vào', 'Validate inputs'], ['Chạy backtest', 'Chạy kiểm thử', 'Run backtest'],
    ['Sẵn sàng.', 'Sẵn sàng.', 'Ready.'], ['Thử tải lại run và chart', 'Thử tải lại kết quả và biểu đồ', 'Retry result and chart'],
    ['Giá giao dịch và lệnh đã khớp', 'Giá giao dịch và lệnh đã khớp', 'Trading prices and fills'],
    ['Vừa khung', 'Vừa khung', 'Fit chart'],
    ['Rê chuột để xem chi tiết; bấm mũi tên BUY/SELL để lọc các bảng và bấm vùng trống để bỏ lọc.', 'Rê chuột để xem chi tiết; bấm mũi tên mua/bán để lọc các bảng và bấm vùng trống để bỏ lọc.', 'Hover for details; click a BUY/SELL arrow to filter tables, or an empty area to clear the filter.'],
    ['Giá, khối lượng và lệnh đã khớp', 'Giá, khối lượng và lệnh đã khớp', 'Prices, volume and fills'],
    ['Dữ liệu thị trường và chỉ báo', 'Dữ liệu thị trường và chỉ báo', 'Market data and indicators'],
    ['Equity từ kết quả backtest', 'Vốn tài khoản từ kết quả kiểm thử', 'Equity from backtest results'],
    ['Run và dataset của chart', 'Lần chạy và bộ dữ liệu của biểu đồ', 'Chart run and dataset'],
    ['Charts by', 'Biểu đồ sử dụng', 'Charts by'], ['Thu gọn', 'Thu gọn', 'Collapse'], ['Mở rộng', 'Mở rộng', 'Expand'],
    ['Lịch sử chạy', 'Lịch sử chạy', 'Run history'],
    ['Tỷ suất sinh lời từ (%)', 'Tỷ suất sinh lời từ (%)', 'Minimum return (%)'],
    ['Tỷ suất sinh lời đến (%)', 'Tỷ suất sinh lời đến (%)', 'Maximum return (%)'],
    ['Vốn cuối kỳ từ', 'Vốn cuối kỳ từ', 'Minimum final equity'], ['Vốn cuối kỳ đến', 'Vốn cuối kỳ đến', 'Maximum final equity'],
    ['Ví dụ: 0', 'Ví dụ: 0', 'Example: 0'], ['Ví dụ: 20', 'Ví dụ: 20', 'Example: 20'],
    ['Trang tiếp', 'Trang tiếp', 'Next page'], ['Xem', 'Xem', 'View'],
    ['Không có dữ liệu.', 'Không có dữ liệu.', 'No data.'], ['Chưa nạp dữ liệu.', 'Chưa nạp dữ liệu.', 'No data loaded.'],
    ['Đang tải…', 'Đang tải…', 'Loading…'], ['Đang tải chart…', 'Đang tải biểu đồ…', 'Loading chart…'],
    ['Đang tìm lịch sử…', 'Đang tìm lịch sử…', 'Searching history…'], ['Không có kết quả phù hợp.', 'Không có kết quả phù hợp.', 'No matching results.'],
    ['Đã tải kết quả và trade history; chart chưa tải được.', 'Đã tải kết quả và lịch sử giao dịch; chưa tải được biểu đồ.', 'Results and trade history loaded; chart unavailable.'],
    ['Đã lưu lần chạy mới. Bấm Tìm lịch sử để cập nhật danh sách.', 'Đã lưu lần chạy mới. Bấm Tìm lịch sử để cập nhật danh sách.', 'Run saved. Select Search history to update the list.'],
    ['Giá trị đến phải lớn hơn hoặc bằng giá trị từ.', 'Giá trị đến phải lớn hơn hoặc bằng giá trị từ.', 'Maximum must be greater than or equal to minimum.'],
    ['Chuyển giao diện', 'Chuyển giao diện', 'Toggle theme'],
    ['Chuyển sang giao diện sáng', 'Chuyển sang giao diện sáng', 'Switch to light mode'],
    ['Chuyển sang giao diện tối', 'Chuyển sang giao diện tối', 'Switch to dark mode'],
    ['Vốn ban đầu', 'Vốn ban đầu', 'Initial capital'], ['Ngày bắt đầu báo cáo', 'Ngày bắt đầu báo cáo', 'Report start date'],
    ['Ngày kết thúc báo cáo', 'Ngày kết thúc báo cáo', 'Report end date'], ['Số nến khởi tạo chỉ báo', 'Số nến khởi tạo chỉ báo', 'Indicator warm-up bars'],
    ['Chế độ khớp theo phiên', 'Chế độ khớp theo phiên', 'Session matching model'],
    ['Thời điểm khớp lệnh', 'Thời điểm khớp lệnh', 'Fill timing'],
    ['Giới hạn khớp mỗi đợt đấu giá', 'Giới hạn khớp mỗi đợt đấu giá', 'Auction fill limit'],
    ['Theo phiên HNX: ATO, LO và ATC', 'Theo phiên HNX: ATO, LO và ATC', 'HNX sessions: ATO, LO and ATC'],
    ['ATO lúc 09:00', 'ATO lúc 09:00', 'ATO at 09:00'], ['Lệnh giới hạn (LO)', 'Lệnh giới hạn (LO)', 'Limit order (LO)'],
    ['Tỷ lệ trượt giá', 'Tỷ lệ trượt giá', 'Slippage rate'],
    ['Tỷ lệ phí', 'Tỷ lệ phí', 'Fee rate'], ['Hệ số nhân hợp đồng', 'Hệ số nhân hợp đồng', 'Contract multiplier'],
    ['Tỷ lệ ký quỹ', 'Tỷ lệ ký quỹ', 'Margin rate'], ['Tỷ lệ thuế', 'Tỷ lệ thuế', 'Tax rate'],
    ['Phí sở / hợp đồng', 'Phí sở / hợp đồng', 'Exchange fee / contract'],
    ['Phí bù trừ / hợp đồng', 'Phí bù trừ / hợp đồng', 'Clearing fee / contract'],
    ['Phí môi giới / hợp đồng', 'Phí môi giới / hợp đồng', 'Broker fee / contract'],
    ['Tỷ lệ vốn chịu rủi ro', 'Tỷ lệ vốn chịu rủi ro', 'Capital at risk'], ['Tỷ lệ dừng lỗ', 'Tỷ lệ dừng lỗ', 'Stop-loss fraction'],
    ['Khoảng dừng lỗ', 'Khoảng dừng lỗ', 'Stop distance'], ['Hệ số dự phòng ký quỹ', 'Hệ số dự phòng ký quỹ', 'Margin buffer'],
    ['Số hợp đồng tối đa', 'Số hợp đồng tối đa', 'Maximum contracts'], ['Thêm vị thế cùng hướng', 'Thêm vị thế cùng hướng', 'Pyramiding'],
    ['5 phút', '5 phút', '5 minutes'], ['1 ngày', '1 ngày', '1 day'], ['Giây', 'Giây', 'Seconds'], ['Mili giây', 'Mili giây', 'Milliseconds'],
    ['Mô phỏng theo giá (normalized)', 'Mô phỏng theo giá', 'Normalized simulation'], ['Hợp đồng phái sinh (contract)', 'Hợp đồng phái sinh', 'Futures contracts'],
    ['Theo tỷ lệ vốn và dừng lỗ', 'Theo tỷ lệ vốn và dừng lỗ', 'Capital fraction and stop loss'],
    ['Theo rủi ro và ký quỹ', 'Theo rủi ro và ký quỹ', 'Risk and margin'], ['Giá mở cửa nến kế tiếp', 'Giá mở cửa nến kế tiếp', 'Next bar open'],
    ['Không', 'Không', 'No'], ['Có', 'Có', 'Yes'], ['Chọn…', 'Chọn…', 'Select…'],
    ['Mô hình tính tiền', 'Mô hình tính tiền', 'Accounting model'], ['Cách tính khối lượng', 'Cách tính khối lượng', 'Position sizing'],
    ['Tên chỉ báo', 'Tên chỉ báo', 'Indicator name'], ['Loại chỉ báo', 'Loại chỉ báo', 'Indicator type'], ['Nguồn chỉ báo', 'Nguồn chỉ báo', 'Indicator source'],
    ['Chu kỳ', 'Chu kỳ', 'Period'], ['Chu kỳ nhanh', 'Chu kỳ nhanh', 'Fast period'], ['Chu kỳ chậm', 'Chu kỳ chậm', 'Slow period'], ['Chu kỳ tín hiệu', 'Chu kỳ tín hiệu', 'Signal period'],
    ['Hệ số độ lệch chuẩn', 'Hệ số độ lệch chuẩn', 'Standard deviation multiplier'], ['Dạng histogram', 'Dạng biểu đồ phân phối', 'Histogram style'],
    ['Điều kiện vào lệnh (entry)', 'Điều kiện vào lệnh', 'Entry rules'], ['Điều kiện thoát lệnh (exit)', 'Điều kiện thoát lệnh', 'Exit rules'],
    ['Giới hạn trong ngày (daily_limits)', 'Giới hạn trong ngày', 'Daily limits'], ['Bảng mã hợp đồng và đáo hạn (contract_map)', 'Bảng mã hợp đồng và đáo hạn', 'Contracts and expiry dates'],
    ['Mã dữ liệu', 'Mã dữ liệu', 'Symbol'], ['Khung thời gian', 'Khung thời gian', 'Timeframe'], ['Đơn vị thời gian', 'Đơn vị thời gian', 'Timestamp unit'], ['Múi giờ', 'Múi giờ', 'Timezone'], ['Đơn vị giá', 'Đơn vị giá', 'Price unit'],
    ['Đang đọc JSON…', 'Đang đọc JSON…', 'Reading JSON…'], ['Đã bỏ nguồn dữ liệu đã chọn.', 'Đã bỏ nguồn dữ liệu đã chọn.', 'Data source cleared.'],
    ['Đã điền mẫu CANSLIM v1. Dữ liệu đã nạp được giữ lại; mẫu chỉ có 2 nến nếu chưa nạp dữ liệu.', 'Đã điền mẫu CANSLIM v1. Dữ liệu đã nạp được giữ lại; mẫu chỉ có 2 nến nếu chưa nạp dữ liệu.', 'CANSLIM v1 example loaded. Existing data retained; the example has only 2 bars if no data was loaded.'],
    ['Payload phải là một object JSON.', 'Đầu vào phải là một đối tượng JSON.', 'Request must be a JSON object.'],
    ['File dữ liệu phải chứa object OHLCV hoặc danh sách nến.', 'Tệp dữ liệu phải chứa đối tượng OHLCV hoặc danh sách nến.', 'Data file must contain an OHLCV object or candle list.'],
    ['Đây là JSON dữ liệu giá. Hãy nạp vào nguồn giao dịch hoặc thị trường.', 'Đây là JSON dữ liệu giá. Hãy nạp vào nguồn giao dịch hoặc thị trường.', 'This is price data JSON. Load it as trading or market data.'],
    ['Mỗi chỉ báo phải là một object JSON.', 'Mỗi chỉ báo phải là một đối tượng JSON.', 'Each indicator must be a JSON object.'],
    ['Cấu hình điều kiện vượt 65.536 ký tự. Không đưa dữ liệu nến vào vùng điều kiện.', 'Cấu hình điều kiện vượt 65.536 ký tự. Không đưa dữ liệu nến vào vùng điều kiện.', 'Rules exceed 65,536 characters. Do not put candle data in the rules area.'],
    ['Vui lòng chờ dữ liệu được nạp xong.', 'Vui lòng chờ dữ liệu được nạp xong.', 'Please wait until data finishes loading.'],
    ['Vui lòng điền các trường bắt buộc và kiểm tra giá trị đã nhập.', 'Vui lòng điền các trường bắt buộc và kiểm tra giá trị đã nhập.', 'Fill required fields and check the entered values.'],
    ['Tên chỉ báo phải hợp lệ và không được trùng.', 'Tên chỉ báo phải hợp lệ và không được trùng.', 'Indicator names must be valid and unique.'],
    ['Kỳ báo cáo cần cả ngày bắt đầu và ngày kết thúc.', 'Kỳ báo cáo cần cả ngày bắt đầu và ngày kết thúc.', 'Report requires both start and end dates.'],
    ['Chi tiết', 'Chi tiết', 'Details'], ['Mã', 'Mã', 'Symbol'], ['Ngày bắt đầu', 'Ngày bắt đầu', 'Start date'], ['Ngày kết thúc', 'Ngày kết thúc', 'End date'],
    ['Sinh lời', 'Sinh lời', 'Return'], ['Vốn cuối kỳ', 'Vốn cuối kỳ', 'Final equity'], ['Thời điểm chạy', 'Thời điểm chạy', 'Run time'],
    ['Ngày khớp', 'Ngày khớp', 'Fill time'], ['Giá', 'Giá', 'Price'], ['Số lượng', 'Số lượng', 'Quantity'], ['Phí', 'Phí', 'Fee'], ['Signal', 'Tín hiệu', 'Signal'], ['Lý do', 'Lý do', 'Reason'],
    ['Lỗi API', 'Lỗi API', 'API error'],
];
const fields = {
    initial_cash: ['Vốn ban đầu', 'Initial capital'], final_equity: ['Vốn cuối kỳ', 'Final equity'], total_return: ['Tỷ suất sinh lời', 'Total return'],
    realized_pnl: ['Lãi/lỗ đã thực hiện', 'Realized P/L'], unrealized_pnl: ['Lãi/lỗ chưa thực hiện', 'Unrealized P/L'],
    fill_time: ['Thời điểm khớp', 'Fill time'], direction: ['Hướng vị thế', 'Direction'], contract_code: ['Mã hợp đồng', 'Contract'], side: ['Mua/bán', 'Side'],
    fill_price: ['Giá khớp', 'Fill price'], quantity: ['Khối lượng', 'Quantity'], fee: ['Phí', 'Fee'], fees: ['Tổng phí', 'Total fees'],
    broker_fee: ['Phí môi giới', 'Broker fee'], exchange_fee: ['Phí sở', 'Exchange fee'], clearing_fee: ['Phí bù trừ', 'Clearing fee'], pit: ['Thuế TNCN', 'Income tax'],
    entry_date: ['Thời điểm vào', 'Entry time'], exit_date: ['Thời điểm thoát', 'Exit time'], entry_price: ['Giá vào', 'Entry price'], exit_price: ['Giá thoát', 'Exit price'],
    net_pnl: ['Lãi/lỗ ròng', 'Net P/L'], close_reason: ['Lý do đóng', 'Close reason'], remaining_entry_cost: ['Chi phí vào còn lại', 'Remaining entry cost'],
    market_value: ['Giá trị thị trường', 'Market value'], signal_time: ['Thời điểm tín hiệu', 'Signal time'], reason: ['Lý do', 'Reason'], pivot: ['Ngưỡng phá vỡ', 'Pivot'],
    created_time: ['Thời điểm tạo', 'Created at'], status: ['Trạng thái', 'Status'], rejection_reason: ['Lý do từ chối', 'Rejection reason'],
    order_type: ['Loại lệnh', 'Order type'], filled_quantity: ['Khối lượng đã khớp', 'Filled quantity'],
    expired_quantity: ['Khối lượng hết hiệu lực', 'Expired quantity'], remaining_quantity: ['Khối lượng còn chờ', 'Remaining quantity'],
    trading_date: ['Thời điểm', 'Time'], cash: ['Tiền mặt', 'Cash'], required_margin: ['Ký quỹ yêu cầu', 'Required margin'], available_cash: ['Tiền khả dụng', 'Available cash'], equity: ['Vốn tài khoản', 'Equity'],
};
const exact = new Map(labels.map(([key, vi, en]) => [key, {vi, en}]));
for (const [key, [vi, en]] of Object.entries(fields)) exact.set(key, {vi, en});
export function translate(text, language = 'vi') {
    const key = text.trim(), match = exact.get(key);
    if (match) return text.replace(key, match[language === 'en' ? 'en' : 'vi']);
    const metric = key.match(/^([a-z_]+): (.*)$/s);
    if (metric && fields[metric[1]]) return `${translate(metric[1], language)}: ${metric[2]}`;
    const patterns = [
        [/^Không tải được chart: (.*)$/s, m => language === 'en' ? `Unable to load chart: ${m[1]}` : `Không tải được biểu đồ: ${m[1]}`],
        [/^Không tải được lịch sử: (.*)$/s, m => language === 'en' ? `Unable to load history: ${m[1]}` : key],
        [/^Đang hiển thị (\d+) kết quả\.$/, m => language === 'en' ? `Showing ${m[1]} results.` : key],
        [/^Đã nạp (.*)\.$/s, m => language === 'en' ? `Loaded ${m[1]}.` : key],
        [/^Đã điền cấu hình và dữ liệu từ (.*)\.$/s, m => language === 'en' ? `Settings and data loaded from ${m[1]}.` : key],
        [/^(.*) · (.*) · (\d+) nến · (\d+) lần khớp · Mua ↑ \/ Bán ↓$/, m => language === 'en' ? `${m[1]} · ${m[2]} · ${m[3]} bars · ${m[4]} fills · Buy ↑ / Sell ↓` : key],
        [/^(.*) nến · (.*)$/s, m => language === 'en' ? `${m[1]} bars · ${m[2]}` : key],
        [/^(BUY|SELL) đã khớp$/, m => language === 'en' ? `${m[1]} filled` : `${m[1] === 'BUY' ? 'Mua' : 'Bán'} đã khớp`],
        [/^Đang lọc theo (.*) lúc (.*)\. Bấm vùng trống trên chart để bỏ lọc\.$/, m => language === 'en' ? `Filtered by ${m[1]} at ${m[2]}. Click an empty chart area to clear.` : `Đang lọc theo ${m[1]} lúc ${m[2]}. Bấm vùng trống trên biểu đồ để bỏ lọc.`],
        [/^Đã tải kết quả và biểu đồ\.(.*)$/s, m => language === 'en' ? `Results and chart loaded.${m[1].replace(' Đánh giá quy tắc: ', ' Rule evaluation: ').replace(' nến thiếu dữ liệu để đánh giá.', ' bars lack evaluation data.')}` : key],
        [/^(.*) phải là một object JSON\.$/, m => language === 'en' ? `${m[1]} must be a JSON object.` : `${m[1]} phải là một đối tượng JSON.`],
        [/^(.*) phải là số nguyên dương\.$/, m => language === 'en' ? `${translate(m[1], language)} must be a positive integer.` : key],
        [/^(.*) phải là số hữu hạn\.$/, m => language === 'en' ? `${translate(m[1], language)} must be finite.` : key],
        [/^(.*): JSON không hợp lệ\.$/, m => language === 'en' ? `${translate(m[1], language)}: invalid JSON.` : key],
        [/^Không tìm thấy dữ liệu (.*) trong file JSON\.$/, m => language === 'en' ? `No ${m[1]} data found in JSON file.` : key],
        [/^(.*) vượt 65\.536 ký tự(.*)$/, m => language === 'en' ? `${translate(m[1], language)} exceeds 65,536 characters.` : key],
        [/^(.*)\. Có thể chạy; từng nến vẫn cần đủ dữ liệu chỉ báo\.$/, m => language === 'en' ? `${m[1]}. Ready to run; each bar still needs sufficient indicator data.` : key],
        [/^(.*)\. Chưa có bộ thực thi\.$/, m => language === 'en' ? `${m[1]}. No execution engine available.` : key],
        [/^Xem kết quả (.*), từ (.*) đến (.*), (.*)$/, m => language === 'en' ? `View ${m[1]} results, from ${m[2]} to ${m[3]}, ${m[4]}` : key],
    ];
    for (const [pattern, render] of patterns) {const match = key.match(pattern); if (match) return render(match);}
    return text;
}

export function mountLanguage(root, selector, storage) {
    let language = 'vi';
    try {storage ??= globalThis.localStorage; if (storage.getItem('backtest-language') === 'en') language = 'en';} catch {}
    const originals = new WeakMap();
    const attributes = new WeakMap();
    const observer = new MutationObserver(records => apply(new Set(records.map(record => record.target.nodeType === 3 ? record.target.parentElement : record.target))));
    function convert(node, key, value, records) {
        let record = records.get(node);
        if (!record) {record = {}; records.set(node, record);}
        const previous = record[key];
        const original = previous && previous.rendered === value ? previous.original : value;
        const rendered = translate(original, language);
        record[key] = {original, rendered};
        return rendered;
    }
    function apply(targets = [root]) {
        observer.disconnect();
        root.ownerDocument.documentElement.lang = language;
        for (const link of selector.querySelectorAll('[data-language]')) {
            if (link.dataset.language === language) link.setAttribute('aria-current', 'true');
            else link.removeAttribute('aria-current');
        }
        for (const target of targets) {
            if (!root.contains(target)) continue;
            const walker = root.ownerDocument.createTreeWalker(target, 4);
            let node;
            while ((node = walker.nextNode())) {
                if (node.parentElement.closest('pre, textarea, script, style, #language-select, .tv-lightweight-charts')) continue;
                if (node.parentElement.tagName === 'TD') continue;
                const value = convert(node, 'text', node.nodeValue, originals);
                if (node.nodeValue !== value) node.nodeValue = value;
            }
            for (const element of [target, ...target.querySelectorAll('[aria-label], [placeholder]')]) {
                for (const name of ['aria-label', 'placeholder']) {
                    if (!element.hasAttribute(name)) continue;
                    const value = convert(element, name, element.getAttribute(name), attributes);
                    if (value !== element.getAttribute(name)) element.setAttribute(name, value);
                }
            }
        }
        observer.observe(root, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['aria-label', 'placeholder']});
    }
    selector.onclick = event => {
        const link = event.target.closest('[data-language]');
        if (!link || !selector.contains(link)) return;
        event.preventDefault();
        language = link.dataset.language === 'en' ? 'en' : 'vi';
        try {storage.setItem('backtest-language', language);} catch {}
        apply();
    };
    apply();
}
if (typeof document !== 'undefined' && document.querySelector('#language-select')) {
    mountLanguage(document.body, document.querySelector('#language-select'));
}
