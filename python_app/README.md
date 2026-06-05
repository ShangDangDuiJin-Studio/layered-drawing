# 不织布分层排版工具（Python）

**纯 Python，不需要 MATLAB。**

单页界面：**手动魔棒分层** + **自动换行排版** + **PDF 导出**（部件外扩 3mm）。

> 说明：这里是「自动排版」，不是「自动分层」。分层靠魔棒手点选区生成部件；排版靠「自动换行与排版」按钮。

## 快速开始

```bash
cd python_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器打开 http://127.0.0.1:8765

## 界面功能（与 MATLAB 简化版一致）

### 分层编辑
- 导入图片
- 魔棒选区（点击画布）
- 生成图层
- 合并部件

### 排版输出
- **自动换行与排版** → 右侧显示排版预览图
- **动态缩放** → 实时重排
- **动态间距** → 实时重排
- **多选相邻两项** → 只调整这两项之间的间距
- **单击列表某项** → 预览单个部件
- **PDF 导出** → 1:1 矢量 PDF，部件外扩 3mm

## 不包含
部件命名、不透明度、上移下移、切换可见、取色来源、手动描边添加、自动颜色分层

## 目录

```
python_app/
  run.py
  backend/
    main.py       # API
    editor.py     # 分层 + 排版状态
    layout.py     # 换行排版算法
    pdf_export.py # PDF（3mm 外扩）
    wand.py       # 魔棒
  frontend/
    index.html    # 单页 Web UI
```
