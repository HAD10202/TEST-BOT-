# Bot tính tiền khách/chủ — bản 1

Chạy Windows: mở CHAY_BOT_WINDOWS.bat. Chạy macOS: mở CHAY_BOT_MACOS.command (nếu bị chặn, chạy `bash CHAY_BOT_MACOS.command` trong thư mục này).
Máy cần Python 3.11+ và mạng để cài thư viện. Dán token và nhập Telegram user ID của người quản lý. Token không được ghi vào source. Chỉ user ID này được dùng bot trong chat riêng.

## Dùng bot
1. /start → Tạo người → `Khách; HBX` hoặc `Chủ; Tên chủ`.
2. Sửa % → `5; 3,5; 18; 23; 38`. Thứ tự Đề; Bao; Xiên 2; Xiên 3,4; Càng.
3. Chọn Xiên ×14 hoặc ×15; đặt % riêng cho mỗi bộ. Trước khi chuyển bộ, kiểm tra bộ hiện trên màn hình. Không dùng bộ chưa đặt %.
4. Sửa thưởng → 7 hệ số Đề; Bao; Xiên 2; Xiên 3; Xiên 4; Càng; Áp càng. Ví dụ `90; 3,5; 15; 48; 180; 400; 10`.
5. Nhập tin → chọn tên hoặc ID → gửi liên tục các tin theo cú pháp bot gốc, ví dụ `Đề 12=10k`, `X 12-34=50k`.
6. Đổi ngày nếu cần. Xem tổng lấy kết quả mới nhất, chỉ tính thưởng khi ngày kết quả khớp ngày bảng. Nếu chưa có đúng ngày, chỉ hiện hàng và %, chưa chốt thu/trả.
7. Danh sách tin xem ID; Sửa tin gửi `ID; nội dung mới`. Sửa giữ tỷ lệ gốc. Xóa tin yêu cầu gõ XÓA.

Một người dùng cả Xiên ×14 và ×15: chọn bộ rồi gửi từng tin riêng. Một tin không trộn hai bộ. Tổng hiển thị hai dòng riêng. Mỗi bộ lưu bộ % riêng; hệ số khác Xiên 2 dùng chung theo profile.

Tin mới giữ bản sao tỷ lệ lúc nhập. Sửa profile không thay tiền của tin cũ. Muốn đổi tỷ lệ cho tin cũ trong bản này: xóa có xác nhận rồi nhập lại; không có chức năng đổi hàng loạt.

Tiền dùng đơn vị k (nghìn đồng), giống parser gốc. Giữ số lẻ khi tính; tổng thu/trả cuối làm tròn đến 1k: 10,5k → 11k, 10,4k → 10k. Phía Khách: hàng trừ % vượt thưởng thì thu; phía Chủ thì trả. Chiều ngược lại đảo thu/trả.

## Dữ liệu và giới hạn
Dữ liệu lưu trong data.sqlite3 cạnh chương trình, vẫn còn sau khi tắt. Sao lưu file này khi bot đã tắt; ZIP/source không chứa dữ liệu riêng.
Không chạy hai cửa sổ cùng token. Bot chỉ nhận chữ; chuyển giọng nói là chức năng điện thoại.
Bản này chưa có nợ cũ, thu/trả đã thanh toán, chốt ngày, tổng lợi nhuận, bảng thu chi sheet 3, lịch sử sửa/xóa đầy đủ hoặc kết quả nhiều ngày. Tập trung đúng giai đoạn tính từng khách/chủ theo ngày.
Tên và % thật cần người dùng thêm bằng menu; không tự suy các tỷ lệ từ bảng đang làm dở.

calculator.py và results.py giữ nguyên từ ZIP gốc. legacy_bot.py giữ bot gốc tham khảo. Bộ kiểm thử cũ kiểm tra parser và menu cũ, không chứng minh menu mới chạy thật. Xem REPORT.md để biết kiểm chứng.

