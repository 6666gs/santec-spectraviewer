#!/usr/bin/env python3
"""SpectraViewer 入口。

设计理念: Laboratory Precision
- 暗色主题，科学仪器美学
- 清晰的视觉层次
- 专业的数据分析工具
"""

import sys
import os
import platform

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.main_window import MainWindow
from gui.styles import apply_styles


def _setup_wsl_display():
    """WSL 环境下自动注入 WSLg 显示相关环境变量。"""
    if not os.path.exists('/proc/version'):
        return
    try:
        with open('/proc/version') as f:
            if 'microsoft' not in f.read().lower():
                return
    except OSError:
        return

    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
    if not os.environ.get('WAYLAND_DISPLAY'):
        os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
    # 使用用户自己的 runtime dir 避免 WSLg 目录权限警告
    if not os.environ.get('XDG_RUNTIME_DIR'):
        uid = os.getuid()
        user_runtime = f'/run/user/{uid}'
        if os.path.isdir(user_runtime):
            os.environ['XDG_RUNTIME_DIR'] = user_runtime
        else:
            os.environ['XDG_RUNTIME_DIR'] = '/mnt/wslg/runtime-dir'


def _get_system_font():
    """根据平台返回合适的 UI 字体。"""
    system = platform.system()
    if system == 'Darwin':
        return 'SF Pro Text', 'Helvetica Neue', 'Helvetica'
    elif system == 'Windows':
        return 'Segoe UI', 'Microsoft YaHei'
    else:
        return 'Noto Sans', 'DejaVu Sans', 'sans-serif'


def _get_matplotlib_fonts():
    """根据平台返回 matplotlib 中文/衬线字体列表。"""
    system = platform.system()
    if system == 'Darwin':
        return ['PingFang SC', 'Heiti SC', 'Arial Unicode MS', 'DejaVu Sans']
    elif system == 'Windows':
        return ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    else:
        return ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'DejaVu Sans']


def configure_matplotlib():
    """配置 matplotlib 后端和中文字体。"""
    import matplotlib

    matplotlib.use('Qt5Agg')
    import matplotlib.pyplot as plt

    plt.rcParams['font.sans-serif'] = _get_matplotlib_fonts()
    plt.rcParams['axes.unicode_minus'] = False


if __name__ == '__main__':
    # WSL 下自动配置显示环境变量（需在 Qt 初始化前）
    _setup_wsl_display()

    # 配置 matplotlib（在创建应用前）
    configure_matplotlib()

    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 应用全局主题
    apply_styles(app)

    # 设置默认字体
    font = QFont(_get_system_font()[0], 10)
    app.setFont(font)

    win = MainWindow()
    win.resize(1300, 850)
    win.show()
    sys.exit(app.exec_())
