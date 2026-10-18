# Ví dụ số học normalized

Các ví dụ dưới đây được kiểm tra trong
[tests/test_execution_accounting.py](../../tests/test_execution_accounting.py),
bằng tín hiệu cố định và dữ liệu tổng hợp. Chúng kiểm tra sổ tiền hiện còn
được dùng, không phải kết quả giao dịch HPG hoặc VN30F1M trên dữ liệu thật.

Công thức tại [tính tiền normalized](../design/normalized-accounting.md).
Mỗi ví dụ dùng phí 0,1% mỗi chiều, slippage 0; không có thuế hoặc cổ tức.
Giá vốn gồm phí mua; lãi/lỗ chưa chốt chưa trừ phí bán dự kiến.

| ID / test | Đầu vào | Kết quả |
| --- | --- | --- |
| ACC-01 / `test_acc_01` | Vốn 8.000.000; mua 200 tại 15.000; mark 16.000; bán 17.000 | Phí mua 3.000; giá vốn 3.003.000; cash sau mua 4.997.000; giá trị vị thế 3.200.000; lãi chưa chốt 197.000; equity lúc giữ 8.197.000; phí bán 3.400; tiền bán ròng 3.396.600; lãi đã chốt 393.600; cash/equity cuối 8.393.600 |
| ACC-02 / `test_acc_02` | Vốn 8.000.000; mua 200 tại 15.000; bán 14.000 | Phí mua 3.000; phí bán 2.800; lỗ đã chốt −205.800; cash/equity cuối 7.794.200 |
| ACC-03 / `test_acc_03` | Vốn 5.000.000; mua 100 tại 10.000; mark 11.000; bán 12.000 | Phí mua 1.000; cash sau mua 3.999.000; lãi chưa chốt 99.000; equity lúc giữ 5.099.000; phí bán 1.200; lãi đã chốt 197.800; cash/equity cuối 5.197.800 |

Cả ba ví dụ kết thúc không còn vị thế. Cùng file còn kiểm tra lệnh bị từ chối,
tín hiệu cuối dữ liệu không tạo fill và cấu hình thực thi sai bị từ chối.

Chạy từ gốc repository:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_execution_accounting.py" -v
```
