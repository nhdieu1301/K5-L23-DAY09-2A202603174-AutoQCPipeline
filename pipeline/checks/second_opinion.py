"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""

from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg["second_opinion"]
    conf_thresh = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]
    n_classes = len(ds.classes)

    issues: list[Issue] = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue

        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        img_size = ds.image_size(stem)
        if img_size is None:
            continue
        img_w, img_h = img_size

        # Parse các dòng nhãn hợp lệ nhưng giữ nguyên số dòng gốc (1-based)
        valid_labels: list[tuple[int, int, float, float, float, float]] = []
        for line_no, text in raw_lines:
            try:
                cid, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if not (0 <= cid < n_classes) or w <= 0 or h <= 0:
                continue
            valid_labels.append((line_no, cid, cx, cy, w, h))

        img_preds = preds[stem]

        # 1. Duyệt từng dự đoán của model theo đúng thứ tự trong preds[stem]
        for p in img_preds:
            p_cls = int(p[0])
            p_conf = float(p[1])
            pcx, pcy, pw, ph = float(p[2]), float(p[3]), float(p[4]), float(p[5])
            area_px = (pw * img_w) * (ph * img_h)

            if p_conf < conf_thresh or area_px < min_area_px:
                continue

            p_box = (pcx, pcy, pw, ph)
            cands = [
                (l_cid, iou_xywh(p_box, (lcx, lcy, lw, lh)))
                for _, l_cid, lcx, lcy, lw, lh in valid_labels
            ]
            cands = [(l_cid, iou) for l_cid, iou in cands if iou >= iou_missing]

            if not cands:
                pred_name = ds.classes[p_cls] if 0 <= p_cls < n_classes else str(p_cls)
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model phát hiện {pred_name} (conf={p_conf:.2f}) nhưng không có box nhãn khớp",
                        line=None,
                        extra={"conf": round(p_conf, 4), "pred_class": p_cls},
                    )
                )
                continue

            same_cands = [iou for l_cid, iou in cands if l_cid == p_cls]
            if same_cands:
                best_same_iou = max(same_cands)
                if best_same_iou < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box nhãn khớp lỏng với model (IoU={best_same_iou:.2f} < {iou_loose})",
                            line=None,
                            extra={"conf": round(p_conf, 4), "iou": round(best_same_iou, 4)},
                        )
                    )
            else:
                best_other_iou, best_other_cls = max((iou, l_cid) for l_cid, iou in cands)
                if best_other_iou >= iou_match:
                    pred_name = ds.classes[p_cls] if 0 <= p_cls < n_classes else str(p_cls)
                    lbl_name = ds.classes[best_other_cls] if 0 <= best_other_cls < n_classes else str(best_other_cls)
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"nhãn ghi {lbl_name} nhưng model đoán {pred_name} (conf={p_conf:.2f}, IoU={best_other_iou:.2f})",
                            line=None,
                            extra={
                                "conf": round(p_conf, 4),
                                "iou": round(best_other_iou, 4),
                                "pred_class": p_cls,
                                "label_class": best_other_cls,
                            },
                        )
                    )

        # 2. Kiểm tra từng dòng nhãn hợp lệ xem có khớp dự đoán nào của model không (conf >= fp_conf, không lọc diện tích)
        fp_pred_boxes = [
            (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
            for p in img_preds
            if float(p[1]) >= fp_conf
        ]
        for line_no, l_cid, lcx, lcy, lw, lh in valid_labels:
            l_box = (lcx, lcy, lw, lh)
            max_iou = max((iou_xywh(l_box, p_box) for p_box in fp_pred_boxes), default=0.0)
            if max_iou < iou_missing:
                lbl_name = ds.classes[l_cid] if 0 <= l_cid < n_classes else str(l_cid)
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"box nhãn ({lbl_name}) không khớp dự đoán nào của model (max IoU={max_iou:.2f} < {iou_missing})",
                        line=line_no,
                        extra={"iou": round(max_iou, 4)},
                    )
                )

    return issues