# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
python main.py
```

本项目无 linter、测试框架或打包配置，为纯 Python 桌面应用。

## 目录结构

```
spectraviewer/
├── main.py                     # 入口 (高 DPI + matplotlib 配置)
│
├── core/                       # 数据层 (无 PyQt5 依赖)
│   ├── io.py                   # CSV 读取
│   ├── manager.py              # SpectraManager
│   ├── grid.py                 # 网格/插值工具
│   └── utils.py                # 通用工具
│
├── analysis/                   # 分析层 (无 PyQt5 依赖)
│   ├── ring.py                 # 微环谐振器 FSR/Q 分析
│   ├── peak.py                 # 峰值/谷值检测
│   └── fitting.py              # 洛伦兹拟合
│
├── gui/                        # GUI 层 (PyQt5)
│   ├── main_window.py          # MainWindow 主窗口
│   ├── styles.py               # 暗色主题样式定义
│   └── widgets.py              # 通用组件
│
└── visualization/              # 可视化 (仅 matplotlib)
    └── plotter.py              # 出版质量绑图
```

## 模块职责

### core/ — 数据处理层

- **`io.py`**: `read_santec_csv()`, `read_csv_arrays()` — CSV 文件读取
- **`manager.py`**: `SpectraManager` — 数据管理，`from_folder()` 加载，`get_xy()` 获取数据
- **`grid.py`**: `create_uniform_grid()`, `sanitize_xy()`, `interp_on_grid()` — 网格与插值
- **`utils.py`**: `_infer_decimals_from_value()` — 工具函数

### analysis/ — 分析层

- **`ring.py`**: `Ring` 类 — 微环谐振器分析
  - `cal_fsr()` — FSR 计算
  - `cal_Q()` — Q 因子拟合
- **`peak.py`**: `analyze_peaks()`, `calc_3db_bandwidth()` — 峰值分析
- **`fitting.py`**: `lorentzian_with_slope()`, `fit_lorentzian_peak()` — 洛伦兹拟合

### gui/ — GUI 层

- **`main_window.py`**: `MainWindow` — 主窗口
  - 顶部工具栏：文件夹选择、数据类型、Reference 文件
  - 左侧表格：元数据列表
  - 右侧面板：公式计算、峰值分析、微环分析（滚动区域）
  - 底部：日志输出

- **`styles.py`**: 暗色主题样式
  - `COLORS`: 颜色常量字典
  - `apply_styles()`: 应用全局样式
  - `group_box_style()`: 生成 QGroupBox 样式
  - `styled_label_style()`: 生成标签样式

### visualization/ — 可视化层

- **`plotter.py`**: `plot_publication()` — 出版质量图像（白色背景，便于分享）

## 关键设计

**分层规则**:
- `core/` 和 `analysis/` 禁止导入 PyQt5
- 分析逻辑与 GUI 严格分离

**UI 设计理念**:
- Apple Design Language：亮色主题，简洁现代
- Apple Blue (#0071e3) 作为主强调色
- 功能区颜色编码：紫色=公式、橙色=峰值、绿色=微环
- 药丸形按钮 (border-radius: 980px)
- 弹窗绘图保持白色背景，便于分享
- 弹窗工具栏使用浅色样式（`_TOOLBAR_LIGHT_STYLE`）
- 峰值/谷值标注智能定位：根据峰谷在 y 轴中的相对位置自动调整标注方向，确保文字始终在绘图区域内

**文件名编码**: SANTEC CSV 文件名如 `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv`

**多量程拼接**: raw 扫描的多量程数据自动拼接

**中文界面**: matplotlib 配置 Microsoft YaHei/SimHei 字体

## 样式使用

```python
from gui.styles import COLORS, group_box_style, styled_label_style

C = COLORS

# 使用颜色常量
color = C['accent']  # 青色强调

# QGroupBox 样式
grp.setStyleSheet(group_box_style(C['accent_purple']))

# 标签样式
label.setStyleSheet(styled_label_style('text_muted', 10))
```

## currentDate
Today's date is 2026/04/07.
