# Kiểm thử hợp đồng và CANSLIM v1

Danh mục này dẫn tới kiểm thử hiện có trong source. Các test dùng dữ liệu
tổng hợp và kho tạm, không phải nghiệm thu bộ dữ liệu thật sáu tháng.

## 1. Thực thi và sổ tiền

Source kiểm thử: [test_contract_execution.py](../../../tests/test_contract_execution.py).

| Nội dung | Test |
| --- | --- |
| Long/short, cash, phí, margin và P/L khi đóng từng phần | `test_long_short_partial_cash_fees_and_margin` |
| Phân bổ phần dư chi phí, từ chối ký quỹ và hệ số hợp đồng | `test_residual_costs_margin_rejection_and_multiplier` |
| Close → Open kế tiếp, đóng 1 rồi 2 hợp đồng, chạy lại cùng kết quả | `test_engine_long_short_next_open_partial_exit_and_repeat` |
| Stop trước target, gap, TP ngay nến entry và TP1=TP2 | `test_stop_priority_gap_and_targets_on_entry_bar` |
| Trailing bỏ cực trị nến TP1, áp dụng từ nến sau và so dữ liệu cắt | `test_trailing_excludes_tp1_bar_and_tightens_only_next_bar` |
| Lệnh đóng chờ tại Open trước stop/TP, fill sai không đổi sổ tiền | `test_pending_exit_precedes_bracket_and_invalid_fill_does_not_mutate` |

Ví dụ trong test: LONG 3 hợp đồng tại 1.000, đóng 1 tại 1.006 rồi 2 tại
1.012, hệ số 100.000, margin 0,17, PIT 0,001, phí sàn 2.700,
bù trừ 2.550, broker 0. Chi phí mở 41.250, P/L ròng tổng 2.917.245.
Vốn 100.000.000 kết thúc thành 102.917.245. Đây là số mô phỏng của test.

## 2. Chiến lược JSON

Source kiểm thử: [test_inline_runtime.py](../../../tests/test_inline_runtime.py).

| Nội dung | Test |
| --- | --- |
| Seed EMA, BB, MACD và MFI | `test_formulas_and_seed` |
| Mẫu thứ 150 tính cả nến đang xét, quantity 5 → TP1 2 → TP2 3 | `test_150_includes_current_market_bar_and_partial_targets` |
| Thay tương lai và cắt cuối báo cáo không đổi quá khứ | `test_future_market_and_report_tail_do_not_change_past` |
| Khoảng thiếu khởi tạo lại, bỏ auction khỏi chỉ báo, giữ lịch sử VNINDEX khi chuyển mã | `test_market_gap_reset_excludes_auction_and_preserves_rollover_history` |
| Forced exit 14:20, thiếu nến, vị thế cuối kỳ và pending cuối kỳ | `test_forced_exit_priority_missing_bar_and_end_of_report` |
| Giới hạn ngày, xung đột hướng, sizing không dùng giá tương lai | `test_daily_entry_limit_conflict_and_sizing_without_future_prices` |
| Nến entry tính là nến giữ thứ nhất, nghỉ trưa không tăng số nến | `test_time_stop_counts_entry_bar_and_lunch_is_not_a_bar` |
| Short theo mẫu và ngừng mở mới khi đạt giới hạn lỗ ngày | `test_approved_short_and_daily_loss_cutoff` |
| Chạy bộ thực thi qua API và đọc lại từ kho file | `test_real_runner_api_and_reload` |
| Notebook dùng đúng cấu trúc JSON/API | `test_results_notebook_uses_the_json_payload_contract` |

## 3. Dữ liệu, lưu trữ và trình bày

| File test | Phạm vi |
| --- | --- |
| [test_inline_strategy.py](../../../tests/test_inline_strategy.py) | Kiểm tra mẫu JSON trong đặc tả API, biểu thức, tham chiếu và tổ hợp chưa hỗ trợ |
| [test_inline_pipeline.py](../../../tests/test_inline_pipeline.py) | Đơn vị thời gian, nến ngày, khả dụng trễ của thị trường, lịch/map/gap, ID từng phần đóng, hash/schema, lỗi ghi và đọc lại |
| [test_auto_fetch_data.py](../../../tests/test_auto_fetch_data.py) | Ưu tiên nguồn tự lấy, khoảng theo report kèm số nến khởi tạo cần dùng, nến đóng, lịch 2026, lỗi nguồn và ghim nguồn gốc |
| [test_session_matching.py](../../../tests/test_session_matching.py) | Phiên HNX, ATO/LO/ATC, giới hạn khớp 5→5/2/0, phần dư hết hiệu lực, phí/vị thế, API, kho file và dữ liệu biểu đồ |
| [test_run_history.py](../../../tests/test_run_history.py) | Lọc, phân trang, thời điểm chạy và kết quả lỗi |
| [test_input_ui.py](../../../tests/test_input_ui.py) | Tài nguyên form và hai file snapshot cục bộ |
| [tests/web/](../../../tests/web/) | Ghép payload, dữ liệu chart/marker, trục, theme, lịch sử và ngôn ngữ |

## 4. Chạy và diễn giải kết quả

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node --test tests/web/*.test.mjs
```

- Kết quả đạt xác nhận các trường hợp đã chạy trong từng bộ test.
- Notebook: kiểm tra cấu trúc ô mã.
- Giao diện: kiểm tra dữ liệu và hành vi trong test.
- Chạy notebook với API, thao tác trình duyệt, Docker và dữ liệu thị trường cần nghiệm thu riêng.
