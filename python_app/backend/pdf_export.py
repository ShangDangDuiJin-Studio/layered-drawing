"""Export layout parts to single-page A4 PDF (1:1 mm scaling, MATLAB-compatible intent)."""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Polygon

from .contours import mask_to_contours
from .layout import PlacedPart


@dataclass
class PdfConfig:
    margin_mm: float = 15.0
    a4_width_mm: float = 210.0
    a4_height_mm: float = 297.0
    dpi: int = 96
    part_expand_mm: float = 3.0


def _part_mask(rgba: np.ndarray) -> np.ndarray:
    if rgba.shape[2] >= 4:
        return rgba[:, :, 3] > 0
    return np.any(rgba[:, :, :3] > 0, axis=2)


def _expand_mask_by_mm(mask: np.ndarray, expand_mm: float, mm_per_px: float) -> np.ndarray:
    """Expand a binary mask outward by a physical distance (mm)."""
    if expand_mm <= 0:
        return mask
    radius_px = int(round(expand_mm / mm_per_px))
    if radius_px <= 0:
        return mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius_px + 1, 2 * radius_px + 1))
    expanded = cv2.dilate(mask.astype(np.uint8), kernel, iterations=1)
    return expanded > 0


def export_layout_pdf(
    placed: list[PlacedPart],
    out_buffer: io.BytesIO | None = None,
    cfg: PdfConfig | None = None,
) -> bytes:
    if cfg is None:
        cfg = PdfConfig()

    if not placed:
        raise ValueError("没有可导出的部件")

    mm_per_px = 25.4 / cfg.dpi

    # Collect global bounds in layout coordinates
    all_x1, all_y1, all_x2, all_y2 = [], [], [], []
    draw_items: list[tuple[np.ndarray, tuple[float, float, float], int, int]] = []

    for part in placed:
        m = _part_mask(part.rgba)
        if not np.any(m):
            continue
        local_ys, local_xs = np.where(m)
        ly1, ly2 = int(local_ys.min()), int(local_ys.max()) + 1
        lx1, lx2 = int(local_xs.min()), int(local_xs.max()) + 1
        gx1 = part.x + lx1
        gy1 = part.y + ly1
        gx2 = part.x + lx2
        gy2 = part.y + ly2

        sub = part.rgba[ly1:ly2, lx1:lx2, :]
        sub_mask = _part_mask(sub)
        sub_mask = _expand_mask_by_mm(sub_mask, cfg.part_expand_mm, mm_per_px)
        contours = mask_to_contours(sub_mask.astype(np.uint8) * 255, include_holes=True)
        for cnt in contours:
            cnt_global = cnt.copy()
            cnt_global[:, 0] += gx1
            cnt_global[:, 1] += gy1
            all_x1.append(float(np.min(cnt_global[:, 0])))
            all_y1.append(float(np.min(cnt_global[:, 1])))
            all_x2.append(float(np.max(cnt_global[:, 0])))
            all_y2.append(float(np.max(cnt_global[:, 1])))
            draw_items.append((cnt_global, part.color_rgb, gx1, gy1))

    if not draw_items:
        raise ValueError("部件轮廓为空")

    view_x1 = min(all_x1)
    view_y1 = min(all_y1)
    view_x2 = max(all_x2)
    view_y2 = max(all_y2)
    content_w_px = max(1, view_x2 - view_x1)
    content_h_px = max(1, view_y2 - view_y1)

    content_w_mm = content_w_px * mm_per_px
    content_h_mm = content_h_px * mm_per_px
    print_w_mm = cfg.a4_width_mm - 2 * cfg.margin_mm
    print_h_mm = cfg.a4_height_mm - 2 * cfg.margin_mm
    fit_scale = min(1.0, print_w_mm / content_w_mm, print_h_mm / content_h_mm)

    fig_w_in = cfg.a4_width_mm / 25.4
    fig_h_in = cfg.a4_height_mm / 25.4
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in), facecolor="white")
    ax.set_aspect("equal")
    ax.axis("off")

    for cnt, color, _, _ in draw_items:
        poly = Polygon(cnt, closed=True, facecolor=color, edgecolor="black", linewidth=0.8)
        ax.add_patch(poly)

    ax.set_xlim(view_x1 - 0.5, view_x2 + 0.5)
    ax.set_ylim(view_y2 + 0.5, view_y1 - 0.5)  # image Y down

    disp_w_frac = (content_w_mm * fit_scale) / cfg.a4_width_mm
    disp_h_frac = (content_h_mm * fit_scale) / cfg.a4_height_mm
    margin_x_frac = cfg.margin_mm / cfg.a4_width_mm
    margin_y_frac = cfg.margin_mm / cfg.a4_height_mm
    ax.set_position([margin_x_frac, margin_y_frac, disp_w_frac, disp_h_frac])

    buf = out_buffer if out_buffer is not None else io.BytesIO()
    with PdfPages(buf) as pdf:
        pdf.savefig(fig, dpi=cfg.dpi)
    plt.close(fig)

    buf.seek(0)
    return buf.read()
