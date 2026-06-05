"""图像工具：图层混合、魔棒选区、轮廓提取（对应 PartAB.m 底部小工具）"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import cv2
import numpy as np

PRESET_PART_NAMES = ["脸", "头发", "左眼", "右眼", "眼白", "瞳孔", "嘴巴", "耳朵"]


@dataclass
class Layer:
    img: np.ndarray  # H×W×4 uint8 RGBA
    name: str
    visible: bool = True
    opacity: float = 100.0  # 0–100


def ensure_rgba(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        img = np.stack([img, img, img], axis=-1)
    if img.shape[2] == 3:
        alpha = np.full(img.shape[:2] + (1,), 255, dtype=img.dtype)
        img = np.concatenate([img, alpha], axis=2)
    return img.astype(np.uint8)


def mix_layers(layers: Sequence[Layer], default_h: int = 1, default_w: int = 1) -> np.ndarray:
    if not layers:
        return np.zeros((default_h, default_w, 4), dtype=np.uint8)
    h, w = layers[0].img.shape[:2]
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    a_out = np.zeros((h, w), dtype=np.float32)
    for ly in reversed(layers):
        if not ly.visible:
            continue
        img = ly.img.astype(np.float32)
        layer_op = ly.opacity / 100.0
        if img.shape[2] >= 4:
            a_src = (img[:, :, 3] / 255.0) * layer_op
            rgb_src = img[:, :, :3]
        else:
            a_src = np.ones((h, w), dtype=np.float32) * layer_op
            rgb_src = img[:, :, : min(3, img.shape[2])]
            if rgb_src.shape[2] < 3:
                rgb_src = np.repeat(rgb_src, 3, axis=2)
        a_src = np.clip(a_src, 0.0, 1.0)
        for c in range(3):
            rgb[:, :, c] = rgb[:, :, c] * (1.0 - a_src) + rgb_src[:, :, c] * a_src
        a_out = a_out + (1.0 - a_out) * a_src
    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    canvas[:, :, :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    canvas[:, :, 3] = np.clip(np.round(a_out * 255), 0, 255).astype(np.uint8)
    return canvas


def click_pick(src_img: np.ndarray, seed_x: float, seed_y: float, tolerance: float = 28.0) -> np.ndarray:
    if src_img.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    rgb = src_img[:, :, :3].astype(np.uint8)
    if rgb.ndim == 2:
        rgb = np.stack([rgb, rgb, rgb], axis=-1)
    h, w = rgb.shape[:2]
    sx = int(np.clip(round(seed_x), 0, w - 1))
    sy = int(np.clip(round(seed_y), 0, h - 1))
    seed = rgb[sy, sx].astype(np.int16)
    diff = np.abs(rgb.astype(np.int16) - seed).sum(axis=2)
    binary = diff <= tolerance * 3
    mask = np.zeros((h, w), dtype=np.uint8)
    stack: List[Tuple[int, int]] = [(sx, sy)]
    visited = np.zeros((h, w), dtype=bool)
    visited[sy, sx] = True
    mask[sy, sx] = 255
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    thresh = tolerance * 3
    while stack:
        x, y = stack.pop()
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= w or ny < 0 or ny >= h or visited[ny, nx]:
                continue
            cur = rgb[ny, nx].astype(np.int16)
            if np.abs(cur - seed).sum() <= thresh:
                visited[ny, nx] = True
                mask[ny, nx] = 255
                stack.append((nx, ny))
    return mask


def clean_mask_for_outline(m: np.ndarray) -> np.ndarray:
    m = (m != 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
    return m.astype(bool)


def get_outline(mask: np.ndarray, include_holes: bool = False) -> List[np.ndarray]:
    if mask.size == 0 or not np.any(mask):
        return []
    m = (mask != 0).astype(np.uint8)
    min_area = max(4, int(m.size * 0.00005))
    nb, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    for i in range(1, nb):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            m[labels == i] = 0
    m = clean_mask_for_outline(m).astype(np.uint8)
    if not np.any(m):
        return []
    h, w = m.shape[:2]
    scale = 1.0
    max_side = 1600
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        m = cv2.resize(m, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    mode = cv2.RETR_TREE if include_holes else cv2.RETR_EXTERNAL
    contours, _ = cv2.findContours(m, mode, cv2.CHAIN_APPROX_NONE)
    result: List[np.ndarray] = []
    inv = 1.0 / scale if scale < 1.0 else 1.0
    for c in contours:
        if len(c) < 3:
            continue
        pts = c.reshape(-1, 2).astype(np.float64)
        if inv != 1.0:
            pts = pts * inv
        result.append(pts)
    return _trim_outline(result)


def get_selection_contours(mask: np.ndarray) -> List[np.ndarray]:
    if mask.size == 0 or not np.any(mask):
        return []
    m = (mask != 0).astype(np.uint8)
    min_area = max(4, int(m.size * 0.00005))
    nb, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    if areas.size == 0:
        return []
    max_area = int(areas.max())
    min_keep = max(16, int(max_area * 0.02))
    contours: List[np.ndarray] = []
    for i in range(1, nb):
        if stats[i, cv2.CC_STAT_AREA] < min_keep:
            continue
        comp = (labels == i).astype(np.uint8)
        c = get_outline(comp, include_holes=False)
        if c:
            contours.append(c[0])
    return contours


def _trim_outline(contours: List[np.ndarray], max_count: int = 250, min_pts: int = 3) -> List[np.ndarray]:
    kept = [c for c in contours if c is not None and len(c) >= min_pts]
    kept.sort(key=lambda c: len(c), reverse=True)
    return kept[:max_count]


def layer_mask(ly: Layer) -> np.ndarray:
    img = ly.img
    if img.shape[2] >= 4:
        return img[:, :, 3] > 0
    return np.any(img > 0, axis=2)


def bounding_box_from_mask(m: np.ndarray) -> Tuple[int, int, int, int]:
    rows, cols = np.where(m)
    if rows.size == 0:
        return 0, 0, 0, 0
    y1, y2 = int(rows.min()), int(rows.max())
    x1, x2 = int(cols.min()), int(cols.max())
    return x1, y1, x2, y2
