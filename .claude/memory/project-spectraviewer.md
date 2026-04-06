---
name: SpectraViewer 项目概述
description: 光谱数据可视化桌面应用 - 项目核心信息
type: project
---

SpectraViewer 是一个基于 PyQt5 的桌面应用，用于可视化 SANTEC 光谱仪 CSV 数据。

**创建日期**: 2026-04-06  
**当前版本**: v1.0 (Baseline)

## 核心模块

- `spectra_lib.py` - CSV 解析、SpectraManager 数据管理、出版质量绘图
- `app.py` - PyQt5 GUI (MainWindow)、公式计算器、峰值/谷值分析
- `Ring_analyse.py` - 微环谐振器 FSR 计算、Q 因子洛伦兹拟合
- `main.py` - 入口，配置 Qt5Agg 后端和中文字体

## 关键功能

1. **数据加载**: 批量加载 CSV、多量程拼接、Reference 减法
2. **公式计算**: 支持 `A0, A1...` 变量语法，自动插值到公共网格
3. **峰值/谷值分析**: 自动寻峰、3dB 带宽计算
4. **微环分析**: FSR 估计、Q 因子拟合、耦合系数提取

## 技术约束

- 纯 Python 脚本项目，无测试框架/打包配置/Linter
- 中文界面，matplotlib 配置 Microsoft YaHei/SimHei 字体
