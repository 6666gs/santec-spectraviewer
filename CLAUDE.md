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
├── main.py                     # 入口 (Qt5Agg + 中文字体)
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
  - 左侧表格：元数据列表
  - 右侧面板：公式计算、峰值分析、微环分析
  - 底部：日志输出

### visualization/ — 可视化层

- **`plotter.py`**: `plot_publication()` — 出版质量图像

## 关键设计

**分层规则**:
- `core/` 和 `analysis/` 禁止导入 PyQt5
- 分析逻辑与 GUI 严格分离

**文件名编码**: SANTEC CSV 文件名如 `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv`

**多量程拼接**: raw 扫描的多量程数据自动拼接

**中文界面**: matplotlib 配置 Microsoft YaHei/SimHei 字体
