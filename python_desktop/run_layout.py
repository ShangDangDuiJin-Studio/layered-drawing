#!/usr/bin/env python3
"""启动主程序并打开「排版输出」Tab — 对应 RunLayout.m"""

import sys
from PyQt6.QtWidgets import QApplication

from main_app import MainApp


def main() -> None:
    app = QApplication(sys.argv)
    win = MainApp()
    win.show()
    win.tabs.setCurrentIndex(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
