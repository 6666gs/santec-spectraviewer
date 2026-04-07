# analysis/peak.py — 峰值/谷值分析
"""峰值和谷值检测与分析。"""

import numpy as np
from scipy.signal import find_peaks


def analyze_peaks(
    x: np.ndarray,
    y: np.ndarray,
    is_peak: bool = True,
    x_range: tuple[float, float] | None = None,
    threshold: float | None = None,
    distance: int = 50,
):
    """分析光谱中的峰值或谷值。

    Args:
        x: x 坐标数组 (波长)
        y: y 值数组 (功率 dB)
        is_peak: True 检测峰值，False 检测谷值
        x_range: 搜索范围 (xmin, xmax)，None 为全范围
        threshold: 峰值高度阈值 (dB)
        distance: 相邻峰最小间距 (点数)

    Returns:
        dict:
        - 'peaks_idx': 峰索引数组
        - 'x_peaks': 峰 x 坐标
        - 'y_peaks': 峰 y 值
        - 'x_full': 完整 x 数组
        - 'y_full': 完整 y 数组
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    # 截取搜索范围
    mask = np.ones(len(x), dtype=bool)
    if x_range is not None:
        xmin, xmax = x_range
        if xmin is not None:
            mask &= x >= xmin
        if xmax is not None:
            mask &= x <= xmax
    x_s, y_s = x[mask], y[mask]

    if len(x_s) < 3:
        return {'peaks_idx': np.array([]), 'x_peaks': np.array([]), 'y_peaks': np.array([]),
                'x_full': x, 'y_full': y}

    # 寻峰
    kwargs = {'distance': distance}
    if threshold is not None:
        if is_peak:
            kwargs['height'] = threshold
        else:
            kwargs['height'] = -threshold

    if is_peak:
        peaks_idx, _ = find_peaks(y_s, **kwargs)
    else:
        peaks_idx, _ = find_peaks(-y_s, **kwargs)

    return {
        'peaks_idx': peaks_idx,
        'x_peaks': x_s[peaks_idx],
        'y_peaks': y_s[peaks_idx],
        'x_full': x,
        'y_full': y,
    }


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


def format_peak_results(results: dict, is_peak: bool = True) -> list[str]:
    """格式化峰值分析结果为文本行。

    Args:
        results: analyze_peaks 返回的结果字典
        is_peak: True 为峰值，False 为谷值

    Returns:
        文本行列表
    """
    lines = []
    label = "峰" if is_peak else "谷"

    for i, (px, py) in enumerate(zip(results['x_peaks'], results['y_peaks'])):
        bw = calc_3db_bandwidth(
            results['x_full'], results['y_full'],
            results['peaks_idx'][i], is_peak
        )
        bw_str = f'{bw:.4f} nm' if bw is not None else 'N/A'
        lines.append(f'  {label} @ {px:.4f} nm, 值={py:.2f} dB, 3dB带宽={bw_str}')

    return lines
