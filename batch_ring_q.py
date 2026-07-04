#!/usr/bin/env python
# batch_ring_q.py — 批量微环直通端 Q 分析（多 FSR 自动分离）
"""批量分析微环直通端透射谱，自动分离多 FSR 模式并逐文件输出 Q 统计图与明细 CSV。

用法:
    python batch_ring_q.py <数据目录> [--out 目录] [选项]

输入支持: 项目定义的 loss / raw（raw 需 --reference），或简单两列（波长, 损耗 dB）。
每个文件按其文件名输出 <stem>_Qdist.png 与 <stem>_results.csv。
"""

import argparse
import csv
import glob
import math
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # 批处理无界面渲染
import matplotlib.pyplot as plt
import numpy as np

from core.io import load_spectrum
from analysis.multimode import analyze_multimode, stats_fits, qi_ql_ratio, DEFAULT_MAX_QI_QL
from visualization.ring_report import plot_multimode_report

CSV_FIELDS = ['mode_id', 'fsr_nm', 'lambda0_nm', 'ql', 'qi', 'qi_ql',
              'er_db', 'gamma_pm', 'r_squared']


def _er_db(er: float) -> float:
    """线性消光比 → 谐振谷深度 (dB, 正值)。"""
    return -10.0 * math.log10(max(1.0 - er, 1e-6))


def _write_csv(path, result):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for fit in result.fits:
            w.writerow({
                'mode_id': fit.mode, 'fsr_nm': f'{fit.fsr_nm:.4f}',
                'lambda0_nm': f'{fit.lambda0_nm:.5f}', 'ql': f'{fit.ql:.6g}',
                'qi': f'{fit.qi:.6g}', 'qi_ql': f'{qi_ql_ratio(fit):.3f}',
                'er_db': f'{_er_db(fit.er):.3f}',
                'gamma_pm': f'{fit.gamma_pm:.4f}', 'r_squared': f'{fit.r_squared:.5f}',
            })


def _log_result(name, meta, result, max_qi_ql=DEFAULT_MAX_QI_QL):
    n_dips = sum(len(f.peak_indices) for f in result.families) + result.unassigned_idx.size
    sfits = stats_fits(result.fits, max_qi_ql)  # 统计口径与出图一致
    print(f"[{name}] type={meta.get('data_type')}, ch={meta.get('channel') or '-'}, 谷={n_dips}")
    print(f"  识别到 {len(result.families)} 个模式（统计仅计入 Qi/Ql ≤ {max_qi_ql:g}）:")
    for fam in result.families:
        fits = [f for f in sfits if f.mode == fam.label]
        ql = np.median([f.ql for f in fits]) if fits else float('nan')
        qi = np.median([f.qi for f in fits]) if fits else float('nan')
        print(f"    {fam.label}: FSR={fam.fsr_nm:.2f} nm, N={len(fam.peak_indices)}, "
              f"统计峰数={len(fits)}, Ql(中位)={ql:.3g}, Qi(中位)={qi:.3g}")
    n_excluded = len(result.fits) - len(sfits)
    if n_excluded:
        print(f"  Qi/Ql > {max_qi_ql:g} 剔除出统计: {n_excluded} 个（CSV 仍保留）")
    if result.unassigned_idx.size:
        print(f"  unassigned: {result.unassigned_idx.size}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="批量微环直通端 Q 分析（多 FSR 自动分离）")
    ap.add_argument('input_dir', help='包含 CSV 数据的目录')
    ap.add_argument('--out', default=None, help='输出目录（默认 <input_dir>/ring_q_results）')
    ap.add_argument('--type', default='auto', choices=['auto', 'loss', 'raw'])
    ap.add_argument('--reference', default=None, help='raw 模式的参考文件路径')
    ap.add_argument('--pattern', default='*.csv', help='文件名匹配（默认 *.csv）')
    ap.add_argument('--channel', default=None, help='指定通道（默认第一通道）')
    ap.add_argument('--min-r2', type=float, default=0.9, help='拟合 R² 阈值（默认 0.9）')
    ap.add_argument('--max-qi-ql', type=float, default=DEFAULT_MAX_QI_QL,
                    help='统计 Qi/Ql 上限；高于此值的峰不纳入统计（默认 20，CSV 仍含全部）')
    ap.add_argument('--max-modes', type=int, default=None, help='模式数上限（默认不限）')
    ap.add_argument('--prominence', type=float, default=None, help='寻峰最小突出度（默认自动）')
    ap.add_argument('--distance', type=int, default=None, help='寻峰最小间距，点数（默认自动）')
    ap.add_argument('--height', type=float, default=None, help='寻峰谷深阈值 dB（默认不限）')
    args = ap.parse_args(argv)

    out = args.out or os.path.join(args.input_dir, 'ring_q_results')
    os.makedirs(out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.input_dir, args.pattern)))
    if not files:
        print(f"未找到匹配文件: {os.path.join(args.input_dir, args.pattern)}")
        return 1

    ok, fail = 0, 0
    for fp in files:
        stem = Path(fp).stem
        try:
            lam, loss_db, meta = load_spectrum(
                fp, data_type=args.type, reference_path=args.reference, channel=args.channel)
            detect_kw = {}
            if args.prominence is not None:
                detect_kw['prominence'] = args.prominence
            if args.distance is not None:
                detect_kw['min_distance'] = args.distance
            if args.height is not None:
                detect_kw['height'] = args.height
            result = analyze_multimode(
                lam, loss_db, source_name=stem, min_r2=args.min_r2,
                max_modes=args.max_modes, **detect_kw)
            fig = plot_multimode_report(result, min_r2=args.min_r2, max_qi_ql=args.max_qi_ql)
            fig.savefig(os.path.join(out, f'{stem}_Qdist.png'), dpi=300, bbox_inches='tight')
            plt.close(fig)
            _write_csv(os.path.join(out, f'{stem}_results.csv'), result)
            _log_result(stem, meta, result, max_qi_ql=args.max_qi_ql)
            ok += 1
        except Exception as e:
            print(f"错误: {stem}: {e}")
            fail += 1

    print(f"\n完成: 成功 {ok}, 失败 {fail}, 输出目录 {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
