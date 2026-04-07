# 3dB 带宽计算 Bug 修复设计

## 问题描述

当峰值出现在平坦谷内时（"谷中峰"），`calc_3db_bandwidth` 函数返回的带宽远大于实际值。

### 问题示例
- 峰值：-6.57 dB
- 周围谷底：-25 ~ -30 dB
- 当前计算结果：34.0740 nm（错误）
- 预期结果：应该只有几 nm（峰值的实际宽度）

### 根本原因

当前算法计算 `half = peak_value - 3.0`，然后搜索**整个数据范围**内满足条件的点。

对于"谷中峰"：
- `half = -6.57 - 3 = -9.57 dB`
- 谷底已经是 -25 ~ -30 dB，远低于 -9.57 dB
- 算法找到远离峰值的交叉点，而非峰值实际下降 3dB 的位置

## 解决方案

采用**自适应窗口**策略：从峰值位置开始向外扩展，找到第一个 3dB 交叉点即停止。

### 算法设计

#### 峰值模式 (is_peak=True)

```
1. 计算 half = y[peak_idx] - 3.0
2. 向左搜索：从 peak_idx-1 开始，找第一个 y[i] <= half 的点
3. 向右搜索：从 peak_idx+1 开始，找第一个 y[i] <= half 的点
4. 最大窗口：500 点（安全边界，防止异常情况）
5. 如果在窗口内找不到交叉点，返回 None
```

#### 谷值模式 (is_peak=False)

```
1. 在窗口内计算局部基线（左右段最大值的均值）
2. 计算 half = ref_level - 3.0
3. 向左搜索：从 peak_idx-1 开始，找第一个 y[i] >= half 的点
4. 向右搜索：从 peak_idx+1 开始，找第一个 y[i] >= half 的点
5. 最大窗口：500 点
6. 如果在窗口内找不到交叉点，返回 None
```

### 修改文件

- `analysis/peak.py` - `calc_3db_bandwidth` 函数

### API 变更

新增可选参数 `max_window`，保持向后兼容：

```python
def calc_3db_bandwidth(
    x: np.ndarray,
    y: np.ndarray,
    peak_idx: int,
    is_peak: bool = True,
    max_window: int = 500,  # 新增：最大搜索窗口（点数）
) -> float | None:
```

### 实现细节

```python
def calc_3db_bandwidth(
    x: np.ndarray,
    y: np.ndarray,
    peak_idx: int,
    is_peak: bool = True,
    max_window: int = 500,
) -> float | None:
    """计算 3dB 带宽（自适应窗口）。

    从峰/谷位置开始向外扩展搜索，找到第一个 3dB 交叉点。
    适用于"谷中峰"等复杂基线情况。

    Args:
        x: x 坐标数组
        y: y 值数组
        peak_idx: 峰/谷索引
        is_peak: True 为峰值，False 为谷值
        max_window: 最大搜索窗口（单侧点数），默认 500

    Returns:
        3dB 带宽 (x 单位)，无法计算时返回 None
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if peak_idx < 0 or peak_idx >= len(x):
        return None

    # 计算搜索边界
    left_bound = max(0, peak_idx - max_window)
    right_bound = min(len(y), peak_idx + max_window + 1)

    if is_peak:
        # 峰值：从峰顶向下 3dB
        half = y[peak_idx] - 3.0

        # 向左搜索第一个 y <= half 的点
        left = peak_idx
        for i in range(peak_idx - 1, left_bound - 1, -1):
            if y[i] <= half:
                left = i
                break

        # 向右搜索第一个 y <= half 的点
        right = peak_idx
        for i in range(peak_idx + 1, right_bound):
            if y[i] <= half:
                right = i
                break
    else:
        # 谷值：计算局部基线
        left_seg = y[left_bound:peak_idx]
        right_seg = y[peak_idx + 1:right_bound]

        left_max = float(np.max(left_seg)) if len(left_seg) > 0 else y[peak_idx]
        right_max = float(np.max(right_seg)) if len(right_seg) > 0 else y[peak_idx]
        ref_level = (left_max + right_max) / 2.0
        half = ref_level - 3.0

        # 向左搜索第一个 y >= half 的点
        left = peak_idx
        for i in range(peak_idx - 1, left_bound - 1, -1):
            if y[i] >= half:
                left = i
                break

        # 向右搜索第一个 y >= half 的点
        right = peak_idx
        for i in range(peak_idx + 1, right_bound):
            if y[i] >= half:
                right = i
                break

    if left >= right:
        return None
    return float(x[right] - x[left])
```

### 行为对比

| 场景 | 原行为 | 新行为 |
|------|--------|--------|
| 正常峰值（平坦基线） | 正确 | 正确（一致） |
| 谷中峰 | 返回过大带宽 | 返回实际峰值带宽 |
| 峰宽 > 500 点 | 返回正确值 | 返回正确值（窗口足够） |
| 峰宽 > max_window | 返回正确值 | 可能返回 None（需调大参数） |

### 风险评估

- **低风险**：仅修改内部实现，API 保持兼容
- **边界情况**：如果用户数据峰宽超过 500 点，可通过 `max_window` 参数调整

## 测试计划

1. 使用用户提供的"谷中峰"数据验证修复效果
2. 确保正常峰值场景行为不变
3. 验证谷值分析功能
