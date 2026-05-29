# analysis/ring.py — 微环谐振器分析
"""微环谐振器 FSR 和 Q 因子分析。"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.constants import c
from scipy.signal import find_peaks

from core.grid import create_uniform_grid, sanitize_xy, interp_on_grid
from core.utils import _infer_decimals_from_value
from .fitting import lorentzian_with_slope, fit_lorentzian_peak

# matplotlib 中文字体由 main.py 统一配置，这里仅确保 unicode_minus 关闭
plt.rcParams['axes.unicode_minus'] = False

# Nature 风格无衬线字体栈（图中已全部使用英文）
# 不含 Helvetica：Windows 无此字体会触发大量 findfont 警告；Arial 优先，DejaVu 兜底
_FONT = ['Arial', 'DejaVu Sans', 'sans-serif']

# 单位转换常数
NM_TO_M = 1e-9
M_TO_NM = 1e9
THZ = 1e12


def _sample_figs_by_wavelength(figs, wavelengths, n):
    """按波长范围均匀抽样，最多选取 n 个图。"""
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


def _plt_ready(n: int = 1, cols: int = 2, figsize=(8, 5)):
    """按子图数量创建图窗。"""
    if n <= 0:
        raise ValueError("子图数量 n 必须大于 0。")
    rows = (n + cols - 1) // cols
    fig, axs = plt.subplots(rows, cols, figsize=(cols * figsize[0], rows * figsize[1]))
    axs = axs.ravel() if isinstance(axs, np.ndarray) else [axs]
    for j in range(n, len(axs)):
        axs[j].axis('off')
    return fig, axs


# ── Nature 风格颜色常量 ──
# 蓝=主数据/Ql，绿=Qi，红=拟合/峰，灰=次要曲线与参考线
_JC = {
    'curve':  '#4D4D4D',   # 光谱曲线 — 中性深灰
    'fit':    '#B64342',   # 拟合曲线 — Nature 红
    'peak':   '#B64342',   # 峰标记 — Nature 红
    'arrow':  '#B8B8B8',   # 辅助参考线 — 浅灰
    'Ql':     '#0F4D92',   # Ql / 负载 Q — Nature 主蓝
    'Qi':     '#2E9E44',   # Qi / 本征 Q — Nature 绿
    'center': '#0F4D92',   # 中心波长线 — 蓝
    'bw':     '#767676',   # 3dB 带宽线 — 中灰
    'kappa':  '#0F4D92',   # 耦合系数 — 蓝
    'trans':  '#4D4D4D',   # 透射谱（twin 轴）— 深灰
}


def _apply_journal_style(ax, xlabel='', ylabel='', title='', fontsize=10,
                         open_spines=True):
    """为 Axes 应用 Nature 风格视觉样式。

    open_spines=True 时移除上/右边框（Nature 标志性的开放坐标轴）。
    孪生轴（twinx）需保留右边框，应传入 open_spines=False 并自行着色。
    """
    ax.set_xlabel(xlabel, fontsize=fontsize, fontfamily=_FONT)
    ax.set_ylabel(ylabel, fontsize=fontsize, fontfamily=_FONT)
    if title:
        ax.set_title(title, fontsize=fontsize + 1, fontfamily=_FONT,
                     fontweight='bold', pad=8)
    ax.tick_params(axis='both', which='major', labelsize=max(6, fontsize - 2),
                   direction='out', length=3.5, width=0.8, top=False, right=False)
    ax.tick_params(axis='both', which='minor', direction='out',
                   length=2, width=0.6, top=False, right=False)
    if open_spines:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontfamily(_FONT)
    ax.grid(False)


class Ring:
    """微环谐振器分析类。

    提供 FSR 计算和 Q 因子拟合功能。
    """

    T: np.ndarray | None = None  # [dB]
    fre: np.ndarray | None = None  # [THz]
    lamda: np.ndarray | None = None  # [nm]

    lambda0: np.ndarray | None = None
    lambda_step: float | None = None
    fsr_mean: float | None = None

    def __init__(self, x, y):
        """初始化。

        Args:
            x: 波长序列 (nm)
            y: 功率序列 (dB)
        """
        lamda, trans = sanitize_xy(
            np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        )
        if lamda.size < 2:
            raise ValueError("至少需要 2 个有效数据点。")
        self.lamda = lamda
        self.T = trans
        self.fre = c / (self.lamda * NM_TO_M) / THZ

    def _get_ring_step_pm(self) -> float:
        """推断步长 (pm)。"""
        if self.lamda is None or self.lamda.size < 2:
            return 1.0
        step_nm = float(np.round(np.mean(np.diff(self.lamda)), 9))
        return max(step_nm * 1e3, 1e-6)

    def _get_lam_grid_from_ring(self, range_nm: tuple[float, float] | None) -> np.ndarray:
        """生成均匀波长网格。"""
        if self.lamda is None:
            return np.array([])
        step_pm = self._get_ring_step_pm()
        start = float(self.lamda.min()) if range_nm is None else float(range_nm[0])
        end = float(self.lamda.max()) if range_nm is None else float(range_nm[1])
        return self._uniform_grid(start, end, step_pm)

    def _uniform_grid(self, start_nm: float, end_nm: float, step_pm: float) -> np.ndarray:
        """生成均匀波长网格 (nm)。"""
        if step_pm is None or step_pm <= 0:
            raise ValueError("step_pm 必须为正数。")
        step_nm = step_pm * 1e-3
        return create_uniform_grid(start_nm, end_nm, step_nm, endpoint=True)

    def get_ring_grid(self, range_nm: tuple[float, float] | None = None, extrapolate: str = 'edge') -> dict:
        """获取统一网格数据。"""
        if self.lamda is None:
            return {'lam': None, 'fre': None, 'T': None}
        lam = self.lamda
        lam_grid = self._get_lam_grid_from_ring(range_nm)
        T_grid = None
        if self.T is not None:
            T_grid = interp_on_grid(lam, self.T, lam_grid, mode=extrapolate)
        fre_grid = c / (lam_grid * NM_TO_M) / THZ
        return {'lam': lam_grid, 'fre': fre_grid, 'T': T_grid}

    def cal_fsr(self, range_nm=None, display=True, figinsert=None,
                height_threshold=None, min_distance=None, fontsize=10):
        """计算自由光谱范围 (FSR)。

        Args:
            range_nm: 波长范围 (start, end) nm
            display: 是否显示结果图
            figinsert: 外部图窗
            height_threshold: 谷的最小深度阈值 (dB)，None 表示不限
            min_distance: 峰间最小距离 (数据点数)，None/0 表示自动推断

        Returns:
            matplotlib Figure 或 None
        """
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

        # 距离参数：用户指定 or 自动推断
        if min_distance and min_distance > 0:
            base_distance = max(1, int(min_distance))
        else:
            base_distance = max(1, int(len(lamda) / 200))

        peak_prominence = max(0.5, float(np.ptp(detect_signal)) * 0.05)

        # height 参数：用户指定 or 不限
        find_kw = dict(distance=base_distance, prominence=peak_prominence)
        if height_threshold is not None:
            find_kw['height'] = float(height_threshold)

        peaks, _ = find_peaks(detect_signal, **find_kw)
        if peaks.size < 3:
            relax_kw = dict(
                distance=max(1, int(base_distance / 2)),
                prominence=max(0.2, peak_prominence * 0.5),
            )
            if height_threshold is not None:
                relax_kw['height'] = float(height_threshold)
            peaks, _ = find_peaks(detect_signal, **relax_kw)
        if peaks.size < 2:
            raise ValueError("自动寻峰失败，峰数量不足以估计 FSR。")

        # MAD 离群值剔除
        coarse_spacing = np.diff(lamda[peaks])
        spacing_median = float(np.median(coarse_spacing))
        mad = float(np.median(np.abs(coarse_spacing - spacing_median)))
        if mad > 0:
            sigma = 1.4826 * mad
            valid = np.abs(coarse_spacing - spacing_median) <= 3.0 * sigma
        else:
            valid = np.ones_like(coarse_spacing, dtype=bool)
        fsr_seed = float(np.mean(coarse_spacing[valid])) if np.any(valid) else spacing_median

        # 精细化寻峰
        refine_distance = max(1, int(0.6 * fsr_seed / step_size))
        peaks_refined, _ = find_peaks(detect_signal, distance=refine_distance, prominence=peak_prominence)
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
                fig, axes = _plt_ready(4, 2, figsize=(8, 6))
            else:
                fig = figinsert
                axes = fig.subplots(2, 2)
                axes = axes.ravel() if isinstance(axes, np.ndarray) else [axes]

            ax1, ax2, ax3, ax4 = axes
            ax1.plot(lambda_peaks[:-1], fsr_lambda_all, '-', color=_JC['Ql'],
                     linewidth=1.0, marker='o', markersize=4,
                     markerfacecolor='white', markeredgecolor=_JC['Ql'],
                     markeredgewidth=1.0)
            _apply_journal_style(ax1, xlabel='Wavelength (nm)', ylabel='FSR (nm)',
                                 title='Free Spectral Range vs Wavelength', fontsize=fontsize)

            if fre_peaks.size > 0:
                ax2.plot(fre_peaks[:-1], fsr_fre, '-', color=_JC['Qi'],
                         linewidth=1.0, marker='o', markersize=4,
                         markerfacecolor='white', markeredgecolor=_JC['Qi'],
                         markeredgewidth=1.0)
            _apply_journal_style(ax2, xlabel='Frequency (THz)', ylabel='FSR (THz)',
                                 title='Free Spectral Range vs Frequency', fontsize=fontsize)

            ax3.plot(lamda, T, color=_JC['curve'], linewidth=0.9, label='Transmission')
            ax3.plot(lambda_peaks, T[peaks], 'o', color=_JC['peak'],
                     markersize=4.5, markeredgecolor='white', markeredgewidth=0.5,
                     label='Resonance Peaks')
            ax3.axhline(np.max(T), color=_JC['arrow'], linestyle='--', linewidth=0.6)
            _apply_journal_style(ax3, xlabel='Wavelength (nm)', ylabel='Transmission (dB)', fontsize=fontsize)
            ax3.legend(fontsize=max(6, fontsize - 2), frameon=False)

            if fre is not None:
                ax4.plot(fre, T, color=_JC['curve'], linewidth=0.9, label='Transmission')
                ax4.plot(fre_peaks, T[peaks], 'o', color=_JC['peak'],
                         markersize=4.5, markeredgecolor='white', markeredgewidth=0.5,
                         label='Resonance Peaks')
            ax4.axhline(np.max(T), color=_JC['arrow'], linestyle='--', linewidth=0.6)
            _apply_journal_style(ax4, xlabel='Frequency (THz)', ylabel='Transmission (dB)', fontsize=fontsize)
            ax4.legend(fontsize=max(6, fontsize - 2), frameon=False)
            fig.tight_layout()
            fig.canvas.draw_idle()
            return fig

    def cal_Q(self, holdon=False, max_holdon=10, figinsert=None, fontsize=10):
        """计算 Q 因子。

        Args:
            holdon: 是否保留单峰拟合图
            max_holdon: 最多保留的单峰图数量
            figinsert: 外部图窗

        Returns:
            matplotlib Figure 或 None
        """
        if self.fre is None or self.lamda is None or self.T is None:
            print("Frequency/wavelength/transmission data are required to calculate Q-factor.")
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

                result = fit_lorentzian_peak(lambda_slice, T_slice_db, self.fsr_mean)

                # 计算 FSR 和 kappa²
                if i == 0:
                    fsr_local = lamda[int(peaks[1])] - lamda[int(peaks[0])]
                elif i == len(peaks) - 1:
                    fsr_local = lamda[int(peaks[-1])] - lamda[int(peaks[-2])]
                else:
                    fsr_local = (lamda[int(peaks[i + 1])] - lamda[int(peaks[i - 1])]) / 2

                result['kappa2'] = float(np.pi * result['gamma'] / max(fsr_local, 1e-9))
                result['lambda0'] = float(result['lambda0'])

                # 绘制单峰拟合图
                fig = self._plot_single_peak_fit(lambda_slice, T_slice_db, result, fontsize=fontsize)
                if fig is not None:
                    figs.append(fig)

                fit_results.append(result)

            except Exception as e:
                print(f"  峰 {i+1} @ {lamda[int(peak)]:.3f} nm 拟合失败: {e}")
                continue

        # 处理单峰图显示
        if holdon and figs:
            lam0_list = [r['lambda0'] for r in fit_results]
            selected = _sample_figs_by_wavelength(figs, lam0_list, max_holdon)
            for fig in figs:
                if fig not in selected:
                    plt.close(fig)
        elif not holdon and figs:
            for fig in figs:
                plt.close(fig)
            figs.clear()

        if len(fit_results) == 0:
            raise ValueError("未获得有效拟合结果，请检查谱线质量或峰值数量。")

        self.fit_results = fit_results
        return self._plot_q_summary(fit_results, peaks, figinsert, fontsize=fontsize)

    def _plot_single_peak_fit(self, lambda_slice, T_slice_db, result, fontsize=10):
        """绘制单峰拟合图。"""
        T_slice_linear = 10 ** (T_slice_db / 10)
        T0, ER, lambda0, gamma_half, slope = result['params']
        gamma = result['gamma']
        Ql = result['Ql']
        Qi = result['Qi']
        r_squared = result['r_squared']

        fig, ax = plt.subplots(figsize=(8, 5))
        baseline_slice = np.maximum(T0 + slope * (lambda_slice - lambda0), 1e-12)
        T_norm = T_slice_linear / baseline_slice

        ax.plot(lambda_slice, T_norm, 'o', markersize=3.5, alpha=0.55,
                color=_JC['curve'], markeredgewidth=0, label='Data')

        lambda_dense = np.linspace(lambda_slice[0], lambda_slice[-1], 500)
        T_fit_dense_raw = lorentzian_with_slope(lambda_dense, *result['params'])
        baseline_dense = np.maximum(T0 + slope * (lambda_dense - lambda0), 1e-12)
        T_fit_dense = T_fit_dense_raw / baseline_dense
        ax.plot(lambda_dense, T_fit_dense, '-', linewidth=1.6,
                color=_JC['fit'], label='Lorentz Fit')

        ax.axvline(lambda0, color=_JC['center'], linestyle=':',
                    linewidth=1.0, alpha=0.85, label='Center')
        ax.axvline(lambda0 - gamma / 2, color=_JC['bw'], linestyle='--',
                    linewidth=0.7, alpha=0.7)
        ax.axvline(lambda0 + gamma / 2, color=_JC['bw'], linestyle='--',
                    linewidth=0.7, alpha=0.7, label='3dB BW')

        info_text = (
            f'Center: {lambda0:.4f} nm\n'
            f'3dB BW: {gamma*1000:.3f} pm\n'
            f'Ql: {Ql:.0f}\n'
            f'Qi: {Qi:.0f}\n'
            f'Qi/Ql: {Qi/Ql:.2f}\n'
            f'ER: {ER:.3f}\n'
            f'R2: {r_squared:.4f}'
        )
        ax.text(
            0.97, 0.95, info_text, transform=ax.transAxes, fontsize=max(6, fontsize - 2),
            verticalalignment='top', horizontalalignment='right',
            fontfamily=_FONT, color=_JC['curve'], linespacing=1.4,
            bbox=dict(boxstyle='round,pad=0.45', facecolor='white',
                      edgecolor='#D0D0D0', linewidth=0.6, alpha=0.92),
        )
        _apply_journal_style(ax, xlabel='Wavelength (nm)', ylabel='Normalized Transmission',
                             title=f'Peak @ {lambda0:.3f} nm  Lorentz Fit (R2={r_squared:.4f})',
                             fontsize=fontsize)
        ax.legend(fontsize=max(6, fontsize - 2), frameon=False, loc='upper left')
        ax.set_ylim((0, 1.1))
        fig.tight_layout()
        return fig

    def _plot_q_summary(self, fit_results, peaks, figinsert, fontsize=10):
        """绘制 Q 因子汇总图。"""
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
            np.array([r['Ql'] for r in fit_results if np.isfinite(r['Ql']) and r['Ql'] > 0])
        )
        Qi_filtered = sigma_filter(
            np.array([r['Qi'] for r in fit_results if np.isfinite(r['Qi']) and r['Qi'] > 0])
        )

        kappa2_all = np.array(
            [r['kappa2'] for r in fit_results if np.isfinite(r['kappa2']) and 0 < r['kappa2'] < 1]
        )
        lambda0_all = np.array(
            [r['lambda0'] for r in fit_results if np.isfinite(r['kappa2']) and 0 < r['kappa2'] < 1]
        )
        kappa2_filtered = sigma_filter(kappa2_all)
        if kappa2_filtered.size > 0:
            kappa_mask = np.isin(kappa2_all, kappa2_filtered)
            lambda0_filtered = lambda0_all[kappa_mask]
        else:
            lambda0_filtered = np.array([])

        if figinsert is None:
            fig, axes = _plt_ready(3, 3, figsize=(8, 10))
        else:
            fig = figinsert
            axes = fig.subplots(1, 3)
            axes = axes.ravel() if isinstance(axes, np.ndarray) else [axes]

        ax1, ax2, ax3 = axes[:3]

        ax1.hist(Ql_filtered, bins=20, color=_JC['Ql'], edgecolor='white',
                 linewidth=0.5, alpha=0.9)
        _apply_journal_style(ax1, xlabel='$Q_L$', ylabel='Count',
                             title='Loaded Q-factor Distribution', fontsize=fontsize)

        ax2.hist(Qi_filtered, bins=20, color=_JC['Qi'], edgecolor='white',
                 linewidth=0.5, alpha=0.9)
        _apply_journal_style(ax2, xlabel='$Q_i$', ylabel='Count',
                             title='Intrinsic Q-factor Distribution', fontsize=fontsize)

        # 耦合系数 κ²（左轴，蓝）与透射谱（右轴，灰）共用同一 x 轴。
        # 两条 y 轴分别着色以与对应曲线匹配，避免黑色叠加看不清。
        tick_fs = max(6, fontsize - 2)

        # 右轴：透射谱作为背景参考，浅灰细线 + 红色谐振峰标记
        ax3_1 = ax3.twinx()
        ax3_1.plot(self.lamda, self.T, color=_JC['trans'], linewidth=0.7,
                   alpha=0.45, zorder=1)
        ax3_1.plot(self.lambda0, self.T[peaks], 'o', color=_JC['peak'],
                   markersize=3.5, markeredgecolor='white', markeredgewidth=0.4,
                   zorder=2, label='Resonance')
        ax3_1.set_ylabel('Transmission (dB)', fontsize=fontsize, fontfamily=_FONT,
                         color=_JC['trans'])
        ax3_1.tick_params(axis='y', labelsize=tick_fs, direction='out', length=3.5,
                          width=0.8, colors=_JC['trans'])
        for lbl in ax3_1.get_yticklabels():
            lbl.set_fontfamily(_FONT)
        ax3_1.spines['right'].set_color(_JC['trans'])
        ax3_1.spines['right'].set_linewidth(0.8)
        ax3_1.spines['top'].set_visible(False)

        # 左轴：耦合系数 κ²，蓝色实线 + 空心圆标记（主数据，置于前景）
        ax3.plot(lambda0_filtered, kappa2_filtered, '--', color=_JC['kappa'],
                 linewidth=1.0, marker='o', markersize=4.5,
                 markerfacecolor='white', markeredgecolor=_JC['kappa'],
                 markeredgewidth=1.1, zorder=3, label='$\\kappa^2$')
        _apply_journal_style(ax3, xlabel='Resonance Wavelength (nm)',
                             ylabel='Coupling Coefficient ($\\kappa^2$)',
                             title='Coupling Coefficient', fontsize=fontsize,
                             open_spines=False)
        ax3.set_zorder(ax3_1.get_zorder() + 1)   # κ² 在透射谱之上
        ax3.patch.set_visible(False)             # 让下层透射谱透出
        ax3.tick_params(axis='y', colors=_JC['kappa'])
        ax3.yaxis.label.set_color(_JC['kappa'])
        ax3.spines['left'].set_color(_JC['kappa'])
        ax3.spines['top'].set_visible(False)

        # 合并两轴图例（蓝 κ² 与红 谐振峰）
        h1, l1 = ax3.get_legend_handles_labels()
        h2, l2 = ax3_1.get_legend_handles_labels()
        ax3.legend(h1 + h2, l1 + l2, fontsize=tick_fs, frameon=False,
                   loc='upper right')

        fig.tight_layout()
        fig.canvas.draw_idle()
        return fig

    def plot_lambda(self, range_nm=None, figinsert=None):
        """横轴为波长，绘制透射谱。"""
        if self.lamda is None:
            print("Wavelength data is not available.")
            return
        grid = self.get_ring_grid(range_nm=range_nm, extrapolate='edge')
        lamda, T = grid['lam'], grid['T']
        if T is None:
            print("No data to plot.")
            return
        if figinsert is None:
            fig, axes = _plt_ready(1, 1, figsize=(8, 5))
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
        """横轴为频率，绘制透射谱。"""
        if self.lamda is None:
            print("Frequency data is not available.")
            return
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
            fig, axes = _plt_ready(1, 1, figsize=(8, 5))
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
