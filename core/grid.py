# core/grid.py — 网格与插值工具
"""波长网格生成与数据插值工具。"""

import numpy as np
from scipy.interpolate import interp1d

from .utils import _infer_decimals_from_value


def create_uniform_grid(
    start: float,
    end: float,
    step: float,
    decimals: int | None = None,
    endpoint: bool = True,
) -> np.ndarray:
    """生成均匀波长网格。

    Args:
        start: 起始波长 (nm)
        end: 结束波长 (nm)
        step: 步长 (nm)
        decimals: 小数位数，None 时自动推断
        endpoint: 是否包含端点

    Returns:
        均匀波长数组
    """
    if step <= 0:
        raise ValueError(f"step 必须为正数，当前值: {step}")
    if start > end:
        raise ValueError(f"start ({start}) 必须小于等于 end ({end})")
    if decimals is None:
        decimals = _infer_decimals_from_value(step)
    if endpoint:
        x = np.arange(start, end + step * 0.1, step, dtype=float)
    else:
        x = np.arange(start, end, step, dtype=float)
    x = np.round(x, decimals)
    if endpoint and x.size > 0:
        end_rounded = round(end, decimals)
        if abs(x[-1] - end_rounded) > 10 ** (-decimals - 1):
            x = np.append(x, end_rounded)
    return x


def sanitize_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """清洗 x/y 数据：去 NaN、排序、对重复 x 取平均。

    Args:
        x: x 坐标数组
        y: y 值数组

    Returns:
        (x, y) 清洗后的数组
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size != y.size:
        raise ValueError(f"x 与 y 长度不一致: x.size={x.size}, y.size={y.size}")
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 2:
        return x, y
    idx = np.argsort(x)
    x, y = x[idx], y[idx]
    uniq, inv = np.unique(x, return_inverse=True)
    if uniq.size == x.size:
        return x, y
    sums = np.bincount(inv, weights=y)
    counts = np.bincount(inv)
    return uniq, sums / np.maximum(counts, 1)


def interp_on_grid(
    x_src: np.ndarray,
    y_src: np.ndarray,
    x_dst: np.ndarray,
    mode: str = 'edge',
) -> np.ndarray:
    """将 y_src 从 x_src 插值到 x_dst 网格。

    Args:
        x_src: 源 x 坐标
        y_src: 源 y 值
        x_dst: 目标 x 网格
        mode: 边界处理模式 ('edge' | 'none' | 'extrapolate')

    Returns:
        插值后的 y 值数组
    """
    x_src, y_src = sanitize_xy(x_src, y_src)
    if x_src.size < 2:
        if x_src.size == 1:
            return np.full_like(x_dst, fill_value=y_src[0], dtype=float)
        return np.full_like(x_dst, fill_value=np.nan, dtype=float)
    if mode == 'edge':
        f = interp1d(x_src, y_src, bounds_error=False,
                     fill_value=(y_src[0], y_src[-1]))
    elif mode == 'none':
        f = interp1d(x_src, y_src, bounds_error=False, fill_value=np.nan)
    else:
        f = interp1d(x_src, y_src, bounds_error=False, fill_value='extrapolate')
    return np.asarray(f(x_dst), dtype=float)
