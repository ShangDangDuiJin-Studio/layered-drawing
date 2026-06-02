# 不织布自动分层 · Python 版

前端上传图片 → 后端**全自动颜色分区** → 流式排版 → 导出 **A4 PDF** 切割图纸。

对应原 MATLAB `TextileLayerApp` 中 Tab1（魔棒分层）+ Tab2（排版 + PDF）的无人值守流程。

## 环境

- Python 3.10+
- 依赖见 `requirements.txt`

## 安装与启动

```bash
cd python_app
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

浏览器打开：**http://127.0.0.1:8765**

## API

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 |
| `POST /api/process/pdf` | 上传图片，直接返回 PDF 文件 |
| `POST /api/process/full` | 上传图片，返回 JSON（含 base64 预览 + PDF） |

表单字段（均可选）：

- `file` — 图片文件
- `max_colors` — 最大颜色簇数（默认 24）
- `min_area_ratio` — 最小区域占比（默认 0.0008）
- `scale_percent` — 排版缩放 %（默认 100）
- `spacing_px` — 部件间距（默认 10）
- `margin_mm` — PDF 四边留白 mm（默认 15）

### 命令行示例

```bash
curl -X POST http://127.0.0.1:8765/api/process/pdf \
  -F "file=@your_pattern.png" \
  -o layout_1to1.pdf
```

## 算法说明

1. **自动分层**（替代魔棒）：颜色量化 + 连通域 → 每个色块区域为一个部件；自动剔除边框背景色。
2. **排版**：与 MATLAB `applyCFlowLayout` 相同的从左到右、自动换行逻辑。
3. **PDF**：按部件轮廓 `patch` 填色，单页 A4，内容过大时等比缩小至可打印区。

## 适用图片

- 适合：色块分明的不织布/卡通平面图（类似原工具预设部件图）
- 不适合：照片、渐变、纹理复杂图（需后续接入 SAM 等模型）

## 目录结构

```
python_app/
  run.py
  requirements.txt
  backend/
    main.py          # FastAPI
    pipeline.py      # 串联流程
    segmentation.py  # 自动分层
    layout.py        # 排版
    pdf_export.py    # PDF
    contours.py
  frontend/
    index.html
```
