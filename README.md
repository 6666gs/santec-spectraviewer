# SpectraViewer

SANTEC 光谱仪数据可视化与分析工具。

## 功能

- CSV 光谱数据加载与可视化
- 峰值/谷值检测与 3dB 带宽计算
- 微环谐振器 FSR / Q 因子分析
- 公式计算（多数据叠加运算）
- 出版质量图像导出

## 快速开始

### Windows

```bash
pip install -r requirements.txt
python main.py
```

### Linux / WSL

```bash
# 一键配置（安装 Qt 依赖 + Python 包 + 中文字体）
bash setup_linux.sh

# 启动
python main.py
```

WSL 环境下会自动使用 Windows 原生文件选择器，数据路径自动转换（如 `F:\data` → `/mnt/f/data`）。  
WSL 的 `DISPLAY` / `XDG_RUNTIME_DIR` 等显示变量由程序自动设置，无需手动配置。

### macOS

```bash
pip install -r requirements.txt
python main.py
```

## 依赖

```
numpy
scipy
pandas
matplotlib
PyQt5
```

## 目录结构

```
spectraviewer/
├── main.py                 # 入口
├── setup_linux.sh          # Linux/WSL 环境配置脚本
├── requirements.txt
├── core/                   # 数据层 (无 PyQt5 依赖)
│   ├── io.py               # CSV 读取
│   ├── manager.py          # SpectraManager
│   ├── grid.py             # 网格/插值工具
│   └── utils.py            # 通用工具
├── analysis/               # 分析层 (无 PyQt5 依赖)
│   ├── ring.py             # 微环谐振器分析
│   ├── peak.py             # 峰值/谷值检测
│   └── fitting.py          # 洛伦兹拟合
├── gui/                    # GUI 层 (PyQt5)
│   ├── main_window.py      # 主窗口
│   ├── styles.py           # 主题样式
│   └── widgets.py          # 通用组件
└── visualization/          # 可视化 (matplotlib)
    └── plotter.py          # 出版质量绑图
```
