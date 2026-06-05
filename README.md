# layered-drawing · 不织布分层工具

**Python 项目，不需要 MATLAB。**

所有功能在 `python/` 目录下，详见 [python/README.md](python/README.md)。

## 快速开始

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_app.py
```

直接打开排版 Tab：`python run_layout.py`

## 模块分工

| 文件 | 负责人 |
|------|--------|
| `part_ab.py` | A/B — 分层编辑 |
| `part_c.py` | C — 排版输出、PDF |
| `main_app.py` | 共用界面与数据同步 |

## 说明

- 旧版 `python_app/`（Web 简化版）已移除，当前以 PyQt6 桌面版为准，功能与 MATLAB 原版一致
- 协作开发请修改 `python/` 下的代码
