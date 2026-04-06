# analysis/fitting.py — 曲线拟合函数
"""洛伦兹拟合及相关工具。"""

import numpy as np
from scipy.optimize import curve_fit


def lorentzian_with_slope(lambda_, T0, ER, lambda0, gamma, slope):
    """带斜率基线的洛伦兹线型。

    Args:
        lambda_: 波长数组 (nm)
        T0: 基线透射率 (线性单位)
        ER: 消光比 (0-1)
        lambda0: 中心波长 (nm)
        gamma: 半宽半高 (nm)
        slope: 基线斜率

    Returns:
        透射率数组 (线性单位)
    """
    baseline = T0 + slope * (lambda_ - lambda0)
    baseline = np.maximum(baseline, 1e-12)
    return baseline * (1 - ER / (1 + ((lambda_ - lambda0) / gamma) ** 2))


def fit_lorentzian_peak(
    lambda_slice: np.ndarray,
    T_slice_db: np.ndarray,
    fsr_mean: float,
    bounds_factor: float = 1.0,
):
    """拟合单个洛伦兹峰。

    Args:
        lambda_slice: 波长切片 (nm)
        T_slice_db: 功率切片 (dB)
        fsr_mean: 平均 FSR (nm)，用于估计初始参数
        bounds_factor: 边界放宽因子

    Returns:
        拟合结果字典，包含:
        - 'params': (T0, ER, lambda0, gamma, slope)
        - 'r_squared': R² 值
        - 'Ql': 负载 Q
        - 'Qi': 本征 Q
        - 'gamma': 全宽 (nm)
        - 'lambda0': 中心波长 (nm)
        - 'extinction': 消光比
        - 'slope': 基线斜率

    Raises:
        RuntimeError: 拟合失败
    """
    T_slice_linear = 10 ** (T_slice_db / 10)

    # 估计初始参数
    edge_len = max(3, len(T_slice_linear) // 10)
    T0_guess = np.mean(
        np.concatenate([T_slice_linear[:edge_len], T_slice_linear[-edge_len:]])
    )
    T_min = max(0.0, float(np.min(T_slice_linear)))
    er_guess = np.clip((T0_guess - T_min) / max(T0_guess, 1e-12), 0.0, 0.99)
    lambda0_guess = float(lambda_slice[np.argmin(T_slice_linear)])

    # 估计 gamma
    half_level = T0_guess * (1 - er_guess / 2)
    below_half = np.where(T_slice_linear < half_level)[0]
    if below_half.size > 1:
        gamma_guess = (lambda_slice[below_half[-1]] - lambda_slice[below_half[0]]) / 2
    else:
        gamma_guess = fsr_mean * 0.01
    gamma_guess = float(np.clip(gamma_guess, 1e-4, fsr_mean * 0.1))

    # 估计斜率
    left_x = lambda_slice[:edge_len]
    left_y = T_slice_linear[:edge_len]
    right_x = lambda_slice[-edge_len:]
    right_y = T_slice_linear[-edge_len:]
    x_edge = np.concatenate([left_x, right_x])
    y_edge = np.concatenate([left_y, right_y])
    if x_edge.size >= 2 and np.ptp(x_edge) > 0:
        slope_guess = float(np.polyfit(x_edge, y_edge, 1)[0])
    else:
        slope_guess = 0.0
    slope_scale = max(
        abs(slope_guess) * 10,
        max(T0_guess, 1e-12) / max(np.ptp(lambda_slice), 1e-9),
    )

    # 设置边界
    bounds = (
        [T0_guess * 0.7, 0.0, lambda0_guess - gamma_guess, gamma_guess * 0.2, -slope_scale],
        [T0_guess * 1.3, 1.0, lambda0_guess + gamma_guess, gamma_guess * 5.0, slope_scale],
    )

    # 中心加权
    center_dist = np.abs(lambda_slice - lambda0_guess) / max(gamma_guess, 1e-9)
    center_weight = 1.0 + 2.5 * np.exp(-0.5 * center_dist ** 2)
    sigma = 1.0 / center_weight

    # 拟合
    popt, _ = curve_fit(
        lorentzian_with_slope,
        lambda_slice,
        T_slice_linear,
        p0=[T0_guess, er_guess, lambda0_guess, gamma_guess, slope_guess],
        bounds=bounds,
        sigma=sigma,
        absolute_sigma=False,
        method='trf',
        maxfev=12000,
        ftol=1e-10,
        xtol=1e-10,
    )

    # 计算拟合质量
    T_fit = lorentzian_with_slope(lambda_slice, *popt)
    residuals = T_slice_linear - T_fit
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((T_slice_linear - np.mean(T_slice_linear)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else -1

    if r_squared < 0.5:
        raise RuntimeError(f"拟合质量差: R² = {r_squared:.4f}")

    T0, extinction_ratio, lambda0, gamma_half, slope = popt
    gamma = 2 * gamma_half
    Ql = lambda0 / gamma
    T_min_norm = max(1e-4, 1 - extinction_ratio)
    Qi = Ql / np.sqrt(T_min_norm)

    return {
        'params': popt,
        'r_squared': float(r_squared),
        'Ql': float(Ql),
        'Qi': float(Qi),
        'gamma': float(gamma),
        'lambda0': float(lambda0),
        'extinction': float(extinction_ratio),
        'slope': float(slope),
    }
