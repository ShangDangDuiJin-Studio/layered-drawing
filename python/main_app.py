"""MainApp — 不织布分层工具 Python 版（对应 MainApp.m）"""

from __future__ import annotations

import sys
from typing import List, Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from image_utils import Layer, PRESET_PART_NAMES
import part_ab
import part_c


class MainApp(QMainWindow):
    """单窗口 Tab 版：分层编辑 + 排版输出"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("不织布分层工具")
        self.resize(min(1180, 1180), min(720, 720))

        # --- A/B 编辑数据 ---
        self.layers: List[Layer] = []
        self.rgba: Optional[np.ndarray] = None
        self.rgb: Optional[np.ndarray] = None
        self.cur_mask: Optional[np.ndarray] = None
        self.color_source: int = 0
        self.current_layer_idx: int = -1
        self.contour_artists: list = []
        self.outline_artists: list = []
        self.border_color = (0.0, 1.0, 1.0)
        self.wand_tolerance = 28.0
        self.is_drawing_manual = False
        self.is_processing_wand = False
        self.is_updating_highlight = False
        self.draw_line_color = "cyan"
        self._polygon_selector = None

        # --- C 排版数据 ---
        self.c_source_layers: List[Layer] = []
        self.c_source_map: List[int] = []
        self.c_rgba: Optional[np.ndarray] = None
        self.c_rgb: Optional[np.ndarray] = None
        self.c_layers: List[Layer] = []
        self.c_laid_out_layers: List[Layer] = []
        self.c_layout_scale = 100
        self.c_layout_spacing = 10
        self.c_layout_gaps: List[int] = []
        self.c_has_laid_out = False
        self.c_is_previewing_single = False
        self.c_outline_artists: list = []
        self.pdf_margin_mm = 15.0
        self.pdf_part_expand_mm = 3.0

        self._build_ui()
        self.c_status_label.setText("请点击「刷新部件列表」同步分层编辑中的部件")

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tabs.addTab(self._build_edit_tab(), "分层编辑")
        self.tabs.addTab(self._build_layout_tab(), "排版输出")
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_edit_tab(self) -> QWidget:
        root = QWidget()
        grid = QGridLayout(root)
        grid.setContentsMargins(8, 8, 8, 8)

        # 左侧画布
        left = QGroupBox()
        left_layout = QVBoxLayout(left)
        self.canvas_title = QLabel("请点击导入图片开始")
        self.canvas_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        left_layout.addWidget(self.canvas_title)

        self.edit_fig = Figure(figsize=(6, 5), facecolor="#f0f0f0")
        self.edit_ax = self.edit_fig.add_subplot(111)
        self.edit_ax.set_xticks([])
        self.edit_ax.set_yticks([])
        self.edit_canvas = FigureCanvasQTAgg(self.edit_fig)
        self.edit_canvas.mpl_connect("button_press_event", lambda e: part_ab.on_edit_axes_click(self, e))
        left_layout.addWidget(self.edit_canvas, stretch=1)

        # 右侧
        right = QWidget()
        right_layout = QVBoxLayout(right)

        parts_box = QGroupBox("部件列表与命名")
        parts_grid = QGridLayout(parts_box)
        parts_grid.addWidget(QLabel("部件列表（可多选）"), 0, 0, 1, 2)
        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.layer_list.currentRowChanged.connect(lambda _: part_ab.on_layer_list_changed(self))
        self.layer_list.itemSelectionChanged.connect(lambda: part_ab.on_layer_list_changed(self))
        parts_grid.addWidget(self.layer_list, 1, 0, 1, 2)

        parts_grid.addWidget(QLabel("部件名称（预设 / 自定义）"), 2, 0, 1, 2)
        self.name_combo = QComboBox()
        self.name_combo.setEditable(True)
        self.name_combo.addItems(PRESET_PART_NAMES)
        self.name_combo.currentTextChanged.connect(lambda _: part_ab.apply_layer_name(self))
        parts_grid.addWidget(self.name_combo, 3, 0, 1, 2)

        self.opacity_label = QLabel("图层不透明度: 100%")
        parts_grid.addWidget(self.opacity_label, 4, 0, 1, 2)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(lambda v: part_ab.on_opacity_changed(self, v))
        parts_grid.addWidget(self.opacity_slider, 5, 0, 1, 2)

        row = QHBoxLayout()
        up_btn = QPushButton("↑ 上移")
        up_btn.clicked.connect(lambda: part_ab.move_layer_up(self))
        down_btn = QPushButton("↓ 下移")
        down_btn.clicked.connect(lambda: part_ab.move_layer_down(self))
        row.addWidget(up_btn)
        row.addWidget(down_btn)
        parts_grid.addLayout(row, 6, 0, 1, 2)

        row2 = QHBoxLayout()
        vis_btn = QPushButton("切换可见")
        vis_btn.clicked.connect(lambda: part_ab.toggle_visible(self))
        color_btn = QPushButton("选区高亮色")
        color_btn.clicked.connect(lambda: part_ab.pick_highlight_color(self))
        row2.addWidget(vis_btn)
        row2.addWidget(color_btn)
        parts_grid.addLayout(row2, 7, 0, 1, 2)
        right_layout.addWidget(parts_box, stretch=2)

        basic_box = QGroupBox("基础功能")
        basic_grid = QGridLayout(basic_box)
        import_btn = QPushButton("导入图片")
        import_btn.clicked.connect(lambda: part_ab.import_image(self))
        make_btn = QPushButton("生成图层")
        make_btn.clicked.connect(lambda: part_ab.make_layer(self))
        cancel_btn = QPushButton("取消选区")
        cancel_btn.clicked.connect(lambda: part_ab.cancel_selection(self))
        self.switch_btn = QPushButton("取色来源：原图")
        self.switch_btn.clicked.connect(lambda: part_ab.switch_color_source(self))
        basic_grid.addWidget(import_btn, 0, 0)
        basic_grid.addWidget(make_btn, 0, 1)
        basic_grid.addWidget(cancel_btn, 1, 0)
        basic_grid.addWidget(self.switch_btn, 1, 1)
        right_layout.addWidget(basic_box)

        grid.addWidget(left, 0, 0)
        grid.addWidget(right, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnMinimumWidth(1, 290)

        # 底部通栏
        draw_box = QGroupBox("精细化编辑")
        draw_layout = QHBoxLayout(draw_box)
        del_btn = QPushButton("删除部件")
        del_btn.clicked.connect(lambda: part_ab.delete_layers(self))
        merge_btn = QPushButton("合并部件")
        merge_btn.clicked.connect(lambda: part_ab.merge_layers(self))
        self.add_btn = QPushButton("添加部件")
        self.add_btn.clicked.connect(lambda: part_ab.add_manual_layer(self))
        self.status_label = QLabel("")
        draw_layout.addWidget(del_btn)
        draw_layout.addWidget(merge_btn)
        draw_layout.addWidget(self.add_btn)
        draw_layout.addWidget(self.status_label, stretch=1)
        grid.addWidget(draw_box, 1, 0, 1, 2)

        return root

    def _build_layout_tab(self) -> QWidget:
        root = QWidget()
        grid = QGridLayout(root)
        grid.setContentsMargins(8, 8, 8, 8)

        left = QGroupBox("排版预览")
        left_layout = QVBoxLayout(left)
        self.layout_fig = Figure(figsize=(6, 5), facecolor="white")
        self.layout_ax = self.layout_fig.add_subplot(111)
        self.layout_ax.set_xticks([])
        self.layout_ax.set_yticks([])
        self.layout_canvas = FigureCanvasQTAgg(self.layout_fig)
        left_layout.addWidget(self.layout_canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        sync_btn = QPushButton("刷新部件列表")
        sync_btn.clicked.connect(lambda: self.sync_data_from_edit_tab(show_alert=True))
        right_layout.addWidget(sync_btn)

        auto_btn = QPushButton("自动换行与排版")
        auto_btn.clicked.connect(self._on_auto_layout)
        right_layout.addWidget(auto_btn)

        self.c_scale_label = QLabel("动态缩放: 100%")
        right_layout.addWidget(self.c_scale_label)
        self.c_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.c_scale_slider.setRange(30, 200)
        self.c_scale_slider.setValue(100)
        self.c_scale_slider.valueChanged.connect(lambda v: part_c.on_scale_changed(self, v))
        right_layout.addWidget(self.c_scale_slider)

        self.c_spacing_label = QLabel("动态间距: 10 px")
        right_layout.addWidget(self.c_spacing_label)
        self.c_spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.c_spacing_slider.setRange(0, 120)
        self.c_spacing_slider.setValue(10)
        self.c_spacing_slider.valueChanged.connect(lambda v: part_c.on_spacing_changed(self, v))
        right_layout.addWidget(self.c_spacing_slider)

        export_btn = QPushButton("1:1 矢量 PDF 导出")
        export_btn.clicked.connect(lambda: part_c.export_pdf(self))
        right_layout.addWidget(export_btn)

        right_layout.addWidget(QLabel("部件列表（Ctrl/⌘+点击 多选相邻两项调间距）"))
        self.c_layer_list = QListWidget()
        self.c_layer_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.c_layer_list.itemSelectionChanged.connect(lambda: part_c.on_c_layer_list_changed(self))
        right_layout.addWidget(self.c_layer_list, stretch=1)

        grid.addWidget(left, 0, 0)
        grid.addWidget(right, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnMinimumWidth(1, 290)

        self.c_status_label = QLabel("")
        self.c_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.c_status_label, 1, 0, 1, 2)

        return root

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and not self.c_source_map:
            self.c_status_label.setText("请点击「刷新部件列表」同步分层编辑中的部件")

    def _on_auto_layout(self) -> None:
        if not self.c_source_map:
            if not self.sync_data_from_edit_tab(show_alert=True):
                return
        part_c.auto_layout(self)

    def sync_data_from_edit_tab(self, show_alert: bool = False) -> bool:
        """【三人共用】A/B 的 Layers → C 的唯一数据接口"""
        if not self.layers:
            if show_alert:
                QMessageBox.information(self, "提示", "请先在「分层编辑」页导入图片并生成部件。")
            return False
        self.c_source_layers = list(self.layers)
        self.c_source_map = list(range(len(self.c_source_layers)))
        if self.c_source_map and self.c_source_layers[0].name == "背景":
            self.c_source_map = self.c_source_map[1:]
        if not self.c_source_map:
            if show_alert:
                QMessageBox.information(self, "提示", "分层编辑页中只有背景层，请先生成部件。")
            return False
        self.c_rgba = self.rgba.copy() if self.rgba is not None else None
        self.c_rgb = self.rgb.copy() if self.rgb is not None else None
        self.c_has_laid_out = False
        self.c_laid_out_layers = []
        self.c_layers = []
        self.c_is_previewing_single = False
        self.c_layout_gaps = []
        part_c.refresh_c_layer_list(self)
        self.layout_ax.clear()
        self.layout_canvas.draw_idle()
        self.c_status_label.setText(f"已同步 {len(self.c_source_map)} 个部件，请点击「自动换行与排版」")
        return True


def run_app() -> None:
    app = QApplication(sys.argv)
    win = MainApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
