"""End-to-end: image bytes -> PDF bytes + metadata."""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image

from .layout import LayoutConfig, flow_layout
from .pdf_export import PdfConfig, export_layout_pdf
from .segmentation import SegmentationConfig, auto_segment_rgba


@dataclass
class ProcessOptions:
    max_colors: int = 24
    min_area_ratio: float = 0.0008
    scale_percent: float = 100.0
    spacing_px: int = 10
    margin_mm: float = 15.0
    part_expand_mm: float = 3.0


@dataclass
class ProcessResult:
    part_count: int
    part_names: list[str]
    pdf_bytes: bytes
    preview_png: bytes | None = None


def _load_rgba(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    return np.array(img, dtype=np.uint8)


def _layout_preview_png(canvas: np.ndarray) -> bytes:
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.fromarray(canvas, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def process_image(data: bytes, options: ProcessOptions | None = None) -> ProcessResult:
    opts = options or ProcessOptions()
    rgba = _load_rgba(data)
    h, w = rgba.shape[:2]

    seg_cfg = SegmentationConfig(
        max_colors=opts.max_colors,
        min_area_ratio=opts.min_area_ratio,
    )
    parts, _ = auto_segment_rgba(rgba, seg_cfg)
    if not parts:
        raise ValueError("未能自动识别到有效部件，请换一张颜色分区更清晰的图")

    layout_cfg = LayoutConfig(scale_percent=opts.scale_percent, spacing_px=opts.spacing_px)
    placed, layout_canvas = flow_layout(parts, canvas_width=w, canvas_height=h, cfg=layout_cfg)

    pdf_cfg = PdfConfig(margin_mm=opts.margin_mm, part_expand_mm=opts.part_expand_mm)
    pdf_bytes = export_layout_pdf(placed, cfg=pdf_cfg)

    return ProcessResult(
        part_count=len(placed),
        part_names=[p.name for p in placed],
        pdf_bytes=pdf_bytes,
        preview_png=_layout_preview_png(layout_canvas),
    )


def options_to_dict(opts: ProcessOptions) -> dict:
    return asdict(opts)
