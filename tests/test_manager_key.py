"""SpectraManager._parse_var_key 元数据解析测试。

回归：当 SANTEC 表头报告负的 source power（如 -1 dBm）时，键名形如
`..._source-1_typeloss_..._array`，早期正则 `_source(\\d+)` 无法匹配负号，
导致整行元数据解析失败、表格全部显示 NaN。
"""

from core.manager import SpectraManager


def test_parse_key_negative_source():
    """负 source（-1 dBm）应完整解析，而非全部落空。"""
    key = 'eoring_col6_1500_1630_step1pm_range0_source-1_typeloss_chCH1_array'
    meta = SpectraManager._parse_var_key(key)
    assert meta['start_nm'] == '1500'
    assert meta['end_nm'] == '1630'
    assert meta['step'] == '1pm'
    assert meta['range'] == '0'
    assert meta['source_dbm'] == '-1'
    assert meta['data_type'] == 'loss'
    assert meta['channel'] == 'CH1'
    assert meta['device'] == 'eoring'


def test_parse_key_negative_decimal_source():
    """负小数 source（-1.5 dBm）也应正确解析。"""
    key = 'eoring_col6_1500_1630_step1pm_range0_source-1.5_typeraw_chCH2_array'
    meta = SpectraManager._parse_var_key(key)
    assert meta['start_nm'] == '1500'
    assert meta['end_nm'] == '1630'
    assert meta['source_dbm'] == '-1.5'
    assert meta['data_type'] == 'raw'
    assert meta['channel'] == 'CH2'


def test_parse_key_nonnegative_source_unchanged():
    """非负 source 的既有行为保持不变（防回归）。"""
    key = 'chip_devA_2_1500_1630_step1pm_range2_source0_typeloss_chCH1_array'
    meta = SpectraManager._parse_var_key(key)
    assert meta['device'] == 'chip'
    assert meta['device_no'] == 'devA'
    assert meta['port'] == '2'
    assert meta['start_nm'] == '1500'
    assert meta['end_nm'] == '1630'
    assert meta['source_dbm'] == '0'
    assert meta['data_type'] == 'loss'
