# core/manager.py — 光谱数据管理
"""SpectraManager 数据管理类。"""

import re
import numbers
import numpy as np
import pandas as pd
from pathlib import Path

from .grid import interp_on_grid
from .io import read_csv_arrays


class SpectraManager:
    """光谱数据管理器。

    管理多条光谱数据，提供统一的访问接口。
    """

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
        """从文件夹加载数据。

        Args:
            folder: 文件夹路径
            data_type: 数据类型 ('auto' | 'loss' | 'raw')
            reference_path: Reference 文件路径
            skiprows: 跳过的文件头行数
            file_pattern: 文件名匹配模式

        Returns:
            SpectraManager 实例
        """
        data = read_csv_arrays(
            str(folder), data_type=data_type,
            reference_path=str(reference_path) if reference_path is not None else None,
            skiprows=skiprows,
            file_pattern=str(file_pattern) if file_pattern is not None else None,
        )
        return cls.from_data(data)

    @classmethod
    def from_data(cls, data_dict: dict):
        """从数据字典创建实例。

        Args:
            data_dict: 以结构化字符串为键的数据字典

        Returns:
            SpectraManager 实例
        """
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
        """解析数据键名，提取元数据。"""
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
        """获取 (波长, 插入损耗) 数据。

        Args:
            key_or_index: 数据键名或索引号
            reference: 参考数据
            subtract_reference: 是否减去参考
            auto_interp_reference: 是否自动插值参考

        Returns:
            (x, y) numpy 数组元组
        """
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
        """获取参考数据。"""
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
