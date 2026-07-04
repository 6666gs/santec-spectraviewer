import matplotlib
matplotlib.use('Agg')
import numpy as np


def _synth(lam, centers, gamma_half, er):
    t_lin = np.ones_like(lam)
    for c0 in centers:
        t_lin *= (1 - er / (1 + ((lam - c0) / gamma_half) ** 2))
    return 10 * np.log10(np.clip(t_lin, 1e-9, None))


def test_report_returns_figure(tmp_path):
    from analysis.multimode import analyze_multimode
    from visualization.ring_report import plot_multimode_report
    lam = np.arange(1500, 1600, 0.002)
    t_db = _synth(lam, np.arange(1504, 1596, 9.0), 0.03, 0.7)
    res = analyze_multimode(lam, t_db, source_name='syn', min_r2=0.8)
    fig = plot_multimode_report(res)
    out = tmp_path / "r.png"
    fig.savefig(str(out), dpi=100)
    assert out.exists() and out.stat().st_size > 0


def test_report_two_modes(tmp_path):
    from analysis.multimode import analyze_multimode
    from visualization.ring_report import plot_multimode_report
    lam = np.arange(1500, 1600, 0.002)
    t_lin = np.ones_like(lam)
    for c0 in np.arange(1504, 1596, 9.0):
        t_lin *= (1 - 0.7 / (1 + ((lam - c0) / 0.03) ** 2))
    for c0 in np.arange(1506, 1596, 13.0):
        t_lin *= (1 - 0.5 / (1 + ((lam - c0) / 0.03) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    res = analyze_multimode(lam, t_db, source_name='two', min_r2=0.8)
    fig = plot_multimode_report(res)
    out = tmp_path / "two.png"
    fig.savefig(str(out), dpi=100)
    assert out.exists() and out.stat().st_size > 0
