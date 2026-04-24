# gui/main_window.py — 主窗口
"""SpectraViewer 主窗口 GUI。

设计理念: Laboratory Precision
- 暗色主题，减少视觉疲劳
- 清晰的功能分区
- 现代化的卡片式布局
"""

import os
import re
import subprocess
import numpy as np
import matplotlib.pyplot as plt

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QAbstractItemView,
    QSizePolicy,
    QHeaderView,
    QSplitter,
    QCheckBox,
    QFrame,
    QScrollArea,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from core.manager import SpectraManager
from core.grid import interp_on_grid
from visualization.plotter import plot_publication
from analysis.ring import Ring
from analysis.peak import analyze_peaks, calc_3db_bandwidth, format_peak_results
from .widgets import redirect_stdout_to
from .styles import (
    apply_styles,
    set_status_label,
    COLORS,
    group_box_style,
    styled_label_style,
)

# 颜色常量
C = COLORS

# 浅色工具栏样式（覆盖全局暗色主题，用于弹出绘图窗口）
_TOOLBAR_LIGHT_STYLE = """
QToolBar {
    background-color: #e8e8e8;
    border-bottom: 1px solid #c0c0c0;
    spacing: 3px;
    padding: 2px 4px;
}
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 5px;
}
QToolButton:hover {
    background-color: #d0d0d0;
    border-color: #b0b0b0;
}
QToolButton:pressed {
    background-color: #c0c0c0;
}
QToolButton:checked {
    background-color: #c8ddf0;
    border-color: #8ab4e0;
}
QStatusBar {
    background-color: #f0f0f0;
    color: #333333;
}
QStatusBar QLabel {
    color: #333333;
}
"""


def _is_wsl():
    """检测是否运行在 WSL 环境中。"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False


def _win_path_to_wsl(win_path):
    """将 Windows 路径转换为 WSL 路径。"""
    if not win_path:
        return ''
    path = win_path.replace('\\', '/')
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        drive = f'{letter}:'
        if path.startswith(drive):
            return f'/mnt/{letter.lower()}{path[len(drive):]}'
    return path


def _windows_folder_dialog():
    """调用 Windows 原生文件夹选择器，返回 WSL 路径。"""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-Command',
         '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
         'Add-Type -AssemblyName System.Windows.Forms; '
         '$f = New-Object System.Windows.Forms.FolderBrowserDialog; '
         'if ($f.ShowDialog() -eq "OK") { $f.SelectedPath }'],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    return _win_path_to_wsl(result.stdout.strip())


def _windows_file_dialog(title='选择文件', filter='CSV 文件 (*.csv)'):
    """调用 Windows 原生文件选择器，返回 WSL 路径。"""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-Command',
         '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
         'Add-Type -AssemblyName System.Windows.Forms; '
         '$f = New-Object System.Windows.Forms.OpenFileDialog; '
         f'$f.Title = "{title}"; '
         f'$f.Filter = "{filter}|*.csv|All files (*.*)|*.*"; '
         'if ($f.ShowDialog() -eq "OK") { $f.FileName }'],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    return _win_path_to_wsl(result.stdout.strip())


_IS_WSL = _is_wsl()


def _parse_float_edit(edit):
    """从 QLineEdit 解析浮点数，空或无效返回 None。"""
    t = edit.text().strip()
    try:
        return float(t) if t else None
    except ValueError:
        return None


class MainWindow(QWidget):
    """SpectraViewer 主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle('SpectraViewer - 光谱数据可视化')
        self.mgr = None
        self.ref_path = None
        self._build_ui()
        self._redirect_stdout()
        apply_styles(self)

    # ── 弹出绘图窗口工具栏样式 ──────────────────────────────────────────────
    @staticmethod
    def _style_popup(fig):
        """给弹出绘图窗口应用浅色工具栏样式。"""
        try:
            window = fig.canvas.manager.window
            window.setStyleSheet(_TOOLBAR_LIGHT_STYLE)
        except Exception:
            pass

    # ── UI 构建 ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # 顶部工具栏
        root.addWidget(self._build_toolbar())

        # 主内容区域
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_table_panel())
        splitter.addWidget(self._build_control_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        # 底部日志
        root.addWidget(self._build_log_panel())

    def _build_toolbar(self):
        """构建顶部工具栏。"""
        toolbar = QFrame()
        toolbar.setObjectName('toolbar')
        toolbar.setStyleSheet(
            f"""
            QFrame#toolbar {{
                background-color: {C['bg_card']};
                border: 1px solid {C['border']};
                border-radius: 8px;
            }}
            QFrame#toolbar QLabel {{
                background: transparent;
                color: {C['text']};
            }}
        """
        )

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 文件夹选择
        self.btn_folder = QPushButton('  选择文件夹')
        self.btn_folder.setToolTip('选择包含光谱数据的文件夹')
        self.btn_folder.clicked.connect(self._on_select_folder)
        layout.addWidget(self.btn_folder)

        # 分隔符
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet(f'background-color: {C["border"]}; border: none;')
        sep1.setFixedWidth(1)
        layout.addWidget(sep1)

        # 数据类型
        layout.addWidget(QLabel('数据类型:'))
        self.combo_type = QComboBox()
        self.combo_type.addItems(['auto', 'loss', 'raw'])
        self.combo_type.setToolTip('选择数据解析模式')
        self.combo_type.currentTextChanged.connect(self._on_type_changed)
        layout.addWidget(self.combo_type)

        # Reference 文件
        self.btn_ref = QPushButton('  Reference')
        self.btn_ref.setToolTip('选择参考文件用于校准')
        self.btn_ref.clicked.connect(self._on_select_ref)
        layout.addWidget(self.btn_ref)

        # Reference 状态
        self.lbl_ref = QLabel(' 未选择 ')
        self.lbl_ref.setStyleSheet(
            f"""
            QLabel {{
                color: {C['text_secondary']};
                font-size: 11px;
                background: transparent;
                padding: 2px 6px;
            }}
        """
        )
        layout.addWidget(self.lbl_ref)

        layout.addStretch()

        # 当前路径
        self.lbl_path = QLabel(' 请选择数据文件夹 ')
        self.lbl_path.setStyleSheet(
            f"""
            QLabel {{
                color: {C['text_secondary']};
                font-size: 11px;
                padding: 4px 8px;
                background-color: {C['bg_input']};
                border-radius: 4px;
            }}
        """
        )
        self.lbl_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.lbl_path)

        return toolbar

    def _build_table_panel(self):
        """构建数据表格面板。"""
        panel = QFrame()
        panel.setStyleSheet(
            f"""
            QFrame {{
                background-color: {C['bg_card']};
                border: 1px solid {C['border']};
                border-radius: 8px;
            }}
        """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        header = QLabel('  数据列表')
        header.setStyleSheet(
            f"""
            QLabel {{
                color: {C['accent']};
                font-size: 13px;
                font-weight: 600;
                padding: 10px 12px;
                background-color: {C['bg_input']};
                border-bottom: 1px solid {C['border']};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
        """
        )
        layout.addWidget(header)

        # 表格
        cols = [
            '#',
            'device',
            'device_no',
            'port',
            'start_nm',
            'end_nm',
            'step',
            'range',
            'source_dbm',
            'data_type',
        ]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._on_row_double_click)

        # 表格样式
        self.table.setStyleSheet(
            f"""
            QTableWidget {{
                background-color: {C['bg_base']};
                alternate-background-color: {C['bg_card']};
                color: {C['text']};
                gridline-color: {C['bg_input']};
                border: none;
                border-top: 1px solid {C['border']};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                selection-background-color: #0d4a5a;
                selection-color: #ffffff;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {C['bg_input']};
            }}
            QTableWidget::item:hover {{
                background-color: {C['bg_hover']};
            }}
            QTableWidget::item:selected {{
                background-color: #0d4a5a;
            }}
            QHeaderView::section {{
                background-color: {C['bg_input']};
                color: {C['text_secondary']};
                font-weight: 600;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid {C['accent']};
                border-right: 1px solid {C['border']};
            }}
            QHeaderView::section:hover {{
                background-color: {C['bg_hover']};
                color: {C['text']};
            }}
        """
        )
        layout.addWidget(self.table)

        return panel

    def _build_control_panel(self):
        """构建右侧控制面板。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
        """
        )

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 公式计算
        layout.addWidget(self._build_formula_group())

        # 绘图按钮
        btn_multi_plot = QPushButton('  绘制选中行')
        btn_multi_plot.setObjectName('accent')
        btn_multi_plot.setToolTip('绘制表格中选中的数据行')
        btn_multi_plot.clicked.connect(self._on_multi_plot)
        layout.addWidget(btn_multi_plot)

        # 图像标签
        layout.addWidget(self._build_labels_group())

        # 坐标轴范围
        layout.addWidget(self._build_range_group())

        # 峰值分析
        layout.addWidget(self._build_peak_panel())

        # 微环分析
        layout.addWidget(self._build_ring_panel())

        layout.addStretch()
        scroll.setWidget(panel)
        return scroll

    def _build_formula_group(self):
        """构建公式计算分组。"""
        grp = QGroupBox(' 公式计算 ')
        grp.setProperty('data-type', 'formula')
        grp.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {C['bg_card']};
                border: 1px solid {C['accent_purple']};
                border-radius: 8px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                font-weight: 500;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                color: {C['accent_purple']};
                background-color: {C['bg_card']};
                border-radius: 4px;
            }}
        """
        )

        vbox = QVBoxLayout(grp)
        vbox.setSpacing(8)

        hint = QLabel('使用 A0, A1, A2... 表示列表序号')
        hint.setStyleSheet(
            f'color: {C["text_muted"]}; font-size: 11px; background: transparent;'
        )
        vbox.addWidget(hint)

        self.formula_edit = QLineEdit()
        self.formula_edit.setPlaceholderText('例如: A12 - A1 - (A2 - A1) * 2')
        self.formula_edit.setToolTip('输入数学表达式，支持加减乘除和括号')
        vbox.addWidget(self.formula_edit)

        self.lbl_formula_err = QLabel('')
        self.lbl_formula_err.setStyleSheet(styled_label_style('accent_error', 11))
        vbox.addWidget(self.lbl_formula_err)

        btn_formula_plot = QPushButton('  公式绘图')
        btn_formula_plot.clicked.connect(self._on_formula_plot)
        vbox.addWidget(btn_formula_plot)

        return grp

    def _build_labels_group(self):
        """构建图像标签分组。"""
        grp = QGroupBox(' 图像标签 ')
        grp.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {C['bg_card']};
                border: 1px solid {C['border']};
                border-radius: 8px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                font-weight: 500;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                color: {C['accent']};
                background-color: {C['bg_card']};
                border-radius: 4px;
            }}
        """
        )

        form = QFormLayout(grp)
        form.setSpacing(8)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText('图像标题（可选）')
        form.addRow('标题:', self.title_edit)

        self.xlabel_edit = QLineEdit('Wavelength (nm)')
        form.addRow('X 轴:', self.xlabel_edit)

        self.ylabel_edit = QLineEdit('Insertion Loss (dB)')
        form.addRow('Y 轴:', self.ylabel_edit)

        return grp

    def _build_range_group(self):
        """构建坐标轴范围分组。"""
        grp = QGroupBox(' 坐标轴范围 ')
        grp.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {C['bg_card']};
                border: 1px solid {C['border']};
                border-radius: 8px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                font-weight: 500;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                color: {C['accent']};
                background-color: {C['bg_card']};
                border-radius: 4px;
            }}
        """
        )

        form = QFormLayout(grp)
        form.setSpacing(8)

        # X 范围
        xrange_w = QWidget()
        xrange_h = QHBoxLayout(xrange_w)
        xrange_h.setContentsMargins(0, 0, 0, 0)
        xrange_h.setSpacing(4)
        self.xmin_edit = QLineEdit()
        self.xmax_edit = QLineEdit()
        self.xmin_edit.setPlaceholderText('最小')
        self.xmax_edit.setPlaceholderText('最大')
        xrange_h.addWidget(self.xmin_edit)
        tilde_x = QLabel('~')
        tilde_x.setStyleSheet(f'color: {C["text_muted"]}; background: transparent;')
        tilde_x.setAlignment(Qt.AlignCenter)
        tilde_x.setFixedWidth(20)
        xrange_h.addWidget(tilde_x)
        xrange_h.addWidget(self.xmax_edit)
        form.addRow('X 范围:', xrange_w)

        # Y 范围
        yrange_w = QWidget()
        yrange_h = QHBoxLayout(yrange_w)
        yrange_h.setContentsMargins(0, 0, 0, 0)
        yrange_h.setSpacing(4)
        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.ymin_edit.setPlaceholderText('最小')
        self.ymax_edit.setPlaceholderText('最大')
        yrange_h.addWidget(self.ymin_edit)
        tilde_y = QLabel('~')
        tilde_y.setStyleSheet(styled_label_style('text_muted'))
        tilde_y.setAlignment(Qt.AlignCenter)
        tilde_y.setFixedWidth(20)
        yrange_h.addWidget(tilde_y)
        yrange_h.addWidget(self.ymax_edit)
        form.addRow('Y 范围:', yrange_w)

        hint = QLabel('留空表示自动范围')
        hint.setStyleSheet(styled_label_style('text_muted', 10))
        form.addRow('', hint)

        return grp

    def _build_peak_panel(self):
        """构建峰值分析面板。"""
        grp = QGroupBox(' 峰值 / 谷值分析 ')
        grp.setProperty('data-type', 'peak')
        grp.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {C['bg_card']};
                border: 1px solid {C['accent_orange']};
                border-radius: 8px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                font-weight: 500;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                color: {C['accent_orange']};
                background-color: {C['bg_card']};
                border-radius: 4px;
            }}
        """
        )

        vbox = QVBoxLayout(grp)
        vbox.setSpacing(8)

        # 峰值/谷值选择
        mode_w = QWidget()
        mode_h = QHBoxLayout(mode_w)
        mode_h.setContentsMargins(0, 0, 0, 0)
        mode_h.setSpacing(16)
        self.radio_peak = QRadioButton('峰值（极大点）')
        self.radio_valley = QRadioButton('谷值（极小点）')
        self.radio_peak.setChecked(True)
        self._peak_group = QButtonGroup()
        self._peak_group.addButton(self.radio_peak)
        self._peak_group.addButton(self.radio_valley)
        mode_h.addWidget(self.radio_peak)
        mode_h.addWidget(self.radio_valley)
        mode_h.addStretch()
        vbox.addWidget(mode_w)

        # 参数表单
        form = QFormLayout()
        form.setSpacing(6)

        # 搜索范围
        xsearch_w = QWidget()
        xsearch_h = QHBoxLayout(xsearch_w)
        xsearch_h.setContentsMargins(0, 0, 0, 0)
        xsearch_h.setSpacing(4)
        self.peak_xmin = QLineEdit()
        self.peak_xmax = QLineEdit()
        self.peak_xmin.setPlaceholderText('最小')
        self.peak_xmax.setPlaceholderText('最大')
        xsearch_h.addWidget(self.peak_xmin)
        tilde = QLabel('~')
        tilde.setStyleSheet(styled_label_style('text_muted'))
        tilde.setAlignment(Qt.AlignCenter)
        tilde.setFixedWidth(20)
        xsearch_h.addWidget(tilde)
        xsearch_h.addWidget(self.peak_xmax)
        form.addRow('搜索范围:', xsearch_w)

        # 阈值
        self.peak_threshold = QLineEdit()
        self.peak_threshold.setPlaceholderText('留空表示不限')
        form.addRow('阈值 (dB):', self.peak_threshold)

        # 最小间距
        self.peak_distance = QLineEdit('50')
        form.addRow('最小间距:', self.peak_distance)

        vbox.addLayout(form)

        btn_analyze = QPushButton('  分析')
        btn_analyze.clicked.connect(self._on_peak_analyze)
        vbox.addWidget(btn_analyze)

        return grp

    def _build_ring_panel(self):
        """构建微环分析面板。"""
        grp = QGroupBox(' 微环谐振器分析 ')
        grp.setProperty('data-type', 'ring')
        grp.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {C['bg_card']};
                border: 1px solid {C['accent_green']};
                border-radius: 8px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                font-weight: 500;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                color: {C['accent_green']};
                background-color: {C['bg_card']};
                border-radius: 4px;
            }}
        """
        )

        vbox = QVBoxLayout(grp)
        vbox.setSpacing(8)

        # 波长范围
        form = QFormLayout()
        form.setSpacing(6)

        xrange_w = QWidget()
        xrange_h = QHBoxLayout(xrange_w)
        xrange_h.setContentsMargins(0, 0, 0, 0)
        xrange_h.setSpacing(4)
        self.ring_xmin = QLineEdit()
        self.ring_xmax = QLineEdit()
        self.ring_xmin.setPlaceholderText('起始')
        self.ring_xmax.setPlaceholderText('终止')
        xrange_h.addWidget(self.ring_xmin)
        tilde = QLabel('~')
        tilde.setStyleSheet(styled_label_style('text_muted'))
        tilde.setAlignment(Qt.AlignCenter)
        tilde.setFixedWidth(20)
        xrange_h.addWidget(tilde)
        xrange_h.addWidget(self.ring_xmax)
        form.addRow('波长范围 (nm):', xrange_w)

        # 阈值
        self.ring_threshold = QLineEdit()
        self.ring_threshold.setPlaceholderText('留空表示不限')
        form.addRow('阈值 (dB):', self.ring_threshold)

        # 最小间距
        self.ring_distance = QLineEdit('0')
        self.ring_distance.setPlaceholderText('0 表示自动')
        form.addRow('最小间距:', self.ring_distance)

        vbox.addLayout(form)

        self.chk_ring_holdon = QCheckBox('显示单峰拟合（最多10个）')
        vbox.addWidget(self.chk_ring_holdon)

        btn_ring = QPushButton('  微环分析')
        btn_ring.clicked.connect(self._on_ring_analyze)
        vbox.addWidget(btn_ring)

        return grp

    def _build_log_panel(self):
        """构建底部日志面板。"""
        panel = QFrame()
        panel.setStyleSheet(
            f"""
            QFrame {{
                background-color: {C['bg_base']};
                border: 1px solid {C['border']};
                border-radius: 6px;
            }}
        """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        header = QLabel('  输出日志')
        header.setStyleSheet(
            f"""
            QLabel {{
                color: {C['text_muted']};
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 4px 10px;
                background-color: {C['bg_card']};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """
        )
        layout.addWidget(header)

        # 日志内容
        self.log = QTextEdit()
        self.log.setObjectName('log')
        self.log.setReadOnly(True)
        self.log.setFixedHeight(100)
        self.log.setFont(QFont('Cascadia Code', 9))
        self.log.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {C['bg_base']};
                color: {C['text_secondary']};
                border: none;
                border-top: 1px solid {C['bg_input']};
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 6px 8px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 11px;
            }}
        """
        )
        layout.addWidget(self.log)

        return panel

    def _redirect_stdout(self):
        redirect_stdout_to(self.log)

    # ── 事件处理 ──────────────────────────────────────────────────────────────
    def _on_type_changed(self, text):
        pass

    def _on_select_ref(self):
        if _IS_WSL:
            path = _windows_file_dialog('选择 Reference 文件', 'CSV 文件 (*.csv)')
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, '选择 Reference 文件', '', 'CSV 文件 (*.csv)'
            )
        if path:
            self.ref_path = path
            short = path.split('/')[-1].split('\\')[-1]
            self.lbl_ref.setText(f' {short} ')
            set_status_label(self.lbl_ref, 'success')
            print(f'Reference 文件: {path}')
            if self.mgr is not None:
                folder = (
                    self.lbl_path.text()
                    .replace(' ', '')
                    .replace('请选择数据文件夹', '')
                )
                if folder:
                    dtype = self.combo_type.currentText()
                    try:
                        self.mgr = SpectraManager.from_folder(
                            folder, data_type=dtype, reference_path=path
                        )
                        self._populate_table()
                        print(f'已重新加载数据（已应用 Reference）')
                    except Exception as e:
                        print(f'重新加载失败: {e}')

    def _on_select_folder(self):
        if _IS_WSL:
            folder = _windows_folder_dialog()
        else:
            folder = QFileDialog.getExistingDirectory(self, '选择数据文件夹')
        if not folder:
            return
        short_path = folder
        if len(folder) > 50:
            short_path = '...' + folder[-47:]
        self.lbl_path.setText(f' {short_path} ')
        dtype = self.combo_type.currentText()
        ref = self.ref_path
        try:
            self.mgr = SpectraManager.from_folder(
                folder, data_type=dtype, reference_path=ref
            )
            self._populate_table()
            print(f'已加载 {len(self.mgr.keys)} 条数据')
        except Exception as e:
            print(f'加载失败: {e}')

    def _populate_table(self):
        if self.mgr is None:
            return
        df = self.mgr.table
        self.table.setRowCount(0)
        cols = [
            'index',
            'device',
            'device_no',
            'port',
            'start_nm',
            'end_nm',
            'step',
            'range',
            'source_dbm',
            'data_type',
        ]
        for _, row in df.iterrows():
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, col in enumerate(cols):
                val = str(row.get(col, ''))
                item = QTableWidgetItem(val)
                item.setTextAlignment(int(Qt.AlignCenter))
                self.table.setItem(r, c, item)

    def _on_row_double_click(self, item):
        row = item.row()
        idx = int(self.table.item(row, 0).text())
        self._plot_indices([idx])

    def _on_multi_plot(self):
        rows = {i.row() for i in self.table.selectedItems()}
        if not rows:
            print('请先在列表中选择数据行')
            return
        indices = [int(self.table.item(r, 0).text()) for r in sorted(rows)]
        self._plot_indices(indices)

    # ── 绘图核心 ──────────────────────────────────────────────────────────────
    def _get_plot_params(self):
        title = self.title_edit.text().strip() or None
        xlabel = self.xlabel_edit.text().strip() or 'Wavelength (nm)'
        ylabel = self.ylabel_edit.text().strip() or 'Insertion Loss (dB)'

        xmin = _parse_float_edit(self.xmin_edit)
        xmax = _parse_float_edit(self.xmax_edit)
        ymin = _parse_float_edit(self.ymin_edit)
        ymax = _parse_float_edit(self.ymax_edit)
        xlim = (xmin, xmax) if (xmin is not None and xmax is not None) else None
        ylim = (ymin, ymax) if (ymin is not None and ymax is not None) else None
        return title, xlabel, ylabel, xlim, ylim

    def _plot_indices(self, indices):
        if self.mgr is None:
            print('请先加载数据')
            return
        title, xlabel, ylabel, xlim, ylim = self._get_plot_params()
        data_list = []
        for idx in indices:
            try:
                x, y = self.mgr.get_xy(idx)
                meta = self.mgr._parse_var_key(self.mgr.keys[idx])
                dev = meta.get('device', '')
                dev_no = meta.get('device_no', '') or ''
                port = meta.get('port', '') or ''
                label = f'[{idx}] {dev} {dev_no} {port}'.strip()
                data_list.append({'x': x, 'y': y, 'label': label})
            except Exception as e:
                print(f'读取索引 {idx} 失败: {e}')
        if not data_list:
            return
        fig, ax = plot_publication(
            data_list, xlabel=xlabel, ylabel=ylabel, title=title, xlim=xlim, ylim=ylim
        )
        self._style_popup(fig)
        plt.show(block=False)
        return fig, ax

    # ── 公式绘图 ──────────────────────────────────────────────────────────────
    def _on_formula_plot(self):
        self.lbl_formula_err.setText('')
        if self.mgr is None:
            self.lbl_formula_err.setText('请先加载数据')
            return
        expr = self.formula_edit.text().strip()
        if not expr:
            self.lbl_formula_err.setText('请输入公式')
            return
        try:
            x_result, y_result = self._eval_formula(expr)
        except Exception as e:
            self.lbl_formula_err.setText(str(e))
            return

        title, xlabel, ylabel, xlim, ylim = self._get_plot_params()
        label = expr
        fig, ax = plot_publication(
            [{'x': x_result, 'y': y_result, 'label': label}],
            xlabel=xlabel,
            ylabel=ylabel,
            title=title,
            xlim=xlim,
            ylim=ylim,
        )
        self._style_popup(fig)
        plt.show(block=False)
        return fig, ax

    def _eval_formula(self, expr):
        """解析并计算形如 A12 - A1 - (A2 - A1) * 2 的表达式。"""
        indices = [int(m) for m in re.findall(r'A(\d+)', expr)]
        if not indices:
            raise ValueError('公式中未找到 A{n} 变量（如 A0, A1...）')
        n = len(self.mgr.keys)
        for idx in indices:
            if idx < 0 or idx >= n:
                raise ValueError(f'索引 A{idx} 超出范围（共 {n} 条数据，索引 0~{n-1}）')

        xy_map = {}
        for idx in set(indices):
            xy_map[idx] = self.mgr.get_xy(idx)

        x_min = max(float(xy_map[i][0].min()) for i in xy_map)
        x_max = min(float(xy_map[i][0].max()) for i in xy_map)
        if x_min >= x_max:
            raise ValueError('各数据的 x 范围无交集，无法计算公式')

        base_idx = max(xy_map, key=lambda i: len(xy_map[i][0]))
        x_base = xy_map[base_idx][0]
        mask = (x_base >= x_min) & (x_base <= x_max)
        x_common = x_base[mask]
        if len(x_common) < 2:
            raise ValueError('交集范围内数据点不足')

        local_vars = {}
        for idx, (x_src, y_src) in xy_map.items():
            if np.array_equal(x_src, x_common):
                y_aligned = y_src
            else:
                y_aligned = interp_on_grid(x_src, y_src, x_common, mode='edge')
            local_vars[f'_v{idx}'] = y_aligned

        safe_expr = re.sub(r'A(\d+)', r'_v\1', expr)
        result = eval(safe_expr, {'__builtins__': {}, 'np': np}, local_vars)
        return x_common, np.asarray(result, dtype=float)

    # ── 峰值/谷值分析 ─────────────────────────────────────────────────────────
    def _get_analysis_data(self):
        """获取当前待分析的 (x, y, label)。"""
        if self.mgr is None:
            print('请先加载数据')
            return None

        expr = self.formula_edit.text().strip()
        if expr:
            try:
                x, y = self._eval_formula(expr)
                self.lbl_formula_err.setText('')
                return x, y, expr, f'公式: {expr}'
            except Exception:
                pass

        rows = {i.row() for i in self.table.selectedItems()}
        if not rows:
            print('请先在列表中选择要分析的数据行（或在公式框中输入有效公式）')
            return None
        if len(rows) > 1:
            print('分析每次只支持单条数据，请只选择一行')
            return None
        idx = int(self.table.item(list(rows)[0], 0).text())
        try:
            x, y = self.mgr.get_xy(idx)
        except Exception as e:
            print(f'读取数据失败: {e}')
            return None
        meta = self.mgr._parse_var_key(self.mgr.keys[idx])
        dev = meta.get('device', '')
        label = f'[{idx}] {dev}'.strip()
        return x, y, label, f'索引 {idx}'

    def _on_peak_analyze(self):
        result = self._get_analysis_data()
        if result is None:
            return
        x, y, label, source_desc = result

        xmin = _parse_float_edit(self.peak_xmin)
        xmax = _parse_float_edit(self.peak_xmax)
        threshold_str = self.peak_threshold.text().strip()
        threshold = float(threshold_str) if threshold_str else None

        dist_str = self.peak_distance.text().strip()
        distance = int(dist_str) if dist_str else 50

        x_range = None
        if xmin is not None or xmax is not None:
            x_range = (xmin, xmax)

        is_peak = self.radio_peak.isChecked()

        # 调用分析模块
        results = analyze_peaks(
            x,
            y,
            is_peak=is_peak,
            x_range=x_range,
            threshold=threshold,
            distance=distance,
        )

        if len(results['peaks_idx']) == 0:
            print(f'未找到{"峰值" if is_peak else "谷值"}，尝试调整阈值或搜索范围')
            return

        # 绘图
        title, xlabel, ylabel, xlim, ylim = self._get_plot_params()
        fig, ax = plot_publication(
            [{'x': x, 'y': y, 'label': label}],
            xlabel=xlabel,
            ylabel=ylabel,
            title=title,
            xlim=xlim,
            ylim=ylim,
        )

        print(f'\n{"峰值" if is_peak else "谷值"}分析结果（{source_desc}）:')
        lines = format_peak_results(results, is_peak)
        for line in lines:
            print(line)

        # 标注 — 智能定位，确保文字始终在绘图区域内
        y_lo, y_hi = ax.get_ylim()
        y_range = y_hi - y_lo if y_hi != y_lo else 1
        for i, (px, py) in enumerate(zip(results['x_peaks'], results['y_peaks'])):
            bw = calc_3db_bandwidth(x, y, results['peaks_idx'][i], is_peak)
            bw_str = f'{bw:.4f} nm' if bw is not None else 'N/A'
            ax.axvline(px, color='red', linestyle='--', linewidth=1, alpha=0.7)
            # 根据峰/谷在 y 轴中的位置决定标注方向（像素偏移）
            rel = (py - y_lo) / y_range
            if is_peak:
                y_off = -25 if rel > 0.7 else 25
            else:
                y_off = 25 if rel < 0.3 else -25
            ax.annotate(
                f'{px:.3f} nm\n{py:.2f} dB\nBW={bw_str}',
                xy=(px, py),
                xytext=(0, y_off),
                textcoords='offset points',
                fontsize=8,
                color='red',
                ha='center',
                arrowprops=dict(arrowstyle='->', color='red', lw=1),
            )

        fig.canvas.draw()
        self._style_popup(fig)
        plt.show(block=False)

    # ── 微环谐振器分析 ────────────────────────────────────────────────────────
    def _on_ring_analyze(self):
        result = self._get_analysis_data()
        if result is None:
            return
        x, y, label, source_desc = result

        xmin = _parse_float_edit(self.ring_xmin)
        xmax = _parse_float_edit(self.ring_xmax)
        range_nm = (xmin, xmax) if (xmin is not None and xmax is not None) else None

        # 新增参数
        height_threshold = _parse_float_edit(self.ring_threshold)
        min_distance_val = _parse_float_edit(self.ring_distance)
        min_distance = int(min_distance_val) if min_distance_val else None

        try:
            ring = Ring(x, y)
            print(f'\n微环分析（{source_desc}）...')
            fig_fsr = ring.cal_fsr(
                range_nm=range_nm, display=True,
                height_threshold=height_threshold,
                min_distance=min_distance,
            )
            print(f'FSR 均值: {ring.fsr_mean:.4f} nm')
            holdon = self.chk_ring_holdon.isChecked()
            fig_q = ring.cal_Q(holdon=holdon, max_holdon=10)
            self._style_popup(fig_fsr)
            self._style_popup(fig_q)
            plt.show(block=False)
            if hasattr(ring, 'fit_results') and ring.fit_results:
                self._print_ring_results(ring)
        except Exception as e:
            print(f'微环分析失败: {e}')

    def _print_ring_results(self, ring):
        """以论文表格格式打印微环分析结果。"""
        fr = ring.fit_results
        sep = '─' * 55

        # 按波长排序
        fr_sorted = sorted(fr, key=lambda r: r['lambda0'])

        print(sep)
        print(f'FSR = {ring.fsr_mean:.4f} nm')
        print(sep)
        print(f'{"λ₀(nm)":>10}  {"Ql":>8}  {"Qi":>8}  {"ER(dB)":>7}  {"γ(pm)":>7}  {"R²":>6}')
        print(sep)
        for r in fr_sorted:
            er_db = -10 * np.log10(max(1 - r['params'][1], 1e-12))
            gamma_pm = r['gamma'] * 1e3
            print(
                f'{r["lambda0"]:10.3f}  '
                f'{r["Ql"]:8.0f}  '
                f'{r["Qi"]:8.0f}  '
                f'{er_db:7.1f}  '
                f'{gamma_pm:7.2f}  '
                f'{r["r_squared"]:6.4f}'
            )
        print(sep)
        ql_vals = [r['Ql'] for r in fr if np.isfinite(r['Ql']) and r['Ql'] > 0]
        qi_vals = [r['Qi'] for r in fr if np.isfinite(r['Qi']) and r['Qi'] > 0]
        if ql_vals:
            print(f'均值 Ql = {np.mean(ql_vals):.0f} ± {np.std(ql_vals):.0f}')
        if qi_vals:
            print(f'均值 Qi = {np.mean(qi_vals):.0f} ± {np.std(qi_vals):.0f}')
        print(sep)
