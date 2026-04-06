# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
cd spectraviewer && python main.py

# 运行环形谐振器分析测试/演示（运行前需先在 main() 中修改 csv_path）
python test_ring_analyse_csv.py
```

本项目无 linter、测试框架或打包配置，为纯 Python 脚本项目。

## 架构

**SpectraViewer** 是一个基于 PyQt5 的桌面应用，用于可视化 SANTEC 光谱仪扫描生成的 CSV 光谱数据。

### 各模块职责

- **`main.py`** — 入口。设置 `Qt5Agg` matplotlib 后端，配置中文字体（`Microsoft YaHei`/`SimHei`），以 1200×800 启动 `MainWindow`。
- **`spectra_lib.py`** — 自包含核心库，负责所有文件 I/O 与数据管理：
  - `read_santec_csv()` — 解析单个 SANTEC CSV：读取 14 行文件头，从文件名或列标题自动识别 `loss`/`raw` 格式，拼接多量程 raw 扫描，支持参考文件减法。
  - `read_csv_arrays()` — 批量加载文件夹，构建以结构化字符串为键（编码器件/端口/波长元数据）的字典。
  - `SpectraManager` — 核心数据对象，封装数据字典与 pandas DataFrame。`from_folder()` 为主构造器，`get_xy(index)` 返回 `(波长, 插入损耗)` numpy 数组。
  - `plot_publication()` — 生成出版质量的 matplotlib 图。
- **`app.py`** — `MainWindow`（PyQt5 `QWidget`），包含所有 UI 与交互逻辑：
  - 左侧面板：由 `SpectraManager` 元数据填充的 `QTableWidget`。
  - 右侧面板：公式计算器、坐标轴控制、峰值/谷值分析。
  - 公式引擎：带 numpy 命名空间的 `eval()`；`A0`、`A1` 等按表格序号映射到光谱数组，所有光谱先插值到公共网格再参与计算。
  - `_Stream` 类将 stdout/stderr 重定向到底部日志 `QTextEdit`。
  - 微环谐振器分析面板：选择一行数据后点击"微环分析"，依次弹出 FSR 图和 Q 分析汇总图；可选"显示单峰拟合"，按波长范围均匀抽样最多显示 10 个单峰洛伦兹拟合图。
- **`Ring_analyse.py`** — 独立光子学分析模块（依赖 `spectra_lib` 的工具函数）：
  - `Ring` 类：接收原始 `(λ, T_dB)` 光谱，提供 `cal_fsr()`（基于 `find_peaks` 与 MAD 离群值剔除计算自由光谱范围）和 `cal_Q(holdon, max_holdon)`（通过 `scipy.optimize.curve_fit` 拟合洛伦兹线型，提取负载 Q、本征 Q、线宽、耦合系数；`holdon=True` 时显示单峰拟合图，最多 `max_holdon` 个，按波长范围均匀抽样）。
  - 工具函数（`sanitize_xy`、`interp_on_grid`、`create_uniform_grid`、`_infer_decimals_from_value`）直接从 `spectra_lib` 导入，不再重复定义。
  - `_sample_figs_by_wavelength(figs, wavelengths, n)` — 按波长范围等距抽样，从所有单峰拟合图中选取至多 n 个。
- **`test_ring_analyse_csv.py`** — `Ring_analyse` 的独立演示脚本。使用 `Agg` 后端（无头模式），将图保存至 `./test_outputs/`。运行前需将 `main()` 中的 `csv_path` 指向真实文件。

### 关键设计细节

**文件名编码元数据：** SANTEC CSV 文件名遵循结构化命名规则，如 `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv`。`read_santec_csv()` 通过正则解析；若文件名不匹配，则回退至 14 行文件头读取元数据。支持三种格式：完整格式、简短格式（`chip_dev_no_port.csv`）和自由格式（任意命名，元数据全部来自文件头）。

**工具函数共享：** `sanitize_xy`、`interp_on_grid`、`create_uniform_grid`、`_infer_decimals_from_value` 定义在 `spectra_lib.py`，`Ring_analyse.py` 直接从其导入，消除了原有的重复定义。

**多量程拼接：** SANTEC raw 扫描在中途切换灵敏度量程，产生重叠片段。`read_santec_csv()` 通过基于阈值的算法将这些片段拼接为单一连续数组。

**中文界面：** 所有标签和日志信息均为简体中文，`main.py` 中已配置支持中文的 matplotlib 字体。
