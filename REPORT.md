# Bản vá an toàn — 06-10-2026

**NOT READY FOR PRODUCTION.** Không phát hiện sai tiền trong các fixture đã chạy; không suy ra mọi input/nguồn kết quả đều đúng. Chưa kiểm chứng Telegram thật, nguồn kết quả online và vận hành; một số rule còn conflict.

Baseline: main commit `6ad2add50155bbcc790b2392bdb2393ea8151a6e`. Đã đọc calculator.py, results.py, accounting.py, bot.py, legacy_bot.py, các test cũ, README và REPORT trước khi patch. Không rewrite project.

## Pipeline hiện tại

| Bước | Source / hành vi |
|---|---|
| RAW TEXT | bot.handle nhận chữ trong chat riêng của admin, theo profile/ngày |
| Normalize | calculator.normalize xử lý alias/đơn vị; alias giá xét trước bỏ dấu để không nhầm bảng |
| Tách loại/clause | _prepare_lines gom header/dòng giá; _category_segments tách loại; MONEY_RE tách khoản giá |
| Số và giá | parse_de_numbers_detailed / parse_xien_groups / parse_quay_sets / parse_cang_numbers; parse_money dùng đơn vị k |
| Entry / calculate | Entry giữ số, giá mỗi vé, số vé, nhóm Xiên; Calculation giữ entries và rejected |
| Xác nhận / lưu | propose_b_choice dùng lại logic legacy; checked_calculation chặn B chưa chọn và bất kỳ rejected; Ledger lưu Entry + config |
| Dò thưởng | _winning_for_entry của results.py; accounting xử lý Càng exact/Áp riêng; kiểm tra đúng ngày, 27 số và ĐB 5 số |
| Accounting | đọc snapshot, không parse lại raw; hàng, % và thưởng Decimal; X2 ×14/×15 riêng; Khách/Chủ đảo chiều |
| Tổng / UI | summary kiểm tra bảng/ngày, làm tròn HALF_UP cuối đến 1k; lỗi không chốt tiền |

## Những file sửa/thêm

| File | Thay đổi |
|---|---|
| calculator.py | Giá triệu dính; alias giá có kiểm soát; split 4 chữ số trong list rõ; đầu,đít; range đầu/đít tăng; báo lỗi prefix/tail/chữ lạ thay vì bỏ qua; named set match trọn; độ chính xác Decimal |
| accounting.py | Chặn B chưa xác nhận; reject toàn tin; Entry snapshot; migration chặn vé cũ chưa kiểm tra; duplicate insert nguyên tử; audit edit/delete cùng transaction; soft delete; validation kết quả/ngày/bảng/snapshot/tỷ lệ; sửa variant chưa cấu hình |
| bot.py | Hỏi Bao/Đề bộ trước add/edit; message ID gốc; nhiều B hỏi lần lượt; hủy pending khi menu/bảng/ngày/config đổi hoặc hết 5 phút; chặn xóa qua bảng khác; xử lý duplicate đã xóa; lỗi /tong; UTC+7 có sẵn |
| test_safety_parser.py | 62 golden/negative/precision tests |
| test_safety_accounting.py | 29 reward/accounting/data tests |
| test_safety_ui.py | 11 luồng UI offline |
| README.md, REPORT.md | Cú pháp, nâng cấp/rollback, phạm vi và bằng chứng |

Không sửa results.py, legacy_bot.py hoặc bất kỳ test cũ nào. Đã so byte-for-byte với baseline.

## Behavior thay đổi chính xác

- `1tr5=1500k`, không còn 1005k. `1tr500`, `1triệu500`, `1,5tr`, `1.5tr` bằng 1500k; `1tr/1triệu=1000k`; `100nghìn/100ngan/100n=100k`. Đuôi triệu 1 hoặc 3 chữ số được hỗ trợ; 2/4 chữ số chưa có rule bị reject. `10.000=10000k` giữ nguyên.
- Bằng/bang/băng/bg nhận khi theo sau là giá. Từ khác bỏ dấu thành bang, như bảng/bàng, giữ là nội dung chưa hiểu qua mọi lượt normalize; không đổi thành dấu bằng.
- Split 4 chữ số chỉ khi toàn thân vé là list token 2/4 chữ số, có ít nhất hai token 2 chữ số và dấu phẩy/chấm chứng minh list. Không áp dụng cho ABC, cặp/đảo hay chuỗi đứng riêng. List chỉ có dấu cách và số dài vẫn reject.
- Đầu/đít nhận digit set dính theo rule ghép cũ. `đầu,đít 0` theo combined cũ: 20 vé, 00 hai lượt. Chỉ thêm range bằng từ “đến” cho đầu/đít tăng; không bung range chung hoặc giảm. Không mở separator mới; `/ -` và `đầu + đít` vốn có trong source giữ nguyên.
- Prefix/tail lạ, token dài trong Bao/Xiên, chữ lạ trong list không bị bỏ qua. Dàn có tên match đầy đủ. Hậu tố `/1cặp` giữ theo test cũ.
- Tin có entries và rejected hiển thị đã hiểu/chưa hiểu nhưng không lưu. Không khẳng định phần đã parse của tin có ranh giới mơ hồ đủ an toàn để lưu riêng.
- Vé mới chụp Entry/config. Vé cũ thiếu Entry snapshot không tự đọc lại bằng parser mới; tổng bị chặn đến khi owner kiểm tra và sửa/xác nhận.
- Audit sửa/xóa: raw cũ, raw mới (null khi delete), UTC timestamp, actor admin. Xóa mềm giữ UNIQUE message ID; delivery cũ không phục hồi vé. Update và audit cùng transaction; lỗi rollback.
- Decimal precision 80 với trap Inexact cho phép tính trung gian; không âm thầm mất chữ số. Giá/config vượt khả năng hỗ trợ được báo lỗi; bước HALF_UP cuối mới cho phép làm tròn. Config được kiểm tra hữu hạn, độ dài, exponent hỗ trợ.

## Golden đã kiểm tra

| Case | Kết quả khóa trong test |
|---|---|
| A37 | 86,89,80 mỗi số230; 98 giá550; hàng1240k |
| A50 | 9497 →94,97; giữ số lặp; 27 vé ×20 =540k |
| A91 | 6×6 ghép đúng thứ tự set162738; 1800k |
| A128 | Hai set345678; 36 vé ×50 =1800k |
| A132 | 36 vé ×550 và 56,88 ×100; 20000k |
| A155 | Đầu,đít0: 20 vé ×30 =600k; 00 hai vé |
| 83,84,8968 98=50n | 83,84,89,68,98; 250k |
| Giá00 | Reject, không sửa giá |
| B91=175k / b20b500k | Hai cách hiểu; Ledger không lưu trước chọn; UI giữ message ID gốc |
| Bao nhiều nháy | Bao12 giá10, hai nháy12 → thưởng70k |
| Xiên2/3/4 | Đúng nhóm; thưởng150/480/1800k khi giá10 |
| Quây2 / Quây | Đúng tổ hợp; không sinh chéo ngoài nhóm |
| Càng exact / Áp | Exact312 giá10 →4000; Áp412 →100; exact không cộng Áp |
| ×14 / ×15 | Thưởng/% riêng theo snapshot, config sau không đổi vé cũ |
| Dữ liệu | Duplicate đồng thời, edit/audit, soft delete/audit, isolation, migration, snapshot hỏng, result sai ngày/thiếu số |

Negative gồm bảng, 9497 đứng riêng, `66 1000 68=50`, `123 4567=50`, range giảm, =00, đảo4 chữ số, giá triệu chưa định nghĩa, unknown tail/prefix, unknown Bao/Xiên, exclusions chưa có rule, precision quá dài và normalize alias nhiều lần.

## Giữ nguyên / conflict cần xác nhận

1. **Dàn 48 đang giữ nguyên behavior hiện tại, chờ xác nhận business rule:** reject. Test cũ khóa reject.
2. **Đề cặp88:** giữ hai vé theo source/test, chờ xác nhận rule cuối; không tự đổi thành một vé.
3. **Partial production:** reject toàn tin. Cần chính sách được xác nhận và chứng minh ranh giới trước khi cho lưu riêng.
4. **Conflict ABC:** yêu cầu nói context cặp/đảo, nhưng test cũ `test_compact_reversed_de_pairs_keep_palindrome_twice` và `test_latest_de_formats_keep_their_exact_ticket_rules` yêu cầu ABC không keyword cũng tách. Dừng thay đổi behavior này, giữ legacy và thêm test khóa. Không dùng ABC tách4 chữ số.
5. **B trong calculate():** test cũ yêu cầu mặc định Bao. Giữ API thấp này; đường lưu qua Ledger chặn B bằng propose_b_choice. Không dùng calculate/legacy_bot như API tự chốt tiền.
6. Chạm/chập/kép/kép lệch và dàn cao/thấp/chẵn/lẻ giữ tập có sẵn. Source không định nghĩa sát chập/sát kép/kép bằng như dàn riêng, hoặc bỏ chập/bỏ kép/bỏ sát kép: reject, không sáng tác tập. “Bỏ kép lệch” không partial-match thành “bỏ kép”.

## Verification

Baseline trước patch: 78/78 PASS.

| Nhóm | Kết quả |
|---|---|
| OLD TESTS | PASS78 / FAIL0 |
| NEW GOLDEN TESTS (toàn bộ test mới) | PASS102 / FAIL0: parser62 + accounting29 + UI11 |
| TOTAL | PASS180 / FAIL0 |
| PARSER REGRESSION | PASS: 67 cũ +62 mới |
| ACCOUNTING | PASS: 5 cũ +29 mới |
| SECURITY/DATA | PASS trong phạm vi offline: isolation, duplicate đồng thời, audit, soft delete, snapshots, migration, UI xác nhận |
| Python compile toàn bộ .py | PASS, gồm run.py và legacy_bot.py |

Lệnh: `python -m compileall -q .`; `python -m unittest discover -v`. Không chỉ dựa test cũ: golden khóa số/giá/tổng cụ thể; negative và SQLite/handler kiểm tra riêng.

NOT RUN: thư viện Telegram thật, bot/kết nối Telegram thật, fetch AZ24 online, launcher Windows/macOS thật, load/stress test và khôi phục backup vận hành thật. UI dùng mock; concurrency test chỉ chứng minh SQLite duplicate trên máy test. results.py giữ nguồn latest và fallback cache; định dạng/ngày đúng không chứng minh nội dung nguồn đúng. Chưa đối chiếu độc lập kết quả.

## TODO / rủi ro còn lại

- Xác nhận rule còn conflict, đặc biệt ABC: người dùng có thể kỳ vọng tiền khác legacy. Không tuyên bố hết lỗi có khả năng sai tiền.
- Chốt/khóa/mở khóa ngày bởi admin chưa triển khai, không scaffold nửa vời. Cần khóa đồng nhất add/edit/delete, snapshot kết quả, audit mở khóa và test cạnh tranh.
- Kết quả nhiều ngày, xác nhận nguồn, kết quả chốt bất biến chưa có. Nguồn/cache sai cùng ngày vẫn có thể làm thưởng sai; cần kiểm chứng trước tiền thật.
- Giới hạn tải/tổ hợp Xiên quây và thử tải chưa có; dàn lớn có thể tốn bộ nhớ/thời gian. Không tự giảm tổ hợp để tính tiền.
- DB thật cần tắt bot/sao lưu/rà vé cũ. Rollback cần source cũ + backup DB; không source cũ + DB mới có soft delete.
- Audit có raw/time/admin nhưng chưa có UI xem/phục hồi; không thể khôi phục lịch sử trước nâng cấp.

Kết luận: case bắt buộc đã kiểm tra đều đạt; rule chưa chốt giữ nguyên hoặc reject. **NOT READY FOR PRODUCTION** đến khi xử lý conflict và kiểm chứng nguồn/vận hành thực tế. Không deploy/chạy token thật trong task này.
