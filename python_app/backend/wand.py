"""Magic wand selection (port of magicWandSelect.m)."""

from __future__ import annotations

import cv2
import numpy as np


def magic_wand_select(
    src_img: np.ndarray,
    seed_x: float,
    seed_y: float,
    tolerance: float = 28,
) -> np.ndarray:
    if src_img.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)

    img = src_img.astype(np.uint8)
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    if img.shape[2] >= 4:
        img = img[:, :, :3]

    h, w = img.shape[:2]
    sx = int(np.clip(round(seed_x), 0, w - 1))
    sy = int(np.clip(round(seed_y), 0, h - 1))

    seed = img[sy, sx].astype(np.int16)
    diff = np.abs(img.astype(np.int16) - seed.reshape(1, 1, 3)).sum(axis=2)
    similar = (diff <= tolerance * 3).astype(np.uint8)

    num, labels = cv2.connectedComponents(similar, connectivity=8)
    label_at_seed = labels[sy, sx]
    if label_at_seed == 0:
        return np.zeros((h, w), dtype=np.uint8)
    return (labels == label_at_seed).astype(np.uint8) * 255
