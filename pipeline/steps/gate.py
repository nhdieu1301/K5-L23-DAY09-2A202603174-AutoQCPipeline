"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""

from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    hold_threshold = cfg["gate"]["warn_ratio_hold"]
    stems_set = set(image_stems)
    reviewed_set = set(reviewed)

    n_images = len(stems_set)
    # Lỗi bắt buộc (ERROR) không bao giờ được bỏ qua kể cả khi ảnh đã duyệt
    n_errors = sum(1 for i in issues if i.severity == ERROR)

    # Cảnh báo (WARN) chỉ tính trên các ảnh thuộc tập hiện tại và chưa qua người duyệt
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stems_set and i.image not in reviewed_set
    }
    n_warn_images = len(warn_images)

    raw_ratio = (n_warn_images / n_images) if n_images > 0 else 0.0
    warn_ratio = round(raw_ratio, 4)

    if n_errors >= 1:
        decision = "Rework"
        reasons = [
            f"Còn {n_errors} lỗi bắt buộc (ERROR) chưa khắc phục nên chặn xuất bản (Rework)."
        ]
    elif n_images > 0 and raw_ratio >= hold_threshold:
        decision = "Hold"
        reasons = [
            f"Tỉ lệ ảnh còn cảnh báo chưa duyệt là {n_warn_images}/{n_images} "
            f"({warn_ratio:.2%}) >= ngưỡng {hold_threshold:.2%} (Hold)."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; tỉ lệ ảnh cảnh báo chưa duyệt là "
            f"{n_warn_images}/{n_images} ({warn_ratio:.2%}) < ngưỡng {hold_threshold:.2%} (Release)."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }