"""PartAB — A/B 同学：分层编辑逻辑（对应 PartAB.m）"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import cv2
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.widgets import PolygonSelector
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QFileDialog, QMessageBox

from image_utils import (
    PRESET_PART_NAMES,
    Layer,
    click_pick,
    ensure_rgba,
    get_selection_contours,
    layer_mask,
    mix_layers,
)

if TYPE_CHECKING:
    from main_app import MainApp


def _alert(app: MainApp, title: str, msg: str, icon=QMessageBox.Icon.Information) -> None:
    QMessageBox(app, icon, title, msg).exec()


def _selected_indices(app: MainApp) -> List[int]:
    return sorted({app.layer_list.row(it) for it in app.layer_list.selectedItems()})


def _clear_contours(app: MainApp) -> None:
    for art in app.contour_artists:
        try:
            art.remove()
        except Exception:
            pass
    app.contour_artists = []


def _clear_outlines(app: MainApp) -> None:
    for art in app.outline_artists:
        try:
            art.remove()
        except Exception:
            pass
    app.outline_artists = []


def _draw_contours(app: MainApp, contours: List[np.ndarray], color=None, linewidth: float = 2.0) -> None:
    _clear_contours(app)
    if not contours:
        return
    ax = app.edit_ax
    color = color or app.border_color
    for pts in contours[:60]:
        if pts is None or len(pts) < 3:
            continue
        closed = np.vstack([pts, pts[0:1]])
        lc = LineCollection([closed], colors=[color], linewidths=linewidth)
        ax.add_collection(lc)
        app.contour_artists.append(lc)


def _draw_edges(app: MainApp, layers: List[Layer], skip_background: bool = True) -> None:
    from image_utils import get_outline

    _clear_outlines(app)
    ax = app.edit_ax
    all_segments = []
    for i, ly in enumerate(layers):
        if skip_background and i == 0 and ly.name == "背景":
            continue
        if not ly.visible:
            continue
        m = layer_mask(ly)
        if not np.any(m):
            continue
        for pts in get_outline(m.astype(np.uint8) * 255, include_holes=True):
            if len(pts) < 3:
                continue
            closed = np.vstack([pts, pts[0:1]])
            all_segments.append(closed)
    if all_segments:
        lc = LineCollection(all_segments, colors="black", linewidths=2.0)
        ax.add_collection(lc)
        app.outline_artists.append(lc)


def refresh_layer_list(app: MainApp) -> None:
    app.layer_list.blockSignals(True)
    app.layer_list.clear()
    for k, ly in enumerate(app.layers):
        mark = "[√] " if ly.visible else "[ ] "
        app.layer_list.addItem(f"{k + 1}. {mark}{ly.name}")
    idx = app.current_layer_idx
    if idx < 0 or idx >= len(app.layers):
        idx = max(0, len(app.layers) - 1)
        app.current_layer_idx = idx
    if app.layers:
        app.layer_list.setCurrentRow(idx)
    app.layer_list.blockSignals(False)
    if not app.is_updating_highlight:
        sync_name_control(app)


def sync_name_control(app: MainApp) -> None:
    idx = app.current_layer_idx
    if idx < 0 or idx >= len(app.layers):
        return
    app.name_combo.blockSignals(True)
    app.name_combo.clear()
    app.name_combo.addItems(PRESET_PART_NAMES)
    app.name_combo.setEditText(app.layers[idx].name)
    app.name_combo.blockSignals(False)


def render_edit(app: MainApp) -> None:
    if not app.layers or app.rgba is None:
        return
    merged = mix_layers(app.layers)
    app.edit_ax.clear()
    app.edit_ax.imshow(merged[:, :, :3], alpha=merged[:, :, 3] / 255.0, origin="upper")
    app.edit_ax.set_xticks([])
    app.edit_ax.set_yticks([])
    _draw_edges(app, app.layers, skip_background=True)
    if app.cur_mask is not None and np.any(app.cur_mask):
        return
    idx = app.current_layer_idx
    if idx == 0 and app.layers and app.layers[0].name == "背景":
        _clear_contours(app)
        app.edit_canvas.draw_idle()
        return
    update_layer_selection_contour(app)
    app.edit_canvas.draw_idle()


def update_layer_selection_contour(app: MainApp) -> None:
    idxs = _selected_indices(app)
    if not idxs:
        idxs = [app.current_layer_idx] if app.current_layer_idx >= 0 else []
    if app.layers and app.layers[0].name == "背景":
        idxs = [i for i in idxs if i != 0]
    all_c: List[np.ndarray] = []
    for idx in idxs:
        if idx < 0 or idx >= len(app.layers):
            continue
        m = layer_mask(app.layers[idx])
        if not np.any(m):
            continue
        all_c.extend(get_selection_contours(m.astype(np.uint8) * 255))
    if all_c:
        _draw_contours(app, all_c)
    else:
        _clear_contours(app)


def import_image(app: MainApp) -> None:
    path, _ = QFileDialog.getOpenFileName(
        app, "选择图片", "", "图像 (*.png *.jpg *.jpeg *.bmp)"
    )
    if not path:
        return
    try:
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("无法读取图像")
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgba = ensure_rgba(img)
        app.rgba = rgba
        app.rgb = rgba[:, :, :3]
        app.layers = [Layer(img=rgba.copy(), name="背景", visible=True, opacity=100.0)]
        app.cur_mask = None
        app.current_layer_idx = 0
        _clear_contours(app)
        refresh_layer_list(app)
        app.canvas_title.setText("")
        render_edit(app)
        app.status_label.setText(f"已加载: {path.split('/')[-1]}")
        app.tabs.setCurrentIndex(0)
    except Exception as e:
        _alert(app, "导入图片失败", str(e), QMessageBox.Icon.Critical)


def make_layer(app: MainApp) -> None:
    if app.rgba is None:
        _alert(app, "提示", "请先导入图片")
        return
    if app.cur_mask is None or not np.any(app.cur_mask):
        _alert(app, "提示", "请先在左侧图上单击选择区域")
        return
    h, w = app.rgba.shape[:2]
    if app.cur_mask.shape[:2] != (h, w):
        _alert(app, "提示", "选区与图像尺寸不一致，请重新选区")
        return
    if app.color_source == 0:
        src = app.rgba
    else:
        src = mix_layers(app.layers)
    m = (app.cur_mask > 0).astype(np.uint8)
    new_layer = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(min(4, src.shape[2])):
        new_layer[:, :, c] = m * src[:, :, c]
    if src.shape[2] < 4:
        new_layer[:, :, 3] = m * 255
    name = f"分层{len(app.layers) + 1}"
    app.layers.append(Layer(img=new_layer, name=name, visible=True, opacity=100.0))
    app.current_layer_idx = len(app.layers) - 1
    app.cur_mask = None
    _clear_contours(app)
    refresh_layer_list(app)
    render_edit(app)
    app.status_label.setText(f"已生成: {name}（共 {len(app.layers)} 层）")


def cancel_selection(app: MainApp) -> None:
    app.cur_mask = None
    _clear_contours(app)
    app.status_label.setText("选区已取消")
    app.edit_canvas.draw_idle()


def switch_color_source(app: MainApp) -> None:
    app.color_source = 1 - app.color_source
    app.switch_btn.setText("取色来源：原图" if app.color_source == 0 else "取色来源：可视化合并")


def pick_highlight_color(app: MainApp) -> None:
    c = QColorDialog.getColor(
        QColor(int(app.border_color[0] * 255), int(app.border_color[1] * 255), int(app.border_color[2] * 255)),
        app,
        "选区高亮颜色",
    )
    if c.isValid():
        app.border_color = (c.redF(), c.greenF(), c.blueF())
        for art in app.contour_artists:
            if hasattr(art, "set_colors"):
                art.set_colors([app.border_color])


def apply_layer_name(app: MainApp) -> None:
    if app.is_updating_highlight:
        return
    idx = app.current_layer_idx
    if idx < 0 or idx >= len(app.layers):
        sel = _selected_indices(app)
        if not sel:
            return
        idx = sel[0]
        app.current_layer_idx = idx
    new_name = app.name_combo.currentText().strip()
    if not new_name:
        return
    app.layers[idx].name = new_name
    app.is_updating_highlight = True
    refresh_layer_list(app)
    app.is_updating_highlight = False
    app.status_label.setText(f"已命名: {new_name}")


def delete_layers(app: MainApp) -> None:
    idx = _selected_indices(app)
    if not idx:
        _alert(app, "提示", "请先在列表中选中要删除的部件")
        return
    if 0 in idx:
        _alert(app, "提示", "背景层不可删除", QMessageBox.Icon.Warning)
        return
    for i in sorted(idx, reverse=True):
        del app.layers[i]
    app.current_layer_idx = min(app.current_layer_idx, len(app.layers) - 1) if app.layers else -1
    app.cur_mask = None
    _clear_contours(app)
    refresh_layer_list(app)
    render_edit(app)
    app.status_label.setText(f"已删除 {len(idx)} 个部件")


def merge_layers(app: MainApp) -> None:
    idx = _selected_indices(app)
    if len(idx) < 2:
        _alert(app, "提示", "请至少多选 2 个部件再执行合并")
        return
    if 0 in idx:
        _alert(app, "提示", "背景层不可参与合并", QMessageBox.Icon.Warning)
        return
    idx = sorted(set(idx))
    h, w = app.rgba.shape[:2]
    merged = np.zeros((h, w, 4), dtype=np.uint8)
    merged_mask = np.zeros((h, w), dtype=bool)
    for i in idx:
        ly = app.layers[i]
        a = layer_mask(ly)
        merged_mask |= a
        for c in range(3):
            ch = merged[:, :, c]
            ch[a] = ly.img[:, :, c][a]
            merged[:, :, c] = ch
    merged[:, :, 3] = merged_mask.astype(np.uint8) * 255
    first = idx[0]
    merged_name = f"{app.layers[first].name}_合并"
    new_layer = Layer(img=merged, name=merged_name, visible=True, opacity=100.0)
    keep = [ly for k, ly in enumerate(app.layers) if k not in idx]
    insert_at = first - sum(1 for k in idx if k < first)
    app.layers = keep[:insert_at] + [new_layer] + keep[insert_at:]
    app.current_layer_idx = insert_at
    app.cur_mask = None
    _clear_contours(app)
    refresh_layer_list(app)
    render_edit(app)
    app.status_label.setText(f"已合并 {len(idx)} 个部件")


def add_manual_layer(app: MainApp) -> None:
    if app.rgba is None:
        _alert(app, "提示", "请先导入图片")
        return
    app.is_drawing_manual = True
    app.status_label.setText("请在左图逐点描边，双击闭合完成")
    app.add_btn.setEnabled(False)

    def on_select(verts):
        app.is_drawing_manual = False
        app.add_btn.setEnabled(True)
        if app._polygon_selector:
            app._polygon_selector.set_active(False)
            app._polygon_selector = None
        if not verts or len(verts) < 3:
            app.status_label.setText("未生成有效手绘区域")
            return
        h, w = app.rgba.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        poly = np.array(verts, dtype=np.float32)
        cv2.fillPoly(mask, [poly.astype(np.int32)], 255)
        if not np.any(mask):
            app.status_label.setText("未生成有效手绘区域")
            return
        new_layer = np.zeros((h, w, 4), dtype=np.uint8)
        m = (mask > 0).astype(np.uint8)
        for c in range(3):
            new_layer[:, :, c] = m * app.rgba[:, :, c]
        new_layer[:, :, 3] = m * 255
        name = f"手动部件{len(app.layers) + 1}"
        app.layers.append(Layer(img=new_layer, name=name, visible=True, opacity=100.0))
        app.current_layer_idx = len(app.layers) - 1
        app.cur_mask = None
        _clear_contours(app)
        refresh_layer_list(app)
        render_edit(app)
        app.status_label.setText(f"已添加手绘部件: {name}")

    app._polygon_selector = PolygonSelector(
        app.edit_ax,
        on_select,
        useblit=True,
        props=dict(color=app.draw_line_color, linewidth=2.5),
    )


def move_layer_up(app: MainApp) -> None:
    idx = app.current_layer_idx
    if idx <= 0:
        return
    app.layers[idx], app.layers[idx - 1] = app.layers[idx - 1], app.layers[idx]
    app.current_layer_idx = idx - 1
    refresh_layer_list(app)
    render_edit(app)


def move_layer_down(app: MainApp) -> None:
    idx = app.current_layer_idx
    if idx < 0 or idx >= len(app.layers) - 1:
        return
    app.layers[idx], app.layers[idx + 1] = app.layers[idx + 1], app.layers[idx]
    app.current_layer_idx = idx + 1
    refresh_layer_list(app)
    render_edit(app)


def toggle_visible(app: MainApp) -> None:
    idx = app.current_layer_idx
    if idx < 0 or idx >= len(app.layers):
        return
    app.layers[idx].visible = not app.layers[idx].visible
    refresh_layer_list(app)
    render_edit(app)


def on_layer_list_changed(app: MainApp) -> None:
    if app.is_updating_highlight:
        return
    idxs = _selected_indices(app)
    if not idxs:
        return
    primary = idxs[0]
    app.current_layer_idx = primary
    op = app.layers[primary].opacity
    app.opacity_slider.blockSignals(True)
    app.opacity_slider.setValue(int(round(op)))
    app.opacity_slider.blockSignals(False)
    app.opacity_label.setText(f"图层不透明度: {int(round(op))}%")
    app.cur_mask = None
    app.is_updating_highlight = True
    sync_name_control(app)
    if primary == 0 and app.layers[0].name == "背景":
        _clear_contours(app)
    else:
        update_layer_selection_contour(app)
    app.is_updating_highlight = False
    app.edit_canvas.draw_idle()


def on_opacity_changed(app: MainApp, value: int) -> None:
    idx = app.current_layer_idx
    if idx < 0 or idx >= len(app.layers):
        sel = _selected_indices(app)
        if not sel:
            _alert(app, "提示", "请先在图层列表中选中一个图层")
            return
        idx = sel[0]
        app.current_layer_idx = idx
    app.layers[idx].opacity = float(value)
    app.opacity_label.setText(f"图层不透明度: {value}%")
    refresh_layer_list(app)
    render_edit(app)


def on_edit_axes_click(app: MainApp, event) -> None:
    if app.is_drawing_manual or app.is_processing_wand:
        return
    if app.rgba is None or event.inaxes != app.edit_ax:
        return
    if event.xdata is None or event.ydata is None:
        return
    do_wand_select(app, event.xdata, event.ydata)


def do_wand_select(app: MainApp, x: float, y: float) -> None:
    if app.is_processing_wand:
        return
    app.is_processing_wand = True
    try:
        h, w = app.rgba.shape[:2]
        xi = int(np.clip(round(x), 0, w - 1))
        yi = int(np.clip(round(y), 0, h - 1))
        app.status_label.setText("正在选择区域…")
        base = app.rgb if app.color_source == 0 else mix_layers(app.layers)[:, :, :3]
        app.cur_mask = click_pick(base, xi, yi, app.wand_tolerance)
        if not np.any(app.cur_mask):
            _clear_contours(app)
            app.status_label.setText("未选中有效区域")
            return
        contours = get_selection_contours(app.cur_mask)
        _draw_contours(app, contours)
        n_pix = int(np.count_nonzero(app.cur_mask))
        app.status_label.setText(f"已选区域 (x={xi},y={yi}) 约 {n_pix} 像素")
        app.edit_canvas.draw_idle()
    except Exception as e:
        _clear_contours(app)
        app.cur_mask = None
        _alert(app, "选区高亮失败", str(e), QMessageBox.Icon.Warning)
        app.status_label.setText("选区高亮失败")
    finally:
        app.is_processing_wand = False
