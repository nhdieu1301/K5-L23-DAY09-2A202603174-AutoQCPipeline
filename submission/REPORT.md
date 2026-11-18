# Báo cáo Day 09 — Nguyễn Hoàng Diệu, 2A202603174

## 1. Kết luận trước
Pipeline kết luận **Hold**. Từ **224** ảnh đầu vào (`data/raw`), bước lọc cửa vào loại **21** ảnh lỗi và xuất **203** ảnh sang `submission/export/clean_v1`. Sau khi máy tự sửa xong toàn bộ lỗi cú pháp và người duyệt dùng hết ngân sách **80/80** ảnh, tập dữ liệu còn **0** lỗi bắt buộc (`ERROR`) nhưng vẫn còn **38/203** ảnh (**18,72%**) mang cảnh báo chưa duyệt, vượt ngưỡng cho phép **10,00%** của cổng chặn.

## 2. Lỗi và phân việc
Tổng hợp từ `02_error_list_v1` trên **224** ảnh thô (21 ảnh bị loại ở cửa vào và 203 ảnh qua bước kiểm nhãn):

| Mã lỗi | Số ảnh / dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `BAD_CLASS_NAME` | 1 file (`data.yaml`, 2 dòng) | Máy (`rename_classes`) | Sai chữ hoa/thường (`Person`, `Bus`), chuẩn hoá lại đúng thứ tự `cfg["classes"]` mà không đổi ngữ nghĩa. |
| `CORRUPT_IMAGE` | 2 / 224 ảnh | Máy (`remove_image`) | File ảnh hỏng/cắt cụt (`UnidentifiedImageError`, `OSError`), không thể dùng để huấn luyện. |
| `BAD_SIZE` | 3 / 224 ảnh | Máy (`remove_image`) | Cạnh ngắn dưới `250px` (`180px`, `226px`), mất chi tiết vật thể theo quy tắc dự án. |
| `DUP_IMAGE_EXACT` | 8 / 224 ảnh | Máy (`remove_image`) | Trùng từng byte (MD5), giữ lại bản đầu tiên và xoá bản lặp để tránh lệch phân phối. |
| `DUP_IMAGE_NEAR` | 3 / 224 ảnh | Máy (`remove_image`) | Trùng gần đúng (`phash <= 8`), xoá bản lặp để tránh rò rỉ nội dung giữa các mẫu. |
| `LEAK_TEST` | 5 / 224 ảnh | Máy (`remove_image`) | Trùng ảnh trong `data/test/images`, bắt buộc loại để đảm bảo đánh giá công bằng. |
| `BAD_FORMAT` | 3 dòng (3 / 203 ảnh) | Máy (`drop_line`) | Dòng chứa `nan` hoặc thiếu cột (`4/5` cột), không khôi phục được toạ độ nên xoá dòng. |
| `BAD_CLASS_ID` | 6 dòng (6 / 203 ảnh) | Máy (`drop_line`) | ID lớp nằm ngoài `0..3` (`-1`, `4`, `7`, `93`), vi phạm danh mục lớp cố định. |
| `BOX_ZERO` | 4 dòng (4 / 203 ảnh) | Máy (`drop_line`) | Chiều rộng hoặc chiều cao bằng `0.0`, box vô nghĩa về mặt hình học. |
| `DUP_BOX` | 7 dòng (7 / 203 ảnh) | Máy (`drop_line`) | Hai box cùng lớp chồng lấn `IoU > 0.9` trên cùng ảnh, xoá dòng trùng phía sau. |
| `BOX_OUT_OF_IMAGE` | 8 dòng (8 / 203 ảnh) | Máy (`clip_box`) | Mép box tràn ngoài `[0, 1]` từ `0.023` đến `0.060`, cắt gọn về biên ảnh an toàn. |
| `MISSING_LABEL_FILE` | 6 / 203 ảnh | Người (`needs_label`) | Ảnh không có file `.txt`; máy không được tự bịa nhãn hay tạo file rỗng nên chuyển người gán. |
| `EMPTY_LABEL` | 12 / 203 ảnh | Người | File `.txt` rỗng có thể là ảnh nền sạch hoặc người gán bỏ sót toàn bộ vật thể, cần mắt người xác nhận. |
| `BOX_TINY` | 6 dòng (4 / 203 ảnh) | Người | Cạnh ngắn `8.9–11.9px < 12px`; cần người xem là vật quá nhỏ cần bỏ hay vật ở xa hợp lệ. |
| `BOX_HUGE` | 3 dòng (3 / 203 ảnh) | Người | Diện tích chiếm `97.0%–98.8%` khung hình (`> 95%`), dễ là box kéo nhầm trùm toàn ảnh. |
| `CLASS_RARE` | 4 dòng (`<dataset>`) | Máy (gián tiếp) | Cảnh báo thống kê cho các ID rác `-1, 4, 7, 93` (1–2 box); tự hết sau khi `autofix` xoá các dòng `BAD_CLASS_ID`. |
| `POSSIBLE_MISSING` | 53 dòng (52 / 203 ảnh) | Người | Model `yolo26l` phát hiện vật (`conf >= 0.6`) chưa có box nhãn, nhưng model cũng có thể nhận nhầm nền. |
| `POSSIBLE_LOOSE_BOX` | 28 dòng (24 / 203 ảnh) | Người | Box nhãn khớp cùng lớp nhưng `IoU` chỉ đạt `0.30–0.49` (`< 0.5`), cần người chỉnh lại biên cho khít. |
| `POSSIBLE_FALSE_POS` | 25 dòng (24 / 203 ảnh) | Người | Box nhãn có `IoU < 0.3` với mọi dự đoán của model (`conf >= 0.1`), nghi ngờ gán thừa hoặc vật bị che khuất. |
| `POSSIBLE_WRONG_CLASS` | 18 dòng (18 / 203 ảnh) | Người | Chồng lấn cao (`IoU` tới `0.77–0.99`) nhưng lệch lớp (vd. `truck` vs `car`, `car` vs `person`), cần người phân định ngữ nghĩa. |

- **Cách xếp hàng đợi (`05_review_queue.csv`):** Pipeline tính điểm ưu tiên từng ảnh bằng tổng trọng số lỗi (`NEEDS_LABEL: 10`, `POSSIBLE_WRONG_CLASS: 3`, `POSSIBLE_MISSING: 2`, `POSSIBLE_FALSE_POS: 2`, `POSSIBLE_LOOSE_BOX: 1.5`, `EMPTY_LABEL: 1`, `BOX_HUGE: 0.5`, `BOX_TINY: 0.3`) kết hợp độ tin cậy `conf`. Nhờ vậy, `6/6` ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) được đẩy lên đầu hàng để xoá sạch lỗi `ERROR`, tiếp theo là các ảnh bị cờ sai lớp hoặc bỏ sót vật thể với `conf` cao.
- **Hiệu quả trong ngân sách 80 ảnh:** Người duyệt xử lý trọn vẹn `6/6` ảnh thiếu file nhãn, `8/12` ảnh nhãn rỗng (`EMPTY_LABEL`) và **67/124** cảnh báo ngữ nghĩa của `second_opinion` (trong đó giải quyết được `15/18` ca `POSSIBLE_WRONG_CLASS` và `40/53` ca `POSSIBLE_MISSING`).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | `8` | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` (`DUP_IMAGE_EXACT` giữ `1.00 / 1.00`) | Lỗi trùng kích hoạt xoá vĩnh viễn ảnh (`remove_image`) nên phải giữ `Precision = 1.00`. Mức `2` bỏ sót một nửa ảnh trùng gần đúng (`Recall = 0.50`); dải `4–14` nâng Recall lên `0.67` mà vẫn an toàn, chọn `8` làm điểm giữa để tránh vùng sụp đổ ở `20` (`Recall` exact tụt còn `0.33`). |
| `second_opinion.conf` | `0.25` | `0.6` | `POSSIBLE_MISSING`: `0.50 / 1.00` → `0.57 / 1.00`<br>`POSSIBLE_WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83` | Ở `0.25`, `POSSIBLE_MISSING` có tới `50%` báo động giả (`P = 0.50`), gây lãng phí ngân sách 80 ảnh duyệt. Tăng lên `0.7–0.8` làm rơi Recall của `POSSIBLE_MISSING` xuống `0.88–0.75`. Tại `0.6`, pipeline vẫn bắt đủ `100%` vật thiếu nhãn trên calib đồng thời giảm nhiễu cho hàng đợi. |

- **Điểm calibration có thể đánh lừa:** Tập `data/calib` chỉ có **39 ảnh** với bối cảnh phân tán nên trên bảng sweep, `phash_dist = 16` đạt `Precision = 1.00, F1 = 0.91` (cao nhất). Tuy nhiên nếu tin theo số này để đặt `16` cho **224 ảnh `raw`** cùng chủ đề giao thông/đám đông, nhiều ảnh chụp cùng góc phố sẽ bị gộp nhầm là trùng và bị xoá oan. Khi kiểm tra thực tế `01_intake.txt` với ngưỡng `8`, 3 cặp bị loại (`img_0076`–`img_0042` phash `0`, `img_0143`–`img_0037` phash `0`, `img_0223`–`img_0077` phash `6`) đều là ảnh trùng thực sự, không xoá nhầm ảnh khác nhau. Ngoài ra, `POSSIBLE_FALSE_POS` luôn giữ `Precision = 0.36` ở mọi mức `conf` do dùng ngưỡng cứng `fp_conf = 0.1`, nên vẫn chiếm `21` dòng cảnh báo còn tồn đọng sau duyệt.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- **(a) Kiểm chứng cửa chặn (`Gate`):** Khi chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`, ngân sách người duyệt bằng `0` nên **6/6** ảnh `MISSING_LABEL_FILE` (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) không được bổ sung nhãn và giữ nguyên mức `ERROR`. Hàm `gate.decide()` ghi nhận `n_errors = 6 >= 1`, trả về kết luận **Rework**, thoát với mã **`20`** và không xuất bộ dữ liệu sạch sang `work/exp_nb`.
- **(b) Các điểm mù của pipeline:**
  1. *Bỏ sót vật thể bị che khuất hoặc ngoài tầm tự tin của model lớn:* Khi soi trực tiếp ảnh `img_0001` bằng `viz_labels.py`, người mặc quân phục đứng bên phải khung hình hoàn toàn chưa có box nhãn; tương tự ở `img_0030`, một số người chơi đứng dọc biên sân cũng bị sót. Nếu `yolo26l` dự đoán các đối tượng này với `conf < 0.6`, `second_opinion` sẽ bỏ qua không cảnh báo.
  2. *Box cắt cụt hoặc trùm rộng ở mức trung bình (`IoU >= 0.5`):* Trên `img_0030`, box `1:person` trùm lên cả quả bóng chuyền phía trên đầu và box `12:person` bị cắt ngang đầu gối, nhưng nếu phần giao với dự đoán của model vẫn đạt `IoU >= 0.5` thì không kích hoạt `POSSIBLE_LOOSE_BOX`. Tương tự, các ca sai lớp có `IoU` nằm trong khoảng `[0.3, 0.5)` cũng im lặng theo thiết kế để tránh nhiễu.
  3. *Ảnh trùng biến đổi hình học mạnh:* `phash_dist = 8` bắt tốt ảnh nén lại hoặc thu phóng nhẹ (phash `0–6`), nhưng nếu ảnh bị xoay góc lớn, lật ngang hoặc crop sâu làm thay đổi cấu trúc tần số thấp, khoảng cách Hamming sẽ vượt quá `8` và lọt qua bước lọc trùng.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Thí nghiệm huấn luyện cùng cấu hình (`yolo26n`, `20` epoch, `2` seed: `0` và `1`, cùng tập `gold_val` 40 ảnh và đánh giá trên `test` 100 ảnh):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.699 ± 0.025 | 0.486 ± 0.013 | 0.796 ± 0.050 | 0.596 ± 0.049 |

Chênh mAP50 (clean − raw) = **-0.027**.

- **So sánh chênh lệch với độ nhiễu & kết luận trung thực:** Chênh lệch mAP50 là `-0.027`, xấp xỉ `1,08` lần độ lệch chuẩn giữa các seed của `clean` (`±0.025`). Tương tự, mức tăng Precision (`+0.032`, nằm gọn trong `±0.061` của `raw` và `±0.050` của `clean`) và mức giảm Recall (`-0.053` vs `±0.049`) đều dao động quanh ngưỡng 1 độ lệch chuẩn với cỡ mẫu chỉ 2 seed. Do đó, kết luận trung thực là **chưa thể khẳng định `clean` cho mAP cao hơn `raw`** ở vòng chạy này: `clean` giúp mô hình dự đoán chắc chắn hơn (Precision tăng từ `0.764` lên `0.796`), nhưng Recall bị kéo giảm (`0.649` xuống `0.596`) khiến mAP tổng thể thấp hơn `raw` `0.027`.
- **Các giả thuyết giải thích và cách kiểm chứng:**
  1. *Rò rỉ tập test (`LEAK_TEST`) làm điểm của `raw` cao giả tạo:* Bước lọc cửa vào (`01_intake.txt`) đã phát hiện `5/224` ảnh trong `raw` trùng trực tiếp với tập `test` (`img_0049`–`test_033`, `img_0101`–`test_039`, `img_0167`–`test_044`, `img_0174`–`test_085`, `img_0221`–`test_009`) cùng `11` ảnh trùng nội bộ. Khi train trên `raw`, mô hình học thuộc lòng `5%` số ảnh của tập `test` (100 ảnh) nên mAP50 bị đội lên `0.726`, còn `clean` đã loại sạch nhóm rò rỉ này. **Cách kiểm:** Đánh giá lại cả hai checkpoint `raw` và `clean` trên `95` ảnh `test` sạch (loại bỏ 5 ảnh bị rò rỉ) để so sánh năng lực tổng quát hoá thực chất.
  2. *Cảnh báo thiếu nhãn còn tồn đọng trong `clean` (`Hold`) làm giảm Recall:* Do ngân sách duyệt dừng ở `80` ảnh (`Hold`), `07_error_list_v3.txt` vẫn còn `38/203` ảnh mang cảnh báo chưa duyệt, gồm `13` ca `POSSIBLE_MISSING` (vd. `img_0183` person `conf=0.81`, `img_0160` truck `conf=0.78`) và `4` file `EMPTY_LABEL` (`img_0013`, `img_0097`, `img_0129`, `img_0192`). Việc giữ các vật thể chưa được gán nhãn trong ảnh train khiến mô hình bị phạt mỗi khi dự đoán trúng chúng, trực tiếp kéo giảm Recall (`0.596`). **Cách kiểm:** Tăng ngân sách duyệt lên `120` ảnh để pipeline đạt `Release` (`warn_ratio < 10%`), sau đó train lại với cùng 2 seed để kiểm tra mức phục hồi của Recall và mAP50.
  3. *Biến động của tập test nhỏ (100 ảnh) và số epoch ít (20 epoch):* Với 200 ảnh train và 100 ảnh test, chỉ vài dự đoán mấp mé ngưỡng IoU/conf thay đổi giữa các seed đã tạo ra độ lệch `±0.025` ở `clean`. **Cách kiểm:** Chạy mở rộng lên `3–5` seed (`seeds 0..4`) và tăng lên `30–50` epoch để thu hẹp khoảng biến thiên.
- **Việc tiếp theo:** Chạy đánh giá tách riêng 5 ảnh rò rỉ trên tập `test`, đồng thời bổ sung duyệt `~40` ảnh còn tồn đọng để đưa `clean_v1` từ `Hold` sang `Release` trước khi huấn luyện lại.

## 6. Quyết định và ghi chú AI
- **(a) Quyết định cuối & điều kiện chuyển thành Release:** Giữ nguyên quyết định **Hold** (`0` lỗi bắt buộc, `38/203 = 18,72%` ảnh còn cảnh báo chưa duyệt). Để chuyển sang **Release** (`warn_ratio < 10,00%`, tức dưới `20/203` ảnh), cần nâng ngân sách duyệt người từ **80** lên khoảng **115–120 ảnh** (xử lý thêm tối thiểu `19` ảnh đang xếp đầu trong `38` ảnh còn cảnh báo, ưu tiên `13` ca `POSSIBLE_MISSING`, `3` ca `POSSIBLE_WRONG_CLASS` và `4` ảnh `EMPTY_LABEL` còn lại).
- **(b) Ghi chú sử dụng AI:**
  - *Prompt chính:* Yêu cầu viết hoàn thiện từng module (`label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py`) theo đúng docstring và schema `Issue` trong `pipeline/common.py`, đọc toàn bộ ngưỡng từ dict `cfg` thay vì viết cứng, xử lý an toàn dòng hỏng/dòng trống và không chỉnh sửa `data/raw/`.
  - *Cách kiểm code AI:* Chạy `python -m pytest -q` kiểm tra toàn bộ **79 unit test** (gồm cả các ca biên dòng trống, nhiều lỗi trên một dòng, tập rỗng), sau đó chạy `make calibrate` và `make run` rồi đối chiếu trực tiếp log trong `02_error_list_v1.txt` với ảnh vẽ từ `scripts/viz_labels.py`.
  - *Một lần AI sai:* Ở bản nháp đầu của `second_opinion.py`, AI dùng `ds.valid_boxes(stem)` để duyệt nhãn khi kiểm tra `POSSIBLE_FALSE_POS` khiến `Issue.line` bị lệch số dòng trên các file có dòng trống ở giữa; đã phát hiện qua test `test_false_positive_line_number_survives_blank_lines` và sửa lại bằng cách đọc `ds.read_label_lines(stem)` để giữ nguyên số dòng gốc.