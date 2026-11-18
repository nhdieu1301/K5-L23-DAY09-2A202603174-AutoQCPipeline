# Báo cáo Day 09 — Nguyễn Hoàng Diệu, 2A202603174

## 1. Kết luận trước
Pipeline kết luận **Hold**. Lô đầu vào có **224** ảnh (`data/raw`), qua bước lọc cửa vào loại **21** ảnh lỗi và xuất **203** ảnh ra `submission/export/clean_v1`. Sau khi máy sửa xong toàn bộ lỗi bắt buộc (`0` ERROR) và người duyệt xem hết ngân sách **80/80** ảnh, vẫn còn **38/203** ảnh (**18,72%**) mang cảnh báo chưa duyệt, cao hơn ngưỡng **10,00%** nên chưa thể Release.

## 2. Lỗi và phân việc
Số liệu lấy từ `02_error_list_v1` (21 ảnh bị loại ở cửa vào từ 224 ảnh gốc, 203 ảnh đi tiếp vào bước kiểm nhãn):

| Mã lỗi | Số ảnh / dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `BAD_CLASS_NAME` | 1 file (`data.yaml`, 2 dòng) | Máy (`rename_classes`) | Viết hoa sai (`Person`, `Bus`), sửa lại cho khớp danh sách lớp chuẩn. |
| `CORRUPT_IMAGE` | 2 / 224 ảnh | Máy (`remove_image`) | Ảnh hỏng/cắt cụt không mở được, phải loại bỏ. |
| `BAD_SIZE` | 3 / 224 ảnh | Máy (`remove_image`) | Cạnh ngắn nhỏ hơn `250px` (`180px`, `226px`), không đủ độ nét để train. |
| `DUP_IMAGE_EXACT` | 8 / 224 ảnh | Máy (`remove_image`) | Trùng y hệt từng byte (MD5), giữ 1 bản và xoá bản lặp. |
| `DUP_IMAGE_NEAR` | 3 / 224 ảnh | Máy (`remove_image`) | Trùng gần đúng (`phash <= 8`), xoá bản trùng để tránh lặp dữ liệu. |
| `LEAK_TEST` | 5 / 224 ảnh | Máy (`remove_image`) | Trùng ảnh trong `data/test/images`, bắt buộc loại để tránh rò rỉ khi đo test. |
| `BAD_FORMAT` | 3 dòng (3 / 203 ảnh) | Máy (`drop_line`) | Dòng có giá trị `nan` hoặc thiếu cột (`4/5` cột), không cứu được nên xoá dòng. |
| `BAD_CLASS_ID` | 6 dòng (6 / 203 ảnh) | Máy (`drop_line`) | ID lớp nằm ngoài `0..3` (`-1`, `4`, `7`, `93`), xoá thẳng. |
| `BOX_ZERO` | 4 dòng (4 / 203 ảnh) | Máy (`drop_line`) | Chiều rộng hoặc chiều cao bằng `0`, box không có diện tích nên xoá. |
| `DUP_BOX` | 7 dòng (7 / 203 ảnh) | Máy (`drop_line`) | Hai box cùng lớp đè lên nhau `IoU > 0.9`, xoá dòng lặp phía sau. |
| `BOX_OUT_OF_IMAGE` | 8 dòng (8 / 203 ảnh) | Máy (`clip_box`) | Mép box lòi ra ngoài `[0, 1]` từ `0.023` đến `0.060`, cắt gọn lại về biên ảnh. |
| `MISSING_LABEL_FILE` | 6 / 203 ảnh | Người (`needs_label`) | Thiếu file `.txt`; máy không được tự bịa nhãn hay tạo file rỗng nên chuyển người gán. |
| `EMPTY_LABEL` | 12 / 203 ảnh | Người | File `.txt` rỗng có thể là ảnh nền thật hoặc bị xoá nhầm hết box, cần người nhìn lại. |
| `BOX_TINY` | 6 dòng (4 / 203 ảnh) | Người | Cạnh ngắn `8.9–11.9px < 12px`, cần người xem là vật ở xa hợp lệ hay box nhiễu. |
| `BOX_HUGE` | 3 dòng (3 / 203 ảnh) | Người | Box chiếm `97.0%–98.8%` diện tích ảnh (`> 95%`), dễ là lỗi kéo nhầm khung. |
| `CLASS_RARE` | 4 dòng (`<dataset>`) | Máy (gián tiếp) | Cảnh báo thống kê cho các ID rác `-1, 4, 7, 93`; tự biến mất sau khi `autofix` xoá `BAD_CLASS_ID`. |
| `POSSIBLE_MISSING` | 53 dòng (52 / 203 ảnh) | Người | Model `yolo26l` bắt được vật (`conf >= 0.6`) nhưng chưa có nhãn, cần người xác nhận vì model cũng có thể đoán nhầm. |
| `POSSIBLE_LOOSE_BOX` | 28 dòng (24 / 203 ảnh) | Người | Box nhãn trùng lớp với model nhưng `IoU` thấp (`0.30–0.49 < 0.5`), cần người kéo lại cho khít. |
| `POSSIBLE_FALSE_POS` | 25 dòng (24 / 203 ảnh) | Người | Box nhãn không khớp dự đoán nào của model (`IoU < 0.3`), nghi gán thừa hoặc vật bị che khuất. |
| `POSSIBLE_WRONG_CLASS` | 18 dòng (18 / 203 ảnh) | Người | Hai box đè khít (`IoU` `0.77–0.99`) nhưng khác lớp (`truck`/`car`, `car`/`person`), cần người phân loại lại. |

Hàng đợi `05_review_queue.csv` sắp xếp ảnh theo tổng trọng số lỗi cộng với độ tự tin `conf` của model. Do `NEEDS_LABEL` có trọng số cao nhất (10 điểm), toàn bộ `6/6` ảnh thiếu file nhãn được đẩy lên đầu hàng để xoá hết lỗi `ERROR`, sau đó mới tới các ảnh nghi sai lớp (3 điểm) và thiếu/thừa box (2 điểm). Với ngân sách 80 ảnh, người duyệt đã xử lý xong `6/6` ảnh thiếu file nhãn, `8/12` ảnh nhãn rỗng và **67/124** cảnh báo ngữ nghĩa của `second_opinion` (trong đó giải quyết được `15/18` ca sai lớp và `40/53` ca thiếu box).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | 8 | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` (`DUP_IMAGE_EXACT` giữ `1.00 / 1.00`) | Lỗi trùng làm xoá hẳn file ảnh nên bắt buộc giữ Precision = 1.00. Mức 2 bỏ sót một nửa số ca trùng gần đúng (Recall 0.50); từ 4 đến 14 Recall tăng lên 0.67 ổn định, nên chọn 8 ở khoảng giữa để tránh ngưỡng 20 bị sụp Recall exact xuống 0.33. |
| `second_opinion.conf` | 0.25 | 0.6 | `POSSIBLE_MISSING`: `0.50 / 1.00` → `0.57 / 1.00`<br>`POSSIBLE_WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83` | Ở 0.25, `POSSIBLE_MISSING` báo giả tới 50% làm tốn ngân sách 80 ảnh duyệt. Nếu đẩy lên 0.7–0.8 thì Recall của `POSSIBLE_MISSING` tụt xuống 0.88–0.75. Chọn 0.6 giữ nguyên Recall 1.00 cho thiếu nhãn mà vẫn lọc bớt cảnh báo nhiễu. |

**Chỗ calibration có thể đánh lừa:** Tập `calib` chỉ có 39 ảnh với bối cảnh khá rời nhau nên khi sweep, `phash_dist = 16` cho F1 cao nhất (`0.91`, `Precision = 1.00`). Nếu lấy mức 16 áp cho 224 ảnh `raw` vốn nhiều cảnh đường phố và đám đông giống nhau, máy rất dễ gộp nhầm ảnh khác nhau thành trùng và xoá oan. Khi kiểm tra `01_intake.txt` ở mức `8`, cả 3 cặp bị loại (`img_0076`–`img_0042` phash 0, `img_0143`–`img_0037` phash 0, `img_0223`–`img_0077` phash 6) đều là ảnh trùng thật. Ngoài ra, `POSSIBLE_FALSE_POS` dùng `fp_conf = 0.1` cố định nên Precision luôn là `0.36` bất kể chỉnh `conf`, dẫn tới vẫn còn 21 dòng tồn đọng sau khi duyệt.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- **(a) Kiểm chứng gate:** Chạy thử `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`. Vì ngân sách duyệt bằng 0 nên 6 ảnh `MISSING_LABEL_FILE` (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) không được gán nhãn và vẫn là `ERROR`. Gate đếm `n_errors = 6 >= 1`, kết luận **Rework**, trả về mã thoát **20** và không xuất thư mục `work/exp_nb`.
- **(b) Các điểm mù của pipeline:**
  1. *Bỏ sót vật bị che khuất hoặc ngoài ngưỡng tin cậy của model lớn:* Khi mở `img_0001` bằng `viz_labels.py`, người mặc quân phục đứng bên phải ảnh không có box; ở `img_0030` cũng sót vài người đứng sát biên sân. Nếu `yolo26l` đoán các người này với `conf < 0.6` thì `second_opinion` sẽ bỏ qua không báo.
  2. *Box cắt cụt hoặc trùm rộng vừa phải (`IoU >= 0.5`):* Trên `img_0030`, box `1:person` kéo trùm lên cả quả bóng chuyền và box `12:person` bị cắt ngang đầu gối, nhưng nếu phần giao với dự đoán của model vẫn đạt `IoU >= 0.5` thì máy không báo `POSSIBLE_LOOSE_BOX`. Các ca lệch lớp có IoU nằm trong `[0.3, 0.5)` cũng bị bỏ qua để tránh nhiễu.
  3. *Ảnh trùng biến đổi hình học mạnh:* `phash_dist = 8` bắt được ảnh nén hoặc thu phóng nhẹ, nhưng nếu ảnh bị lật ngang, xoay góc lớn hoặc crop sâu làm đổi cấu trúc tần số thấp thì khoảng cách pHash vượt quá 8 và lọt qua cửa vào.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chạy train `yolo26n`, `20` epoch, `2` seed (`0` và `1`), cùng tập `gold_val` (40 ảnh) và đánh giá trên `test` (100 ảnh):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.699 ± 0.025 | 0.486 ± 0.013 | 0.796 ± 0.050 | 0.596 ± 0.049 |

Chênh mAP50 (clean − raw) = **-0.027**.

- **So sánh với độ nhiễu & kết luận:** Độ lệch mAP50 giữa `clean` và `raw` là `-0.027`, gần bằng độ lệch chuẩn giữa 2 seed của `clean` (`±0.025`). Mức tăng Precision (`+0.032` so với độ lệch `±0.061` / `±0.050`) và mức giảm Recall (`-0.053` so với `±0.049`) cũng nằm quanh mức dao động ngẫu nhiên giữa các seed. Vì vậy kết luận trung thực là **chưa đủ cơ sở nói `clean` tốt hơn `raw`** ở lần chạy này: `clean` giúp mô hình dự đoán chắc tay hơn (Precision tăng từ `0.764` lên `0.796`) nhưng Recall giảm nên kéo mAP50 thấp hơn `0.027`.
- **Giả thuyết giải thích và cách kiểm:**
  1. *Tập `raw` bị rò rỉ 5 ảnh từ tập `test`:* Cửa vào đã chỉ ra 5 ảnh trong `raw` trùng thẳng với tập `test` (`img_0049`–`test_033`, `img_0101`–`test_039`, `img_0167`–`test_044`, `img_0174`–`test_085`, `img_0221`–`test_009`). Model train trên `raw` học thuộc luôn 5% tập test nên mAP50 bị đội lên `0.726`, còn `clean` đã loại bỏ 5 ảnh này. **Cách kiểm:** Đánh giá lại cả hai model trên 95 ảnh `test` sạch (bỏ 5 ảnh bị rò rỉ) để so công bằng.
  2. *Tập `clean` vẫn đang `Hold` và còn sót nhãn:* Do mới duyệt 80 ảnh, `07_error_list_v3.txt` vẫn còn `13` ca `POSSIBLE_MISSING` và `4` file `EMPTY_LABEL`. Khi train trên ảnh có vật thể chưa gán nhãn, model dự đoán đúng lại bị tính là sai nên Recall tụt xuống `0.596`. **Cách kiểm:** Tăng ngân sách duyệt lên ~120 ảnh để đưa tập dữ liệu sang `Release` rồi train lại.
  3. *Tập test nhỏ (100 ảnh) và số epoch ít (20 epoch):* Với 200 ảnh train và 100 ảnh test, vài box mấp mé ngưỡng IoU/conf thay đổi giữa các seed đủ tạo ra độ lệch `±0.025`. **Cách kiểm:** Train thử với 3–5 seed và tăng lên 40–50 epoch.
- **Việc tiếp theo:** Đo lại điểm trên 95 ảnh test không bị rò rỉ và duyệt nốt số ảnh còn cảnh báo để đưa `clean_v1` về trạng thái `Release` trước khi train lại.

## 6. Quyết định và ghi chú AI
- **(a) Quyết định cuối:** Giữ kết luận **Hold** (`0` lỗi bắt buộc, `38/203 = 18,72%` ảnh còn cảnh báo). Để chuyển thành **Release** (`warn_ratio < 10%`, tức dưới 20/203 ảnh), cần tăng ngân sách duyệt từ 80 lên khoảng **115–120 ảnh** nhằm xử lý thêm ít nhất 19 ảnh trong số 38 ảnh còn tồn đọng.
- **(b) Ghi chú dùng AI:**
  - *Prompt chính:* Yêu cầu viết từng module (`label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py`) theo đúng docstring có sẵn trong file khung, lấy ngưỡng từ `cfg`, không chạm vào `data/raw/` và giữ nguyên số dòng gốc khi file nhãn có dòng trống.
  - *Cách kiểm code AI:* Chạy `pytest` kiểm tra toàn bộ 79 unit test (gồm cả các ca biên dòng trống, nhiều lỗi trên 1 dòng), chạy `make calibrate` và `make run`, rồi dùng `viz_labels.py` mở ảnh kiểm tra chéo với `02_error_list_v1.txt`.
  - *1 lần AI sai:* Bản nháp đầu của `second_opinion.py` duyệt nhãn qua `ds.valid_boxes()` nên làm mất số dòng gốc, khiến `POSSIBLE_FALSE_POS` báo sai số dòng ở file có dòng trống ở giữa; chạy test phát hiện ra và đã sửa lại bằng cách đọc qua `ds.read_label_lines()`.