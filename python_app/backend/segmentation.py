"""Automatic color-region segmentation for flat textile / craft illustrations."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans


@dataclass
class LayerPart:
    name: str
    rgba: np.ndarray  # HxWx4 uint8
    color_rgb: tuple[float, float, float]  # 0-1 mean color for PDF fill


@dataclass
class SegmentationConfig:
    max_colors: int = 24
    color_quantize_step: int = 12
    min_area_ratio: float = 0.0008
    merge_similar_colors: int = 18  # L2 in RGB, max distance to merge labels
    max_side: int = 1200


def _resize_if_needed(rgb: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    h, w = rgb.shape[:2]
    scale = 1.0
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        nh, nw = int(h * scale), int(w * scale)
        rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    return rgb, scale


def _detect_background_label(labels: np.ndarray, rgb: np.ndarray) -> int:
    """Background = dominant color near image borders."""
    h, w = labels.shape
    border = np.concatenate(
        [
            labels[0, :],
            labels[-1, :],
            labels[:, 0],
            labels[:, -1],
        ]
    )
    border = border[border >= 0]
    if border.size == 0:
        flat = labels[labels >= 0].ravel()
        border = flat
    border_vals, counts = np.unique(border, return_counts=True)
    border_mode = int(border_vals[np.argmax(counts)])

    # Also treat near-white large regions as background
    flat = labels.ravel()
    uniq, cnt = np.unique(flat, return_counts=True)
    largest = int(uniq[np.argmax(cnt)])
    if largest != border_mode:
        mean_c = rgb[labels == largest].mean(axis=0)
        if mean_c.min() > 240:
            return largest
    return border_mode


def _quantize_labels(rgb: np.ndarray, cfg: SegmentationConfig) -> np.ndarray:
    step = cfg.color_quantize_step
    q = (rgb // step) * step + step // 2
    flat = q.reshape(-1, 3).astype(np.float32)
    uniq = np.unique(flat, axis=0)
    if len(uniq) <= cfg.max_colors:
        label_map = {tuple(u): i for i, u in enumerate(uniq)}
        labels = np.array([label_map[tuple(p)] for p in flat], dtype=np.int32).reshape(rgb.shape[:2])
        return labels

    k = min(cfg.max_colors, len(uniq))
    km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=4096)
    cluster_ids = km.fit_predict(flat)
    return cluster_ids.reshape(rgb.shape[:2])


def _merge_similar_labels(rgb: np.ndarray, labels: np.ndarray, thresh: int) -> np.ndarray:
    uniq = np.unique(labels)
    means = {u: rgb[labels == u].mean(axis=0) for u in uniq}
    parent = {int(u): int(u) for u in uniq}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    items = list(uniq)
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if np.linalg.norm(means[a] - means[b]) <= thresh:
                union(int(a), int(b))

    remap = {}
    new_id = 0
    out = labels.copy()
    for u in uniq:
        r = find(int(u))
        if r not in remap:
            remap[r] = new_id
            new_id += 1
        out[labels == u] = remap[r]
    return out


def auto_segment_rgba(
    rgba: np.ndarray,
    cfg: SegmentationConfig | None = None,
) -> tuple[list[LayerPart], np.ndarray]:
    """
    Split image into layers by color-connected regions.
    Returns (parts excluding background, full RGBA canvas same size as input).
    """
    if cfg is None:
        cfg = SegmentationConfig()

    if rgba.ndim != 3 or rgba.shape[2] < 3:
        raise ValueError("Expected HxWx3 or HxWx4 image")

    h0, w0 = rgba.shape[:2]
    if rgba.shape[2] == 4:
        alpha = rgba[:, :, 3]
        rgb = rgba[:, :, :3].copy()
        transparent = alpha < 16
    else:
        rgb = rgba[:, :, :3].copy()
        transparent = np.zeros((h0, w0), dtype=bool)

    work_rgb, scale = _resize_if_needed(rgb, cfg.max_side)
    work_alpha = (
        cv2.resize(alpha, (work_rgb.shape[1], work_rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
        if rgba.shape[2] == 4
        else None
    )
    if work_alpha is not None:
        transparent_work = work_alpha < 16
    else:
        transparent_work = np.zeros(work_rgb.shape[:2], dtype=bool)

    labels = _quantize_labels(work_rgb, cfg)
    labels[transparent_work] = -1
    labels = _merge_similar_labels(work_rgb, labels, cfg.merge_similar_colors)

    valid = labels >= 0
    if not np.any(valid):
        return [], rgba if rgba.shape[2] == 4 else np.dstack([rgb, np.full((h0, w0), 255, np.uint8)])

    bg_label = _detect_background_label(labels, work_rgb)
    min_area = max(16, int(cfg.min_area_ratio * work_rgb.shape[0] * work_rgb.shape[1]))

    parts: list[LayerPart] = []
    part_idx = 0
    for label_id in np.unique(labels):
        if label_id < 0 or label_id == bg_label:
            continue
        mask = labels == label_id
        n_cc, cc_labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        for cc in range(1, n_cc):
            area = stats[cc, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            cc_mask = cc_labels == cc
            ys, xs = np.where(cc_mask)
            y1, y2 = ys.min(), ys.max() + 1
            x1, x2 = xs.min(), xs.max() + 1

            if scale != 1.0:
                inv = 1.0 / scale
                y1f, y2f = int(y1 * inv), int(np.ceil(y2 * inv))
                x1f, x2f = int(x1 * inv), int(np.ceil(x2 * inv))
                y1f, x1f = max(0, y1f), max(0, x1f)
                y2f, x2f = min(h0, y2f), min(w0, x2f)
                full_mask = np.zeros((h0, w0), dtype=bool)
                full_mask[y1f:y2f, x1f:x2f] = True
                region_rgb = rgb[y1f:y2f, x1f:x2f]
                # Refine mask on full resolution using color similarity
                mean_c = work_rgb[cc_mask].mean(axis=0)
                diff = np.linalg.norm(region_rgb.astype(np.float32) - mean_c, axis=2)
                full_mask[y1f:y2f, x1f:x2f] &= diff < (cfg.color_quantize_step * 2.5)
            else:
                full_mask = np.zeros((h0, w0), dtype=bool)
                full_mask[y1:y2, x1:x2] = cc_mask[y1:y2, x1:x2]
                if transparent.any():
                    full_mask &= ~transparent

            if not np.any(full_mask):
                continue

            layer = np.zeros((h0, w0, 4), dtype=np.uint8)
            for c in range(3):
                layer[:, :, c] = np.where(full_mask, rgb[:, :, c], 0)
            layer[:, :, 3] = np.where(full_mask, 255, 0)

            mean_c = rgb[full_mask].mean(axis=0) / 255.0
            part_idx += 1
            parts.append(
                LayerPart(
                    name=f"部件{part_idx}",
                    rgba=layer,
                    color_rgb=(float(mean_c[0]), float(mean_c[1]), float(mean_c[2])),
                )
            )

    parts.sort(key=lambda p: np.count_nonzero(p.rgba[:, :, 3]), reverse=True)
    canvas = rgba if rgba.shape[2] == 4 else np.dstack([rgb, np.full((h0, w0), 255, np.uint8)])
    return parts, canvas
