# SpectraViewer

光谱数据可视化桌面工具，用于加载、浏览和分析 SANTEC 光谱仪扫描的 CSV 数据。

## 功能

- **批量加载** — 自动识别 loss / raw 格式，支持多量程拼接
- **表格浏览** — 显示器件名、端口、波长范围、步长等元数据
- **交互绘图** — 双击或多选绘制光谱曲线
- **公式计算** — 支持 `A0 - A1`、`A12 - A1 - (A2 - A1) * 2` 等表达式
- **峰值/谷值分析** — 自动标注位置、数值和 3dB 带宽
- **微环分析** — FSR 估计、Q 因子拟合、耦合系数提取

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 项目结构

```
spectraviewer/
├── main.py              # 入口
├── core/                # 数据处理 (CSV 读取、数据管理)
├── analysis/            # 光子学分析 (微环、峰值、拟合)
├── gui/                 # 图形界面 (PyQt5)
└── visualization/       # 可视化 (matplotlib)
```

## 依赖

- Python 3.8+
- PyQt5
- matplotlib
- numpy
- scipy
- pandas

## 文件格式

支持 SANTEC CSV 格式（14 行头 + 数据列），自动识别三种命名：

| 格式 | 示例 |
|------|------|
| 完整 | `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv` |
| 简短 | `chip_dev_no_port.csv` |
| 自由 | 任意命名（元数据从文件头读取） |

## License

MIT
