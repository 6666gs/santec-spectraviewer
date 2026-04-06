import re
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QFileDialog, QRadioButton,
    QButtonGroup, QAbstractItemView, QSizePolicy, QHeaderView,
    QSplitter, QCheckBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from spectra_lib import SpectraManager, interp_on_grid, plot_publication
from Ring_analyse import Ring

# ──────────────────────────────────────────────────────────────────────────────
# stdout 重定向到 QTextEdit
# ──────────────────────────────────────────────────────────────────────────────
class _Stream:
    def __init__(self, text_edit):
        self._te = text_edit
    def write(self, msg):
        self._te.moveCursor(self._te.textCursor().End)
        self._te.insertPlainText(msg)
        self._te.ensureCursorVisible()
    def flush(self):
        pass


# ──────────────────────────────────────────────────────────────────────────────
# 主窗口
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('光谱数据可视化工具')
        self.mgr = None          # SpectraManager 实例
        self.ref_path = None     # raw 模式下的 reference 文件路径
        self._build_ui()
        self._redirect_stdout()

    # ── 构建 UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── 顶部工具栏 ──
        root.addLayout(self._build_topbar())

        # ── 主体：左侧表格 + 右侧控制面板 ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        # ── 日志 ──
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(90)
        self.log.setFont(QFont('Consolas', 9))
        root.addWidget(self.log)

    def _build_topbar(self):
        bar = QHBoxLayout()

        self.btn_folder = QPushButton('选择文件夹')
        self.btn_folder.clicked.connect(self._on_select_folder)
        bar.addWidget(self.btn_folder)

        bar.addWidget(QLabel('数据类型:'))
        self.combo_type = QComboBox()
        self.combo_type.addItems(['auto', 'loss', 'raw'])
        self.combo_type.currentTextChanged.connect(self._on_type_changed)
        bar.addWidget(self.combo_type)

        self.btn_ref = QPushButton('选择 Reference 文件')
        self.btn_ref.clicked.connect(self._on_select_ref)
        bar.addWidget(self.btn_ref)

        self.lbl_ref = QLabel('未选择 Reference')
        self.lbl_ref.setStyleSheet('color: gray; font-size: 10px;')
        bar.addWidget(self.lbl_ref)

        self.lbl_path = QLabel('未选择文件夹')
        self.lbl_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(self.lbl_path)

        return bar

    def _build_table(self):
        cols = ['#', 'device', 'device_no', 'port',
                'start_nm', 'end_nm', 'step', 'range', 'source_dbm', 'data_type']
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._on_row_double_click)
        return self.table

    def _build_right_panel(self):
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setSpacing(8)

        # ── 公式计算 ──
        grp_formula = QGroupBox('公式计算（A0, A1... 对应列表序号）')
        fl = QVBoxLayout(grp_formula)
        self.formula_edit = QLineEdit()
        self.formula_edit.setPlaceholderText('例如: A12 - A1 - (A2 - A1) * 2')
        fl.addWidget(self.formula_edit)
        self.lbl_formula_err = QLabel('')
        self.lbl_formula_err.setStyleSheet('color: red;')
        fl.addWidget(self.lbl_formula_err)
        btn_formula_plot = QPushButton('公式绘图')
        btn_formula_plot.clicked.connect(self._on_formula_plot)
        fl.addWidget(btn_formula_plot)
        vbox.addWidget(grp_formula)

        # ── 多选绘图 ──
        btn_multi_plot = QPushButton('绘制选中行')
        btn_multi_plot.clicked.connect(self._on_multi_plot)
        vbox.addWidget(btn_multi_plot)

        # ── 图像标签设置 ──
        grp_labels = QGroupBox('图像标签')
        form_labels = QFormLayout(grp_labels)
        self.title_edit = QLineEdit()
        self.xlabel_edit = QLineEdit('Wavelength (nm)')
        self.ylabel_edit = QLineEdit('Insertion Loss (dB)')
        form_labels.addRow('标题:', self.title_edit)
        form_labels.addRow('X 轴:', self.xlabel_edit)
        form_labels.addRow('Y 轴:', self.ylabel_edit)
        vbox.addWidget(grp_labels)

        # ── 坐标轴范围 ──
        grp_range = QGroupBox('坐标轴范围（空=自动）')
        form_range = QFormLayout(grp_range)
        xrange_w = QWidget()
        xrange_h = QHBoxLayout(xrange_w)
        xrange_h.setContentsMargins(0, 0, 0, 0)
        self.xmin_edit = QLineEdit()
        self.xmax_edit = QLineEdit()
        self.xmin_edit.setPlaceholderText('最小值')
        self.xmax_edit.setPlaceholderText('最大值')
        xrange_h.addWidget(self.xmin_edit)
        xrange_h.addWidget(QLabel('~'))
        xrange_h.addWidget(self.xmax_edit)
        form_range.addRow('X 范围:', xrange_w)

        yrange_w = QWidget()
        yrange_h = QHBoxLayout(yrange_w)
        yrange_h.setContentsMargins(0, 0, 0, 0)
        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.ymin_edit.setPlaceholderText('最小值')
        self.ymax_edit.setPlaceholderText('最大值')
        yrange_h.addWidget(self.ymin_edit)
        yrange_h.addWidget(QLabel('~'))
        yrange_h.addWidget(self.ymax_edit)
        form_range.addRow('Y 范围:', yrange_w)
        vbox.addWidget(grp_range)

        # ── 峰值/谷值分析 ──
        vbox.addWidget(self._build_peak_panel())

        # ── 微环谐振器分析 ──
        vbox.addWidget(self._build_ring_panel())

        vbox.addStretch()
        return panel

    def _build_peak_panel(self):
        grp = QGroupBox('峰值 / 谷值分析')
        vbox = QVBoxLayout(grp)

        # 峰/谷 选择
        mode_w = QWidget()
        mode_h = QHBoxLayout(mode_w)
        mode_h.setContentsMargins(0, 0, 0, 0)
        self.radio_peak = QRadioButton('峰值（极大点）')
        self.radio_valley = QRadioButton('谷值（极小点）')
        self.radio_peak.setChecked(True)
        self._peak_group = QButtonGroup()
        self._peak_group.addButton(self.radio_peak)
        self._peak_group.addButton(self.radio_valley)
        mode_h.addWidget(self.radio_peak)
        mode_h.addWidget(self.radio_valley)
        vbox.addWidget(mode_w)

        form = QFormLayout()
        # 搜索 X 范围
        xsearch_w = QWidget()
        xsearch_h = QHBoxLayout(xsearch_w)
        xsearch_h.setContentsMargins(0, 0, 0, 0)
        self.peak_xmin = QLineEdit()
        self.peak_xmax = QLineEdit()
        self.peak_xmin.setPlaceholderText('最小值（空=全范围）')
        self.peak_xmax.setPlaceholderText('最大值（空=全范围）')
        xsearch_h.addWidget(self.peak_xmin)
        xsearch_h.addWidget(QLabel('~'))
        xsearch_h.addWidget(self.peak_xmax)
        form.addRow('搜索 X 范围:', xsearch_w)

        self.peak_threshold = QLineEdit()
        self.peak_threshold.setPlaceholderText('峰值阈值（dB），空=不限')
        form.addRow('阈值 (dB):', self.peak_threshold)

        self.peak_distance = QLineEdit('50')
        form.addRow('最小间距（点数）:', self.peak_distance)

        vbox.addLayout(form)

        btn_analyze = QPushButton('分析')
        btn_analyze.clicked.connect(self._on_peak_analyze)
        vbox.addWidget(btn_analyze)

        return grp

    def _build_ring_panel(self):
        grp = QGroupBox('微环谐振器分析')
        vbox = QVBoxLayout(grp)

        form = QFormLayout()
        # 独立波长范围输入
        xrange_w = QWidget()
        xrange_h = QHBoxLayout(xrange_w)
        xrange_h.setContentsMargins(0, 0, 0, 0)
        self.ring_xmin = QLineEdit()
        self.ring_xmax = QLineEdit()
        self.ring_xmin.setPlaceholderText('起始（空=全范围）')
        self.ring_xmax.setPlaceholderText('终止（空=全范围）')
        xrange_h.addWidget(self.ring_xmin)
        xrange_h.addWidget(QLabel('~'))
        xrange_h.addWidget(self.ring_xmax)
        form.addRow('波长范围 (nm):', xrange_w)
        vbox.addLayout(form)

        self.chk_ring_holdon = QCheckBox('显示单峰拟合（最多10个，按范围抽样）')
        vbox.addWidget(self.chk_ring_holdon)

        btn_ring = QPushButton('微环分析')
        btn_ring.clicked.connect(self._on_ring_analyze)
        vbox.addWidget(btn_ring)

        return grp

    # ── stdout 重定向 ─────────────────────────────────────────────────────────
    def _redirect_stdout(self):
        stream = _Stream(self.log)
        sys.stdout = stream
        sys.stderr = stream

    # ── 事件处理 ──────────────────────────────────────────────────────────────
    def _on_type_changed(self, text):
        pass  # reference button always enabled

    def _on_select_ref(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 Reference 文件', '', 'CSV 文件 (*.csv)')
        if path:
            self.ref_path = path
            short = path.split('/')[-1].split('\\')[-1]
            self.lbl_ref.setText(short)
            self.lbl_ref.setStyleSheet('color: green; font-size: 10px;')
            print(f'Reference 文件: {path}')
            # 若已加载数据，则重新加载以应用 reference 减法
            if self.mgr is not None:
                folder = self.lbl_path.text()
                if folder and folder != '未选择文件夹':
                    dtype = self.combo_type.currentText()
                    try:
                        self.mgr = SpectraManager.from_folder(
                            folder, data_type=dtype, reference_path=path
                        )
                        self._populate_table()
                        print(f'已重新加载数据（已应用 Reference）')
                    except Exception as e:
                        print(f'重新加载失败: {e}')

    def _on_select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择数据文件夹')
        if not folder:
            return
        self.lbl_path.setText(folder)
        dtype = self.combo_type.currentText()
        ref = self.ref_path  # always pass reference if set
        try:
            self.mgr = SpectraManager.from_folder(
                folder, data_type=dtype, reference_path=ref
            )
            self._populate_table()
            print(f'已加载 {len(self.mgr.keys)} 条数据')
        except Exception as e:
            print(f'加载失败: {e}')

    def _populate_table(self):
        if self.mgr is None:
            return
        df = self.mgr.table
        self.table.setRowCount(0)
        cols = ['index', 'device', 'device_no', 'port',
                'start_nm', 'end_nm', 'step', 'range', 'source_dbm', 'data_type']
        for _, row in df.iterrows():
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, col in enumerate(cols):
                val = str(row.get(col, ''))
                item = QTableWidgetItem(val)
                item.setTextAlignment(int(Qt.AlignCenter))
                self.table.setItem(r, c, item)

    def _on_row_double_click(self, item):
        row = item.row()
        idx = int(self.table.item(row, 0).text())
        self._plot_indices([idx])

    def _on_multi_plot(self):
        rows = {i.row() for i in self.table.selectedItems()}
        if not rows:
            print('请先在列表中选择数据行')
            return
        indices = [int(self.table.item(r, 0).text()) for r in sorted(rows)]
        self._plot_indices(indices)

    # ── 绘图核心 ──────────────────────────────────────────────────────────────
    def _get_plot_params(self):
        """读取图像标签和坐标轴范围设置"""
        title = self.title_edit.text().strip() or None
        xlabel = self.xlabel_edit.text().strip() or 'Wavelength (nm)'
        ylabel = self.ylabel_edit.text().strip() or 'Insertion Loss (dB)'

        def _parse_float(edit):
            t = edit.text().strip()
            try:
                return float(t) if t else None
            except ValueError:
                return None

        xmin = _parse_float(self.xmin_edit)
        xmax = _parse_float(self.xmax_edit)
        ymin = _parse_float(self.ymin_edit)
        ymax = _parse_float(self.ymax_edit)
        xlim = (xmin, xmax) if (xmin is not None and xmax is not None) else None
        ylim = (ymin, ymax) if (ymin is not None and ymax is not None) else None
        return title, xlabel, ylabel, xlim, ylim

    def _plot_indices(self, indices):
        if self.mgr is None:
            print('请先加载数据')
            return
        title, xlabel, ylabel, xlim, ylim = self._get_plot_params()
        data_list = []
        for idx in indices:
            try:
                x, y = self.mgr.get_xy(idx)
                meta = self.mgr._parse_var_key(self.mgr.keys[idx])
                dev = meta.get('device', '')
                dev_no = meta.get('device_no', '') or ''
                port = meta.get('port', '') or ''
                label = f'[{idx}] {dev} {dev_no} {port}'.strip()
                data_list.append({'x': x, 'y': y, 'label': label})
            except Exception as e:
                print(f'读取索引 {idx} 失败: {e}')
        if not data_list:
            return
        fig, ax = plot_publication(data_list, xlabel=xlabel, ylabel=ylabel,
                                   title=title, xlim=xlim, ylim=ylim)
        plt.show(block=False)
        return fig, ax  # type: ignore[return-value]

    # ── 公式绘图 ──────────────────────────────────────────────────────────────
    def _on_formula_plot(self):
        self.lbl_formula_err.setText('')
        if self.mgr is None:
            self.lbl_formula_err.setText('请先加载数据')
            return
        expr = self.formula_edit.text().strip()
        if not expr:
            self.lbl_formula_err.setText('请输入公式')
            return
        try:
            x_result, y_result = self._eval_formula(expr)
        except Exception as e:
            self.lbl_formula_err.setText(str(e))
            return

        title, xlabel, ylabel, xlim, ylim = self._get_plot_params()
        label = expr
        fig, ax = plot_publication(
            [{'x': x_result, 'y': y_result, 'label': label}],
            xlabel=xlabel, ylabel=ylabel, title=title, xlim=xlim, ylim=ylim,
        )
        plt.show(block=False)
        return fig, ax

    def _eval_formula(self, expr):
        """解析并计算形如 A12 - A1 - (A2 - A1) * 2 的表达式"""
        # 提取所有 A{n} 索引
        indices = [int(m) for m in re.findall(r'A(\d+)', expr)]
        if not indices:
            raise ValueError('公式中未找到 A{n} 变量（如 A0, A1...）')
        n = len(self.mgr.keys)
        for idx in indices:
            if idx < 0 or idx >= n:
                raise ValueError(f'索引 A{idx} 超出范围（共 {n} 条数据，索引 0~{n-1}）')

        # 加载所有涉及的数据
        xy_map = {}
        for idx in set(indices):
            xy_map[idx] = self.mgr.get_xy(idx)

        # 以各数据 x 范围的交集为公共网格（小范围主导）
        x_min = max(float(xy_map[i][0].min()) for i in xy_map)
        x_max = min(float(xy_map[i][0].max()) for i in xy_map)
        if x_min >= x_max:
            raise ValueError('各数据的 x 范围无交集，无法计算公式')

        # 在交集范围内，以点数最多的数据为基准，截取对应区间
        base_idx = max(xy_map, key=lambda i: len(xy_map[i][0]))
        x_base = xy_map[base_idx][0]
        mask = (x_base >= x_min) & (x_base <= x_max)
        x_common = x_base[mask]
        if len(x_common) < 2:
            raise ValueError('交集范围内数据点不足')

        # 将所有数据插值到公共网格
        local_vars = {}
        for idx, (x_src, y_src) in xy_map.items():
            if np.array_equal(x_src, x_common):
                y_aligned = y_src
            else:
                y_aligned = interp_on_grid(x_src, y_src, x_common, mode='edge')
            local_vars[f'_v{idx}'] = y_aligned

        # 将 A{n} 替换为 _v{n}
        safe_expr = re.sub(r'A(\d+)', r'_v\1', expr)

        # 安全 eval
        result = eval(safe_expr, {'__builtins__': {}, 'np': np}, local_vars)  # noqa: S307
        return x_common, np.asarray(result, dtype=float)

    # ── 峰值/谷值分析 ─────────────────────────────────────────────────────────
    def _get_analysis_data(self):
        """获取当前待分析的 (x, y, label)。

        优先级：
        1. 若公式输入框不为空且公式合法 → 使用公式计算结果
        2. 否则 → 使用列表中选中的单行数据

        返回 (x, y, label, source_desc) 或在出错时 print 错误信息并返回 None。
        """
        if self.mgr is None:
            print('请先加载数据')
            return None

        expr = self.formula_edit.text().strip()
        if expr:
            try:
                x, y = self._eval_formula(expr)
                self.lbl_formula_err.setText('')
                return x, y, expr, f'公式: {expr}'
            except Exception:
                pass  # 公式不合法，降级到列表选中行

        rows = {i.row() for i in self.table.selectedItems()}
        if not rows:
            print('请先在列表中选择要分析的数据行（或在公式框中输入有效公式）')
            return None
        if len(rows) > 1:
            print('分析每次只支持单条数据，请只选择一行')
            return None
        idx = int(self.table.item(list(rows)[0], 0).text())
        try:
            x, y = self.mgr.get_xy(idx)
        except Exception as e:
            print(f'读取数据失败: {e}')
            return None
        meta = self.mgr._parse_var_key(self.mgr.keys[idx])
        dev = meta.get('device', '')
        label = f'[{idx}] {dev}'.strip()
        return x, y, label, f'索引 {idx}'

    def _on_peak_analyze(self):
        result = self._get_analysis_data()
        if result is None:
            return
        x, y, label, source_desc = result

        # 解析搜索范围
        def _pf(edit):
            t = edit.text().strip()
            try:
                return float(t) if t else None
            except ValueError:
                return None

        xmin = _pf(self.peak_xmin)
        xmax = _pf(self.peak_xmax)
        threshold_str = self.peak_threshold.text().strip()
        threshold = float(threshold_str) if threshold_str else None

        dist_str = self.peak_distance.text().strip()
        distance = int(dist_str) if dist_str else 50

        # 截取搜索范围
        mask = np.ones(len(x), dtype=bool)
        if xmin is not None:
            mask &= x >= xmin
        if xmax is not None:
            mask &= x <= xmax
        x_s, y_s = x[mask], y[mask]
        if len(x_s) < 3:
            print('搜索范围内数据点不足')
            return

        is_peak = self.radio_peak.isChecked()
        self._run_peak_analysis(x, y, x_s, y_s, label, source_desc, is_peak, threshold, distance)

    def _run_peak_analysis(self, x_full, y_full, x_s, y_s, label, source_desc, is_peak, threshold, distance):
        title, xlabel, ylabel, xlim, ylim = self._get_plot_params()

        if is_peak:
            # 峰值：找极大点
            kwargs = {'distance': distance}
            if threshold is not None:
                kwargs['height'] = threshold
            peaks_idx, props = find_peaks(y_s, **kwargs)
        else:
            # 谷值：对 y 取负后找极大点
            kwargs = {'distance': distance}
            if threshold is not None:
                kwargs['height'] = -threshold  # 谷值阈值取负
            peaks_idx, props = find_peaks(-y_s, **kwargs)

        if len(peaks_idx) == 0:
            print(f'未找到{"峰值" if is_peak else "谷值"}，尝试调整阈值或搜索范围')
            return

        # 绘图
        fig, ax = plot_publication(
            [{'x': x_full, 'y': y_full, 'label': label}],
            xlabel=xlabel, ylabel=ylabel, title=title, xlim=xlim, ylim=ylim,
        )

        print(f'\n{"峰值" if is_peak else "谷值"}分析结果（{source_desc}）:')
        for pi in peaks_idx:
            px, py = x_s[pi], y_s[pi]
            bw = self._calc_3db_bandwidth(x_s, y_s, pi, is_peak)
            bw_str = f'{bw:.4f} nm' if bw is not None else 'N/A'
            print(f'  {"峰" if is_peak else "谷"} @ {px:.4f} nm, 值={py:.2f} dB, 3dB带宽={bw_str}')
            # 标注
            ax.axvline(px, color='red', linestyle='--', linewidth=1, alpha=0.7)
            ax.annotate(
                f'{px:.3f} nm\n{py:.2f} dB\nBW={bw_str}',
                xy=(px, py),
                xytext=(px, py + (3 if is_peak else -3)),
                fontsize=8,
                color='red',
                ha='center',
                arrowprops=dict(arrowstyle='->', color='red', lw=1),
            )

        fig.canvas.draw()
        plt.show(block=False)

    def _calc_3db_bandwidth(self, x, y, peak_idx, is_peak):
        """计算 3dB 带宽"""
        if is_peak:
            # 峰值：从峰顶向下 3dB
            half = y[peak_idx] - 3.0
            try:
                left = np.max(np.where(y[:peak_idx] <= half)[0])
            except ValueError:
                left = 0
            try:
                right = np.min(np.where(y[peak_idx:] <= half)[0]) + peak_idx
            except ValueError:
                right = len(x) - 1
        else:
            # 谷值：谷两侧较大值向下 3dB
            # 谷值旁边的"平坦部分"取谷两侧各自的局部最大值
            left_seg = y[:peak_idx]
            right_seg = y[peak_idx:]
            left_max = np.max(left_seg) if len(left_seg) > 0 else y[peak_idx]
            right_max = np.max(right_seg) if len(right_seg) > 0 else y[peak_idx]
            ref_level = (left_max + right_max) / 2.0
            half = ref_level - 3.0
            try:
                left = np.max(np.where(y[:peak_idx] >= half)[0])
            except ValueError:
                left = 0
            try:
                right = np.min(np.where(y[peak_idx:] >= half)[0]) + peak_idx
            except ValueError:
                right = len(x) - 1

        if left >= right:
            return None
        return float(x[right] - x[left])

    # ── 微环谐振器分析 ────────────────────────────────────────────────────────
    def _on_ring_analyze(self):
        result = self._get_analysis_data()
        if result is None:
            return
        x, y, label, source_desc = result

        def _pf(edit):
            t = edit.text().strip()
            try:
                return float(t) if t else None
            except ValueError:
                return None

        xmin = _pf(self.ring_xmin)
        xmax = _pf(self.ring_xmax)
        range_nm = (xmin, xmax) if (xmin is not None and xmax is not None) else None

        try:
            ring = Ring(x, y)
            print(f'\n微环分析（{source_desc}）...')
            fig_fsr = ring.cal_fsr(range_nm=range_nm, display=True)
            print(f'FSR 均值: {ring.fsr_mean:.4f} nm')
            holdon = self.chk_ring_holdon.isChecked()
            fig_q = ring.cal_Q(holdon=holdon, max_holdon=10)
            # 统一显示所有图窗（Qt 后端下须在主线程调用 show）
            plt.show(block=False)
            if hasattr(ring, 'fit_results') and ring.fit_results:
                ql_vals = [r['Ql'] for r in ring.fit_results if np.isfinite(r['Ql']) and r['Ql'] > 0]
                qi_vals = [r['Qi'] for r in ring.fit_results if np.isfinite(r['Qi']) and r['Qi'] > 0]
                if ql_vals:
                    print(f'Ql 均值: {np.mean(ql_vals):.0f}  (共 {len(ql_vals)} 个有效峰)')
                if qi_vals:
                    print(f'Qi 均值: {np.mean(qi_vals):.0f}')
        except Exception as e:
            print(f'微环分析失败: {e}')
