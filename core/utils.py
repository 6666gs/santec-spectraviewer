# core/utils.py — 通用工具函数
"""通用工具函数，无外部依赖。"""


def _infer_decimals_from_value(value: float) -> int:
    """从数值推断小数位数。"""
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
