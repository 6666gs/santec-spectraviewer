# 项目基线规范: SpectraViewer v1.0

**创建日期**: 2026-04-06  
**状态**: 已完成 (Baseline)  
**版本**: v1.0

---

## 项目概述

**SpectraViewer** 是一个基于 PyQt5 的桌面应用程序，用于可视化 SANTEC 光谱仪扫描生成的 CSV 光谱数据，并提供微环谐振器分析功能。

### 技术栈

- **语言**: Python 3.x
- **GUI 框架**: PyQt5
- **数据处理**: NumPy, Pandas
- **可视化**: Matplotlib (Qt5Agg 后端)
- **科学计算**: SciPy (signal, optimize, interpolate)

---

## 核心功能模块

### 1. 数据管理 (`spectra_lib.py`)

#### 1.1 CSV 文件解析

| 功能 | 描述 |
|------|------|
| `read_santec_csv()` | 解析单个 SANTEC CSV 文件，支持 14 行文件头 |
| `read_csv_arrays()` | 批量加载文件夹中的所有 CSV 文件 |
| 自动格式检测 | 支持 `loss` 和 `raw` 两种格式自动识别 |
| 多量程拼接 | 自动拼接 SANTEC raw 扫描的多量程数据 |
| 参考文件减法 | 支持通过 reference 文件计算插入损耗 |

#### 1.2 文件名解析

支持三种命名格式：
- **完整格式**: `chip_dev_no_port_1500_1630_step1pm_range2_source0dbm_loss.csv`
- **简短格式**: `chip_dev_no_port.csv` (元数据来自文件头)
- **自由格式**: 任意命名 (元数据全部来自文件头)

#### 1.3 SpectraManager 类

```python
SpectraManager.from_folder(folder, data_type='auto', reference_path=None)
# 从文件夹加载数据

SpectraManager.get_xy(key_or_index)
# 获取 (波长, 插入损耗) numpy 数组
```

#### 1.4 工具函数

| 函数 | 功能 |
|------|------|
| `sanitize_xy(x, y)` | 数据清洗：去 NaN、排序、去重取平均 |
| `interp_on_grid(x_src, y_src, x_dst, mode)` | 插值到目标网格 |
| `create_uniform_grid(start, end, step)` | 创建均匀波长网格 |
| `plot_publication(data_list, ...)` | 生成出版质量图像 |

---

### 2. GUI 界面 (`app.py`)

#### 2.1 布局结构

```
┌─────────────────────────────────────────────────────────┐
│  工具栏: 选择文件夹 | 数据类型 | Reference 文件         │
├─────────────────────┬───────────────────────────────────┤
│                     │  公式计算器                        │
│   数据表格          │  图像标签设置                      │
│   (元数据列表)      │  坐标轴范围控制                    │
│                     │  峰值/谷值分析面板                 │
│                     │  微环谐振器分析面板                │
├─────────────────────┴───────────────────────────────────┤
│  日志输出区域                                            │
└─────────────────────────────────────────────────────────┘
```

#### 2.2 交互功能

| 功能 | 操作方式 |
|------|----------|
| 加载数据 | 点击"选择文件夹" |
| 单曲线绘图 | 双击表格行 |
| 多曲线绘图 | 多选行 + "绘制选中行" |
| 公式计算 | 输入表达式 (如 `A12 - A1 - (A2 - A1) * 2`) |
| Reference 减法 | 选择 Reference 文件后自动重新加载 |

#### 2.3 公式引擎

- 变量语法: `A0`, `A1`, `A2`... 对应表格序号
- 支持 NumPy 函数 (通过 `np.*` 命名空间)
- 自动插值到公共网格进行计算

---

### 3. 峰值/谷值分析

#### 3.1 功能参数

| 参数 | 说明 |
|------|------|
| 峰值/谷值选择 | 单选按钮切换 |
| 搜索 X 范围 | 可指定波长范围 |
| 阈值 (dB) | 峰值高度阈值 |
| 最小间距 (点数) | 相邻峰最小间隔 |

#### 3.2 输出

- 峰/谷位置 (nm)
- 峰/谷值 (dB)
- 3dB 带宽 (nm)
- 图像标注

---

### 4. 微环谐振器分析 (`Ring_analyse.py`)

#### 4.1 Ring 类

```python
ring = Ring(x, y)  # x: 波长(nm), y: 功率(dB)
ring.cal_fsr(range_nm=(1530, 1550), display=True)
ring.cal_Q(holdon=False, max_holdon=10)
```

#### 4.2 FSR 计算 (`cal_fsr`)

- 基于 `find_peaks` 自动寻峰
- MAD (Median Absolute Deviation) 离群值剔除
- 输出: FSR vs 波长图、FSR vs 频率图、透射谱标注图

#### 4.3 Q 因子拟合 (`cal_Q`)

- **洛伦兹拟合模型**: 带斜率基线的洛伦兹线型
- **拟合参数**: T0 (基线)、ER (消光比)、λ0 (中心波长)、γ (半宽)、slope (斜率)
- **输出参数**:
  - 负载 Q (Ql)
  - 本征 Q (Qi)
  - 耦合系数 (κ²)
  - 3dB 带宽

#### 4.4 单峰拟合图

- 可选显示最多 10 个单峰拟合图
- 按波长范围均匀抽样选取
- 显示归一化透射率 + 洛伦兹拟合曲线

---

## 数据流

```
CSV 文件 → read_santec_csv() → SpectraManager → get_xy() → (λ, IL)
                                                          ↓
                                         GUI 表格显示 / 绘图 / 分析
```

---

## 文件结构

```
spectraviewer/
├── main.py              # 入口，Qt 后端和字体配置
├── app.py               # MainWindow GUI 实现
├── spectra_lib.py       # 核心数据处理库
├── Ring_analyse.py      # 微环谐振器分析模块
└── test_ring_analyse_csv.py  # 独立测试/演示脚本
```

---

## 已知限制

1. **无单元测试框架**: 项目为纯脚本，无 pytest/unittest 配置
2. **无打包配置**: 未配置 pyinstaller/setuptools
3. **无 Linter**: 未配置 flake8/black/mypy
4. **硬编码路径**: `test_ring_analyse_csv.py` 需手动修改 `csv_path`

---

## 未来开发方向

可能的增强功能：

- [ ] 添加单元测试框架
- [ ] 数据导出功能 (Excel, PNG)
- [ ] 批量分析报告生成
- [ ] 更多光子学器件分析 (MZI, AWG)
- [ ] 配置文件持久化
- [ ] 深色主题支持
- [ ] 国际化 (英文界面)

---

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
cd spectraviewer && python main.py
```
