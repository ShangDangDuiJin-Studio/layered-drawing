# layered-drawing · 不织布分层排版

**Python 项目，不需要 MATLAB。**

所有功能在 `python_app/` 目录下，详见 [python_app/README.md](python_app/README.md)。

## 快速开始

```bash
cd python_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器打开 http://127.0.0.1:8765

## PyQt 桌面版（可选）

`python_desktop/` 为 MATLAB 原版的 PyQt6 完整移植（含 A/B/C 三模块）。C 同学排版逻辑见 `python_desktop/part_c.py`。

```bash
cd python_desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_app.py
```

## 说明

- 根目录下的 `.m` 文件为早期 MATLAB 原型备份，**不参与运行**
- 协作开发请只修改 `python_app/` 下的 Python 代码
