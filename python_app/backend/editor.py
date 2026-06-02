"""Manual editor + auto layout (MATLAB simplified Tab1 + Tab2)."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from .contours import mask_to_contours
from .layers import EditorState, Layer, merge_visible_layers
from .layout import LayoutConfig, flow_layout
from .pdf_export import PdfConfig, export_layout_pdf as render_layout_pdf
from .segmentation import LayerPart
from .wand import magic_wand_select

_session = EditorState()


def get_session() -> EditorState:
    return _session


def reset_session() -> None:
    global _session
    _session = EditorState()


def _parts_for_layout(s: EditorState) -> list[LayerPart]:
    parts: list[LayerPart] = []
    for i, ly in enumerate(s.layers):
        if i == 0 and ly.name == "背景":
            continue
        alpha = ly.img[:, :, 3] if ly.img.shape[2] >= 4 else np.any(ly.img[:, :, :3] > 0, axis=2)
        if not np.any(alpha):
            continue
        rgb = ly.img[:, :, :3]
        mean_c = rgb[alpha > 0].mean(axis=0) / 255.0
        parts.append(
            LayerPart(
                name=ly.name,
                rgba=ly.img,
                color_rgb=(float(mean_c[0]), float(mean_c[1]), float(mean_c[2])),
            )
        )
    return parts


def _invalidate_layout(s: EditorState) -> None:
    s.has_laid_out = False
    s.layout_canvas = None
    s.laid_out_placed = []
    s.layout_part_names = []
    s.layout_gaps = []
    s.is_previewing_single = False
    s.preview_single_index = -1


def import_image(data: bytes) -> dict:
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    rgba = np.array(img, dtype=np.uint8)
    rgb = rgba[:, :, :3].copy()

    s = get_session()
    s.rgba = rgba
    s.rgb = rgb
    s.layers = [Layer(img=rgba.copy(), name="背景")]
    s.cur_mask = None
    s.current_layer_idx = 0
    _invalidate_layout(s)
    return {"width": rgba.shape[1], "height": rgba.shape[0], "layer_count": len(s.layers)}


def wand_at(x: float, y: float) -> dict:
    s = get_session()
    if s.rgb is None:
        raise ValueError("请先导入图片")
    s.cur_mask = magic_wand_select(s.rgb, x, y, s.wand_tolerance)
    if not np.any(s.cur_mask):
        s.cur_mask = None
        return {"selected_pixels": 0, "contours": []}
    contours = mask_to_contours(s.cur_mask, include_holes=True)
    return {
        "selected_pixels": int(np.count_nonzero(s.cur_mask)),
        "contours": [c.tolist() for c in contours],
        "border_color": list(s.border_color),
    }


def cancel_selection() -> None:
    get_session().cur_mask = None


def make_layer() -> dict:
    s = get_session()
    if s.rgba is None:
        raise ValueError("请先导入图片")
    if s.cur_mask is None or not np.any(s.cur_mask):
        raise ValueError("请先在图上点击进行魔棒选区")

    h, w = s.rgba.shape[:2]
    m = (s.cur_mask > 0).astype(np.uint8)
    new_layer = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(4):
        new_layer[:, :, c] = m * s.rgba[:, :, c]

    name = f"分层{len(s.layers)}"
    s.layers.append(Layer(img=new_layer, name=name))
    s.current_layer_idx = len(s.layers) - 1
    s.cur_mask = None
    _invalidate_layout(s)
    return {"name": name, "layer_count": len(s.layers)}


def delete_layers(indices: list[int]) -> dict:
    s = get_session()
    if not indices:
        raise ValueError("请先选中要删除的部件")
    if any(i == 0 for i in indices):
        raise ValueError("背景层不可删除")

    keep = [i for i in range(len(s.layers)) if i not in set(indices)]
    s.layers = [s.layers[i] for i in keep]
    s.current_layer_idx = min(max(s.current_layer_idx, 0), max(0, len(s.layers) - 1))
    s.cur_mask = None
    _invalidate_layout(s)
    return {"layer_count": len(s.layers)}


def merge_layers(indices: list[int]) -> dict:
    s = get_session()
    if len(indices) < 2:
        raise ValueError("请至少多选 2 个部件再合并")
    if any(i == 0 for i in indices):
        raise ValueError("背景层不可参与合并")

    indices = sorted(set(indices))
    h, w = s.rgba.shape[:2]
    merged = np.zeros((h, w, 4), dtype=np.uint8)
    merged_mask = np.zeros((h, w), dtype=bool)

    for idx in indices:
        ly = s.layers[idx].img
        alpha = ly[:, :, 3] > 0 if ly.shape[2] >= 4 else np.any(ly[:, :, :3] > 0, axis=2)
        merged_mask |= alpha
        for c in range(3):
            ch = merged[:, :, c]
            ch[alpha] = ly[:, :, c][alpha]
            merged[:, :, c] = ch
    merged[:, :, 3] = merged_mask.astype(np.uint8) * 255

    first = indices[0]
    merged_name = f"{s.layers[first].name}_合并"
    new_layer = Layer(img=merged, name=merged_name)
    remaining = [s.layers[i] for i in range(len(s.layers)) if i not in indices]
    insert_at = sum(1 for i in indices if i < first)
    remaining.insert(insert_at, new_layer)
    s.layers = remaining
    s.current_layer_idx = insert_at
    s.cur_mask = None
    _invalidate_layout(s)
    return {"name": merged_name, "layer_count": len(s.layers)}


def list_layers() -> list[dict]:
    return [{"index": i, "name": ly.name} for i, ly in enumerate(get_session().layers)]


def list_layout_parts() -> list[dict]:
    s = get_session()
    return [{"index": i + 1, "name": n} for i, n in enumerate(s.layout_part_names)]


def set_border_color(r: float, g: float, b: float) -> None:
    get_session().border_color = (r, g, b)


def edit_preview_png() -> bytes:
    s = get_session()
    if not s.layers:
        raise ValueError("无图层")
    merged = merge_visible_layers(s.layers)
    buf = io.BytesIO()
    Image.fromarray(merged, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def apply_auto_layout(reset_gaps: bool = True) -> dict:
    """自动换行与排版 — 完成后返回排版预览。"""
    s = get_session()
    if s.rgba is None:
        raise ValueError("请先导入图片")

    parts = _parts_for_layout(s)
    if not parts:
        raise ValueError("没有可排版的部件，请先用魔棒生成部件")

    if reset_gaps:
        s.layout_gaps = []

    n = len(parts)
    if not s.layout_gaps or len(s.layout_gaps) != max(0, n - 1):
        s.layout_gaps = [s.layout_spacing] * max(0, n - 1)

    h, w = s.rgba.shape[:2]
    cfg = LayoutConfig(
        scale_percent=s.layout_scale,
        spacing_px=s.layout_spacing,
        gaps=s.layout_gaps,
    )
    placed, canvas = flow_layout(parts, canvas_width=w, canvas_height=h, cfg=cfg)

    s.laid_out_placed = placed
    s.layout_canvas = canvas
    s.layout_part_names = [p.name for p in parts]
    s.has_laid_out = True
    s.is_previewing_single = False
    s.preview_single_index = -1

    return {
        "part_count": len(placed),
        "scale_percent": s.layout_scale,
        "spacing_px": s.layout_spacing,
        "message": f"排版完成：{len(placed)} 个部件，缩放 {int(s.layout_scale)}%",
    }


def update_layout_params(
    scale_percent: float | None = None,
    spacing_px: int | None = None,
    selected_positions: list[int] | None = None,
) -> dict:
    """动态缩放 / 动态间距；多选相邻两项时只改它们之间的间距。"""
    s = get_session()
    spacing_label = f"动态间距: {s.layout_spacing} px"
    pair_mode = False

    if scale_percent is not None:
        s.layout_scale = float(scale_percent)

    if spacing_px is not None:
        s.layout_spacing = int(spacing_px)
        sel = sorted(set(selected_positions or []))
        if (
            len(sel) == 2
            and sel[1] == sel[0] + 1
            and s.has_laid_out
            and len(s.layout_gaps) >= sel[0]
        ):
            s.layout_gaps[sel[0] - 1] = s.layout_spacing
            spacing_label = f"两部件间距: {s.layout_spacing} px"
            pair_mode = True
        elif not (len(sel) == 2 and sel[1] == sel[0] + 1):
            s.layout_gaps = []

    if not s.has_laid_out:
        return {
            "has_laid_out": False,
            "message": "请先点「自动换行与排版」，再调整缩放或间距",
            "spacing_label": spacing_label,
        }

    apply_auto_layout(reset_gaps=False)
    return {
        "has_laid_out": True,
        "scale_percent": s.layout_scale,
        "spacing_px": s.layout_spacing,
        "spacing_label": spacing_label,
        "pair_mode": pair_mode,
        "message": f"排版已更新，缩放 {int(s.layout_scale)}%",
    }


def preview_layout_part(list_pos: int) -> None:
    """单击排版列表某项 → 预览单个部件。"""
    s = get_session()
    if list_pos < 1 or list_pos > len(s.layout_part_names):
        raise ValueError("无效的部件序号")
    s.is_previewing_single = True
    s.preview_single_index = list_pos


def layout_preview_png() -> bytes:
    s = get_session()
    if s.is_previewing_single and 1 <= s.preview_single_index <= len(_parts_for_layout(s)):
        parts = _parts_for_layout(s)
        idx = s.preview_single_index - 1
        ly = parts[idx].rgba
        h, w = s.rgba.shape[:2] if s.rgba is not None else ly.shape[:2]
        canvas = np.zeros((h, w, 4), dtype=np.uint8)
        lh = min(h, ly.shape[0])
        lw = min(w, ly.shape[1])
        canvas[:lh, :lw, :] = ly[:lh, :lw, :]
    elif s.has_laid_out and s.layout_canvas is not None:
        canvas = s.layout_canvas
    else:
        raise ValueError("请先点击「自动换行与排版」")

    buf = io.BytesIO()
    Image.fromarray(canvas, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def export_pdf_from_session(
    margin_mm: float = 15.0,
    part_expand_mm: float = 3.0,
) -> bytes:
    s = get_session()
    if not s.has_laid_out or not s.laid_out_placed:
        raise ValueError("请先完成排版")

    return render_layout_pdf(
        s.laid_out_placed,
        cfg=PdfConfig(margin_mm=margin_mm, part_expand_mm=part_expand_mm),
    )


def session_info() -> dict:
    s = get_session()
    return {
        "has_image": s.rgba is not None,
        "layer_count": len(s.layers),
        "layers": list_layers(),
        "layout_parts": list_layout_parts(),
        "has_laid_out": s.has_laid_out,
        "layout_scale": s.layout_scale,
        "layout_spacing": s.layout_spacing,
        "border_color": list(s.border_color),
    }
