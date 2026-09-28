# CANSLIM v1 — Ví dụ số và nghiệm thu

Cập nhật: 25/09/2026. **S10 để điền sau theo yêu cầu user.**
Chưa có expected values; chưa implement hoặc chạy các case dưới đây.
Các header là khung để bổ sung, không phải evidence test pass.

Tham chiếu: [rule](../../strategies/canslim-v1-rules.md),
[execution/accounting](../../design/canslim-v1-execution-accounting.md),
[data](../../data/vn30f1m/data-contract-v1.md).

## V1-01 — Long entry và full exit

- Input/config:
- Signal/time/fill kỳ vọng:
- Cash/margin/fees/realized/unrealized/equity kỳ vọng:
- Evidence:

## V1-02 — Short entry và full exit

- Input/config:
- Signal/time/fill kỳ vọng:
- Accounting kỳ vọng:
- Evidence:

## V1-03 — Partial exit quantity 1, 2 và 5

- Input/config:
- TP1/TP2/quantity còn lại:
- Phí/margin/P&L kỳ vọng:
- Evidence:

## V1-04 — Stop gap, stop và target cùng nến

- Input/config:
- Giá fill/thứ tự kỳ vọng:
- Evidence:

## V1-05 — Trailing và time-stop

- Input/config:
- Thời điểm hiệu lực/đếm bar/exit kỳ vọng:
- Evidence:

## V1-06 — Cutoff, nghỉ trưa, forced exit và cuối report

- Input/config:
- Pending/cancel/fill/INVALID kỳ vọng:
- Evidence:

## V1-07 — Sizing, margin breach và chi phí

- Input/config:
- Quantity/rejection/liquidation kỳ vọng:
- Accounting kỳ vọng:
- Evidence:

## V1-08 — Indicator, daily pivot, rollover và missing data

- Input/config:
- Expected values/availability/UNEVALUABLE:
- Evidence:

## V1-09 — No-lookahead, determinism và regression v0

- Input/config/cutoff:
- Events/values kỳ vọng:
- Evidence:

## V1-10 — API, storage, notebook, browser và Docker

- Input/run/profile:
- Expected response/reload/chart:
- Evidence từng môi trường:
