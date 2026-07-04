# analysis/multimode.py — 多模式(多 FSR)微环 Q 分析
"""频域贪心梳状提取分离多模式，逐峰洛伦兹拟合 Q。纯 numpy/scipy，无 PyQt5。"""

from dataclasses import dataclass
import numpy as np
from scipy.constants import c
from scipy.signal import find_peaks

from core.grid import create_uniform_grid, sanitize_xy, interp_on_grid
from .fitting import fit_lorentzian_peak

NM_TO_M = 1e-9
THZ = 1e12

# ── 频域分离常量 ──
K_NEIGH = 6        # 候选 FSR 播种时考察的近邻数
MATCH_TOL = 0.14   # 链延伸匹配容差（FSR 的比例）；收紧以避免跨族误吸收
MIN_FAMILY = 3     # 成族最小峰数
MAX_SKIP = 1       # 延伸时允许跳过的缺齿数


@dataclass(frozen=True)
class ModeFamily:
    """一个模式族（同一 FSR 的谐振梳）。"""
    label: str
    peak_indices: np.ndarray   # 指向统一网格的整型索引，已按波长升序
    fsr_nm: float
    fsr_thz: float


@dataclass(frozen=True)
class ResonanceFit:
    """单个谐振峰的拟合结果。"""
    mode: str
    lambda0_nm: float
    ql: float
    qi: float
    er: float          # 消光比（线性 0-1）
    gamma_pm: float    # 3dB 全宽 (pm)
    r_squared: float
    fsr_nm: float      # 所属族本地 FSR


@dataclass(frozen=True)
class MultiModeResult:
    """单文件多模式分析结果。"""
    source_name: str
    lam: np.ndarray
    t_db: np.ndarray
    families: tuple
    fits: tuple
    unassigned_idx: np.ndarray


def _infer_step_nm(lam: np.ndarray) -> float:
    d = np.diff(lam)
    d = d[d > 0]
    return float(np.median(d)) if d.size else 1e-3


def detect_resonances(lam, t_db, *, prominence=None, min_distance=None, height=None):
    """检测直通端谐振谷（信号取 -T）。返回 (lam_grid, t_grid, dip_idx)。"""
    lam, t_db = sanitize_xy(np.asarray(lam, float), np.asarray(t_db, float))
    if lam.size < 5:
        raise ValueError("数据点不足，无法检测谐振。")
    step = _infer_step_nm(lam)
    grid = create_uniform_grid(float(lam.min()), float(lam.max()), step, endpoint=True)
    t_grid = interp_on_grid(lam, t_db, grid, mode='edge')
    detect = -t_grid
    if prominence is None:
        prominence = max(0.5, float(np.ptp(detect)) * 0.05)
    if not min_distance or min_distance <= 0:
        min_distance = max(1, int(len(grid) / 500))
    kw = dict(distance=int(min_distance), prominence=float(prominence))
    if height is not None:
        kw['height'] = float(height)
    dip_idx, _ = find_peaks(detect, **kw)
    return grid, t_grid, dip_idx


def _candidate_fsrs(freqs_sorted: np.ndarray, k_neigh: int, rel_tol: float = 0.05) -> np.ndarray:
    """由多近邻两两间距的贪心聚类给出候选 FSR（按支持度降序）。

    不依赖带宽/直方图边界：把排序后的间距按相对容差合并为簇，簇均值即候选
    FSR，簇内计数即支持度。基频与各次谐波（2×FSR…）都会作为独立候选出现，
    真正的族由后续贪心链长度胜出。
    """
    n = freqs_sorted.size
    if n < 2:
        return np.array([])
    diffs = []
    for i in range(n):
        for j in range(i + 1, min(i + 1 + k_neigh, n)):
            diffs.append(freqs_sorted[j] - freqs_sorted[i])
    diffs = np.sort(np.asarray(diffs, float))
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return np.array([])
    clusters: list = []  # (mean, count)
    cur = [float(diffs[0])]
    for v in diffs[1:]:
        m = float(np.mean(cur))
        if m > 0 and abs(v - m) / m <= rel_tol:
            cur.append(float(v))
        else:
            clusters.append((float(np.mean(cur)), len(cur)))
            cur = [float(v)]
    clusters.append((float(np.mean(cur)), len(cur)))
    clusters.sort(key=lambda cc: -cc[1])
    return np.asarray([cc[0] for cc in clusters])


def _extend_chain(freqs, used, start, fsr0, match_tol, max_skip):
    """从 start 向频率增大方向延伸一条梳链，返回下标列表（升序）。

    freqs 为升序数组。容差按 FSR 固定比例（不随跳齿放大），使错误 FSR 的链
    尽早断裂、真链胜出；本地 FSR 用 EMA 跟踪缓慢色散漂移。
    """
    chain = [int(start)]
    inset = {int(start)}
    fsr_local = float(fsr0)
    cur = int(start)
    n = freqs.size
    while True:
        matched = None
        for mult in range(1, max_skip + 2):
            target = freqs[cur] + mult * fsr_local
            tol = match_tol * fsr_local
            best_j, best_d = -1, np.inf
            for j in range(cur + 1, n):
                if used[j] or j in inset:
                    continue
                d = abs(freqs[j] - target)
                if d < best_d:
                    best_d, best_j = d, j
                if freqs[j] - target > tol:
                    break
            if best_j >= 0 and best_d <= tol:
                matched = (best_j, mult)
                break
        if matched is None:
            break
        jbest, mult = matched
        if mult == 1:
            fsr_local = 0.7 * fsr_local + 0.3 * float(freqs[jbest] - freqs[cur])
        chain.append(jbest)
        inset.add(jbest)
        cur = jbest
    return sorted(chain)


def separate_modes(dip_freqs, *, k_neigh=K_NEIGH, match_tol=MATCH_TOL,
                   min_family=MIN_FAMILY, max_skip=MAX_SKIP, max_modes=None):
    """将谐振频率按 FSR 分成若干模式族。

    返回 (families_positions, unassigned)，均为 dip_freqs 的下标数组。
    """
    freqs_in = np.asarray(dip_freqs, float)
    order = np.argsort(freqs_in)
    f = freqs_in[order]
    used = np.zeros(f.size, dtype=bool)
    families: list = []
    while True:
        if max_modes is not None and len(families) >= max_modes:
            break
        avail = np.where(~used)[0]
        if avail.size < min_family:
            break
        cands = _candidate_fsrs(f[avail], k_neigh)
        if cands.size == 0:
            break
        best: list = []
        for fsr0 in cands:
            for start in avail:
                if used[start]:
                    continue
                chain = _extend_chain(f, used, start, fsr0, match_tol, max_skip)
                if len(chain) > len(best):
                    best = chain
        if len(best) < min_family:
            break
        for k in best:
            used[k] = True
        families.append(np.array(best, dtype=int))
    fam_orig = [np.sort(order[fam]) for fam in families]
    unassigned = np.sort(order[np.where(~used)[0]])
    return fam_orig, unassigned


def _neighbor_window(lam_grid, all_sorted, gpos, min_points=40):
    """按全局最近谐振谷的中点取拟合窗口，隔离相邻（含他族）谷。"""
    n = len(lam_grid)
    m = len(all_sorted)
    p = int(all_sorted[gpos])
    edge = (lam_grid[min(1, n - 1)] - lam_grid[0]) * 20 if n > 1 else 0.01
    if gpos == 0:
        if m > 1:
            right_mid = 0.5 * (lam_grid[p] + lam_grid[int(all_sorted[1])])
            left_est = lam_grid[p] - (right_mid - lam_grid[p])
        else:
            left_est = lam_grid[p] - edge
        left_idx = int(np.searchsorted(lam_grid, left_est, side='left'))
    else:
        left_mid = 0.5 * (lam_grid[int(all_sorted[gpos - 1])] + lam_grid[p])
        left_idx = int(np.searchsorted(lam_grid, left_mid, side='left'))
    if gpos == m - 1:
        if m > 1:
            left_mid = 0.5 * (lam_grid[int(all_sorted[gpos - 1])] + lam_grid[p])
            right_est = lam_grid[p] + (lam_grid[p] - left_mid)
        else:
            right_est = lam_grid[p] + edge
        right_idx = int(np.searchsorted(lam_grid, right_est, side='right')) - 1
    else:
        right_mid = 0.5 * (lam_grid[p] + lam_grid[int(all_sorted[gpos + 1])])
        right_idx = int(np.searchsorted(lam_grid, right_mid, side='right')) - 1
    left_idx = max(0, min(left_idx, p - 1))
    right_idx = min(n - 1, max(right_idx, p + 1))
    if (right_idx - left_idx + 1) < min_points:
        expand = (min_points - (right_idx - left_idx + 1)) // 2 + 1
        left_idx = max(0, left_idx - expand)
        right_idx = min(n - 1, right_idx + expand)
    return left_idx, right_idx


def analyze_multimode(lam, t_db, *, source_name='', min_r2=0.9, max_modes=None, **detect_kw):
    """完整多模式分析：检测→分离→逐峰拟合。返回 MultiModeResult。"""
    lam_g, t_g, dip_idx = detect_resonances(lam, t_db, **detect_kw)
    if dip_idx.size < MIN_FAMILY:
        return MultiModeResult(source_name, lam_g, t_g, tuple(), tuple(),
                               np.asarray(dip_idx, dtype=int))

    dip_lam = lam_g[dip_idx]
    dip_freq = c / (dip_lam * NM_TO_M) / THZ
    fam_pos, unassigned_pos = separate_modes(dip_freq, max_modes=max_modes)

    # 按 FSR 升序整理各族
    fams_tmp = []
    for pos in fam_pos:
        members = np.sort(dip_idx[pos])
        m_lam = lam_g[members]
        fsr_nm = float(np.median(np.diff(m_lam))) if members.size > 1 else float('nan')
        m_freq = c / (m_lam * NM_TO_M) / THZ
        fsr_thz = float(np.median(np.abs(np.diff(m_freq)))) if members.size > 1 else float('nan')
        fams_tmp.append((fsr_nm, fsr_thz, members))
    fams_tmp.sort(key=lambda t: (np.inf if np.isnan(t[0]) else t[0]))

    all_sorted = np.sort(dip_idx)  # 全局窗口用
    families = []
    fits = []
    for k, (fsr_nm, fsr_thz, members) in enumerate(fams_tmp, start=1):
        label = f'Mode {k}'
        families.append(ModeFamily(label, members, fsr_nm, fsr_thz))
        for p in members:
            gpos = int(np.searchsorted(all_sorted, p))
            li, ri = _neighbor_window(lam_g, all_sorted, gpos)
            lam_s = lam_g[li:ri + 1]
            t_s = t_g[li:ri + 1]
            try:
                r = fit_lorentzian_peak(lam_s, t_s, fsr_nm if np.isfinite(fsr_nm) else 1.0)
            except Exception:
                continue
            if not np.isfinite(r['r_squared']) or r['r_squared'] < min_r2:
                continue
            if not (np.isfinite(r['Ql']) and r['Ql'] > 0 and np.isfinite(r['Qi']) and r['Qi'] > 0):
                continue
            fits.append(ResonanceFit(
                mode=label, lambda0_nm=float(r['lambda0']), ql=float(r['Ql']),
                qi=float(r['Qi']), er=float(r['extinction']),
                gamma_pm=float(r['gamma']) * 1000.0, r_squared=float(r['r_squared']),
                fsr_nm=fsr_nm,
            ))
    unassigned_idx = (np.sort(dip_idx[unassigned_pos])
                      if unassigned_pos.size else np.array([], dtype=int))
    return MultiModeResult(source_name, lam_g, t_g, tuple(families), tuple(fits), unassigned_idx)
