# core/__init__.py — 核心模块公共 API
"""核心数据处理模块。"""

from .utils import _infer_decimals_from_value
from .grid import create_uniform_grid, sanitize_xy, interp_on_grid
from .io import read_santec_csv, read_csv_arrays
from .manager import SpectraManager

__all__ = [
    '_infer_decimals_from_value',
    'create_uniform_grid',
    'sanitize_xy',
    'interp_on_grid',
    'read_santec_csv',
    'read_csv_arrays',
    'SpectraManager',
]
