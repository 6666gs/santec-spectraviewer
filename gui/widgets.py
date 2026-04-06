# gui/widgets.py — GUI 通用组件
"""PyQt5 通用小部件。"""

import sys
from PyQt5.QtWidgets import QTextEdit


class StreamRedirector:
    """将 stdout/stderr 重定向到 QTextEdit。"""

    def __init__(self, text_edit: QTextEdit):
        self._te = text_edit

    def write(self, msg: str):
        self._te.moveCursor(self._te.textCursor().End)
        self._te.insertPlainText(msg)
        self._te.ensureCursorVisible()

    def flush(self):
        pass


def redirect_stdout_to(text_edit: QTextEdit):
    """将 stdout 和 stderr 重定向到指定的 QTextEdit。

    Args:
        text_edit: 目标 QTextEdit 控件

    Returns:
        StreamRedirector 实例
    """
    stream = StreamRedirector(text_edit)
    sys.stdout = stream
    sys.stderr = stream
    return stream
