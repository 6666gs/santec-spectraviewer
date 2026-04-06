# 项目基线规范: SpectraViewer v1.1

**创建日期**: 2026-04-06
**更新日期**: 2026-04-06
**状态**: 已完成 (Baseline)
**版本**: v1.1

---

## 项目概述

**SpectraViewer** 是一个基于 PyQt5 的桌面应用程序，用于可视化 SANTEC 光谱仪扫描生成的 CSV 光谱数据，并提供微环谐振器分析功能。

### 技术栈

- **语言**: Python 3.8+
- **GUI 框架**: PyQt5
- **数据处理**: NumPy, Pandas
- **可视化**: Matplotlib (Qt5Agg 后端)
- **科学计算**: SciPy (signal, optimize, interpolate)

---

## 目录结构

```
spectraviewer/
├── main.py                     # 入口 (Qt5Agg + 中文字体)
│
├── core/                       # 数据层 (无 PyQt5 依赖)
│   ├── __init__.py
│   ├── io.py                   # CSV 读取: read_santec_csv, read_csv_arrays
│   ├── manager.py              # SpectraManager 数据管理
│   ├── grid.py                 # 网格工具: create_uniform_grid, sanitize_xy, interp_on_grid
│   └── utils.py                # 工具函数: _infer_decimals_from_value
│
├── analysis/                   # 分析层 (无 PyQt5 依赖)
│   ├── __init__.py
│   ├── ring.py                 # Ring 类: 微环 FSR/Q 分析
│   ├── peak.py                 # 峰值/谷值检测, 3dB 带宽
│   └── fitting.py              # 洛伦兹拟合函数
│
├── gui/                        # GUI 层 (PyQt5)
│   ├── __init__.py
│   ├── main_window.py          # MainWindow 主窗口
│   └── widgets.py              # 通用组件: StreamRedirector
│
└── visualization/              # 可视化层 (仅 matplotlib)
    ├── __init__.py
    └── plotter.py              # plot_publication 出版质量绑图
```

---

## 模块职责

### core/ — 数据处理层

| 模块 | 函数/类 | 功能 |
|------|---------|------|
| `io.py` | `read_santec_csv()` | 解析单个 SANTEC CSV |
| `io.py` | `read_csv_arrays()` | 批量加载文件夹 |
| `manager.py` | `SpectraManager` | 数据管理器 |
| `grid.py` | `sanitize_xy()` | 数据清洗 |
| `grid.py` | `interp_on_grid()` | 网格插值 |
| `grid.py` | `create_uniform_grid()` | 创建均匀网格 |

### analysis/ — 分析层

| 模块 | 函数/类 | 功能 |
|------|---------|------|
| `ring.py` | `Ring` | 微环谐振器分析 |
| `ring.py` | `cal_fsr()` | FSR 计算 |
| `ring.py` | `cal_Q()` | Q 因子拟合 |
| `peak.py` | `analyze_peaks()` | 峰值/谷值检测 |
| `peak.py` | `calc_3db_bandwidth()` | 3dB 带宽 |
| `fitting.py` | `lorentzian_with_slope()` | 洛伦兹模型 |
| `fitting.py` | `fit_lorentzian_peak()` | 峰拟合 |

### gui/ — GUI 层

| 模块 | 类 | 功能 |
|------|-----|------|
| `main_window.py` | `MainWindow` | 主窗口 |
| `widgets.py` | `StreamRedirector` | stdout 重定向 |

### visualization/ — 可视化层

| 模块 | 函数 | 功能 |
|------|------|------|
| `plotter.py` | `plot_publication()` | 出版质量图像 |

---

## 核心功能

### 1. 数据加载

- 批量加载 CSV 文件夹
- 自动识别 `loss` / `raw` 格式
- 多量程数据自动拼接
- Reference 文件减法

### 2. 公式计算

- 语法: `A0, A1, A2...` 对应表格序号
- 支持 NumPy 函数 (`np.*`)
- 自动插值到公共网格

### 3. 峰值/谷值分析

- 自动寻峰
- 3dB 带宽计算
- 可配置阈值和间距

### 4. 微环分析

- FSR 估计 (MAD 离群值剔除)
- Q 因子洛伦兹拟合
- 耦合系数提取
- 单峰拟合图 (可选)

---

## 分层规则

```
core/        → 无 PyQt5 依赖
analysis/    → 无 PyQt5 依赖
visualization/ → 仅 matplotlib
gui/         → PyQt5 + matplotlib
```

---

## 文件格式

SANTEC CSV (14 行头 + 数据列)，支持三种命名：

| 格式 | 示例 |
|------|------|
| 完整 | `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv` |
| 简短 | `chip_dev_no_port.csv` |
| 自由 | 任意命名（元数据从文件头读取） |

---

## 运行方式

```bash
pip install -r requirements.txt
python main.py
```

---

## 已知限制

1. 无单元测试框架
2. 无打包配置
3. 无 Linter

---

## 未来开发

新功能在 `specs/001-xxx/` 目录下创建规范后开发。
