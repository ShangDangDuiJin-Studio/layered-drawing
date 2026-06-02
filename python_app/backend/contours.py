"""Extract display contours from binary masks (aligned with MATLAB maskToContours)."""

from __future__ import annotations

import cv2
import numpy as np


def mask_to_contours(mask: np.ndarray, include_holes: bool = False) -> list[np.ndarray]:
    """Return list of Nx2 arrays (x, y) in image coordinates."""
    if mask is None or mask.size == 0 or not np.any(mask):
        return []

    binary = (mask != 0).astype(np.uint8)
    mode = cv2.RETR_TREE if include_holes else cv2.RETR_EXTERNAL
    found, _ = cv2.findContours(binary, mode, cv2.CHAIN_APPROX_SIMPLE)

    contours: list[np.ndarray] = []
    for c in found:
        if c.shape[0] < 3:
            continue
        pts = c.reshape(-1, 2).astype(np.float64)
        contours.append(pts)
    return _filter_contours(contours)


def _filter_contours(contours: list[np.ndarray], min_points: int = 3) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for pts in contours:
        if pts.shape[0] >= min_points:
            out.append(pts)
    return out
