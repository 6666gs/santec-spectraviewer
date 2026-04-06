# SpectraViewer

光谱数据可视化桌面工具，用于加载、浏览和分析 SANTEC 光谱仪扫描的 CSV 数据。

## 功能

- 批量加载文件夹内所有 CSV 光谱文件（自动识别 loss / raw 格式）
- 表格浏览：显示器件名、端口、波长范围、步长、量程等元数据
- 双击行或多选后点击"绘制选中行"，弹出 matplotlib 图窗
- 公式计算：支持 `A0 - A1`、`A12 - A1 - (A2 - A1) * 2` 等表达式绘图
- 峰值 / 谷值分析：自动标注位置、数值和 3 dB 带宽
- 可自定义图像标题、坐标轴标签和显示范围

## 文件命名格式

支持三种格式（均可自动识别）：

| 格式 | 示例 |
|------|------|
| 完整格式 | `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv` |
| 简短格式 | `chip_dev_no_port.csv`（波长等信息从文件头读取） |
| 自由格式 | `E2_PORT_3.csv`（任意命名，元数据全部从文件头读取） |

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
cd spectraviewer
python main.py
```

## 使用说明

1. 点击"选择文件夹"，选择包含 CSV 文件的数据目录
2. 若数据为 raw 格式，先点击"选择 Reference 文件"指定参考文件
3. 在"数据类型"下拉框选择 `auto` / `loss` / `raw`（默认 auto 自动识别）
4. 表格加载后，双击某行可直接绘图；多选后点击"绘制选中行"可叠加绘图
5. 在"公式计算"框输入表达式（`A0`、`A1` 对应表格序号），点击"公式绘图"
6. 在"峰值 / 谷值分析"区域选择模式、设置搜索范围后点击"分析"

## 项目结构

```
spectraviewer/
├── main.py          # 入口，启动 QApplication
├── app.py           # 主窗口 UI 与交互逻辑
├── spectra_lib.py   # 数据读取、SpectraManager、绘图函数（自包含）
└── requirements.txt
```
