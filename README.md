# Bot tính tiền khách/chủ — bản vá an toàn (chưa dùng production)

**NOT READY FOR PRODUCTION.** Đây là bản để kiểm tra trước khi dùng tiền thật. Xem REPORT.md về test, conflict và việc chưa kiểm chứng.

## Chạy trên Windows: chỉ mở file

Máy cần Python 3.11 trở lên và Internet. Giải nén source vào một thư mục riêng.

1. Double-click **CHAY_BOT_WINDOWS.bat**. Bot tự chuẩn bị thư viện nếu cần.
2. Lần đầu: copy token từ BotFather, **Ctrl+V rồi Enter**. Nhập Telegram Admin ID rồi Enter. Token có thể hiện lúc nhập; không chia sẻ ảnh màn hình này.
3. Thấy “Đã lưu cấu hình”, nhấn Enter để chạy. Khi thấy **BOT ĐANG CHẠY**, mở Telegram. Giữ cửa sổ này mở.
4. Những lần sau chỉ double-click **CHAY_BOT_WINDOWS.bat**; không cần nhập lại token hoặc Admin ID.
5. Muốn đổi token hoặc Admin ID: double-click **CAI_DAT_BOT_WINDOWS.bat**, nhập lại cả hai. Tắt cửa sổ bot cũ rồi chạy lại.

Token lưu riêng ở `%APPDATA%\TEST-BOT\secrets.env`, ngoài source. Tải source mới vẫn giữ cấu hình trên cùng tài khoản Windows. Không gửi file đó cho người khác, đưa vào ZIP hoặc GitHub. Token lỗi do cách dán sẽ bị chặn trước khi gọi Telegram. Chỉ Admin ID được cấu hình mới dùng bot trong chat riêng.

Nếu báo token không hợp lệ: mở CAI_DAT_BOT_WINDOWS.bat để dán lại. Nếu báo không kết nối Telegram: kiểm tra Internet rồi mở lại file chạy. Không cần mở PowerShell hay gõ lệnh.

macOS: mở CHAY_BOT_MACOS.command (nếu bị chặn, chạy `bash CHAY_BOT_MACOS.command` trong thư mục này). Setup cũng dùng nhập bình thường và lưu ngoài source trong `~/Library/Application Support/TEST-BOT/secrets.env`.

## Dùng bot
1. /start → Tạo người → `Khách; HBX` hoặc `Chủ; Tên chủ`.
2. Sửa % → `5; 3,5; 18; 23; 38`. Thứ tự Đề; Bao; Xiên 2; Xiên 3,4; Càng.
3. Chọn Xiên ×14 hoặc ×15; đặt % riêng cho mỗi bộ. Trước khi chuyển bộ, kiểm tra bộ hiện trên màn hình. Không dùng bộ chưa đặt %.
4. Sửa thưởng → 7 hệ số Đề; Bao; Xiên 2; Xiên 3; Xiên 4; Càng; Áp càng. Ví dụ `90; 3,5; 15; 48; 180; 400; 10`.
5. Nhập tin → chọn tên hoặc ID → gửi liên tục các tin theo cú pháp bot gốc, ví dụ `Đề 12=10k`, `X 12-34=50k`.
6. Đổi ngày nếu cần. Xem tổng lấy kết quả mới nhất, chỉ tính thưởng khi ngày kết quả khớp ngày bảng. Nếu chưa có đúng ngày, chỉ hiện hàng và %, chưa chốt thu/trả.
7. Sổ vé xem ID và tiền từng loại, không hiện nguyên tin; Xem raw → nhập ID để xem riêng nội dung gốc. Sửa tin gửi `ID; nội dung mới`. Sửa giữ tỷ lệ gốc. Xóa tin yêu cầu gõ XÓA.

Nếu nhập `B91=175k` hoặc `b20b500k`, bot hỏi **BAO TOÀN BỘ / ĐỀ BỘ**; chưa chọn thì chưa lưu. Đổi người, ngày, tỷ lệ, bấm menu khác hoặc Hủy sẽ hủy lựa chọn. Lựa chọn hết hạn sau 5 phút. Nhiều dòng B sẽ được hỏi lần lượt.

Tin có phần chưa hiểu: bot hiện phần đã hiểu và phần chưa hiểu, **không lưu cả tin**. Sửa lại rồi gửi; bot chưa hỗ trợ lưu một phần. `1tr5` và `1tr500` đều là 1.500k; `10.000` vẫn là 10.000k. Các giá chưa có rule như `1tr50` bị từ chối. `bằng/bang/băng/bg` dùng ghi giá; `bảng` không phải dấu bằng.

Số 4 chữ số chỉ tách khi có danh sách rõ: ít nhất hai số 2 chữ số, có dấu phẩy/chấm, tất cả token dài 2 hoặc 4. Ví dụ `83,84,8968 98=50n`. `9497=50` hoặc `66 1000 68=50` bị từ chối. Range chỉ nhận đầu/đít tăng như `từ đầu 3 đến 8 ghép đít 3 đến 8=50`; range giảm bị từ chối; dấu `-` vẫn là dấu ngăn cách cũ.

Một người dùng cả Xiên ×14 và ×15: chọn bộ rồi gửi từng tin riêng. Một tin không trộn hai bộ. Tổng hiển thị hai dòng riêng. Mỗi bộ lưu bộ % riêng; hệ số khác Xiên 2 dùng chung theo profile.

Tin mới giữ bản sao tỷ lệ lúc nhập. Sửa profile không thay tiền của tin cũ. Muốn đổi tỷ lệ cho tin cũ trong bản này: xóa có xác nhận rồi nhập lại; không có chức năng đổi hàng loạt.

Tiền dùng đơn vị k (nghìn đồng), giống parser gốc. Giữ số lẻ khi tính; tổng thu/trả cuối làm tròn đến 1k: 10,5k → 11k, 10,4k → 10k. Phía Khách: hàng trừ % vượt thưởng thì thu; phía Chủ thì trả. Chiều ngược lại đảo thu/trả.

## Dữ liệu và giới hạn
Dữ liệu lưu trong data.sqlite3 cạnh chương trình, vẫn còn sau khi tắt. Sao lưu file này khi bot đã tắt; ZIP/source không chứa dữ liệu riêng.
Không chạy hai cửa sổ cùng token. Bot chỉ nhận chữ; chuyển giọng nói là chức năng điện thoại.
Bản này chưa có theo dõi thu/trả đã thanh toán, chốt/khóa ngày, tổng lợi nhuận, bảng thu chi sheet 3 hoặc kết quả nhiều ngày. Sửa/xóa vé được lưu lịch sử trong SQLite: raw cũ/mới, thời gian UTC, admin thực hiện. Xóa mềm giữ vé cũ để kiểm tra; không cộng lại message ID đã xóa.
Tên và % thật cần người dùng thêm bằng menu; không tự suy các tỷ lệ từ bảng đang làm dở.

## Nâng cấp dữ liệu cũ
1. Tắt bot, sao lưu nguyên file `data.sqlite3` trước khi nâng cấp.
2. Bản mới thêm cột lưu cách hiểu vé và dấu xóa mềm. Không tự tính lại vé cũ bằng parser mới.
3. Vé cũ chưa có cách hiểu đã lưu sẽ chặn tổng. Vào Sổ vé, dùng Xem raw để kiểm tra từng vé rồi Sửa tin với nội dung được xác nhận; thao tác này giữ tỷ lệ gốc và có audit. Đặc biệt rà lại `1tr5` từng được tính sai ở bản cũ.
4. Nếu rollback, tắt bot rồi phục hồi **cả source cũ và database đã sao lưu**. Không chạy source cũ với DB mới: source cũ không hiểu xóa mềm và có thể cộng lại vé đã xóa.

Vé mới lưu cả cách hiểu và cấu hình; đổi parser/profile không đọc lại raw của vé đó. Phép tính trung gian dùng Decimal 80 chữ số và báo lỗi nếu mất chữ số; % trên màn hình làm tròn nguyên k cho dễ nhìn; số % gốc vẫn dùng để tính. Tiền thu/trả cuối làm tròn sau khi cộng nợ cũ. Dữ liệu vượt khả năng số hỗ trợ bị chặn.

`results.py`, `legacy_bot.py` và toàn bộ test cũ giữ nguyên. `legacy_bot.py` chỉ là tham khảo, **không dùng để ghi/chốt tiền production**. Khi tích hợp module, chỉ lưu qua Ledger.add/replace: `calculate()` giữ behavior B mặc định Bao cho tương thích test cũ, còn Ledger bắt buộc xác nhận B.

Kiểm tra offline: `python -m compileall -q .` và `python -m unittest discover -v`. Test UI mô phỏng Telegram; không chứng minh bot chạy thật hoặc nguồn kết quả đúng.

## Nợ cũ và tổng mới

Chọn đúng người → **Nợ cũ** → gửi `THU 2356` (người đó nợ mình 2.356k), `TRẢ 2356` (mình nợ người đó), hoặc `0` để bỏ nợ cũ. Đây là **thay số dư**, không phải cộng thêm mỗi lần gửi. Tiền là k; số lẻ dùng dấu phẩy, không dùng dấu chấm ngăn nghìn.

Nợ cũ thuộc riêng từng người, theo góc nhìn admin cho cả Khách và Chủ. Khi Xem tổng có kết quả đúng ngày, bot cộng số dư ngày và nợ cũ chính xác rồi mới làm tròn. Nợ cũ không tự hết khi sang ngày hay xem tổng: khi đã thanh toán/cập nhật, tự nhập lại số dư hoặc 0. Đây không phải sổ giao dịch đã thanh toán.

Xem tổng chỉ hiện loại có tiền hàng. Khối THƯỞNG chỉ hiện loại trúng. X3 và AC hiện tiền gốc, ghi rõ hệ số và tiền thưởng thực tính vào tổng. Các loại khác hiện tiền thưởng thực. Sổ vé đọc cách hiểu đã lưu, không đọc lại raw; ×14/×15 lấy từ tỷ lệ lúc lưu từng tin.

Trước nâng cấp, tắt bot và sao lưu DB. Migration thêm `profiles.old_balance` mặc định 0 và lịch sử sửa số dư; không thay vé/tỷ lệ cũ. Test checkpoint và các giới hạn kiểm chứng xem DISPLAY_SETUP_REPORT.md.
