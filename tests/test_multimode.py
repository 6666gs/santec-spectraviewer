import numpy as np


def _lorentzian_comb_db(lam, centers, gamma_half, er=0.7):
    """在给定波长网格上叠加若干洛伦兹谷，返回 dB 透射。"""
    t_lin = np.ones_like(lam)
    for c0 in centers:
        t_lin *= (1 - er / (1 + ((lam - c0) / gamma_half) ** 2))
    return 10 * np.log10(np.clip(t_lin, 1e-9, None))


def test_detect_resonances_counts_dips():
    from analysis.multimode import detect_resonances
    lam = np.arange(1500, 1600, 0.002)
    centers = np.arange(1505, 1596, 10.0)  # 10 个谷
    t_db = _lorentzian_comb_db(lam, centers, gamma_half=0.02)
    lam_g, t_g, idx = detect_resonances(lam, t_db)
    assert idx.size == len(centers)
    found = np.sort(lam_g[idx])
    assert np.allclose(found, centers, atol=0.05)


def test_separate_two_interleaved_combs():
    from analysis.multimode import separate_modes
    # 两把 FSR 明显不同（2.0 与 2.4 THz，比值 1.2，接近真实横模差异）的交错梳
    f1 = 190.0 + np.arange(10) * 2.0
    f2 = 190.9 + np.arange(8) * 2.4
    freqs = np.concatenate([f1, f2])
    rng = np.random.default_rng(0)
    freqs = freqs + rng.normal(0, 0.002, freqs.size)  # 小抖动
    fams, unassigned = separate_modes(freqs)
    assert len(fams) == 2
    sizes = sorted(len(f) for f in fams)
    assert sizes == [8, 10]


def test_separate_single_mode():
    from analysis.multimode import separate_modes
    freqs = 190.0 + np.arange(15) * 0.9
    fams, unassigned = separate_modes(freqs)
    assert len(fams) == 1 and len(fams[0]) == 15


def test_analyze_recovers_two_modes_q():
    from analysis.multimode import analyze_multimode
    lam = np.arange(1500, 1600, 0.002)
    c1 = np.arange(1504, 1596, 9.0)    # 模式1 FSR≈9nm, ER=0.7
    c2 = np.arange(1506, 1596, 13.0)   # 模式2 FSR≈13nm, ER=0.5
    gamma_half = 0.03
    ql_target = 1550.0 / (2 * gamma_half)   # Ql = λ0 / γ_full ≈ 25833
    t_lin = np.ones_like(lam)
    for c0 in c1:
        t_lin *= (1 - 0.7 / (1 + ((lam - c0) / gamma_half) ** 2))
    for c0 in c2:
        t_lin *= (1 - 0.5 / (1 + ((lam - c0) / gamma_half) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    res = analyze_multimode(lam, t_db, source_name='syn', min_r2=0.8)
    assert len(res.families) == 2
    qls = np.array([fit.ql for fit in res.fits])
    assert qls.size >= 10
    assert 0.75 * ql_target < np.median(qls) < 1.25 * ql_target  # 真实 Q 恢复
    labels = sorted({fit.mode for fit in res.fits})
    assert labels[0] == 'Mode 1'  # FSR 升序编号


def test_analyze_single_mode_smoke():
    from analysis.multimode import analyze_multimode
    lam = np.arange(1500, 1600, 0.002)
    t_lin = np.ones_like(lam)
    for c0 in np.arange(1505, 1596, 8.0):
        t_lin *= (1 - 0.6 / (1 + ((lam - c0) / 0.025) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    res = analyze_multimode(lam, t_db, source_name='one', min_r2=0.8)
    assert len(res.families) == 1
    assert len(res.fits) >= 8
