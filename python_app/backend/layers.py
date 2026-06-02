"""Layer merge/display helpers (port of mergeVisibleLayers.m)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Layer:
    img: np.ndarray  # HxWx4 uint8
    name: str
    visible: bool = True
    opacity: float = 100.0


@dataclass
class EditorState:
    rgba: np.ndarray | None = None
    rgb: np.ndarray | None = None
    layers: list[Layer] = field(default_factory=list)
    cur_mask: np.ndarray | None = None
    current_layer_idx: int = 0
    border_color: tuple[float, float, float] = (0.0, 1.0, 1.0)
    wand_tolerance: float = 28.0
    # 排版（Tab2）
    layout_scale: float = 100.0
    layout_spacing: int = 10
    layout_gaps: list[int] = field(default_factory=list)
    has_laid_out: bool = False
    layout_part_names: list[str] = field(default_factory=list)
    laid_out_placed: list = field(default_factory=list)
    layout_canvas: np.ndarray | None = None
    is_previewing_single: bool = False
    preview_single_index: int = -1


def merge_visible_layers(layers: list[Layer], default_h: int = 1, default_w: int = 1) -> np.ndarray:
    if not layers:
        return np.zeros((default_h, default_w, 4), dtype=np.uint8)

    h, w = layers[0].img.shape[:2]
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    alpha_out = np.zeros((h, w), dtype=np.float32)

    for layer in reversed(layers):
        if not layer.visible:
            continue
        img = layer.img.astype(np.float32)
        layer_op = layer.opacity / 100.0
        if img.shape[2] >= 4:
            alpha_src = (img[:, :, 3] / 255.0) * layer_op
            rgb_src = img[:, :, :3]
        else:
            alpha_src = np.ones((h, w), dtype=np.float32) * layer_op
            rgb_src = img[:, :, :3]

        alpha_src = np.clip(alpha_src, 0, 1)
        for c in range(3):
            rgb[:, :, c] = rgb[:, :, c] * (1 - alpha_src) + rgb_src[:, :, c] * alpha_src
        alpha_out = alpha_out + (1 - alpha_out) * alpha_src

    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    canvas[:, :, :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    canvas[:, :, 3] = np.clip(np.round(alpha_out * 255), 0, 255).astype(np.uint8)
    return canvas
