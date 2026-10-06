# Bot tính tiền khách/chủ — bản vá an toàn (chưa dùng production)

**NOT READY FOR PRODUCTION.** Đây là bản để kiểm tra trước khi dùng tiền thật. Xem REPORT.md về test, conflict và việc chưa kiểm chứng.

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

Nếu nhập `B91=175k` hoặc `b20b500k`, bot hỏi **BAO TOÀN BỘ / ĐỀ BỘ**; chưa chọn thì chưa lưu. Đổi người, ngày, tỷ lệ, bấm menu khác hoặc Hủy sẽ hủy lựa chọn. Lựa chọn hết hạn sau 5 phút. Nhiều dòng B sẽ được hỏi lần lượt.

Tin có phần chưa hiểu: bot hiện phần đã hiểu và phần chưa hiểu, **không lưu cả tin**. Sửa lại rồi gửi; bot chưa hỗ trợ lưu một phần. `1tr5` và `1tr500` đều là 1.500k; `10.000` vẫn là 10.000k. Các giá chưa có rule như `1tr50` bị từ chối. `bằng/bang/băng/bg` dùng ghi giá; `bảng` không phải dấu bằng.

Số 4 chữ số chỉ tách khi có danh sách rõ: ít nhất hai số 2 chữ số, có dấu phẩy/chấm, tất cả token dài 2 hoặc 4. Ví dụ `83,84,8968 98=50n`. `9497=50` hoặc `66 1000 68=50` bị từ chối. Range chỉ nhận đầu/đít tăng như `từ đầu 3 đến 8 ghép đít 3 đến 8=50`; range giảm bị từ chối; dấu `-` vẫn là dấu ngăn cách cũ.

Một người dùng cả Xiên ×14 và ×15: chọn bộ rồi gửi từng tin riêng. Một tin không trộn hai bộ. Tổng hiển thị hai dòng riêng. Mỗi bộ lưu bộ % riêng; hệ số khác Xiên 2 dùng chung theo profile.

Tin mới giữ bản sao tỷ lệ lúc nhập. Sửa profile không thay tiền của tin cũ. Muốn đổi tỷ lệ cho tin cũ trong bản này: xóa có xác nhận rồi nhập lại; không có chức năng đổi hàng loạt.

Tiền dùng đơn vị k (nghìn đồng), giống parser gốc. Giữ số lẻ khi tính; tổng thu/trả cuối làm tròn đến 1k: 10,5k → 11k, 10,4k → 10k. Phía Khách: hàng trừ % vượt thưởng thì thu; phía Chủ thì trả. Chiều ngược lại đảo thu/trả.

## Dữ liệu và giới hạn
Dữ liệu lưu trong data.sqlite3 cạnh chương trình, vẫn còn sau khi tắt. Sao lưu file này khi bot đã tắt; ZIP/source không chứa dữ liệu riêng.
Không chạy hai cửa sổ cùng token. Bot chỉ nhận chữ; chuyển giọng nói là chức năng điện thoại.
Bản này chưa có nợ cũ, thu/trả đã thanh toán, chốt/khóa ngày, tổng lợi nhuận, bảng thu chi sheet 3 hoặc kết quả nhiều ngày. Sửa/xóa vé được lưu lịch sử trong SQLite: raw cũ/mới, thời gian UTC, admin thực hiện. Xóa mềm giữ vé cũ để kiểm tra; không cộng lại message ID đã xóa.
Tên và % thật cần người dùng thêm bằng menu; không tự suy các tỷ lệ từ bảng đang làm dở.

## Nâng cấp dữ liệu cũ
1. Tắt bot, sao lưu nguyên file `data.sqlite3` trước khi nâng cấp.
2. Bản mới thêm cột lưu cách hiểu vé và dấu xóa mềm. Không tự tính lại vé cũ bằng parser mới.
3. Vé cũ chưa có cách hiểu đã lưu sẽ chặn tổng. Vào Danh sách tin, kiểm tra từng vé rồi Sửa tin với nội dung được xác nhận; thao tác này giữ tỷ lệ gốc và có audit. Đặc biệt rà lại `1tr5` từng được tính sai ở bản cũ.
4. Nếu rollback, tắt bot rồi phục hồi **cả source cũ và database đã sao lưu**. Không chạy source cũ với DB mới: source cũ không hiểu xóa mềm và có thể cộng lại vé đã xóa.

Vé mới lưu cả cách hiểu và cấu hình; đổi parser/profile không đọc lại raw của vé đó. Phép tính trung gian dùng Decimal 80 chữ số và báo lỗi nếu mất chữ số; chỉ tiền thu/trả cuối mới làm tròn. Dữ liệu vượt khả năng số hỗ trợ bị chặn.

`results.py`, `legacy_bot.py` và toàn bộ test cũ giữ nguyên. `legacy_bot.py` chỉ là tham khảo, **không dùng để ghi/chốt tiền production**. Khi tích hợp module, chỉ lưu qua Ledger.add/replace: `calculate()` giữ behavior B mặc định Bao cho tương thích test cũ, còn Ledger bắt buộc xác nhận B.

Kiểm tra offline: `python -m compileall -q .` và `python -m unittest discover -v`. Test UI mô phỏng Telegram; không chứng minh bot chạy thật hoặc nguồn kết quả đúng.
