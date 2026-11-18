"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""

from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMG_PREFIXES = ("DUP_IMAGE_",)
REMOVE_IMG_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove_image_code(code: str) -> bool:
    return code in REMOVE_IMG_CODES or code.startswith(REMOVE_IMG_PREFIXES)


def fix(ds, issues, cfg):
    fixes: list[dict] = []
    error_issues = [i for i in issues if i.severity == ERROR]

    # 1. Xử lý lỗi cấp dataset (data.yaml)
    if any(i.code == "BAD_CLASS_NAME" for i in error_issues) and ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        old_names = data.get("names", {})
        target_classes = list(cfg["classes"])
        current_map = ds.yaml_names()
        if [current_map.get(idx) for idx in range(len(target_classes))] != target_classes or len(current_map) != len(target_classes):
            data["names"] = target_classes
            if "nc" in data:
                data["nc"] = len(target_classes)
            ds.yaml_path.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            fixes.append(
                {
                    "image": "data.yaml",
                    "line": None,
                    "action": "rename_classes",
                    "before": str(old_names),
                    "after": str(target_classes),
                }
            )

    # 2. Xử lý xoá ảnh lỗi ở cửa vào (ưu tiên chạy trước để bỏ qua các lỗi dòng của ảnh đã xoá)
    removed_stems: set[str] = set()
    for iss in error_issues:
        if _is_remove_image_code(iss.code):
            stem = iss.image
            if stem in removed_stems:
                continue
            img_p = ds.image_path(stem)
            lbl_p = ds.label_path(stem)
            if img_p is None and not lbl_p.exists():
                removed_stems.add(stem)
                continue
            before_name = img_p.name if img_p is not None else stem
            if img_p is not None and img_p.exists():
                img_p.unlink()
            if lbl_p.exists():
                lbl_p.unlink()
            removed_stems.add(stem)
            fixes.append(
                {
                    "image": stem,
                    "line": None,
                    "action": "remove_image",
                    "before": before_name,
                    "after": "(đã xoá)",
                }
            )

    # 3. Ghi nhận ảnh thiếu file nhãn (không tạo file rỗng)
    seen_missing_label: set[str] = set()
    for iss in error_issues:
        if iss.code == "MISSING_LABEL_FILE":
            stem = iss.image
            if stem in removed_stems or stem in seen_missing_label:
                continue
            if not ds.label_path(stem).exists():
                seen_missing_label.add(stem)
                fixes.append(
                    {
                        "image": stem,
                        "line": None,
                        "action": "needs_label",
                        "before": "(không có file)",
                        "after": "chuyển người gán",
                    }
                )

    # 4. Gom lỗi theo từng file nhãn và số dòng gốc để sửa một lần
    line_codes_by_stem: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for iss in error_issues:
        if iss.image in removed_stems or iss.line is None:
            continue
        if iss.code in DROP_CODES or iss.code == "BOX_OUT_OF_IMAGE":
            line_codes_by_stem[iss.image][iss.line].add(iss.code)

    for stem in sorted(line_codes_by_stem):
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue

        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines: list[str] = []
        changed = False
        line_map = line_codes_by_stem[stem]

        for idx, orig_line in enumerate(raw_lines):
            line_no = idx + 1
            codes = line_map.get(line_no)
            if not codes:
                new_lines.append(orig_line)
                continue

            # Ưu tiên xoá dòng nếu dòng có bất kỳ lỗi nào thuộc nhóm DROP_CODES
            if codes & DROP_CODES:
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig_line.strip(),
                        "after": "(xoá dòng)",
                    }
                )
                continue

            # Xử lý BOX_OUT_OF_IMAGE: cắt toạ độ về [0, 1]
            try:
                cid, cx, cy, w, h = parse_yolo_line(orig_line)
            except ValueError:
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig_line.strip(),
                        "after": "(xoá dòng)",
                    }
                )
                continue

            nx1 = max(0.0, min(1.0, cx - w / 2.0))
            ny1 = max(0.0, min(1.0, cy - h / 2.0))
            nx2 = max(0.0, min(1.0, cx + w / 2.0))
            ny2 = max(0.0, min(1.0, cy + h / 2.0))
            nw = nx2 - nx1
            nh = ny2 - ny1

            if nw <= 1e-9 or nh <= 1e-9:
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig_line.strip(),
                        "after": "(xoá dòng)",
                    }
                )
                continue

            ncx = (nx1 + nx2) / 2.0
            ncy = (ny1 + ny2) / 2.0
            clipped_str = f"{cid} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
            if clipped_str != orig_line.strip():
                changed = True
                new_lines.append(clipped_str)
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": orig_line.strip(),
                        "after": clipped_str,
                    }
                )
            else:
                new_lines.append(orig_line)

        if changed:
            content = "\n".join(new_lines) + ("\n" if new_lines else "")
            lbl_p.write_text(content, encoding="utf-8")

    return fixes