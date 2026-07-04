# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用（GUI）
python main.py

# 批量微环 Q 分析（CLI，多 FSR 自动分离，直通端）
python batch_ring_q.py <数据目录> --out <输出目录> [--type auto|loss|raw] [--reference REF] [--min-r2 0.9]

# 运行测试（需 pytest）
pytest -q
```

本项目为纯 Python 桌面应用；GUI 无 linter/打包配置。`analysis/`、`core/`、`visualization/`
的纯逻辑部分带 pytest 单测（见 `tests/`）。

## 目录结构

```
spectraviewer/
├── main.py                     # 入口 (高 DPI + matplotlib 配置)
├── batch_ring_q.py             # 批量微环 Q 分析 CLI (多 FSR 自动分离，直通端)
│
├── core/                       # 数据层 (无 PyQt5 依赖)
│   ├── io.py                   # CSV 读取；detect_header_rows/load_spectrum 自动表头
│   ├── manager.py              # SpectraManager
│   ├── grid.py                 # 网格/插值工具
│   └── utils.py                # 通用工具
│
├── analysis/                   # 分析层 (无 PyQt5 依赖)
│   ├── ring.py                 # 微环谐振器 FSR/Q 分析 (GUI 用，单模)
│   ├── multimode.py            # 多 FSR 分离 + 分模式逐峰 Q 拟合 (批量 CLI 用)
│   ├── peak.py                 # 峰值/谷值检测
│   └── fitting.py              # 洛伦兹拟合
│
├── gui/                        # GUI 层 (PyQt5)
│   ├── main_window.py          # MainWindow 主窗口
│   ├── styles.py               # 暗色主题样式定义
│   └── widgets.py              # 通用组件
│
├── visualization/              # 可视化 (仅 matplotlib)
│   ├── plotter.py              # 出版质量绑图
│   └── ring_report.py          # 单文件多模式 Q 报告图 (批量 CLI 用)
│
└── tests/                      # pytest 单测 (core/analysis/visualization/CLI)
```

### 批量微环 Q 分析（`batch_ring_q.py`）

单文件=单微环，逐个处理，按输入文件名输出 `<stem>_Qdist.png` 与 `<stem>_results.csv`。
核心为 `analysis/multimode.py` 的频域贪心梳状分离：候选 FSR 用间距贪心聚类播种，
链延伸收紧容差以避免跨族误吸收，EMA 跟踪本地 FSR 容忍色散；自动确定模式数 K（K=1
退化为单模）。拟合窗口按**全局**最近谷中点取，隔离相邻他族谷。设计/计划见
`docs/superpowers/specs/2026-07-04-batch-ring-q-analysis-design.md`。

## 模块职责

### core/ — 数据处理层

- **`io.py`**: `read_santec_csv()`, `read_csv_arrays()` — CSV 文件读取
- **`manager.py`**: `SpectraManager` — 数据管理，`from_folder()` 加载，`get_xy()` 获取数据
- **`grid.py`**: `create_uniform_grid()`, `sanitize_xy()`, `interp_on_grid()` — 网格与插值
- **`utils.py`**: `_infer_decimals_from_value()` — 工具函数

### analysis/ — 分析层

- **`ring.py`**: `Ring` 类 — 微环谐振器分析
  - `cal_fsr(height_threshold=None, min_distance=None)` — FSR 计算，支持阈值和间隔参数
  - `cal_Q()` — Q 因子拟合
  - 图表采用期刊风格（`_apply_journal_style`），颜色常量 `_JC`
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
