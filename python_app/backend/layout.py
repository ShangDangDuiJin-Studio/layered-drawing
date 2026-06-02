"""Flow layout for cut parts (matches MATLAB applyCFlowLayout)."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .segmentation import LayerPart


@dataclass
class LayoutConfig:
    scale_percent: float = 100.0
    spacing_px: int = 10
    margin_px: int | None = None
    gaps: list[int] = field(default_factory=list)


@dataclass
class PlacedPart:
    name: str
    rgba: np.ndarray
    x: int
    y: int
    width: int
    height: int
    color_rgb: tuple[float, float, float]


def _bbox_from_layer(rgba: np.ndarray) -> tuple[int, int, int, int] | None:
    alpha = rgba[:, :, 3] if rgba.shape[2] >= 4 else np.any(rgba > 0, axis=2)
    if not np.any(alpha):
        return None
    ys, xs = np.where(alpha)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _normalize_gaps(n_parts: int, spacing_px: int, gaps: list[int] | None) -> list[int]:
    need = max(0, n_parts - 1)
    if not gaps or len(gaps) != need:
        return [spacing_px] * need
    return list(gaps)


def flow_layout(
    parts: list[LayerPart],
    canvas_width: int,
    canvas_height: int,
    cfg: LayoutConfig | None = None,
) -> tuple[list[PlacedPart], np.ndarray]:
    if cfg is None:
        cfg = LayoutConfig()

    scale = cfg.scale_percent / 100.0
    margin = cfg.spacing_px if cfg.margin_px is None else cfg.margin_px
    w = canvas_width

    crops: list[tuple[LayerPart, np.ndarray]] = []
    for p in parts:
        bb = _bbox_from_layer(p.rgba)
        if bb is None:
            continue
        x1, y1, x2, y2 = bb
        crop = p.rgba[y1:y2, x1:x2, :].copy()
        if abs(scale - 1.0) > 1e-6:
            nh = max(1, int(round(crop.shape[0] * scale)))
            nw = max(1, int(round(crop.shape[1] * scale)))
            crop = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_NEAREST)
        crops.append((p, crop))

    n_part = len(crops)
    if n_part == 0:
        empty = np.zeros((canvas_height, w, 4), dtype=np.uint8)
        return [], empty

    gaps = _normalize_gaps(n_part, margin, cfg.gaps)

    x = 1 + margin
    y = 1 + margin
    row_h = 0
    max_bottom = y
    placements: list[tuple[LayerPart, np.ndarray, int, int]] = []

    for n, (p, crop) in enumerate(crops):
        ph, pw = crop.shape[0], crop.shape[1]
        if x + pw - 1 > w - margin:
            x = 1 + margin
            y = y + row_h + margin
            row_h = 0
        max_bottom = max(max_bottom, y + ph - 1)
        placements.append((p, crop, x, y))
        gap_after = margin if n >= n_part - 1 else gaps[n]
        x = x + pw + gap_after
        row_h = max(row_h, ph)

    canvas_h = max(canvas_height, max_bottom + margin)
    layout_canvas = np.zeros((canvas_h, w, 4), dtype=np.uint8)
    placed: list[PlacedPart] = []

    for p, crop, px, py in placements:
        ph, pw = crop.shape[0], crop.shape[1]
        layout_canvas[py : py + ph, px : px + pw, :] = crop
        placed.append(
            PlacedPart(
                name=p.name,
                rgba=crop,
                x=px,
                y=py,
                width=pw,
                height=ph,
                color_rgb=p.color_rgb,
            )
        )

    return placed, layout_canvas
