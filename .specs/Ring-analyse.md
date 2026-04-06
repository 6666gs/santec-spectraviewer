# Ring Analyse Specification

微环谐振器分析模块，提取 FSR 和 Q 因子。

## 模块概述

`Ring` 类接收 `(λ, T_dB)` 光谱数据，提供：
- `cal_fsr()`: 计算自由光谱范围
- `cal_Q()`: 洛伦兹拟合提取 Q 因子

---

## Ring 类

### 初始化

```python
ring = Ring(x, y)
# x: 波长数组 (nm)
# y: 功率数组 (dB)
```

**内部处理：**
1. 调用 `sanitize_xy()` 清理数据
2. 计算频率 `fre = c / λ` (THz)

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `lamda` | np.ndarray | 波长 (nm) |
| `T` | np.ndarray | 透射率 (dB) |
| `fre` | np.ndarray | 频率 (THz) |
| `fsr_mean` | float | 平均 FSR (nm) |
| `lambda0` | np.ndarray | 谐振峰波长 |
| `fit_results` | list[dict] | Q 拟合结果 |

---

## FSR 计算 (`cal_fsr`)

### 签名
```python
ring.cal_fsr(range_nm=None, display=True, figinsert=None) -> Figure | None
```

### 算法流程

1. **峰检测**
   - 使用 `scipy.signal.find_peaks` 检测谷底（透射最小点）
   - `distance`: 基于 FSR 估计的自适应间距
   - `prominence`: 基于信号动态范围的自适应阈值

2. **离群值剔除**
   - 使用 MAD (Median Absolute Deviation) 方法
   - 剔除超过 3σ 的异常间距

3. **FSR 计算**
   - `fsr_mean = median(fsr_lambda)` 过滤后取均值

### 输出图窗 (display=True)

| 子图 | 内容 |
|------|------|
| 1 | FSR vs 波长 |
| 2 | FSR vs 频率 |
| 3 | 透射谱 + 峰标注 (波长轴) |
| 4 | 透射谱 + 峰标注 (频率轴) |

---

## Q 因子拟合 (`cal_Q`)

### 签名
```python
ring.cal_Q(holdon=False, max_holdon=10, figinsert=None) -> Figure
```

### 拟合模型

**带斜率的洛伦兹函数：**
```
T(λ) = baseline(λ) × (1 - ER / (1 + ((λ - λ₀) / γ)²))
baseline(λ) = T₀ + slope × (λ - λ₀)
```

| 参数 | 含义 |
|------|------|
| `T₀` | 基线高度 |
| `ER` | 消光比 (0~1) |
| `λ₀` | 谐振波长 |
| `γ` | 半宽半高 (HWHM) |
| `slope` | 基线斜率 |

### Q 因子计算

```
Ql = λ₀ / (2γ)      # 负载 Q
Qi = Ql / √(1 - ER) # 本征 Q
```

### 窗口划分

每个峰的拟合窗口由相邻峰位置决定：
- 左边界 = (前一峰 + 当前峰) / 2
- 右边界 = (当前峰 + 后一峰) / 2
- 边缘峰：外推半个间距

### 质量控制

- R² < 0.5 的拟合被丢弃
- 使用 4σ 过滤剔除异常 Q 值

### 输出

**`fit_results` 列表项：**
```python
{
    'lambda0': float,    # 谐振波长 (nm)
    'gamma': float,      # 3dB 带宽 (nm)
    'Ql': float,         # 负载 Q
    'Qi': float,         # 本征 Q
    'kappa2': float,     # 耦合系数
    'extinction': float, # 消光比
    'r_squared': float,  # 拟合优度
}
```

### 输出图窗

| 子图 | 内容 |
|------|------|
| 1 | Ql 分布直方图 |
| 2 | Qi 分布直方图 |
| 3 | kappa² vs 波长 + 透射谱叠加 |

**单峰拟合图** (holdon=True):
- 最多显示 `max_holdon` 个
- 按波长范围均匀抽样选取

---

## 错误处理

| 条件 | 行为 |
|------|------|
| 数据点 < 2 | `ValueError` |
| 峰数量 < 2 | `ValueError` |
| 无有效拟合 | `ValueError` |
| R² 过低 | 跳过该峰，继续其他 |
