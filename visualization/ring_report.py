# visualization/ring_report.py — 单文件多模式 Q 报告图
"""生成着色谱 + 各模式 Qi/Ql 分布 + 小结表的综合图。仅 matplotlib。"""

import numpy as np
import matplotlib.pyplot as plt

from analysis.multimode import stats_fits, DEFAULT_MAX_QI_QL

# 兼容中文注记：优先各平台常见 CJK 字体，回退 DejaVu
plt.rcParams['font.sans-serif'] = [
    'Microsoft YaHei', 'SimHei', 'PingFang SC', 'Heiti SC', 'STHeiti',
    'Arial Unicode MS', 'WenQuanYi Zen Hei', 'DejaVu Sans',
]
plt.rcParams['axes.unicode_minus'] = False

# 各模式定性配色
_MODE_COLORS = ['#c0392b', '#2c3e50', '#27ae60', '#8e44ad', '#d68910', '#16a085', '#2980b9']


def _style(ax, xlabel='', ylabel='', title=''):
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=11, fontweight='bold')
    ax.tick_params(axis='both', which='major', labelsize=8, direction='in', top=True, right=True)
    for s in ax.spines.values():
        s.set_linewidth(0.8)
    ax.grid(False)


def _sigma_filter(values, k=4.0):
    a = np.asarray(list(values), dtype=float)
    a = a[np.isfinite(a) & (a > 0)]
    if a.size <= 2:
        return a
    m, s = float(np.mean(a)), float(np.std(a))
    return a if s == 0 else a[np.abs(a - m) < k * s]


def _dist_axis(ax, families, fits, attr, xlabel):
    drew = False
    for fam, color in zip(families, _MODE_COLORS):
        vals = _sigma_filter(getattr(f, attr) for f in fits if f.mode == fam.label)
        if vals.size == 0:
            continue
        drew = True
        if vals.size >= 8:
            bins = min(20, max(5, vals.size // 2))
            ax.hist(vals, bins=bins, color=color, alpha=0.55,
                    edgecolor='white', linewidth=0.5, label=fam.label)
        else:
            ax.plot(vals, np.zeros_like(vals), 'o', color=color, markersize=6,
                    linestyle='none', alpha=0.7, label=fam.label)
    _style(ax, xlabel=xlabel, ylabel='Count')
    if drew:
        ax.legend(fontsize=7, frameon=False)


def plot_multimode_report(result, *, min_r2=0.9, max_qi_ql=DEFAULT_MAX_QI_QL):
    """单文件多模式 Q 综合报告图。返回 matplotlib Figure。

    统计（分布图与小结表）仅计入 Qi/Ql <= max_qi_ql 的峰；CSV 仍含全部数据。
    """
    sfits = stats_fits(result.fits, max_qi_ql)  # 统计用子集（剔除高 Qi/Ql）
    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(2, 3)
    ax_spec = fig.add_subplot(gs[0, :])
    ax_ql = fig.add_subplot(gs[1, 0])
    ax_qi = fig.add_subplot(gs[1, 1])
    ax_tbl = fig.add_subplot(gs[1, 2])
    ax_tbl.axis('off')

    # ── 着色谱 ──
    ax_spec.plot(result.lam, result.t_db, color='#000000', linewidth=0.7)
    for fam, color in zip(result.families, _MODE_COLORS):
        idx = np.asarray(fam.peak_indices, dtype=int)
        if idx.size == 0:
            continue
        ax_spec.plot(result.lam[idx], result.t_db[idx], 'v', color=color, markersize=6,
                     linestyle='none',
                     label=f'{fam.label} (FSR={fam.fsr_nm:.2f} nm, N={idx.size})')
    if result.unassigned_idx.size:
        u = np.asarray(result.unassigned_idx, dtype=int)
        ax_spec.plot(result.lam[u], result.t_db[u], 'x', color='#999999',
                     markersize=5, linestyle='none', label='unassigned')
    _style(ax_spec, xlabel='Wavelength (nm)', ylabel='Transmission (dB)',
           title=f'{result.source_name} — resonances by mode')
    if result.families or result.unassigned_idx.size:
        ax_spec.legend(fontsize=7, frameon=False, ncol=2)

    # ── Ql / Qi 分布（仅统计 Qi/Ql <= 阈值 的峰）──
    _dist_axis(ax_ql, result.families, sfits, 'ql', r'$Q_L$')
    _dist_axis(ax_qi, result.families, sfits, 'qi', r'$Q_i$')

    # ── 小结表 ──
    header = ['Mode', 'FSR(nm)', 'N', 'Ql(med)', 'Qi(med)']
    body = []
    for fam in result.families:
        ql = _sigma_filter(f.ql for f in sfits if f.mode == fam.label)
        qi = _sigma_filter(f.qi for f in sfits if f.mode == fam.label)
        body.append([
            fam.label, f'{fam.fsr_nm:.2f}', str(int(ql.size)),
            f'{np.median(ql):.2e}' if ql.size else '—',
            f'{np.median(qi):.2e}' if qi.size else '—',
        ])
    if not body:
        body = [['—', '—', '0', '—', '—']]
    tbl = ax_tbl.table(cellText=body, colLabels=header, loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.4)

    # ── 统计口径注记（CSV 仍含全部数据）──
    n_excluded = len(result.fits) - len(sfits)
    fig.text(0.5, 0.008,
             f'统计仅计入 Qi/Ql ≤ {max_qi_ql:g} 的峰；Qi/Ql > {max_qi_ql:g} 不纳入统计'
             f'（本次剔除 {n_excluded} 个）。CSV 输出仍含全部数据。',
             ha='center', va='bottom', fontsize=9, color='#c0392b')
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig
