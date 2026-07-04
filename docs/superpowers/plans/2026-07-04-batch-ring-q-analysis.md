# 批量微环 Q 分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增独立 CLI 程序 `batch_ring_q.py`，批量分析微环直通端透射谱，自动分离多 FSR 模式并逐文件输出各模式 Q 统计图与明细 CSV。

**Architecture:** 频域贪心梳状提取分离模式（`analysis/multimode.py`，纯 numpy/scipy），复用 `analysis/fitting.py` 逐峰洛伦兹拟合，`visualization/ring_report.py` 出综合图，`core/io.py` 增自动表头探测。单文件=单微环，逐个处理，无跨文件汇总。

**Tech Stack:** Python, numpy, scipy, pandas, matplotlib, pytest（新增开发依赖）。

## Global Constraints

- `core/` 与 `analysis/` 禁止导入 PyQt5（分层规则）。
- 不可变优先：结果用 `@dataclass(frozen=True)`。
- 只处理直通端（谐振为谷，检测信号取 `-T`）。
- 期刊风格出图：白底、刻度向内、无网格；多模式用定性配色区分。
- 拟合 R² 阈值默认 0.9；Ql=λ₀/γ(full)、Qi=Ql/√(1-ER)（沿用 `fit_lorentzian_peak`）。
- `er_db = -10*log10(max(1-er, 1e-6))`（正值谷深）。
- 频域分离常量：`K_NEIGH=6`、`MATCH_TOL=0.25`、`MIN_FAMILY=3`、`MAX_SKIP=1`。

---

### Task 1: `core/io.py` — 自动表头探测 + `load_spectrum`

**Files:**
- Modify: `core/io.py`（追加函数，不改现有）
- Test: `tests/test_io_header.py`

**Interfaces:**
- Produces:
  - `detect_header_rows(path, max_scan=300) -> int`
  - `load_spectrum(path, data_type='auto', reference_path=None, channel=None) -> tuple[np.ndarray, np.ndarray, dict]` 返回 `(lam_nm, loss_db, meta)`；`meta` 含 `data_type/channel/ranges/skiprows`。

- [ ] **Step 1: 写失败测试** `tests/test_io_header.py`

```python
import numpy as np
from pathlib import Path
from core.io import detect_header_rows, load_spectrum

SANTEC = """Instrument,MPM
Start,1500
Stop,1600
Step,0.001
Source power,0
line5,x
line6,x
line7,x
line8,x
line9,x
line10,x
line11,x
line12,x
Wavelength,IL[CH1]
1500.000,-20.10
1500.001,-20.20
1500.002,-20.30
1500.003,-20.40
"""

TWO_COL = "1500.000,-20.10\n1500.001,-20.20\n1500.002,-20.30\n1500.003,-20.40\n"

def test_detect_header_santec(tmp_path):
    p = tmp_path / "a_loss.csv"; p.write_text(SANTEC)
    assert detect_header_rows(str(p)) == 13  # 列头行(Wavelength,IL[CH1]) 的索引

def test_detect_header_two_col(tmp_path):
    p = tmp_path / "b.csv"; p.write_text(TWO_COL)
    assert detect_header_rows(str(p)) == 0

def test_load_spectrum_two_col(tmp_path):
    p = tmp_path / "b.csv"; p.write_text(TWO_COL)
    lam, loss, meta = load_spectrum(str(p))
    assert lam.shape == loss.shape and lam.size == 4
    assert np.isclose(lam[0], 1500.0) and np.isclose(loss[0], -20.10)
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_io_header.py -v` → FAIL (ImportError)

- [ ] **Step 3: 实现** 在 `core/io.py` 末尾追加：

```python
def _io_tokens(line: str) -> list[str]:
    return [p.strip() for p in re.split(r'[,\t;]', line.rstrip('\n')) if p.strip() != '']


def _io_is_numeric_row(line: str, min_cols: int = 2) -> bool:
    toks = _io_tokens(line)
    if len(toks) < min_cols:
        return False
    for t in toks:
        try:
            float(t)
        except ValueError:
            return False
    return True


def detect_header_rows(path: str | Path, max_scan: int = 300) -> int:
    """自动探测数据前的头行数（skiprows）。

    兼容 SANTEC 多行头 + 列头，与无头简单两列文件。
    返回值语义与 read_santec_csv 的 skiprows 一致：列头行索引（若存在），
    否则首个数据行索引。
    """
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = [f.readline() for _ in range(max_scan)]
    first_data = None
    for i in range(len(lines) - 1):
        if not lines[i]:
            break
        if _io_is_numeric_row(lines[i]) and _io_is_numeric_row(lines[i + 1]):
            first_data = i
            break
    if first_data is None:
        for i, ln in enumerate(lines):
            if ln and _io_is_numeric_row(ln):
                first_data = i
                break
    if first_data is None:
        return 0
    if first_data >= 1:
        prev = lines[first_data - 1]
        if len(_io_tokens(prev)) >= 2 and not _io_is_numeric_row(prev):
            return first_data - 1
    return first_data


def load_spectrum(path, data_type='auto', reference_path=None, channel=None):
    """加载单个直通端谱，返回 (lam_nm, loss_db, meta)。"""
    skip = detect_header_rows(path)
    results = read_santec_csv(path, data_type=data_type,
                              reference_path=reference_path, skiprows=skip)
    if not results:
        raise ValueError(f"无法读取数据: {path}")
    chosen = results[0]
    if channel:
        for r in results:
            if str(r.get('channel', '')).upper() == str(channel).upper():
                chosen = r
                break
    lam = np.asarray(chosen['wavelength'], dtype=float)
    loss = np.asarray(chosen['loss'], dtype=float)
    meta = {
        'data_type': chosen['data_type'], 'channel': chosen.get('channel', ''),
        'ranges': chosen.get('ranges', []), 'skiprows': skip,
    }
    return lam, loss, meta
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_io_header.py -v` → PASS

- [ ] **Step 5: 提交** — `git add -A && git commit -m "feat: core/io 自动表头探测与 load_spectrum"`

---

### Task 2: `analysis/multimode.py` — 数据结构 + `detect_resonances`

**Files:**
- Create: `analysis/multimode.py`
- Test: `tests/test_multimode.py`

**Interfaces:**
- Produces:
  - `ModeFamily(label:str, peak_indices:np.ndarray, fsr_nm:float, fsr_thz:float)` frozen dataclass
  - `ResonanceFit(mode, lambda0_nm, ql, qi, er, gamma_pm, r_squared, fsr_nm)` frozen dataclass
  - `MultiModeResult(source_name, lam, t_db, families:tuple, fits:tuple, unassigned_idx:np.ndarray)` frozen dataclass
  - `detect_resonances(lam, t_db, *, prominence=None, min_distance=None, height=None) -> tuple[np.ndarray, np.ndarray, np.ndarray]` 返回 `(lam_grid, t_grid, dip_idx)`

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_multimode.py`）

```python
import numpy as np
from analysis.multimode import detect_resonances

def _lorentzian_comb_db(lam, centers, gamma_half, er=0.7):
    t_lin = np.ones_like(lam)
    for c0 in centers:
        t_lin *= (1 - er / (1 + ((lam - c0) / gamma_half) ** 2))
    return 10 * np.log10(np.clip(t_lin, 1e-9, None))

def test_detect_resonances_counts_dips():
    lam = np.arange(1500, 1600, 0.002)
    centers = np.arange(1505, 1596, 10.0)  # 10 个谷
    t_db = _lorentzian_comb_db(lam, centers, gamma_half=0.02)
    lam_g, t_g, idx = detect_resonances(lam, t_db)
    assert idx.size == len(centers)
    found = np.sort(lam_g[idx])
    assert np.allclose(found, centers, atol=0.05)
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_multimode.py::test_detect_resonances_counts_dips -v` → FAIL

- [ ] **Step 3: 实现** `analysis/multimode.py`（本步只加结构与 detect）

```python
# analysis/multimode.py — 多模式(多 FSR)微环 Q 分析
"""频域贪心梳状提取分离多模式，逐峰洛伦兹拟合 Q。纯 numpy/scipy。"""

from dataclasses import dataclass
import numpy as np
from scipy.constants import c
from scipy.signal import find_peaks

from core.grid import create_uniform_grid, sanitize_xy, interp_on_grid
from .fitting import fit_lorentzian_peak

NM_TO_M = 1e-9
THZ = 1e12

K_NEIGH = 6
MATCH_TOL = 0.25
MIN_FAMILY = 3
MAX_SKIP = 1


@dataclass(frozen=True)
class ModeFamily:
    label: str
    peak_indices: np.ndarray
    fsr_nm: float
    fsr_thz: float


@dataclass(frozen=True)
class ResonanceFit:
    mode: str
    lambda0_nm: float
    ql: float
    qi: float
    er: float
    gamma_pm: float
    r_squared: float
    fsr_nm: float


@dataclass(frozen=True)
class MultiModeResult:
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
    """检测直通端谐振谷。返回 (lam_grid, t_grid, dip_idx)。"""
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
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_multimode.py::test_detect_resonances_counts_dips -v` → PASS

- [ ] **Step 5: 提交** — `git add -A && git commit -m "feat: multimode 数据结构与谐振检测"`

---

### Task 3: `analysis/multimode.py` — `separate_modes`（核心分离算法）

**Files:**
- Modify: `analysis/multimode.py`
- Test: `tests/test_multimode.py`

**Interfaces:**
- Consumes: 无（纯频率数组）
- Produces: `separate_modes(dip_freqs, *, k_neigh=K_NEIGH, match_tol=MATCH_TOL, min_family=MIN_FAMILY, max_skip=MAX_SKIP, max_modes=None) -> tuple[list[np.ndarray], np.ndarray]` 返回 `(families_positions, unassigned_positions)`，位置为 `dip_freqs` 的下标。

- [ ] **Step 1: 写失败测试**（交错双梳）

```python
from analysis.multimode import separate_modes

def test_separate_two_interleaved_combs():
    # 频率域两把已知 FSR 的梳: 8 THz 与 11 THz, 交错
    f1 = 190.0 + np.arange(12) * 0.8       # FSR≈0.8 THz
    f2 = 190.3 + np.arange(9) * 1.1        # FSR≈1.1 THz
    freqs = np.concatenate([f1, f2])
    rng = np.random.default_rng(0)
    freqs = freqs + rng.normal(0, 0.002, freqs.size)  # 小抖动
    fams, unassigned = separate_modes(freqs)
    assert len(fams) == 2
    sizes = sorted(len(f) for f in fams)
    assert sizes == [9, 12]

def test_separate_single_mode():
    freqs = 190.0 + np.arange(15) * 0.9
    fams, unassigned = separate_modes(freqs)
    assert len(fams) == 1 and len(fams[0]) == 15
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_multimode.py -k separate -v` → FAIL

- [ ] **Step 3: 实现** 追加到 `analysis/multimode.py`：

```python
def _candidate_fsrs(freqs_sorted: np.ndarray, k_neigh: int) -> np.ndarray:
    """由多近邻两两间距分布给出候选 FSR（按支持度降序）。"""
    n = freqs_sorted.size
    if n < 2:
        return np.array([])
    diffs = []
    for i in range(n):
        for j in range(i + 1, min(i + 1 + k_neigh, n)):
            diffs.append(freqs_sorted[j] - freqs_sorted[i])
    diffs = np.asarray(diffs, float)
    diffs = diffs[diffs > 0]
    if diffs.size < 2:
        return np.array([np.median(diffs)]) if diffs.size else np.array([])
    lo, hi = float(diffs.min()), float(diffs.max())
    xs = np.linspace(lo, hi, 512)
    try:
        from scipy.stats import gaussian_kde
        dens = gaussian_kde(diffs, bw_method='scott')(xs)
    except Exception:
        hist, edges = np.histogram(diffs, bins=64)
        xs = 0.5 * (edges[:-1] + edges[1:])
        dens = hist.astype(float)
    pk, _ = find_peaks(dens, prominence=float(dens.max()) * 0.05)
    if pk.size == 0:
        return np.array([float(np.median(diffs))])
    cand = xs[pk][np.argsort(-dens[pk])]
    merged: list[float] = []
    for v in cand:
        if all(abs(v - m) / m > 0.05 for m in merged):
            merged.append(float(v))
    return np.asarray(merged)


def _extend_chain(freqs, used, start, fsr0, match_tol, max_skip):
    """从 start 向频率增大方向延伸一条梳链，返回下标列表（升序）。"""
    chain = [int(start)]
    fsr_local = float(fsr0)
    cur = int(start)
    n = freqs.size
    all_idx = np.arange(n)
    while True:
        found = None
        for mult in range(1, max_skip + 2):
            target = freqs[cur] + mult * fsr_local
            tol = match_tol * fsr_local * mult
            avail = all_idx[(~used) & (all_idx != cur)]
            avail = np.array([k for k in avail if k not in chain and freqs[k] > freqs[cur]])
            if avail.size == 0:
                break
            d = np.abs(freqs[avail] - target)
            jbest = int(avail[int(np.argmin(d))])
            if float(np.min(d)) <= tol:
                found = (jbest, mult)
                break
        if found is None:
            break
        jbest, mult = found
        realized = freqs[jbest] - freqs[cur]
        chain.append(jbest)
        if mult == 1:
            fsr_local = 0.5 * fsr_local + 0.5 * float(realized)
        cur = jbest
    return sorted(chain)


def separate_modes(dip_freqs, *, k_neigh=K_NEIGH, match_tol=MATCH_TOL,
                   min_family=MIN_FAMILY, max_skip=MAX_SKIP, max_modes=None):
    """将谐振频率按 FSR 分成若干模式族。返回 (families_positions, unassigned)。"""
    freqs_in = np.asarray(dip_freqs, float)
    order = np.argsort(freqs_in)
    f = freqs_in[order]
    used = np.zeros(f.size, dtype=bool)
    families: list[np.ndarray] = []
    while True:
        if max_modes is not None and len(families) >= max_modes:
            break
        avail = np.where(~used)[0]
        if avail.size < min_family:
            break
        cands = _candidate_fsrs(f[avail], k_neigh)
        if cands.size == 0:
            break
        best: list[int] = []
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
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_multimode.py -k separate -v` → PASS

- [ ] **Step 5: 提交** — `git add -A && git commit -m "feat: 频域贪心梳状多 FSR 分离算法"`

---

### Task 4: `analysis/multimode.py` — `analyze_multimode`（拟合编排）

**Files:**
- Modify: `analysis/multimode.py`
- Test: `tests/test_multimode.py`

**Interfaces:**
- Consumes: `detect_resonances`, `separate_modes`, `fit_lorentzian_peak`
- Produces: `analyze_multimode(lam, t_db, *, source_name='', min_r2=0.9, max_modes=None, **detect_kw) -> MultiModeResult`

- [ ] **Step 1: 写失败测试**（已知 Q 交错双梳，验证分族与 Q 提取）

```python
from analysis.multimode import analyze_multimode

def test_analyze_recovers_two_modes_q():
    lam = np.arange(1500, 1600, 0.002)
    c1 = np.arange(1504, 1596, 9.0)    # 模式1 FSR≈9nm
    c2 = np.arange(1506, 1596, 13.0)   # 模式2 FSR≈13nm
    ql_target = 1500.0 / (2 * 0.03)    # gamma_half=0.03 → Ql=λ/γ_full
    t_lin = np.ones_like(lam)
    for c0 in c1: t_lin *= (1 - 0.7 / (1 + ((lam - c0) / 0.03) ** 2))
    for c0 in c2: t_lin *= (1 - 0.5 / (1 + ((lam - c0) / 0.03) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    res = analyze_multimode(lam, t_db, source_name='syn', min_r2=0.8)
    assert len(res.families) == 2
    qls = np.array([fit.ql for fit in res.fits])
    assert np.median(qls) > 0
    # FSR 排序编号
    labels = sorted({fit.mode for fit in res.fits})
    assert labels[0] == 'Mode 1'
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_multimode.py -k recovers -v` → FAIL

- [ ] **Step 3: 实现** 追加到 `analysis/multimode.py`：

```python
def _family_window(lam_grid, members, i, min_points=40):
    n = len(lam_grid)
    p = int(members[i])
    if i == 0:
        if len(members) > 1:
            right_mid = 0.5 * (lam_grid[p] + lam_grid[int(members[1])])
            left_est = lam_grid[p] - (right_mid - lam_grid[p])
        else:
            left_est = lam_grid[p] - (lam_grid[1] - lam_grid[0]) * 20
        left_idx = int(np.searchsorted(lam_grid, left_est, side='left'))
    else:
        left_mid = 0.5 * (lam_grid[int(members[i - 1])] + lam_grid[p])
        left_idx = int(np.searchsorted(lam_grid, left_mid, side='left'))
    if i == len(members) - 1:
        if len(members) > 1:
            left_mid = 0.5 * (lam_grid[int(members[i - 1])] + lam_grid[p])
            right_est = lam_grid[p] + (lam_grid[p] - left_mid)
        else:
            right_est = lam_grid[p] + (lam_grid[1] - lam_grid[0]) * 20
        right_idx = int(np.searchsorted(lam_grid, right_est, side='right')) - 1
    else:
        right_mid = 0.5 * (lam_grid[p] + lam_grid[int(members[i + 1])])
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

    fams_tmp = []
    for pos in fam_pos:
        members = np.sort(dip_idx[pos])
        m_lam = lam_g[members]
        fsr_nm = float(np.median(np.diff(m_lam))) if members.size > 1 else float('nan')
        m_freq = c / (m_lam * NM_TO_M) / THZ
        fsr_thz = float(np.median(np.abs(np.diff(m_freq)))) if members.size > 1 else float('nan')
        fams_tmp.append((fsr_nm, fsr_thz, members))
    fams_tmp.sort(key=lambda t: (np.inf if np.isnan(t[0]) else t[0]))

    families = []
    fits = []
    for k, (fsr_nm, fsr_thz, members) in enumerate(fams_tmp, start=1):
        label = f'Mode {k}'
        families.append(ModeFamily(label, members, fsr_nm, fsr_thz))
        for i in range(len(members)):
            li, ri = _family_window(lam_g, members, i)
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
            er = float(r['extinction'])
            fits.append(ResonanceFit(
                mode=label, lambda0_nm=float(r['lambda0']), ql=float(r['Ql']),
                qi=float(r['Qi']), er=er, gamma_pm=float(r['gamma']) * 1000.0,
                r_squared=float(r['r_squared']), fsr_nm=fsr_nm,
            ))
    unassigned_idx = np.sort(dip_idx[unassigned_pos]) if unassigned_pos.size else np.array([], dtype=int)
    return MultiModeResult(source_name, lam_g, t_g, tuple(families), tuple(fits), unassigned_idx)
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_multimode.py -v` → PASS（全部）

- [ ] **Step 5: 提交** — `git add -A && git commit -m "feat: analyze_multimode 分模式逐峰 Q 拟合"`

---

### Task 5: `visualization/ring_report.py` — 综合报告图

**Files:**
- Create: `visualization/ring_report.py`
- Test: `tests/test_ring_report.py`

**Interfaces:**
- Consumes: `MultiModeResult`
- Produces: `plot_multimode_report(result, *, min_r2=0.9) -> matplotlib.figure.Figure`

- [ ] **Step 1: 写失败测试**（冒烟：返回 Figure 且可存盘）

```python
import matplotlib
matplotlib.use('Agg')
import numpy as np
from analysis.multimode import analyze_multimode
from visualization.ring_report import plot_multimode_report

def test_report_returns_figure(tmp_path):
    lam = np.arange(1500, 1600, 0.002)
    t_lin = np.ones_like(lam)
    for c0 in np.arange(1504, 1596, 9.0):
        t_lin *= (1 - 0.7 / (1 + ((lam - c0) / 0.03) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    res = analyze_multimode(lam, t_db, source_name='syn', min_r2=0.8)
    fig = plot_multimode_report(res)
    out = tmp_path / "r.png"; fig.savefig(str(out), dpi=100)
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_ring_report.py -v` → FAIL

- [ ] **Step 3: 实现** `visualization/ring_report.py`：

```python
# visualization/ring_report.py — 单文件多模式 Q 报告图
"""生成着色谱 + 各模式 Qi/Ql 分布 + 小结表的综合图。仅 matplotlib。"""

import numpy as np
import matplotlib.pyplot as plt

plt.rcParams['axes.unicode_minus'] = False

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


def _sigma_filter(a, k=4.0):
    a = np.asarray(a, float)
    a = a[np.isfinite(a) & (a > 0)]
    if a.size <= 2:
        return a
    m, s = float(np.mean(a)), float(np.std(a))
    return a if s == 0 else a[np.abs(a - m) < k * s]


def _dist_axis(ax, result, attr, xlabel):
    for fam, color in zip(result.families, _MODE_COLORS):
        vals = _sigma_filter([getattr(f, attr) for f in result.fits if f.mode == fam.label])
        if vals.size == 0:
            continue
        if vals.size >= 8:
            bins = min(20, max(5, vals.size // 2))
            ax.hist(vals, bins=bins, color=color, alpha=0.55,
                    edgecolor='white', linewidth=0.5, label=fam.label)
        else:
            ax.plot(vals, np.zeros_like(vals), 'o', color=color, ms=6,
                    alpha=0.7, label=fam.label)
    _style(ax, xlabel=xlabel, ylabel='Count')
    ax.legend(fontsize=7, frameon=False)


def plot_multimode_report(result, *, min_r2=0.9):
    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(2, 3)
    ax_spec = fig.add_subplot(gs[0, :])
    ax_ql = fig.add_subplot(gs[1, 0])
    ax_qi = fig.add_subplot(gs[1, 1])
    ax_tbl = fig.add_subplot(gs[1, 2]); ax_tbl.axis('off')

    ax_spec.plot(result.lam, result.t_db, color='#000000', linewidth=0.7)
    for fam, color in zip(result.families, _MODE_COLORS):
        idx = np.asarray(fam.peak_indices, dtype=int)
        ax_spec.plot(result.lam[idx], result.t_db[idx], 'v', color=color, markersize=6,
                     linestyle='none',
                     label=f'{fam.label} (FSR={fam.fsr_nm:.2f} nm, N={idx.size})')
    if result.unassigned_idx.size:
        u = result.unassigned_idx
        ax_spec.plot(result.lam[u], result.t_db[u], 'x', color='#999999',
                     markersize=5, linestyle='none', label='unassigned')
    _style(ax_spec, xlabel='Wavelength (nm)', ylabel='Transmission (dB)',
           title=f'{result.source_name} — resonances by mode')
    ax_spec.legend(fontsize=7, frameon=False, ncol=2)

    _dist_axis(ax_ql, result, 'ql', r'$Q_L$')
    _dist_axis(ax_qi, result, 'qi', r'$Q_i$')

    rows = [['Mode', 'FSR(nm)', 'N', 'Ql(med)', 'Qi(med)']]
    for fam in result.families:
        ql = _sigma_filter([f.ql for f in result.fits if f.mode == fam.label])
        qi = _sigma_filter([f.qi for f in result.fits if f.mode == fam.label])
        rows.append([
            fam.label, f'{fam.fsr_nm:.2f}', str(len(ql)),
            f'{np.median(ql):.2e}' if ql.size else '—',
            f'{np.median(qi):.2e}' if qi.size else '—',
        ])
    tbl = ax_tbl.table(cellText=rows[1:], colLabels=rows[0], loc='center', cellLoc='center')
    tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1, 1.4)

    fig.tight_layout()
    return fig
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_ring_report.py -v` → PASS

- [ ] **Step 5: 提交** — `git add -A && git commit -m "feat: 多模式 Q 报告综合图"`

---

### Task 6: `batch_ring_q.py` — CLI 入口

**Files:**
- Create: `batch_ring_q.py`
- Test: `tests/test_batch_cli.py`

**Interfaces:**
- Consumes: `load_spectrum`, `analyze_multimode`, `plot_multimode_report`
- Produces: `main(argv=None) -> int`；CSV writer `_write_csv(path, result)`

- [ ] **Step 1: 写失败测试**（端到端：合成 CSV → 出 png + csv）

```python
import csv
import numpy as np
from pathlib import Path
from batch_ring_q import main

def _write_two_col(path, lam, t_db):
    with open(path, 'w') as f:
        for x, y in zip(lam, t_db):
            f.write(f"{x:.4f},{y:.4f}\n")

def test_cli_end_to_end(tmp_path):
    lam = np.arange(1500, 1600, 0.002)
    t_lin = np.ones_like(lam)
    for c0 in np.arange(1504, 1596, 9.0):
        t_lin *= (1 - 0.7 / (1 + ((lam - c0) / 0.03) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    d = tmp_path / "data"; d.mkdir()
    _write_two_col(d / "ringA_loss.csv", lam, t_db)
    out = tmp_path / "out"
    rc = main([str(d), "--out", str(out), "--min-r2", "0.8"])
    assert rc == 0
    assert (out / "ringA_loss_Qdist.png").exists()
    csv_path = out / "ringA_loss_results.csv"
    assert csv_path.exists()
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1
    assert {'mode_id', 'fsr_nm', 'lambda0_nm', 'ql', 'qi', 'er_db', 'gamma_pm', 'r_squared'} <= set(rows[0].keys())
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_batch_cli.py -v` → FAIL

- [ ] **Step 3: 实现** `batch_ring_q.py`：

```python
#!/usr/bin/env python
# batch_ring_q.py — 批量微环直通端 Q 分析（多 FSR 自动分离）
"""用法: python batch_ring_q.py <数据目录> [--out 目录] [选项]"""

import argparse
import csv
import glob
import math
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from core.io import load_spectrum
from analysis.multimode import analyze_multimode
from visualization.ring_report import plot_multimode_report

CSV_FIELDS = ['mode_id', 'fsr_nm', 'lambda0_nm', 'ql', 'qi', 'er_db', 'gamma_pm', 'r_squared']


def _er_db(er: float) -> float:
    return -10.0 * math.log10(max(1.0 - er, 1e-6))


def _write_csv(path, result):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for fit in result.fits:
            w.writerow({
                'mode_id': fit.mode, 'fsr_nm': f'{fit.fsr_nm:.4f}',
                'lambda0_nm': f'{fit.lambda0_nm:.5f}', 'ql': f'{fit.ql:.6g}',
                'qi': f'{fit.qi:.6g}', 'er_db': f'{_er_db(fit.er):.3f}',
                'gamma_pm': f'{fit.gamma_pm:.4f}', 'r_squared': f'{fit.r_squared:.5f}',
            })


def _log_result(name, meta, result):
    print(f"[{name}] type={meta.get('data_type')}, ch={meta.get('channel') or '-'}, "
          f"谷={sum(len(f.peak_indices) for f in result.families) + result.unassigned_idx.size}")
    print(f"  识别到 {len(result.families)} 个模式:")
    import numpy as np
    for fam in result.families:
        fits = [f for f in result.fits if f.mode == fam.label]
        ql = np.median([f.ql for f in fits]) if fits else float('nan')
        qi = np.median([f.qi for f in fits]) if fits else float('nan')
        print(f"    {fam.label}: FSR={fam.fsr_nm:.2f} nm, N={len(fam.peak_indices)}, "
              f"有效拟合={len(fits)}, Ql(中位)={ql:.3g}, Qi(中位)={qi:.3g}")
    if result.unassigned_idx.size:
        print(f"  unassigned: {result.unassigned_idx.size}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="批量微环直通端 Q 分析（多 FSR 自动分离）")
    ap.add_argument('input_dir')
    ap.add_argument('--out', default=None)
    ap.add_argument('--type', default='auto', choices=['auto', 'loss', 'raw'])
    ap.add_argument('--reference', default=None)
    ap.add_argument('--pattern', default='*.csv')
    ap.add_argument('--channel', default=None)
    ap.add_argument('--min-r2', type=float, default=0.9)
    ap.add_argument('--max-modes', type=int, default=None)
    ap.add_argument('--prominence', type=float, default=None)
    ap.add_argument('--distance', type=int, default=None)
    ap.add_argument('--height', type=float, default=None)
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
            if args.prominence is not None: detect_kw['prominence'] = args.prominence
            if args.distance is not None: detect_kw['min_distance'] = args.distance
            if args.height is not None: detect_kw['height'] = args.height
            result = analyze_multimode(
                lam, loss_db, source_name=stem, min_r2=args.min_r2,
                max_modes=args.max_modes, **detect_kw)
            fig = plot_multimode_report(result, min_r2=args.min_r2)
            fig.savefig(os.path.join(out, f'{stem}_Qdist.png'), dpi=300, bbox_inches='tight')
            plt.close(fig)
            _write_csv(os.path.join(out, f'{stem}_results.csv'), result)
            _log_result(stem, meta, result)
            ok += 1
        except Exception as e:
            print(f"错误: {stem}: {e}")
            fail += 1

    print(f"\n完成: 成功 {ok}, 失败 {fail}, 输出目录 {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_batch_cli.py -v` → PASS

- [ ] **Step 5: 全量测试 + 提交**

```bash
pytest -q
git add -A && git commit -m "feat: batch_ring_q CLI 批量多模式 Q 分析入口"
```

---

### Task 7: 文档与依赖

**Files:**
- Modify: `requirements.txt`（备注 pytest）
- Modify: `README.md` 或 `CLAUDE.md`（用法说明，可选）

- [ ] **Step 1:** 在 `requirements.txt` 追加注释行 `# 开发/测试: pytest`（保持运行依赖不变）。
- [ ] **Step 2:** 在 `CLAUDE.md` 的"常用命令"补一行批量分析用法：`python batch_ring_q.py <目录> --out <目录>`。
- [ ] **Step 3:** 提交 — `git add -A && git commit -m "docs: 批量微环 Q 分析用法与依赖备注"`

---

## Self-Review

- **Spec coverage:** 需求1(loss/raw/两列)→Task1 `load_spectrum`+现有io；需求2(自动识别)→Task1 表头探测+现有io判别；需求3(目标目录出图)→Task6 CLI `--out`+Task5 图；需求4(多FSR)→Task3/4 核心算法；需求5(直通端)→全程 `-T` 检测、忽略drop。✅ 全覆盖。
- **Placeholder scan:** 无 TBD/TODO；每步含完整代码与命令。✅
- **Type consistency:** `ModeFamily.peak_indices`/`fsr_nm`、`ResonanceFit.ql/qi/er/gamma_pm`、`MultiModeResult.families/fits/unassigned_idx`、`separate_modes` 返回 `(list, ndarray)`、`analyze_multimode` 返回 `MultiModeResult`、CLI 用 `fit.er→_er_db` 换算 —— 各任务签名一致。✅
