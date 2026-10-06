# Kết quả bản 1

Đã triển khai: profile Khách/Chủ, chọn tên/ID, sửa % và hệ số thưởng bằng menu, hai bộ Xiên 2 ×14/×15 riêng, ghi liên tục tin theo người/ngày, snapshot cấu hình mỗi tin, lưu SQLite bền vững, danh sách/sửa/xóa tin có xác nhận xóa, tổng hàng/%/thưởng, chiều thu/trả ngược nhau, làm tròn cuối đến nghìn. Chỉ admin ID dùng chat riêng. Tin chưa hiểu đủ không được lưu. Kết quả sai ngày không chốt thưởng.

Đã kiểm tra: 78 tests PASS (72 tests gốc, 5 tests kế toán, 1 luồng UI offline). Python compile PASS. calculator.py và results.py giống byte-for-byte source ZIP gốc. Test UI dùng mô phỏng Telegram, không phải kiểm chứng Telegram thật.

NOT RUN: kết nối Telegram thật, lấy kết quả online, chạy launcher trên Windows/macOS thật. Môi trường này không có thư viện telegram; kiểm tra import và network runtime thật chưa thực hiện. Launcher cài python-telegram-bot 22.5 trên máy người dùng.

Chưa thuộc bản này: công nợ/thu trả thực tế, chốt ngày, lợi nhuận, sheet 3, lịch sử sửa/xóa đầy đủ. Kết quả chỉ hỗ trợ nguồn latest của bot gốc; ngày khác chưa có kết quả thì không chốt. Hai bộ ×14/×15 phải nhập thành các tin riêng. Profiles chưa có tên/tỷ lệ thật được seed; người dùng thêm bằng menu, không đoán dữ liệu Excel đang dở.

Không có token, admin ID thật, dữ liệu khách hay cơ sở dữ liệu trong ZIP hoặc GitHub.
