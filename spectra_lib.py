# spectra_lib.py — SpectraViewer 专用库（仅包含项目所需函数）
import re
import os
import numbers
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['text.usetex'] = False


# ──────────────────────────────────────────────────────────────────────────────
# 内部工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _infer_decimals_from_value(value: float) -> int:
    from decimal import Decimal
    try:
        s = f"{float(value):.12f}".rstrip('0').rstrip('.')
        if '.' in s:
            return min(9, max(0, len(s.split('.')[1])))
        return 0
    except (ValueError, TypeError):
        try:
            d = Decimal(str(float(value)))
            return min(9, max(0, int(abs(d.as_tuple().exponent))))
        except Exception:
            return 6


def create_uniform_grid(
    start: float,
    end: float,
    step: float,
    decimals: int | None = None,
    endpoint: bool = True,
) -> np.ndarray:
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
    x_src, y_src = sanitize_xy(x_src, y_src)
    if x_src.size < 2:
        if x_src.size == 1:
            return np.full_like(x_dst, fill_value=y_src[0], dtype=float)
        return np.full_like(x_dst, fill_value=np.nan, dtype=float)
    if mode == 'edge':
        f = interp1d(x_src, y_src, bounds_error=False,
                     fill_value=(y_src[0], y_src[-1]))  # type: ignore
    elif mode == 'none':
        f = interp1d(x_src, y_src, bounds_error=False, fill_value=np.nan)
    else:
        f = interp1d(x_src, y_src, bounds_error=False, fill_value='extrapolate')  # type: ignore
    return np.asarray(f(x_dst), dtype=float)


# ──────────────────────────────────────────────────────────────────────────────
# CSV 读取
# ──────────────────────────────────────────────────────────────────────────────

def read_santec_csv(
    filepath: str | Path,
    data_type: str = 'auto',
    reference_path: str | None = None,
    skiprows: int = 14,
) -> dict:
    RANGE_LIMITS = {1: (-30, 10), 2: (-40, 0), 3: (-50, -10), 4: (-60, -20), 5: (-80, -30)}

    def _parse_file_header(path) -> dict:
        meta = {}
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for _ in range(skiprows):
                    line = f.readline()
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        k = parts[0].lower()
                        v = parts[1]
                        if 'start' in k:
                            try: meta['start_nm'] = float(v)
                            except ValueError: pass
                        elif 'stop' in k:
                            try: meta['stop_nm'] = float(v)
                            except ValueError: pass
                        elif 'step' in k:
                            try: meta['step_nm'] = float(v)
                            except ValueError: pass
                        elif 'source power' in k:
                            try: meta['source_dbm'] = float(v)
                            except ValueError: pass
        except Exception:
            pass
        return meta

    def _parse_ranges_from_filename(filename: str) -> list[int]:
        m = re.search(r'_range(\d+)', filename, re.IGNORECASE)
        if m:
            return [int(c) for c in m.group(1) if c.isdigit()]
        return []

    def _detect_columns(path, skip) -> tuple[str, int]:
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for _ in range(skip):
                    f.readline()
                header_line = f.readline()
            cols = [c.strip().lower() for c in header_line.split(',') if c.strip()]
            if any('il' in c for c in cols):
                return 'loss', 1
            if any('monitor' in c or 'raw' in c for c in cols):
                n_raw = sum(1 for c in cols if 'raw' in c)
                return 'raw', max(n_raw, 1)
            n_data_cols = len(cols) - 1
            if n_data_cols == 1:
                return 'loss', 1
            return 'raw', max(n_data_cols // 2, 1)
        except Exception:
            return 'loss', 1

    def _read_data(path, skip):
        df = pd.read_csv(path, skiprows=skip, header=None)
        first_val = df.iloc[0, 0]
        if isinstance(first_val, str) and not first_val.replace('.', '').replace('-', '').lstrip().replace(' ', '').isdigit():
            df = df.iloc[1:].reset_index(drop=True)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=[0])

    def _auto_assign_ranges(raw_scans):
        medians = [float(np.median(s)) for s in raw_scans]
        order = sorted(range(len(medians)), key=lambda i: -medians[i])
        ranges = [0] * len(raw_scans)
        for rank, orig_idx in enumerate(order):
            ranges[orig_idx] = rank + 2
        return ranges

    def _stitch_multi_range(raw_scans, ranges):
        if len(raw_scans) == 1:
            return raw_scans[0], []
        sorted_pairs = sorted(zip(ranges, raw_scans), key=lambda x: x[0])
        sorted_ranges = [p[0] for p in sorted_pairs]
        sorted_scans = [p[1] for p in sorted_pairs]
        thresholds = []
        result = sorted_scans[0].copy()
        for i in range(1, len(sorted_scans)):
            threshold = RANGE_LIMITS.get(sorted_ranges[i], (-60, -20))[1]
            thresholds.append(threshold)
            result = np.where(result > threshold, result, sorted_scans[i])
        return result, thresholds

    filepath = Path(filepath)
    filename = filepath.name.lower()
    meta = _parse_file_header(filepath)
    detected_type, n_scans = _detect_columns(filepath, skiprows)

    if data_type == 'auto':
        if 'loss' in filename:
            data_type = 'loss'
        elif 'raw' in filename:
            data_type = 'raw'
        else:
            data_type = detected_type

    result = {'data_type': data_type, 'ranges': [], 'threshold': [], 'meta': meta}
    df = _read_data(filepath, skiprows)
    wavelength = df.iloc[:, 0].to_numpy(dtype=float)
    result['wavelength'] = wavelength

    if data_type == 'loss':
        result['loss'] = df.iloc[:, 1].to_numpy(dtype=float)
        result['ranges'] = _parse_ranges_from_filename(filename)
    else:
        raw_scans = []
        for i in range(n_scans):
            raw_col_idx = 1 + n_scans + i
            if raw_col_idx < len(df.columns):
                raw_scans.append(df.iloc[:, raw_col_idx].to_numpy(dtype=float))
        if not raw_scans:
            raw_scans = [df.iloc[:, min(2, len(df.columns) - 1)].to_numpy(dtype=float)]
        ranges = _parse_ranges_from_filename(filename)
        if len(ranges) != len(raw_scans):
            ranges = [2] if len(raw_scans) == 1 else _auto_assign_ranges(raw_scans)
        result['ranges'] = ranges
        stitched_raw, thresholds = _stitch_multi_range(raw_scans, ranges)
        result['threshold'] = thresholds
        if reference_path is not None:
            _, ref_n_scans = _detect_columns(reference_path, skiprows)
            ref_df = _read_data(reference_path, skiprows)
            ref_wavelength = ref_df.iloc[:, 0].to_numpy(dtype=float)
            ref_detected_type, _ = _detect_columns(reference_path, skiprows)
            if ref_detected_type == 'raw':
                ref_raw_col = 1 + ref_n_scans
                ref_raw = ref_df.iloc[:, ref_raw_col if ref_raw_col < len(ref_df.columns) else 2].to_numpy(dtype=float)
            else:
                ref_raw = ref_df.iloc[:, 1].to_numpy(dtype=float)
            if len(ref_raw) == len(stitched_raw) and np.allclose(ref_wavelength, wavelength, rtol=1e-6):
                result['loss'] = stitched_raw - ref_raw
            else:
                result['loss'] = stitched_raw - np.interp(wavelength, ref_wavelength, ref_raw,
                                                           left=ref_raw[0], right=ref_raw[-1])
        else:
            result['loss'] = stitched_raw
    return result


def read_csv_arrays(
    prefile: str,
    data_type: str = 'auto',
    reference_path: str | None = None,
    skiprows: int = 14,
    file_pattern: str | None = None,
) -> dict:
    import glob

    def _sanitize(s: str) -> str:
        return re.sub(r'[^a-zA-Z0-9.]', '_', s).strip('_')

    def _parse_filename_meta(filename: str) -> dict:
        info: dict = {'step': None, 'range': None, 'source': None, 'dtype': None, 'core': None}
        name = filename.lower()
        if '_loss' in name or name.endswith('_loss.csv'):
            info['dtype'] = 'loss'
        elif '_raw' in name or name.endswith('_raw.csv'):
            info['dtype'] = 'raw'
        m = re.search(r'_step(\d+(?:\.\d+)?[a-zA-Z]+)', name)
        if m:
            info['step'] = m.group(1)
        m = re.search(r'_range(\d+)', name)
        if m:
            info['range'] = m.group(1)
        m = re.search(r'_source(\d+)dbm', name)
        if m:
            info['source'] = m.group(1)
        stem = re.sub(r'\.(csv)$', '', filename, flags=re.IGNORECASE)
        for pat in [r'_step\d+(?:\.\d+)?[a-zA-Z]+', r'_range\d+', r'_source\d+dbm', r'_(loss|raw)$']:
            stem = re.sub(pat, '', stem, flags=re.IGNORECASE)
        info['core'] = _sanitize(stem) or 'data'
        return info

    def _build_key(fn_meta: dict, file_meta: dict, detected_dtype: str) -> str:
        core = fn_meta['core'] or 'data'
        core_tokens = core.split('_')
        num_tokens = [t for t in core_tokens if re.fullmatch(r'\d+(?:\.\d+)?', t) and float(t) >= 100]
        if len(num_tokens) < 2:
            start = file_meta.get('start_nm')
            stop = file_meta.get('stop_nm')
            if start is not None and stop is not None:
                s_str = str(int(start)) if start == int(start) else str(start)
                e_str = str(int(stop)) if stop == int(stop) else str(stop)
                core = f"{core}_{s_str}_{e_str}"
        if file_meta.get('step_nm') is not None:
            sv_pm = file_meta['step_nm'] * 1000
            step_val = f"{int(sv_pm)}pm" if sv_pm == int(sv_pm) else f"{sv_pm:.4g}pm"
        elif fn_meta['step']:
            step_val = fn_meta['step']
        else:
            step_val = 'unknown'
        range_val = fn_meta['range'] or '0'
        if file_meta.get('source_dbm') is not None:
            src = file_meta['source_dbm']
            source_val = str(int(src)) if src == int(src) else str(src)
        elif fn_meta['source']:
            source_val = fn_meta['source']
        else:
            source_val = '0'
        dtype_val = fn_meta['dtype'] or detected_dtype or 'unknown'
        return f"{core}_step{step_val}_range{range_val}_source{source_val}_type{dtype_val}_array"

    data_dict: dict = {}
    loaded_count = 0
    conflict_counter: dict[str, int] = {}

    if file_pattern:
        files = glob.glob(os.path.join(prefile, file_pattern))
    else:
        files = [os.path.join(prefile, f) for f in os.listdir(prefile) if f.lower().endswith('.csv')]

    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        try:
            result = read_santec_csv(filepath, data_type=data_type,
                                     reference_path=reference_path, skiprows=skiprows)
            fn_meta = _parse_filename_meta(filename)
            key = _build_key(fn_meta, result.get('meta', {}), result['data_type'])
            if key in conflict_counter:
                conflict_counter[key] += 1
                unique_key = key.replace('_array', f'_{conflict_counter[key]}_array')
            else:
                conflict_counter[key] = 0
                unique_key = key
            data_dict[unique_key] = np.column_stack([result['wavelength'], result['loss']])
            loaded_count += 1
            print(f"已加载: {unique_key} ← {filename} (type={result['data_type']}, ranges={result['ranges']})")
        except Exception as e:
            print(f"错误: {filename} 读取失败 ({e})")

    print(f"\n总计导入 {loaded_count} 个文件")
    return data_dict


# ──────────────────────────────────────────────────────────────────────────────
# SpectraManager
# ──────────────────────────────────────────────────────────────────────────────

class SpectraManager:
    def __init__(self, data_dict: dict, table: pd.DataFrame, keys_list: list[str]):
        self.data = data_dict
        self.table = table
        self.keys = keys_list

    @classmethod
    def from_folder(
        cls,
        folder: str | Path,
        data_type: str = 'auto',
        reference_path: str | Path | None = None,
        skiprows: int = 14,
        file_pattern: str | Path | None = None,
    ):
        data = read_csv_arrays(
            str(folder), data_type=data_type,
            reference_path=str(reference_path) if reference_path is not None else None,
            skiprows=skiprows,
            file_pattern=str(file_pattern) if file_pattern is not None else None,
        )
        return cls.from_data(data)

    @classmethod
    def from_data(cls, data_dict: dict):
        keys = sorted(data_dict.keys())
        rows = []
        for idx, k in enumerate(keys):
            meta = cls._parse_var_key(k)
            meta['index'] = idx
            rows.append(meta)
        table = pd.DataFrame(rows, columns=[
            'index', 'key', 'device', 'device_no', 'port',
            'start_nm', 'end_nm', 'step', 'range', 'source_dbm', 'data_type',
        ])
        return cls(data_dict, table, keys)

    @staticmethod
    def _parse_var_key(var_key: str) -> dict:
        m = re.match(
            r"^(?P<core>.*?)_step(?P<step>[^_]+)_range(?P<range>\d+)_source(?P<source>\d+)_type(?P<dtype>\w+)(?:_(?P<dup>\d+))?_array$",
            var_key,
        )
        if not m:
            m = re.match(
                r"^(?P<core>.*?)_step(?P<step>[^_]+)_range(?P<range>\d+)_source(?P<source>\d+)(?:_(?P<dup>\d+))?_array$",
                var_key,
            )
            data_type = 'unknown'
        else:
            data_type = m.group('dtype') if m.group('dtype') else 'unknown'

        if not m:
            return {'key': var_key, 'core': var_key, 'data_type': 'unknown'}

        core = m.group('core')
        step = m.group('step')
        range_val = m.group('range')
        source = m.group('source')
        dup = m.group('dup') if 'dup' in m.groupdict() else None

        tokens = core.split('_') if core else []
        num_idx = [i for i, t in enumerate(tokens) if re.fullmatch(r'\d+(?:\.\d+)?', t) and float(t) >= 100]
        chip_name = device_name = ''
        device_no = port = start_nm = end_nm = None

        if tokens:
            if len(num_idx) >= 2:
                start_nm_idx, end_nm_idx = num_idx[-2], num_idx[-1]
                start_nm = tokens[start_nm_idx]
                end_nm = tokens[end_nm_idx]
                prefix_tokens = tokens[:start_nm_idx]
                if len(prefix_tokens) >= 4:
                    chip_name = prefix_tokens[0]
                    port = prefix_tokens[-1]
                    device_no = prefix_tokens[-2]
                    device_name = '_'.join(prefix_tokens[1:-2])
                elif len(prefix_tokens) == 3:
                    device_name = prefix_tokens[0]
                    device_no = prefix_tokens[1]
                    port = prefix_tokens[2]
                elif len(prefix_tokens) == 2:
                    device_name = prefix_tokens[0]
                    port = prefix_tokens[1]
                elif len(prefix_tokens) == 1:
                    device_name = prefix_tokens[0]
                if chip_name and device_name:
                    device_name = f"{chip_name}_{device_name}"
                elif chip_name:
                    device_name = chip_name
            elif len(num_idx) == 1:
                first_num_i = num_idx[0]
                device_name = '_'.join(tokens[:first_num_i]) or (tokens[0] if tokens else '')
                if first_num_i < len(tokens):
                    start_nm = tokens[first_num_i]
            else:
                device_name = '_'.join(tokens)

        return {
            'key': var_key, 'core': core, 'device': device_name,
            'device_no': device_no, 'port': port, 'start_nm': start_nm,
            'end_nm': end_nm, 'step': step, 'range': range_val,
            'source_dbm': source, 'data_type': data_type, 'dup': dup,
        }

    def get_xy(self, key_or_index: int | str, reference=None,
               subtract_reference: bool = True, auto_interp_reference: bool = True):
        if isinstance(key_or_index, int):
            if key_or_index < 0 or key_or_index >= len(self.keys):
                raise IndexError('index 越界')
            k = self.keys[key_or_index]
        else:
            k = key_or_index
        arr = np.asarray(self.data[k])
        if arr.ndim != 2:
            raise ValueError(f"数据维度应为2D，实际为 {arr.ndim}D")
        if arr.shape[1] >= 2:
            x, y = arr[:, 0].astype(float), arr[:, 1].astype(float)
        elif arr.shape[0] >= 2:
            x, y = arr[0, :].astype(float), arr[1, :].astype(float)
        else:
            raise ValueError(f"无法从形状 {arr.shape} 中提取 (x,y)")
        if reference is not None and subtract_reference:
            x_ref, y_ref, _ = self.get_reference(reference)
            if x_ref is not None and y_ref is not None:
                if np.array_equal(x, x_ref):
                    y = y - y_ref
                elif auto_interp_reference:
                    y = y - interp_on_grid(np.asarray(x_ref), np.asarray(y_ref), x, mode='edge')
        return x, y

    def get_reference(self, reference):
        if reference is None:
            return None, None, None
        if isinstance(reference, numbers.Integral):
            xr, yr = self.get_xy(int(reference))
            return xr, yr, f"ref=index {reference}"
        if isinstance(reference, dict):
            xr = np.asarray(reference.get('lambda'))
            yr = np.asarray(reference.get('power'))
            if xr is None or yr is None:
                return None, None, None
            return xr.astype(float), yr.astype(float), 'ref=dict'
        return None, None, None


# ──────────────────────────────────────────────────────────────────────────────
# 绘图
# ──────────────────────────────────────────────────────────────────────────────

def plot_publication(
    data_list,
    xlabel='X',
    ylabel='Y',
    x_major=None,
    y_major=None,
    xlim=None,
    ylim=None,
    figsize=(8, 6),
    save_path=None,
    dpi=300,
    title=None,
):
    default_colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    ]
    fig, ax = plt.subplots(figsize=figsize)
    has_label = False
    for i, data in enumerate(data_list):
        x = data['x']
        y = data['y']
        label = data.get('label', None)
        color = data.get('color', default_colors[i % len(default_colors)])
        marker = data.get('marker', False)
        marker_size = data.get('marker_size', 50)
        linewidth = data.get('linewidth', 2)
        linestyle = data.get('linestyle', '-')
        if label:
            has_label = True
        ax.plot(x, y, linestyle, color=color, linewidth=linewidth, label=label, zorder=1)
        if marker:
            ax.scatter(x, y, s=marker_size, color=color, zorder=2)
    ax.set_xlabel(xlabel, fontsize=16, fontweight='bold', family='Times New Roman')
    ax.set_ylabel(ylabel, fontsize=16, fontweight='bold', family='Times New Roman')
    if title:
        ax.set_title(title, fontsize=18, fontweight='bold', family='Times New Roman')
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)
    ax.grid(False)
    if x_major:
        ax.xaxis.set_major_locator(MultipleLocator(x_major))
    if y_major:
        ax.yaxis.set_major_locator(MultipleLocator(y_major))
    ax.tick_params(axis='both', which='major', labelsize=12, width=2, length=6,
                   direction='in', top=True, right=True, bottom=True, left=True, zorder=10)
    ax.minorticks_off()
    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontweight('bold')
        tick_label.set_fontname('Times New Roman')
    for spine in ax.spines.values():
        spine.set_linewidth(2)
        spine.set_zorder(10)
    if has_label:
        ax.legend(fontsize=12, frameon=False,
                  prop={'family': 'Times New Roman', 'weight': 'bold'})
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"图像已保存到: {save_path}")
    return fig, ax
