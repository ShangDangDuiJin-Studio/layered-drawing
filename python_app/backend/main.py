"""FastAPI: upload image -> auto layer -> PDF."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import ProcessOptions, process_image

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="不织布自动分层排版", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/process")
async def api_process(
    file: UploadFile = File(...),
    max_colors: int = Form(24),
    min_area_ratio: float = Form(0.0008),
    scale_percent: float = Form(100),
    spacing_px: int = Form(10),
    margin_mm: float = Form(15),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件 (PNG/JPG 等)")

    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 25MB")

    try:
        opts = ProcessOptions(
            max_colors=max_colors,
            min_area_ratio=min_area_ratio,
            scale_percent=scale_percent,
            spacing_px=spacing_px,
            margin_mm=margin_mm,
        )
        result = process_image(raw, opts)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"处理失败: {e}") from e

    return {
        "part_count": result.part_count,
        "part_names": result.part_names,
        "preview_png_base64": None,
        "message": f"已识别 {result.part_count} 个部件并完成排版",
        "_pdf_size": len(result.pdf_bytes),
    }


@app.post("/api/process/pdf")
async def api_process_pdf(
    file: UploadFile = File(...),
    max_colors: int = Form(24),
    min_area_ratio: float = Form(0.0008),
    scale_percent: float = Form(100),
    spacing_px: int = Form(10),
    margin_mm: float = Form(15),
):
    """One-shot: returns PDF file directly."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")

    raw = await file.read()
    try:
        opts = ProcessOptions(
            max_colors=max_colors,
            min_area_ratio=min_area_ratio,
            scale_percent=scale_percent,
            spacing_px=spacing_px,
            margin_mm=margin_mm,
        )
        result = process_image(raw, opts)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"处理失败: {e}") from e

    return StreamingResponse(
        io.BytesIO(result.pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="layout_1to1.pdf"'},
    )


@app.post("/api/process/full")
async def api_process_full(
    file: UploadFile = File(...),
    max_colors: int = Form(24),
    min_area_ratio: float = Form(0.0008),
    scale_percent: float = Form(100),
    spacing_px: int = Form(10),
    margin_mm: float = Form(15),
):
    """JSON metadata + separate endpoints; returns multipart-like JSON with base64 preview."""
    import base64

    raw = await file.read()
    try:
        opts = ProcessOptions(
            max_colors=max_colors,
            min_area_ratio=min_area_ratio,
            scale_percent=scale_percent,
            spacing_px=spacing_px,
            margin_mm=margin_mm,
        )
        result = process_image(raw, opts)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"处理失败: {e}") from e

    preview_b64 = base64.b64encode(result.preview_png).decode("ascii") if result.preview_png else None
    pdf_b64 = base64.b64encode(result.pdf_bytes).decode("ascii")

    return {
        "part_count": result.part_count,
        "part_names": result.part_names,
        "preview_png_base64": preview_b64,
        "pdf_base64": pdf_b64,
    }


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:

    @app.get("/")
    def index_fallback():
        return {"message": "API running. Place frontend in python_app/frontend/"}
