"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    lf_cfg = cfg["label_format"]
    overflow_tol = lf_cfg["overflow_tol"]
    min_box_px = lf_cfg["min_box_px"]
    max_box_frac = lf_cfg["max_box_frac"]
    dup_box_iou = lf_cfg["dup_box_iou"]
    n_classes = len(ds.classes)

    issues = []
    for lp in ds.label_files():
        stem = lp.stem
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        img_size = ds.image_size(stem)
        seen_boxes: list[tuple[int, float, float, float, float]] = []

        for line_no, text in lines:
            try:
                cid, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BAD_FORMAT",
                        stem,
                        f"dòng nhãn sai định dạng: {e}",
                        line=line_no,
                    )
                )
                continue

            if not (0 <= cid < n_classes):
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BAD_CLASS_ID",
                        stem,
                        f"id lớp ngoài phạm vi 0..{n_classes - 1}: {cid}",
                        line=line_no,
                        extra={"class_id": cid},
                    )
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_ZERO",
                        stem,
                        f"kích thước box <= 0 (w={w}, h={h})",
                        line=line_no,
                    )
                )
                continue

            # Kiểm tra tràn biên ảnh [0, 1]
            x1, y1 = cx - w / 2.0, cy - h / 2.0
            x2, y2 = cx + w / 2.0, cy + h / 2.0
            overflow = max(0.0, -x1, x2 - 1.0, -y1, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"box tràn khỏi ảnh {overflow:.4f} (> {overflow_tol})",
                        line=line_no,
                        extra={"overflow": round(overflow, 6)},
                    )
                )

            # Kiểm tra box lặp cùng lớp với các dòng trước đó
            curr_box = (cx, cy, w, h)
            for prev_cid, pcx, pcy, pw, ph in seen_boxes:
                if prev_cid == cid and iou_xywh(curr_box, (pcx, pcy, pw, ph)) > dup_box_iou:
                    issues.append(
                        Issue(
                            "label_format",
                            ERROR,
                            "DUP_BOX",
                            stem,
                            f"box trùng lặp cùng lớp {cid} (IoU > {dup_box_iou})",
                            line=line_no,
                        )
                    )
                    break
            seen_boxes.append((cid, cx, cy, w, h))

            # Cảnh báo kích thước quá nhỏ (tính theo pixel)
            if img_size is not None:
                img_w, img_h = img_size
                short_side_px = min(w * img_w, h * img_h)
                if short_side_px < min_box_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"cạnh ngắn box {short_side_px:.1f}px < {min_box_px}px",
                            line=line_no,
                            extra={"short_side_px": round(short_side_px, 2)},
                        )
                    )

            # Cảnh báo diện tích quá lớn
            area_frac = w * h
            if area_frac > max_box_frac:
                issues.append(
                    Issue(
                        "label_format",
                        WARN,
                        "BOX_HUGE",
                        stem,
                        f"diện tích box {area_frac:.3f} > {max_box_frac}",
                        line=line_no,
                        extra={"area_frac": round(area_frac, 4)},
                    )
                )

    return issues