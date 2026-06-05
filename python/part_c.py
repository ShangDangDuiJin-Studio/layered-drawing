"""PartC — C 同学：排版输出与 PDF 导出（对应 PartC.m）"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

import cv2
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from image_utils import Layer, bounding_box_from_mask, ensure_rgba, get_outline, layer_mask, mix_layers

if TYPE_CHECKING:
    from main_app import MainApp


def _c_selected_positions(app: MainApp) -> List[int]:
    return sorted({app.c_layer_list.row(it) for it in app.c_layer_list.selectedItems()})


def refresh_c_layer_list(app: MainApp) -> None:
    app.c_layer_list.clear()
    for k, src_idx in enumerate(app.c_source_map):
        name = app.c_source_layers[src_idx].name
        app.c_layer_list.addItem(f"{k + 1}. {name}")
    if app.c_source_map:
        app.c_layer_list.setCurrentRow(0)


def _clear_c_outlines(app: MainApp) -> None:
    for art in getattr(app, "c_outline_artists", []):
        try:
            art.remove()
        except Exception:
            pass
    app.c_outline_artists = []


def _display_canvas(app: MainApp, canvas: np.ndarray, layers_for_edge: List[Layer] | None = None) -> None:
    if canvas.size == 0:
        return
    canvas = ensure_rgba(canvas)
    h, w = canvas.shape[:2]
    app.layout_ax.clear()
    app.layout_ax.imshow(canvas[:, :, :3], alpha=canvas[:, :, 3] / 255.0, origin="upper")
    app.layout_ax.set_xticks([])
    app.layout_ax.set_yticks([])
    _clear_c_outlines(app)
    if layers_for_edge:
        segments = []
        for ly in layers_for_edge:
            m = layer_mask(ly)
            if not np.any(m):
                continue
            for pts in get_outline(m.astype(np.uint8) * 255, include_holes=True):
                if len(pts) >= 3:
                    segments.append(np.vstack([pts, pts[0:1]]))
        if segments:
            lc = LineCollection(segments, colors="black", linewidths=2.0)
            app.layout_ax.add_collection(lc)
            app.c_outline_artists = [lc]
    app.layout_canvas.draw_idle()


def render_layout(app: MainApp) -> None:
    if app.c_is_previewing_single:
        return
    layers = app.c_laid_out_layers if app.c_has_laid_out and app.c_laid_out_layers else app.c_layers
    if not layers:
        return
    merged = mix_layers(layers)
    _display_canvas(app, merged, layers)


def show_single_part_preview(app: MainApp, list_pos: int) -> None:
    if list_pos < 0 or list_pos >= len(app.c_source_map):
        return
    app.c_is_previewing_single = True
    if app.c_has_laid_out and list_pos < len(app.c_laid_out_layers):
        canvas = app.c_laid_out_layers[list_pos].img
    else:
        src_idx = app.c_source_map[list_pos]
        ly = app.c_source_layers[src_idx].img
        if app.c_rgba is None:
            canvas = ly
        else:
            h, w = app.c_rgba.shape[:2]
            canvas = np.zeros((h, w, 4), dtype=np.uint8)
            lh, lw = min(h, ly.shape[0]), min(w, ly.shape[1])
            canvas[:lh, :lw, :] = ly[:lh, :lw, :]
    m = layer_mask(Layer(img=ensure_rgba(canvas), name="preview"))
    if not np.any(m):
        QMessageBox.information(app, "提示", "该部件没有有效像素")
        app.c_is_previewing_single = False
        return
    _display_canvas(app, canvas, [Layer(img=ensure_rgba(canvas), name="preview", visible=True)])


def apply_c_flow_layout(app: MainApp) -> None:
    if not app.c_source_map or app.c_rgba is None:
        QMessageBox.warning(app, "提示", "缺少画布尺寸，请先在「分层编辑」页导入图片。")
        return
    idx = app.c_source_map
    h0, w = app.c_rgba.shape[:2]
    scale_factor = app.c_layout_scale / 100.0
    parts: List[np.ndarray] = []
    names: List[str] = []
    for src_idx in idx:
        ly = app.c_source_layers[src_idx].img
        m = ly[:, :, 3] > 0 if ly.shape[2] >= 4 else np.any(ly > 0, axis=2)
        if not np.any(m):
            continue
        x1, y1, x2, y2 = bounding_box_from_mask(m)
        if x2 < x1 or y2 < y1:
            continue
        part = ly[y1 : y2 + 1, x1 : x2 + 1, :]
        if abs(scale_factor - 1.0) > 1e-6:
            nh = max(1, int(round(part.shape[0] * scale_factor)))
            nw = max(1, int(round(part.shape[1] * scale_factor)))
            part = cv2.resize(part, (nw, nh), interpolation=cv2.INTER_NEAREST)
        parts.append(ensure_rgba(part))
        names.append(app.c_source_layers[src_idx].name)
    n_part = len(parts)
    if n_part == 0:
        QMessageBox.warning(app, "提示", "没有可排版的部件。")
        return
    if not app.c_layout_gaps or len(app.c_layout_gaps) != max(0, n_part - 1):
        app.c_layout_gaps = [app.c_layout_spacing] * max(0, n_part - 1)
    margin = app.c_layout_spacing
    x, y, row_h, max_bottom = 1 + margin, 1 + margin, 0, 1 + margin
    for n, part in enumerate(parts):
        ph, pw = part.shape[:2]
        if x + pw - 1 > w - margin:
            x = 1 + margin
            y = y + row_h + margin
            row_h = 0
        max_bottom = max(max_bottom, y + ph - 1)
        gap_after = app.c_layout_gaps[n] if n < n_part - 1 else margin
        x = x + pw + gap_after
        row_h = max(row_h, ph)
    canvas_h = max(h0, max_bottom + margin)
    placed: List[Layer] = []
    x, y, row_h = 1 + margin, 1 + margin, 0
    for n, part in enumerate(parts):
        ph, pw = part.shape[:2]
        if x + pw - 1 > w - margin:
            x = 1 + margin
            y = y + row_h + margin
            row_h = 0
        px, py = x, y
        out = np.zeros((canvas_h, w, 4), dtype=np.uint8)
        out[py : py + ph, px : px + pw, :] = part
        placed.append(Layer(img=out, name=names[n], visible=True, opacity=100.0))
        gap_after = app.c_layout_gaps[n] if n < n_part - 1 else margin
        x = px + pw + gap_after
        row_h = max(row_h, ph)
    app.c_layers = placed
    app.c_laid_out_layers = placed
    app.c_rgba = np.zeros((canvas_h, w, 4), dtype=np.uint8)
    app.c_rgb = app.c_rgba[:, :, :3]
    app.c_has_laid_out = True
    app.c_is_previewing_single = False
    render_layout(app)
    app.c_status_label.setText(f"排版完成：{len(placed)} 个部件，缩放 {app.c_layout_scale}%")


def auto_layout(app: MainApp) -> None:
    app.c_layout_gaps = []
    apply_c_flow_layout(app)


def on_scale_changed(app: MainApp, value: int) -> None:
    app.c_layout_scale = value
    app.c_scale_label.setText(f"动态缩放: {value}%")
    if not app.c_has_laid_out:
        app.c_status_label.setText("请先点「自动换行与排版」，再调整缩放")
        return
    apply_c_flow_layout(app)


def on_spacing_changed(app: MainApp, value: int) -> None:
    app.c_layout_spacing = value
    sel = _c_selected_positions(app)
    if len(sel) == 2 and sel[1] == sel[0] + 1 and app.c_has_laid_out and len(app.c_layout_gaps) >= sel[0]:
        app.c_layout_gaps[sel[0]] = value
        app.c_spacing_label.setText(f"两部件间距: {value} px")
    else:
        if not (len(sel) == 2 and sel[1] == sel[0] + 1):
            app.c_layout_gaps = []
        app.c_spacing_label.setText(f"动态间距: {value} px")
    if not app.c_has_laid_out:
        app.c_status_label.setText("请先点「自动换行与排版」，再调整间距")
        return
    apply_c_flow_layout(app)


def on_c_layer_list_changed(app: MainApp) -> None:
    if not app.c_source_map:
        return
    sel = _c_selected_positions(app)
    if len(sel) == 2:
        app.c_is_previewing_single = False
        if sel[1] == sel[0] + 1:
            if app.c_has_laid_out and len(app.c_layout_gaps) >= sel[0]:
                app.c_spacing_slider.blockSignals(True)
                app.c_spacing_slider.setValue(app.c_layout_gaps[sel[0]])
                app.c_spacing_slider.blockSignals(False)
                app.c_layout_spacing = app.c_layout_gaps[sel[0]]
            app.c_spacing_label.setText(f"两部件间距: {app.c_layout_spacing} px")
            app.c_status_label.setText("已选中相邻两部件：拖动「动态间距」只改它们之间的间距")
        else:
            app.c_status_label.setText("请选中列表中相邻的两个部件以单独调间距")
        if app.c_has_laid_out:
            render_layout(app)
        return
    if len(sel) != 1:
        return
    show_single_part_preview(app, sel[0])
    name = app.c_source_layers[app.c_source_map[sel[0]]].name
    app.c_status_label.setText(f"预览部件：{name}")


def _collect_pdf_parts(layers: List[Layer]) -> List[dict]:
    parts = []
    for ly in layers:
        if not ly.visible:
            continue
        img = ensure_rgba(ly.img)
        m = img[:, :, 3] > 0
        if not np.any(m):
            continue
        rows, cols = np.where(m)
        contours = get_outline(m.astype(np.uint8) * 255, include_holes=True)
        col = [
            float(img[m, 0].mean()) / 255.0,
            float(img[m, 1].mean()) / 255.0,
            float(img[m, 2].mean()) / 255.0,
        ]
        parts.append(
            {
                "x1": int(cols.min()),
                "y1": int(rows.min()),
                "x2": int(cols.max()),
                "y2": int(rows.max()),
                "contours": contours,
                "color": col,
            }
        )
    return parts


def _pdf_default_folder() -> str:
    home = Path.home()
    docs = home / "Documents"
    if docs.is_dir():
        return str(docs)
    return str(home)


def export_pdf(app: MainApp) -> None:
    if not app.c_has_laid_out or not app.c_laid_out_layers:
        QMessageBox.information(app, "提示", "请先完成排版")
        return
    default = os.path.join(_pdf_default_folder(), "layout_1to1.pdf")
    path, _ = QFileDialog.getSaveFileName(app, "导出 1:1 PDF", default, "PDF (*.pdf)")
    if not path:
        return
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    margin_mm = app.pdf_margin_mm
    parts = _collect_pdf_parts(app.c_laid_out_layers)
    if not parts:
        QMessageBox.warning(app, "提示", "没有可导出的部件")
        return
    xs1 = [p["x1"] for p in parts]
    ys1 = [p["y1"] for p in parts]
    xs2 = [p["x2"] for p in parts]
    ys2 = [p["y2"] for p in parts]
    view_x1, view_y1 = min(xs1), min(ys1)
    view_x2, view_y2 = max(xs2), max(ys2)
    try:
        import matplotlib.pyplot as plt

        a4_w_cm, a4_h_cm = 21.0, 29.7
        content_w_px = max(1, view_x2 - view_x1 + 1)
        content_h_px = max(1, view_y2 - view_y1 + 1)
        mm_per_px = 25.4 / 96.0
        content_w_mm = content_w_px * mm_per_px
        content_h_mm = content_h_px * mm_per_px
        print_w_mm = 210 - 2 * margin_mm
        print_h_mm = 297 - 2 * margin_mm
        fit_scale = min(1.0, print_w_mm / content_w_mm, print_h_mm / content_h_mm)
        disp_w_mm = content_w_mm * fit_scale
        disp_h_mm = content_h_mm * fit_scale
        fig_w_in = a4_w_cm / 2.54
        fig_h_in = a4_h_cm / 2.54
        fig = plt.figure(figsize=(fig_w_in, fig_h_in), facecolor="white")
        ax = fig.add_axes(
            [
                margin_mm / 210.0,
                margin_mm / 297.0,
                disp_w_mm / 210.0,
                disp_h_mm / 297.0,
            ]
        )
        ax.set_aspect("equal")
        ax.invert_yaxis()
        ax.axis("off")
        for p in parts:
            for pts in p["contours"]:
                if len(pts) < 3:
                    continue
                poly = Polygon(pts, closed=True, facecolor=p["color"], edgecolor="black", linewidth=1.2)
                ax.add_patch(poly)
        ax.set_xlim(view_x1 - 0.5, view_x2 + 0.5)
        ax.set_ylim(view_y2 + 0.5, view_y1 - 0.5)
        with PdfPages(path) as pdf:
            pdf.savefig(fig, format="pdf")
        plt.close(fig)
        app.c_status_label.setText(
            f"已导出 PDF: {path}（单页 A4，全部 {len(parts)} 个部件，四边 {int(round(margin_mm))}mm 留白）"
        )
    except Exception as e:
        QMessageBox.critical(app, "PDF 导出失败", str(e))
