# core/io.py — CSV 文件读取
"""SANTEC 光谱仪 CSV 文件读取模块。"""

import re
import os
import numpy as np
import pandas as pd
from pathlib import Path

RANGE_LIMITS = {1: (-30, 10), 2: (-40, 0), 3: (-50, -10), 4: (-60, -20), 5: (-80, -30)}


def read_santec_csv(
    filepath: str | Path,
    data_type: str = 'auto',
    reference_path: str | None = None,
    skiprows: int = 14,
) -> dict:
    """读取单个 SANTEC CSV 文件。

    Args:
        filepath: CSV 文件路径
        data_type: 数据类型 ('auto' | 'loss' | 'raw')
        reference_path: Reference 文件路径 (仅 raw 模式)
        skiprows: 跳过的文件头行数

    Returns:
        包含 wavelength, loss, meta 等字段的字典
    """
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
    """批量读取文件夹中的 CSV 文件。

    Args:
        prefile: 文件夹路径
        data_type: 数据类型 ('auto' | 'loss' | 'raw')
        reference_path: Reference 文件路径
        skiprows: 跳过的文件头行数
        file_pattern: 文件名匹配模式

    Returns:
        以结构化字符串为键的数据字典
    """
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
