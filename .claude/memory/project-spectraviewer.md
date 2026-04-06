---
name: SpectraViewer 项目概述
description: 光谱数据可视化桌面应用 - 项目核心信息
type: project
---

SpectraViewer 是一个基于 PyQt5 的桌面应用，用于可视化 SANTEC 光谱仪 CSV 数据。

**创建日期**: 2026-04-06
**当前版本**: v1.1 (重构后)

## 目录结构

```
spectraviewer/
├── main.py                     # 入口配置 (Qt5Agg + 中文字体)
│
├── core/                       # 数据层 (无 PyQt5 依赖)
│   ├── utils.py                # 工具函数
│   ├── grid.py                 # 网格生成、插值、数据清洗
│   ├── io.py                   # SANTEC CSV 读取
│   └── manager.py              # SpectraManager 数据管理
│
├── analysis/                   # 分析层 (无 PyQt5 依赖)
│   ├── fitting.py              # 洛伦兹拟合函数
│   ├── peak.py                 # 峰值/谷值检测、3dB 带宽
│   └── ring.py                 # 微环谐振器 FSR/Q 分析
│
├── visualization/              # 可视化层 (仅 matplotlib)
│   └── plotter.py              # 出版质量绑图
│
└── gui/                        # GUI 层 (PyQt5)
    ├── widgets.py              # 通用组件 (StreamRedirector)
    └── main_window.py          # MainWindow 主窗口
```

## 关键功能

1. **数据加载**: 批量加载 CSV、多量程拼接、Reference 减法
2. **公式计算**: 支持 `A0, A1...` 变量语法，自动插值到公共网格
3. **峰值/谷值分析**: 自动寻峰、3dB 带宽计算
4. **微环分析**: FSR 估计、Q 因子拟合、耦合系数提取

## 导入方式

```python
# 推荐方式
from core import SpectraManager, read_santec_csv
from analysis import Ring, analyze_peaks
from visualization import plot_publication
from gui import MainWindow
```

## 技术约束

- 模块化分层：core/analysis 禁止导入 PyQt5
- 中文界面，matplotlib 配置 Microsoft YaHei/SimHei 字体
- 纯 Python 脚本项目，无测试框架/打包配置
