# gui/styles.py — SpectraViewer UI 样式
"""现代化暗色主题样式表。

设计理念: Laboratory Precision
- 统一的深色背景，避免视觉割裂
- 青色/蓝绿色作为主强调色，体现科学仪器感
- 清晰的视觉层次，卡片式布局
- 柔和的渐变和圆角，现代感十足
"""

# ─────────────────────────────────────────────────────────────────────────────
# 颜色定义 - 统一的深灰色调
# ─────────────────────────────────────────────────────────────────────────────

# 主背景色（统一使用）
BG_BASE = "#1a1d23"          # 主背景
BG_CARD = "#22262e"          # 卡片背景
BG_INPUT = "#2a2f38"         # 输入框背景
BG_HOVER = "#333840"         # 悬停背景

# 强调色
ACCENT_PRIMARY = "#00d9ff"   # 主强调色（青色）
ACCENT_SECONDARY = "#7ee787" # 次强调色（绿色）
ACCENT_WARNING = "#f0883e"   # 警告色（橙色）
ACCENT_ERROR = "#f85149"     # 错误色（红色）
ACCENT_PURPLE = "#a371f7"    # 紫色

# 文字色
TEXT_PRIMARY = "#e6edf3"     # 主文字
TEXT_SECONDARY = "#8b949e"   # 次要文字
TEXT_MUTED = "#6e7681"       # 最淡文字

# 边框
BORDER_SUBTLE = "#30363d"
BORDER_MEDIUM = "#484f58"

# ─────────────────────────────────────────────────────────────────────────────
# 样式表组件
# ─────────────────────────────────────────────────────────────────────────────

MAIN_WINDOW = f"""
/* 全局样式 */
* {{
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
}}

/* 主窗口 */
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
}}

/* 所有标签透明背景 */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}

/* 滚动区域透明 */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
"""

BUTTONS = f"""
/* 主要按钮 */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    min-width: 80px;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {ACCENT_PRIMARY};
}}

QPushButton:pressed {{
    background-color: #1a4a5a;
}}

QPushButton:disabled {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
}}

/* 强调按钮 */
QPushButton#accent {{
    background-color: #0d5a6a;
    color: #ffffff;
    border: 1px solid #0d6a7a;
    font-weight: 600;
}}

QPushButton#accent:hover {{
    background-color: #0d6a7a;
    border-color: {ACCENT_PRIMARY};
}}
"""

INPUTS = f"""
/* 单行输入框 */
QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: {ACCENT_PRIMARY};
    selection-color: {BG_BASE};
}}

QLineEdit:hover {{
    border-color: {BORDER_MEDIUM};
}}

QLineEdit:focus {{
    border-color: {ACCENT_PRIMARY};
}}

QLineEdit:disabled {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
}}

QLineEdit::placeholder {{
    color: {TEXT_MUTED};
}}

/* 下拉框 */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 80px;
}}

QComboBox:hover {{
    border-color: {BORDER_MEDIUM};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {TEXT_SECONDARY};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_MEDIUM};
    border-radius: 4px;
    selection-background-color: #0d5a6a;
    selection-color: {TEXT_PRIMARY};
}}
"""

GROUP_BOX = f"""
/* 分组框 */
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_SUBTLE};
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
    color: {ACCENT_PRIMARY};
    background-color: {BG_CARD};
    border-radius: 4px;
}}
"""

RADIO_CHECKBOX = f"""
/* 单选按钮 */
QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    background: transparent;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {BORDER_MEDIUM};
    border-radius: 8px;
    background-color: {BG_INPUT};
}}

QRadioButton::indicator:hover {{
    border-color: {ACCENT_PRIMARY};
}}

QRadioButton::indicator:checked {{
    border-color: {ACCENT_PRIMARY};
    background-color: {BG_BASE};
    border-width: 5px;
}}

/* 复选框 */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {BORDER_MEDIUM};
    border-radius: 3px;
    background-color: {BG_INPUT};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT_PRIMARY};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT_PRIMARY};
    border-color: {ACCENT_PRIMARY};
}}
"""

SCROLL_BAR = f"""
/* 滚动条 */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background-color: {BG_INPUT};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {BORDER_MEDIUM};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background-color: {BG_INPUT};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {BORDER_MEDIUM};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""

SPLITTER = f"""
/* 分割器 */
QSplitter {{
    background-color: transparent;
}}

QSplitter::handle {{
    background-color: transparent;
}}

QSplitter::handle:horizontal {{
    width: 8px;
}}

QSplitter::handle:horizontal:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent, stop:0.3 {ACCENT_PRIMARY}, stop:0.7 {ACCENT_PRIMARY}, stop:1 transparent);
}}
"""

TOOLTIP = f"""
/* 工具提示 */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_MEDIUM};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""

# ─────────────────────────────────────────────────────────────────────────────
# 完整样式表
# ─────────────────────────────────────────────────────────────────────────────

FULL_STYLESHEET = f"""
{MAIN_WINDOW}
{BUTTONS}
{INPUTS}
{GROUP_BOX}
{RADIO_CHECKBOX}
{SCROLL_BAR}
{SPLITTER}
{TOOLTIP}
"""

# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

# 颜色常量导出（供 main_window.py 直接使用）
COLORS = {
    'bg_base': BG_BASE,
    'bg_card': BG_CARD,
    'bg_input': BG_INPUT,
    'bg_hover': BG_HOVER,
    'accent': ACCENT_PRIMARY,
    'accent_green': ACCENT_SECONDARY,
    'accent_orange': ACCENT_WARNING,
    'accent_purple': ACCENT_PURPLE,
    'accent_error': ACCENT_ERROR,
    'text': TEXT_PRIMARY,
    'text_secondary': TEXT_SECONDARY,
    'text_muted': TEXT_MUTED,
    'border': BORDER_SUBTLE,
    'border_medium': BORDER_MEDIUM,
}


def apply_styles(app_or_widget):
    """应用完整样式表到应用程序或控件。"""
    app_or_widget.setStyleSheet(FULL_STYLESHEET)


def set_status_label(label, status: str):
    """设置状态标签的样式。"""
    colors = {
        'success': ACCENT_SECONDARY,
        'error': ACCENT_ERROR,
        'warning': ACCENT_WARNING,
        'info': TEXT_SECONDARY,
    }
    color = colors.get(status, TEXT_SECONDARY)
    label.setStyleSheet(f"""
        QLabel {{
            color: {color};
            font-size: 11px;
            background: transparent;
            padding: 2px 6px;
        }}
    """)


def group_box_style(accent_color: str) -> str:
    """生成 QGroupBox 样式表，使用指定的强调色。"""
    return f"""
        QGroupBox {{
            background-color: {BG_CARD};
            border: 1px solid {accent_color};
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
            color: {accent_color};
            background-color: {BG_CARD};
            border-radius: 4px;
        }}
    """


def styled_label_style(color_key: str, font_size: int = 11, extra: str = '') -> str:
    """生成标签样式字符串。"""
    color = COLORS.get(color_key, TEXT_SECONDARY)
    return f'color: {color}; font-size: {font_size}px; background: transparent; {extra}'.strip()
