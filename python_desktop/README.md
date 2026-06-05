# 不织布分层工具 — Python 桌面版（PyQt6）

MATLAB 原版的 Python 移植，模块划分与三人分工一致：

| 文件 | 对应 MATLAB | 负责人 |
|------|-------------|--------|
| `main_app.py` | `MainApp.m` | 共用（界面 + 数据同步） |
| `part_ab.py` | `PartAB.m` | **A/B 同学** — 分层编辑 |
| `part_c.py` | `PartC.m` | **C 同学** — 排版输出、PDF |
| `image_utils.py` | PartAB 底部工具函数 | 共用 |
| `run_app.py` | `RunApp.m` | 启动入口 |
| `run_layout.py` | `RunLayout.m` | 直接打开排版 Tab |

> 组内主项目为根目录 `python_app/`（Web 版 FastAPI）。本目录为独立桌面客户端，逻辑与 MATLAB 版一致。
## 环境

- Python 3.10+
- 依赖见 `requirements.txt`

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 运行

```bash
cd python
python run_app.py      # 打开分层编辑
python run_layout.py   # 直接打开排版输出
```

## 功能概览

**Tab1 分层编辑（part_ab.py）**

- 导入 PNG/JPG/BMP
- 魔棒选区 → 生成部件图层
- 手绘多边形添加部件
- 删除 / 合并 / 排序 / 命名 / 不透明度

**Tab2 排版输出（part_c.py）**

- 从分层编辑同步部件
- 自动换行排版、缩放、间距
- 导出 1:1 矢量 PDF（单页 A4）

## 上传到组内 GitHub

在仓库根目录执行（把 `<仓库地址>` 换成组长给的 URL）：

```bash
git init
git add python/ .gitignore
git commit -m "Add Python port of nonwoven layer tool"
git remote add origin <仓库地址>
git branch -M main
git push -u origin main
```

若只上传自己负责的部分，例如 C 同学：

```bash
git add python/part_c.py python/image_utils.py
git commit -m "Add Part C: layout and PDF export"
git push
```

`main_app.py` 中的 `sync_data_from_edit_tab` 是 A/B 与 C 之间的唯一数据接口，与 MATLAB 版约定相同。
