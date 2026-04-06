#!/usr/bin/env python3
"""SpectraViewer 入口。

设计理念: Laboratory Precision
- 暗色主题，科学仪器美学
- 清晰的视觉层次
- 专业的数据分析工具
"""

import sys

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.main_window import MainWindow
from gui.styles import apply_styles


def configure_matplotlib():
    """配置 matplotlib 后端和中文字体。"""
    import matplotlib
    matplotlib.use('Qt5Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


if __name__ == '__main__':
    # 配置 matplotlib（在创建应用前）
    configure_matplotlib()

    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 应用全局暗色主题
    apply_styles(app)

    # 设置默认字体
    font = QFont('Segoe UI', 10)
    app.setFont(font)

    win = MainWindow()
    win.resize(1300, 850)
    win.show()
    sys.exit(app.exec_())
