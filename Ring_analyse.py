r'''
微环谐振器轻量分析模块（FSR + Q 拟合）。

当前版本特性：
1. 输入仅保留 x 和 y（波长与功率），不再内置文件读取。
2. FSR 通过多峰自动估计得到。
3. 洛伦兹拟合窗口通过相邻峰自动分窗。
4. 已移除损耗（alpha）和色散（cal_D）计算链路。

示例：

import Ring_analyse as Ra

x = [1540.0, 1540.01, 1540.02]
y = [-18.2, -18.5, -18.1]
ring = Ra.Ring(x, y)
ring.cal_fsr(range_nm=(1530, 1550))
ring.cal_Q(holdon=False)
ring.plot_lambda(range_nm=(1548, 1550))
'''

from scipy.constants import c
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
import numpy as np
import matplotlib.pyplot as plt

from spectra_lib import (
    _infer_decimals_from_value,
    create_uniform_grid,
    sanitize_xy,
    interp_on_grid,
)

# 配置 matplotlib 中文显示
plt.rcParams['font.sans-serif'] = [
    'SimHei',
    'Microsoft YaHei',
    'SimSun',
    'Arial Unicode MS',
]  # 中文字体优先级
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 单位转换常数（提高代码可读性）
NM_TO_M = 1e-9  # 纳米转米
M_TO_NM = 1e9  # 米转纳米
THz = 1e12  # 太赫兹


def plt_ready(n: int = 1, cols: int = 2, figsize=(8, 5)):
    """按子图数量创建图窗，自动关闭多余坐标轴。"""
    if n <= 0:
        raise ValueError("子图数量 n 必须大于 0。")
    rows = (n + cols - 1) // cols
    fig, axs = plt.subplots(rows, cols, figsize=(cols * figsize[0], rows * figsize[1]))
    axs = axs.ravel() if isinstance(axs, np.ndarray) else [axs]
    for j in range(n, len(axs)):
        axs[j].axis('off')
    return fig, axs


def _sample_figs_by_wavelength(figs, wavelengths, n):
    """按波长范围均匀抽样，最多选取 n 个图。

    将波长范围等分为 n 个区间，每个区间取距区间中心最近的峰对应的图。
    """
    if not figs or n <= 0:
        return []
    pairs = sorted(zip(wavelengths, figs), key=lambda p: p[0])
    lams = [p[0] for p in pairs]
    sorted_figs = [p[1] for p in pairs]
    if len(figs) <= n:
        return sorted_figs
    lam_min, lam_max = lams[0], lams[-1]
    lam_range = lam_max - lam_min
    selected = []
    selected_set = set()
    for i in range(n):
        center = lam_min + (i + 0.5) * lam_range / n
        best_idx = int(np.argmin([abs(lam - center) for lam in lams]))
        if best_idx not in selected_set:
            selected_set.add(best_idx)
            selected.append(sorted_figs[best_idx])
    return selected


class Ring:
    T: np.ndarray | None = None  # [db]
    fre: np.ndarray | None = None  # [THz]
    lamda: np.ndarray | None = None  # [nm]

    lambda0: np.ndarray | None = None
    lambda_step: float | None = None  # 波长步长
    fsr_mean: float | None = None  # 平均自由光谱范围，单位nm

    def __init__(self, x, y):
        """
        轻量版微环分析类，仅依赖 x/y 谱线数据。

        Args:
            x: 波长序列（nm）
            y: 功率序列（dB）
        """
        lamda, trans = sanitize_xy(
            np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        )
        if lamda.size < 2:
            raise ValueError("至少需要 2 个有效数据点。")
        self.lamda = lamda
        self.T = trans
        self.fre = c / (self.lamda * NM_TO_M) / THz

    def _get_ring_step_pm(self) -> float:
        """从 self.lamda 推断步长（pm），若点数不足则返回 1.0 pm 作为保守默认。"""
        if self.lamda is None or self.lamda.size < 2:
            return 1.0
        step_nm = float(np.round(np.mean(np.diff(self.lamda)), 9))
        return max(step_nm * 1e3, 1e-6)  # 至少保持正数

    def _get_lam_grid_from_ring(
        self, range_nm: tuple[float, float] | None
    ) -> np.ndarray:
        """按微环步长在指定范围内生成吸附后的均匀波长网格。"""
        if self.lamda is None:
            return np.array([])
        step_pm = self._get_ring_step_pm()
        start = float(self.lamda.min()) if range_nm is None else float(range_nm[0])
        end = float(self.lamda.max()) if range_nm is None else float(range_nm[1])
        return self._uniform_grid(start, end, step_pm)

    def _uniform_grid(
        self, start_nm: float, end_nm: float, step_pm: float
    ) -> np.ndarray:
        """生成均匀波长网格（单位：nm）。

        Args:
            start_nm: 起始波长（纳米）
            end_nm: 结束波长（纳米）
            step_pm: 步长（皮米，自动转换为纳米）

        Returns:
            均匀波长网格，自动修正浮点数精度问题
        """
        if step_pm is None or step_pm <= 0:
            raise ValueError("step_pm 必须为正数。")
        step_nm = step_pm * 1e-3
        return create_uniform_grid(start_nm, end_nm, step_nm, endpoint=True)

    def _sanitize_xy(
        self, x: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """去 NaN、排序、对重复 x 取平均。"""
        return sanitize_xy(x, y)

    def _interp_on_x(
        self,
        x_src: np.ndarray,
        y_src: np.ndarray,
        x_dst: np.ndarray,
        mode: str = 'edge',
    ) -> np.ndarray:
        """将 y_src 按 x_src 插值到 x_dst。

        Args:
            x_src: 源数据 x 坐标
            y_src: 源数据 y 值
            x_dst: 目标网格 x 坐标
            mode: 'edge' | 'none' | 'extrapolate'

        Returns:
            插值后的 y 值数组
        """
        return interp_on_grid(x_src, y_src, x_dst, mode=mode)

    def cal_fsr(self, range_nm=None, display=True, figinsert=None):
        '''
        根据透射谱计算自由光谱范围（FSR），并绘制FSR随波长和频率的变化图。
        Args:
            range_nm: 计算FSR以及最后显示的波长范围，格式为(start, end)，单位nm
            display: 是否显示FSR随波长和频率的变化图
        '''
        if self.lamda is None or self.T is None:
            print("Frequency and wavelength data are required to calculate FSR.")
            return

        grid = self.get_ring_grid(range_nm=range_nm, extrapolate='edge')
        lamda = grid['lam']
        fre = grid['fre']
        T = grid['T']

        if lamda is None or lamda.size < 5 or T is None:
            raise ValueError("波长数据点不足，无法计算 FSR。")

        detect_signal = -T
        step_size = float(np.mean(np.diff(lamda)))
        base_distance = max(1, int(len(lamda) / 200))
        peak_prominence = max(0.5, float(np.ptp(detect_signal)) * 0.05)

        peaks, _ = find_peaks(
            detect_signal,
            distance=base_distance,
            prominence=peak_prominence,
        )
        if peaks.size < 3:
            peaks, _ = find_peaks(
                detect_signal,
                distance=max(1, int(base_distance / 2)),
                prominence=max(0.2, peak_prominence * 0.5),
            )
        if peaks.size < 2:
            raise ValueError("自动寻峰失败，峰数量不足以估计 FSR。")

        coarse_spacing = np.diff(lamda[peaks])
        spacing_median = float(np.median(coarse_spacing))
        mad = float(np.median(np.abs(coarse_spacing - spacing_median)))
        if mad > 0:
            sigma = 1.4826 * mad
            valid = np.abs(coarse_spacing - spacing_median) <= 3.0 * sigma
        else:
            valid = np.ones_like(coarse_spacing, dtype=bool)
        fsr_seed = (
            float(np.mean(coarse_spacing[valid])) if np.any(valid) else spacing_median
        )

        refine_distance = max(1, int(0.6 * fsr_seed / step_size))
        peaks_refined, _ = find_peaks(
            detect_signal,
            distance=refine_distance,
            prominence=peak_prominence,
        )
        if peaks_refined.size >= 2:
            peaks = peaks_refined

        lambda_peaks = lamda[peaks]
        fsr_lambda_all = np.abs(np.diff(lambda_peaks))
        if fsr_lambda_all.size == 0:
            raise ValueError("峰数量不足，无法计算 FSR。")
        fsr_median = float(np.median(fsr_lambda_all))
        mad2 = float(np.median(np.abs(fsr_lambda_all - fsr_median)))
        if mad2 > 0:
            sigma2 = 1.4826 * mad2
            valid2 = np.abs(fsr_lambda_all - fsr_median) <= 3.0 * sigma2
        else:
            valid2 = np.ones_like(fsr_lambda_all, dtype=bool)
        fsr_lambda = fsr_lambda_all[valid2] if np.any(valid2) else fsr_lambda_all

        self.fsr_mean = float(np.mean(fsr_lambda))
        self.lambda0 = lambda_peaks
        self._peak_indices = peaks
        fre_peaks = fre[peaks] if fre is not None else np.array([])
        fsr_fre = np.abs(np.diff(fre_peaks))
        if display:
            if figinsert is None:
                fig, axes = plt_ready(4, 2, figsize=(8, 6))
            else:
                fig = figinsert
                axes = fig.subplots(2, 2)
                axes = axes.ravel() if isinstance(axes, np.ndarray) else [axes]

            ax1, ax2, ax3, ax4 = axes
            ax1.plot(lambda_peaks[:-1], fsr_lambda_all, 'o-')
            ax1.set_xlabel('Wavelength (nm)')
            ax1.set_ylabel('FSR (nm)')
            ax1.set_title('Free Spectral Range vs Wavelength')
            ax1.grid(True)

            if fre_peaks.size > 0:
                ax2.plot(fre_peaks[:-1], fsr_fre, 'o-')
            ax2.set_xlabel('Frequency (THz)')
            ax2.set_ylabel('FSR (THz)')
            ax2.set_title('Free Spectral Range vs Frequency')
            ax2.grid(True)

            ax3.plot(lamda, T, label='Transmission Spectrum')
            ax3.plot(lambda_peaks, T[peaks], 'ro', label='Resonance Peaks')
            ax3.axhline(
                np.max(T),
                color='gray',
                linestyle='--',
                label='Max Transmission',
            )
            ax3.text(
                np.max(lamda),
                np.max(T),
                f'{np.max(T):.2f}',
                va='center',
                ha='left',
                color='gray',
                fontsize=12,
                bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'),
            )
            ax3.set_xlabel('Wavelength (nm)')
            ax3.set_ylabel('dB')

            if fre is not None:
                ax4.plot(fre, T, label='Transmission Spectrum')
                ax4.plot(fre_peaks, T[peaks], 'ro', label='Resonance Peaks')
            ax4.set_xlabel('Frequency (THz)')
            ax4.set_ylabel('dB')
            ax4.axhline(
                np.max(T),
                color='gray',
                linestyle='--',
                label='Max Transmission',
            )
            ax4.text(
                np.max(fre),
                np.max(T),
                f'{np.max(T):.2f}',
                va='center',
                ha='left',
                color='gray',
                fontsize=12,
                bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'),
            )
            fig.tight_layout()
            fig.canvas.draw_idle()
            return fig

    def cal_Q(self, holdon=False, max_holdon=10, figinsert=None):
        '''
        根据透射谱计算Q因子。
        Args:
            holdon: 是否保留每个峰的拟合图像
        '''

        def lorentzian_with_slope(lambda_, T0, ER, lambda0, gamma, slope):
            # 引入局部线性基线，降低包络起伏对谷底拟合的偏置。
            baseline = T0 + slope * (lambda_ - lambda0)
            baseline = np.maximum(baseline, 1e-12)
            return baseline * (1 - ER / (1 + ((lambda_ - lambda0) / gamma) ** 2))

        if self.fre is None or self.lamda is None or self.T is None:
            print(
                "Frequency/wavelength/transmission data are required to calculate Q-factor."
            )
            return

        if self.fsr_mean is None:
            self.cal_fsr(display=False)
        assert self.fsr_mean is not None

        lamda = self.lamda
        T_db = self.T
        if self.lambda0 is not None and len(self.lambda0) >= 2:
            peaks = np.array(
                [int(np.abs(lamda - lam0).argmin()) for lam0 in self.lambda0], dtype=int
            )
            peaks = np.unique(peaks)
        else:
            step_size = float(np.mean(np.diff(lamda)))
            distance_pts = max(1, int(self.fsr_mean * 0.6 / step_size))
            peaks, _ = find_peaks(-T_db, distance=distance_pts, prominence=1.0)

        if peaks.size < 2:
            raise ValueError("有效峰数量不足，无法进行 Q 拟合。")

        def fit_window_by_neighbors(i: int, min_points: int = 40) -> tuple[int, int]:
            n = len(lamda)
            p = int(peaks[i])
            if i == 0:
                right_mid = 0.5 * (lamda[p] + lamda[int(peaks[i + 1])])
                left_est = lamda[p] - 0.5 * (right_mid - lamda[p])
                left_idx = int(np.searchsorted(lamda, left_est, side='left'))
            else:
                left_mid = 0.5 * (lamda[int(peaks[i - 1])] + lamda[p])
                left_idx = int(np.searchsorted(lamda, left_mid, side='left'))

            if i == len(peaks) - 1:
                left_mid = 0.5 * (lamda[int(peaks[i - 1])] + lamda[p])
                right_est = lamda[p] + 0.5 * (lamda[p] - left_mid)
                right_idx = int(np.searchsorted(lamda, right_est, side='right')) - 1
            else:
                right_mid = 0.5 * (lamda[p] + lamda[int(peaks[i + 1])])
                right_idx = int(np.searchsorted(lamda, right_mid, side='right')) - 1

            left_idx = max(0, min(left_idx, p - 1))
            right_idx = min(n - 1, max(right_idx, p + 1))

            if (right_idx - left_idx + 1) < min_points:
                expand = (min_points - (right_idx - left_idx + 1)) // 2 + 1
                left_idx = max(0, left_idx - expand)
                right_idx = min(n - 1, right_idx + expand)
            return left_idx, right_idx

        fit_results = []
        figs = []

        for i, peak in enumerate(peaks):
            try:
                left_idx, right_idx = fit_window_by_neighbors(i)
                lambda_slice = lamda[left_idx : right_idx + 1]
                T_slice_db = T_db[left_idx : right_idx + 1]
                T_slice_linear = 10 ** (T_slice_db / 10)

                edge_len = max(3, len(T_slice_linear) // 10)
                T0_guess = np.mean(
                    np.concatenate(
                        [T_slice_linear[:edge_len], T_slice_linear[-edge_len:]]
                    )
                )
                T_min = max(0.0, float(np.min(T_slice_linear)))
                ER_guess = np.clip((T0_guess - T_min) / max(T0_guess, 1e-12), 0.0, 0.99)
                lambda0_guess = float(lambda_slice[np.argmin(T_slice_linear)])

                half_level = T0_guess * (1 - ER_guess / 2)
                below_half = np.where(T_slice_linear < half_level)[0]
                if below_half.size > 1:
                    gamma_guess = (
                        lambda_slice[below_half[-1]] - lambda_slice[below_half[0]]
                    ) / 2
                else:
                    gamma_guess = self.fsr_mean * 0.01
                gamma_guess = float(np.clip(gamma_guess, 1e-4, self.fsr_mean * 0.1))

                edge_len = max(3, len(lambda_slice) // 10)
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

                bounds = (
                    [
                        T0_guess * 0.7,
                        0.0,
                        lambda0_guess - gamma_guess,
                        gamma_guess * 0.2,
                        -slope_scale,
                    ],
                    [
                        T0_guess * 1.3,
                        1.0,
                        lambda0_guess + gamma_guess,
                        gamma_guess * 5.0,
                        slope_scale,
                    ],
                )

                # 对谷底附近提高权重，使中心位置与最小值更一致。
                center_dist = np.abs(lambda_slice - lambda0_guess) / max(
                    gamma_guess, 1e-9
                )
                center_weight = 1.0 + 2.5 * np.exp(-0.5 * center_dist**2)
                sigma = 1.0 / center_weight

                popt, _ = curve_fit(
                    lorentzian_with_slope,
                    lambda_slice,
                    T_slice_linear,
                    p0=[T0_guess, ER_guess, lambda0_guess, gamma_guess, slope_guess],
                    bounds=bounds,
                    sigma=sigma,
                    absolute_sigma=False,
                    method='trf',
                    maxfev=12000,
                    ftol=1e-10,
                    xtol=1e-10,
                )

                T_fit = lorentzian_with_slope(lambda_slice, *popt)
                residuals = T_slice_linear - T_fit
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((T_slice_linear - np.mean(T_slice_linear)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else -1
                if r_squared < 0.5:
                    continue

                T0, extinction_ratio, lambda0, gamma_half, slope = popt
                gamma = 2 * gamma_half
                Ql = lambda0 / gamma

                T_min_norm = max(1e-4, 1 - extinction_ratio)
                Qi = Ql / np.sqrt(T_min_norm)

                if i == 0:
                    fsr_local = lamda[int(peaks[1])] - lamda[int(peaks[0])]
                elif i == len(peaks) - 1:
                    fsr_local = lamda[int(peaks[-1])] - lamda[int(peaks[-2])]
                else:
                    fsr_local = (
                        lamda[int(peaks[i + 1])] - lamda[int(peaks[i - 1])]
                    ) / 2

                fit_results.append(
                    {
                        'lambda0': float(lambda0),
                        'gamma': float(gamma),
                        'kappa2': float(np.pi * gamma / max(fsr_local, 1e-9)),
                        'Ql': float(Ql),
                        'Qi': float(Qi),
                        'params': popt,
                        'r_squared': float(r_squared),
                        'extinction': float(extinction_ratio),
                        'slope': float(slope),
                    }
                )

                fig, ax = plt.subplots(figsize=(10, 6))
                baseline_slice = np.maximum(
                    T0 + slope * (lambda_slice - lambda0), 1e-12
                )
                T_norm = T_slice_linear / baseline_slice
                ax.plot(
                    lambda_slice,
                    T_norm,
                    'o',
                    markersize=5,
                    alpha=0.6,
                    color='blue',
                    label='实验数据',
                )
                lambda_dense = np.linspace(lambda_slice[0], lambda_slice[-1], 500)
                T_fit_dense_raw = lorentzian_with_slope(lambda_dense, *popt)
                baseline_dense = np.maximum(
                    T0 + slope * (lambda_dense - lambda0), 1e-12
                )
                T_fit_dense = T_fit_dense_raw / baseline_dense
                ax.plot(
                    lambda_dense,
                    T_fit_dense,
                    '-',
                    linewidth=2,
                    color='red',
                    alpha=0.8,
                    label='洛伦兹拟合',
                )
                ax.axvline(
                    lambda0,
                    color='green',
                    linestyle='--',
                    linewidth=1.5,
                    alpha=0.7,
                    label='中心波长',
                )
                ax.axvline(
                    lambda0 - gamma / 2,
                    color='orange',
                    linestyle=':',
                    linewidth=1.5,
                    alpha=0.7,
                )
                ax.axvline(
                    lambda0 + gamma / 2,
                    color='orange',
                    linestyle=':',
                    linewidth=1.5,
                    alpha=0.7,
                    label='3dB带宽',
                )

                info_text = (
                    f'中心波长: {lambda0:.4f} nm\n'
                    f'3dB带宽: {gamma*1000:.3f} pm\n'
                    f'负载Q (Ql): {Ql:.0f}\n'
                    f'本征Q (Qi): {Qi:.0f}\n'
                    f'Qi/Ql: {Qi/Ql:.2f}\n'
                    f'消光比: {extinction_ratio:.3f}\n'
                    f'R^2: {r_squared:.4f}'
                )
                ax.text(
                    0.98,
                    0.97,
                    info_text,
                    transform=ax.transAxes,
                    fontsize=11,
                    verticalalignment='top',
                    horizontalalignment='right',
                    bbox=dict(
                        boxstyle='round,pad=0.8',
                        facecolor='wheat',
                        alpha=0.8,
                        edgecolor='black',
                        linewidth=1.5,
                    ),
                )
                ax.set_xlabel('波长 (nm)', fontsize=12)
                ax.set_ylabel('归一化透射率', fontsize=12)
                ax.set_title(
                    f'峰 @ {lambda0:.3f} nm - 洛伦兹拟合 (R^2={r_squared:.4f})',
                    fontsize=14,
                    fontweight='bold',
                )
                ax.legend(loc='upper left', fontsize=10)
                ax.grid(True, alpha=0.3, linestyle='--')
                ax.set_ylim((0, 1.1))
                fig.tight_layout()
                figs.append(fig)

            except Exception as e:
                print(f"  峰 {i+1} @ {lamda[int(peak)]:.3f} nm 拟合失败: {e}")
                continue

        if holdon and figs:
            # 按波长范围均匀抽样，最多显示 max_holdon 个单峰拟合图
            lam0_list = [r['lambda0'] for r in fit_results]
            selected = _sample_figs_by_wavelength(figs, lam0_list, max_holdon)
            for fig in figs:
                if fig not in selected:
                    plt.close(fig)
        elif not holdon and figs:
            # 只关闭单峰拟合图，不影响 FSR 等其他图窗
            for fig in figs:
                plt.close(fig)
            figs.clear()

        if len(fit_results) == 0:
            raise ValueError("未获得有效拟合结果，请检查谱线质量或峰值数量。")

        self.fit_results = fit_results

        def sigma_filter(arr: np.ndarray) -> np.ndarray:
            if arr.size == 0:
                return arr
            if arr.size <= 2:
                return arr
            m = np.mean(arr)
            s = np.std(arr)
            if s == 0:
                return arr
            return arr[np.abs(arr - m) < 4 * s]

        Ql_filtered = sigma_filter(
            np.array(
                [
                    res['Ql']
                    for res in fit_results
                    if np.isfinite(res['Ql']) and res['Ql'] > 0
                ]
            )
        )
        Qi_filtered = sigma_filter(
            np.array(
                [
                    res['Qi']
                    for res in fit_results
                    if np.isfinite(res['Qi']) and res['Qi'] > 0
                ]
            )
        )

        kappa2_all = np.array(
            [
                res['kappa2']
                for res in fit_results
                if np.isfinite(res['kappa2']) and 0 < res['kappa2'] < 1
            ]
        )
        lambda0_all = np.array(
            [
                res['lambda0']
                for res in fit_results
                if np.isfinite(res['kappa2']) and 0 < res['kappa2'] < 1
            ]
        )
        kappa2_filtered = sigma_filter(kappa2_all)
        if kappa2_filtered.size > 0:
            kappa_mask = np.isin(kappa2_all, kappa2_filtered)
            lambda0_filtered = lambda0_all[kappa_mask]
        else:
            lambda0_filtered = np.array([])

        if figinsert is None:
            fig, axes = plt_ready(3, 3, figsize=(8, 10))
        else:
            fig = figinsert
            axes = fig.subplots(1, 3)
            axes = axes.ravel() if isinstance(axes, np.ndarray) else [axes]

        ax1, ax2, ax3 = axes[:3]

        ax1.hist(Ql_filtered, bins=20, color='mediumseagreen', edgecolor='black')
        ax1.set_title('Loaded Q-factor Distribution')
        ax1.set_xlabel('Ql')
        ax1.set_ylabel('Count')
        ax1.grid(True)

        ax2.hist(Qi_filtered, bins=20, color='steelblue', edgecolor='black')
        ax2.set_title('Intrinsic Q-factor Distribution')
        ax2.set_xlabel('Qi')
        ax2.set_ylabel('Count')
        ax2.grid(True)

        ax3.plot(
            lambda0_filtered,
            kappa2_filtered,
            'bo--',
            markerfacecolor='none',
            label='kappa2',
        )
        ax3.set_xlabel('Resonance Wavelength (nm)')
        ax3.set_ylabel('Coupling Coefficient (kappa^2)')
        ax3_1 = ax3.twinx()
        ax3_1.plot(self.lamda, self.T, 'g-', alpha=0.3)
        ax3_1.plot(self.lambda0, self.T[peaks], 'go')
        ax3_1.set_ylabel('Transmission Spectrum (dB)')
        ax3.set_title('Coupling Coefficient')
        ax3.grid(True)
        ax3.legend()

        fig.tight_layout()
        fig.canvas.draw_idle()
        return fig

    def plot_lambda(self, range_nm=None, figinsert=None):
        '''
        横轴为波长，绘制透射谱
        Args:
            range_nm: 显示的波长范围，格式为(start, end)，单位nm
        '''
        if self.lamda is None:
            print("Frequency data is not available.")
        else:
            grid = self.get_ring_grid(range_nm=range_nm, extrapolate='edge')
            lamda, T = grid['lam'], grid['T']
            if T is None:
                print("No data to plot.")
                return
            if figinsert is None:
                fig, axes = plt_ready(1, 1, figsize=(8, 5))
            else:
                fig = figinsert
                axes = fig.subplots(1, 1)
                axes = axes.ravel() if isinstance(axes, np.ndarray) else [axes]

            ax = axes[0]
            ax.plot(lamda, T, label='Transmission Spectrum', color='b')
            ax.set_xlabel('Lambda (nm)')
            ax.set_ylabel('dB')
            ax.set_title('Transmission Spectrum')
            ax.grid(True)
            ax.legend()
            fig.tight_layout()
            fig.canvas.draw_idle()
            return fig

    def plot_fre(self, range_THz=None, figinsert=None):
        '''
        横轴为频率，绘制透射谱
        Args:
            range_THz: 显示的频率范围，格式为(start, end)，单位THz
        '''
        if self.lamda is None:
            print("Frequency data is not available.")
        else:
            grid = self.get_ring_grid(range_nm=None, extrapolate='edge')
            fre, T = grid['fre'], grid['T']
            if range_THz is not None and fre is not None:
                start, end = range_THz
                m = (fre >= start) & (fre <= end)
                fre = fre[m]
                T = T[m] if T is not None else None
            if T is None:
                print("No data to plot.")
                return
            if figinsert is None:
                fig, axes = plt_ready(1, 1, figsize=(8, 5))
            else:
                fig = figinsert
                axes = fig.subplots(1, 1)
                axes = axes.ravel() if isinstance(axes, np.ndarray) else [axes]

            ax = axes[0]
            ax.plot(fre, T, label='Transmission Spectrum', color='b')
            ax.set_xlabel('Frequency (THz)')
            ax.set_ylabel('dB')
            ax.set_title('Transmission Spectrum')
            ax.grid(True)
            ax.legend()
            fig.tight_layout()
            fig.canvas.draw_idle()
            return fig

    # ========================= 统一网格：微环主轨迹 ========================= #
    def get_ring_grid(
        self, range_nm: tuple[float, float] | None = None, extrapolate: str = 'edge'
    ) -> dict:
        """
        返回统一吸附网格下的微环数据：{'lam','fre','T'}。
        - lam：按微环步长推断出的 pm 步长，生成均匀网格并吸附到小数位
        - fre：由 lam 计算得到（THz）
        - T：将原始 self.T 插值到 lam 上（默认边界延拓）
        - range_nm：可选，仅在该范围内生成网格
        """
        if self.lamda is None:
            return {'lam': None, 'fre': None, 'T': None}
        lam = self.lamda
        lam_grid = self._get_lam_grid_from_ring(range_nm)
        T_grid = None
        if self.T is not None:
            T_grid = self._interp_on_x(lam, self.T, lam_grid, mode=extrapolate)
        fre_grid = c / (lam_grid * NM_TO_M) / THz
        return {'lam': lam_grid, 'fre': fre_grid, 'T': T_grid}

    # 色散与模式文件相关能力已在轻量版中移除。
