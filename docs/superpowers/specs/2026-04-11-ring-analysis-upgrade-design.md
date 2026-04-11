# 微环分析升级设计

## 概述

两项改进：
1. 微环分析面板开放峰值检测参数（阈值、最小间隔），解决噪声被误判为谐振峰的问题
2. 重新设计微环分析图表，采用顶级期刊风格（Nature/Science），包含光谱总览图、参数趋势图、结果汇总表格

## 方案选择

**方案 A：在 Ring 类内部重构图表生成**（已采纳）

将 Ring 类中的绑图逻辑抽取为独立方法，重新设计输出图表。不将图表逻辑移到 visualization 层（方案 B），也不在 GUI 层重复绑图（方案 C）。

理由：改动集中，不破坏现有 core/analysis 与 gui 的分层，Ring 类本身已依赖 matplotlib。

---

## 需求 1：峰值检测参数开放

### GUI 改动（`gui/main_window.py`）

在 `_build_ring_panel` 新增两个控件，位于波长范围输入框下方：

| 控件 | 变量名 | 类型 | 默认值 | 说明 |
|------|--------|------|--------|------|
| 阈值 | `ring_threshold` | `QLineEdit` | 留空 | placeholder "留空表示不限（单位 dB）"，与峰值分析面板风格一致 |
| 最小间隔 | `ring_distance` | `QLineEdit` | `'0'` | 0 表示自动推断，单位为数据点数 |

### API 改动（`analysis/ring.py`）

`Ring.cal_fsr()` 新增参数：

```python
def cal_fsr(self, range_nm=None, display=True, figinsert=None,
            height_threshold=None, min_distance=None):
```

- `height_threshold`：传给 `find_peaks(-detect_signal, ..., height=height_threshold)`。注意信号取反后是 `-T`，所以 height 阈值对应谷的深度。
- `min_distance`：覆盖自动推断的 `base_distance`。`None` 或 0 表示使用现有自动逻辑。

`_on_ring_analyze()` 从 GUI 读取这两个值并传入 `cal_fsr()`。

---

## 需求 2：图表重新设计

### 视觉风格规范（顶级期刊）

所有微环相关图表统一遵循：

| 要素 | 规范 |
|------|------|
| 英文/数字字体 | Times New Roman |
| 中文字体 | SimHei / Microsoft YaHei |
| 光谱曲线 | 黑色，0.8pt |
| 拟合曲线 | 深红色 `#c0392b`，虚线 |
| 峰标记 | 深红色 `#c0392b` |
| FSR 箭头/辅助线 | 灰色 `#7f8c8d` |
| 数据点（Ql） | 深蓝 `#2c3e50` |
| 数据点（Qi） | 深绿 `#27ae60` |
| 中心波长线 | 深蓝 `#2c3e50`，点线 |
| 3dB 带宽线 | 灰色 `#7f8c8d`，虚线 |
| 轴标签字号 | 10pt |
| Tick label 字号 | 8pt |
| 标注文字字号 | 7pt |
| Spine 线宽 | 0.8pt |
| 刻度方向 | 向内 |
| 网格 | 无 |
| 背景色 | 白色 |

### 2.1 光谱总览图（替换 cal_fsr 的 4 面板图）

单面板布局，包含：

- 全光谱曲线（黑色 0.8pt）
- 谐振峰位置用倒三角 ▽ 标记（深红色），上方标注波长值（7pt）
- 峰间双向箭头标注 FSR 值（只标 2-3 个代表性的，避免拥挤）
- 右上角文本框：`FSR_mean = xx.x nm`
- 频率域：如检测到峰值，同时生成频率域总览图（同样风格，作为第二张图）

### 2.2 参数趋势图 + 汇总表格（替换 cal_Q 的 3 面板摘要图）

1×2 布局：

**左面板 — 参数趋势图：**
- x 轴：波长 (nm)
- 主 y 轴：Ql（深蓝 `#2c3e50`）、Qi（深绿 `#27ae60`），小圆点 + 连线
- 保持 4σ 离群值过滤
- 可选：kappa² 叠加在第二 y 轴

**右面板 — 结果汇总表格：**
- matplotlib `table` 绘制论文风格表格
- 列：Peak #、λ₀ (nm)、Ql、Qi、ER (dB)、γ (pm)、R²
- 行：每个有效峰一行，按波长排序
- 底部行：均值 ± 标准差
- 表头加粗，黑色边框，Times New Roman 8pt

### 2.3 单峰拟合图优化（`_plot_single_peak_fit`）

保持按需生成逻辑（用户勾选"显示单峰拟合"后按波长取样生成）。视觉优化：

- 光谱曲线：黑色 0.8pt
- 拟合曲线：深红色 `#c0392b` 虚线
- 3dB 带宽边界：灰色 `#7f8c8d` 虚线
- 中心波长线：深蓝 `#2c3e50` 点线
- 标注文字：7pt，位于空白区域避免遮挡
- 无网格，白色背景，spine 0.8pt，刻度向内

### 2.4 Log 输出格式优化

`_on_ring_analyze` 的控制台输出改为类论文表格格式：

```
微环分析结果
───────────────────────────────────────
FSR = 12.34 nm
───────────────────────────────────────
  λ₀ (nm)    Ql        Qi       ER(dB)  γ(pm)   R²
  1550.123   15234    18567    -3.45    12.3    0.998
  1562.456   14891    17432    -2.98    13.1    0.995
  ...
───────────────────────────────────────
均值 Ql = 15063 ± 243
均值 Qi = 18000 ± 812
```

---

## 涉及文件

| 文件 | 改动内容 |
|------|----------|
| `analysis/ring.py` | `cal_fsr` 新增参数；重写 `_plot_fsr_overview`；重写 `_plot_q_summary`；优化 `_plot_single_peak_fit`；新增 `_journal_style()` 样式配置方法 |
| `gui/main_window.py` | `_build_ring_panel` 新增阈值和间隔控件；`_on_ring_analyze` 读取新参数并传入；优化 log 输出格式 |

不涉及 `analysis/peak.py`、`analysis/fitting.py`、`visualization/plotter.py`、`gui/styles.py` 的改动。
