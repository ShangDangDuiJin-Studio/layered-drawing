"""FastAPI: single-page manual edit + auto layout (Python, no MATLAB)."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import editor

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="不织布分层排版", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class WandRequest(BaseModel):
    x: float
    y: float


class IndicesRequest(BaseModel):
    indices: list[int]


class LayoutUpdateRequest(BaseModel):
    scale_percent: float | None = None
    spacing_px: int | None = None
    selected_positions: list[int] = []


class LayoutSelectRequest(BaseModel):
    list_pos: int


class PdfExportRequest(BaseModel):
    margin_mm: float = 15.0
    part_expand_mm: float = 3.0


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/state")
def api_state():
    return editor.session_info()


# ---------- 分层编辑 ----------
@app.post("/api/edit/import")
async def edit_import(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        info = editor.import_image(raw)
        preview = base64.b64encode(editor.edit_preview_png()).decode("ascii")
        return {**info, "preview_png_base64": preview, "layers": editor.list_layers()}
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/edit/preview")
def edit_preview():
    try:
        return Response(content=editor.edit_preview_png(), media_type="image/png")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/edit/wand")
def edit_wand(req: WandRequest):
    try:
        return editor.wand_at(req.x, req.y)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/edit/cancel")
def edit_cancel():
    editor.cancel_selection()
    return {"ok": True}


@app.post("/api/edit/make-layer")
def edit_make_layer():
    try:
        return editor.make_layer()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/edit/delete")
def edit_delete(req: IndicesRequest):
    try:
        return editor.delete_layers(req.indices)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/edit/merge")
def edit_merge(req: IndicesRequest):
    try:
        return editor.merge_layers(req.indices)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


# ---------- 自动排版（Tab2）----------
@app.post("/api/layout/auto")
def layout_auto():
    try:
        result = editor.apply_auto_layout(reset_gaps=True)
        preview = base64.b64encode(editor.layout_preview_png()).decode("ascii")
        return {
            **result,
            "preview_png_base64": preview,
            "layout_parts": editor.list_layout_parts(),
        }
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/layout/update")
def layout_update(req: LayoutUpdateRequest):
    try:
        result = editor.update_layout_params(
            scale_percent=req.scale_percent,
            spacing_px=req.spacing_px,
            selected_positions=req.selected_positions,
        )
        preview = None
        if result.get("has_laid_out"):
            preview = base64.b64encode(editor.layout_preview_png()).decode("ascii")
        return {**result, "preview_png_base64": preview, "layout_parts": editor.list_layout_parts()}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/layout/preview-part")
def layout_preview_part(req: LayoutSelectRequest):
    try:
        editor.preview_layout_part(req.list_pos)
        preview = base64.b64encode(editor.layout_preview_png()).decode("ascii")
        return {"preview_png_base64": preview, "name": editor.get_session().layout_part_names[req.list_pos - 1]}
    except (ValueError, IndexError) as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/layout/preview")
def layout_preview():
    try:
        return Response(content=editor.layout_preview_png(), media_type="image/png")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/layout/export-pdf")
def layout_export_pdf(req: PdfExportRequest):
    try:
        pdf_bytes = editor.export_pdf_from_session(req.margin_mm, req.part_expand_mm)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="layout_1to1.pdf"'},
    )


if os.getenv("SERVE_FRONTEND", "0") == "1" and FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:

    @app.get("/")
    def index_fallback():
        return {
            "message": "API 服务运行中。前端由独立项目对接，接口文档见 /docs",
            "docs": "/docs",
        }
